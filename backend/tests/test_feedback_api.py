import uuid
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

import seed
from app.api.routes.feedback import get_feedback_extractor
from app.core.config import Settings
from app.main import app
from app.models import RejectionFeedback
from app.schemas.feedback import StructuredFeedback
from app.services import gemini_feedback_extractor
from app.services.demo_feedback_extractor import DemoFeedbackExtractor
from app.services.feedback_extractor import FeedbackExtractionError, create_feedback_extractor
from app.services.gemini_feedback_extractor import GeminiFeedbackExtractor
from app.services.openai_feedback_extractor import OpenAIFeedbackExtractor

URL = "/api/feedback/analyze"


@pytest.fixture(autouse=True)
def demo_extractor() -> Iterator[None]:
    """Never call a live AI provider from tests, whatever FEEDBACK_EXTRACTOR is set to locally."""
    app.dependency_overrides[get_feedback_extractor] = DemoFeedbackExtractor
    yield
    app.dependency_overrides.pop(get_feedback_extractor, None)


@pytest.fixture
def ids(session_factory: sessionmaker[Session]) -> tuple[str, str]:
    with session_factory() as session:
        seed.seed(session)
        session.commit()
    return str(seed.demo_id("client", "Rahul")), str(seed.demo_id("profile", "Ishita"))


def body(ids: tuple[str, str], raw_feedback: str) -> dict:
    client_id, profile_id = ids
    return {"client_id": client_id, "profile_id": profile_id, "raw_feedback": raw_feedback}


def test_valid_feedback_returns_saved_analysis(ids: tuple[str, str], api: TestClient) -> None:
    response = api.post(URL, json=body(ids, "Great profile, but I don't want someone who smokes."))

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"id", "client_id", "profile_id", "raw_feedback", "structured_feedback"}
    assert data["client_id"] == ids[0]
    assert data["profile_id"] == ids[1]
    assert data["raw_feedback"] == "Great profile, but I don't want someone who smokes."
    assert data["structured_feedback"]["needs_review"] is False
    [reason] = data["structured_feedback"]["reasons"]
    assert set(reason) == {"attribute", "value", "preference_type", "kind", "explanation"}
    assert (reason["attribute"], reason["value"], reason["preference_type"], reason["kind"]) == (
        "smoking", True, "DEAL_BREAKER", "VIOLATION"
    )


def test_response_contains_no_match_decision(ids: tuple[str, str], api: TestClient) -> None:
    response = api.post(URL, json=body(ids, "Smoking is a deal breaker."))

    text = response.text
    assert "decision" not in text
    assert not any(word in text for word in ('"PASS"', '"REVIEW"', '"BLOCK"', "score"))


def test_multiple_reasons_are_extracted(ids: tuple[str, str], api: TestClient) -> None:
    response = api.post(
        URL,
        json=body(ids, "Great profile, but I don't want someone who smokes and I can't move to Bangalore."),
    )

    reasons = response.json()["structured_feedback"]["reasons"]
    assert [(r["attribute"], r["value"], r["preference_type"]) for r in reasons] == [
        ("smoking", True, "DEAL_BREAKER"),
        ("location", "Bangalore", "HARD"),
    ]


def test_ambiguous_feedback_needs_review(ids: tuple[str, str], api: TestClient) -> None:
    response = api.post(URL, json=body(ids, "Maybe smoking could be an issue."))

    structured = response.json()["structured_feedback"]
    assert structured["needs_review"] is True
    assert structured["reasons"][0]["kind"] == "UNCLEAR"


def test_unknown_client_returns_404(ids: tuple[str, str], api: TestClient) -> None:
    response = api.post(URL, json=body((str(uuid.uuid4()), ids[1]), "Smoking is a deal breaker."))

    assert response.status_code == 404
    assert response.json() == {"detail": "Client not found"}


def test_unknown_profile_returns_404(ids: tuple[str, str], api: TestClient) -> None:
    response = api.post(URL, json=body((ids[0], str(uuid.uuid4())), "Smoking is a deal breaker."))

    assert response.status_code == 404
    assert response.json() == {"detail": "Profile not found"}


@pytest.mark.parametrize("raw_feedback", ["", "   ", "\n\t"])
def test_empty_feedback_returns_422(ids: tuple[str, str], api: TestClient, raw_feedback: str) -> None:
    response = api.post(URL, json=body(ids, raw_feedback))

    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"client_id": "not-a-uuid", "profile_id": str(uuid.uuid4()), "raw_feedback": "x"},
        {"client_id": str(uuid.uuid4()), "profile_id": str(uuid.uuid4())},
        {"client_id": str(uuid.uuid4()), "profile_id": str(uuid.uuid4()), "raw_feedback": "x" * 5001},
    ],
)
def test_invalid_request_returns_422(session_factory: sessionmaker[Session], api: TestClient, payload: dict) -> None:
    assert api.post(URL, json=payload).status_code == 422


def test_feedback_is_persisted(
    ids: tuple[str, str], api: TestClient, session_factory: sessionmaker[Session]
) -> None:
    response = api.post(URL, json=body(ids, "  Not a fan of smokers. Bangalore is too far.  "))
    data = response.json()

    with session_factory() as session:
        row = session.scalars(select(RejectionFeedback)).one()
        assert str(row.id) == data["id"]
        assert str(row.client_id) == ids[0]
        assert str(row.profile_id) == ids[1]
        assert row.raw_feedback == "Not a fan of smokers. Bangalore is too far."
        assert row.structured_feedback == data["structured_feedback"]
        assert StructuredFeedback.model_validate(row.structured_feedback).reasons[1].value == "Bangalore"


def test_unconfigured_openai_returns_503(
    ids: tuple[str, str], api: TestClient, session_factory: sessionmaker[Session]
) -> None:
    app.dependency_overrides[get_feedback_extractor] = lambda: OpenAIFeedbackExtractor(
        api_key="", model="gpt-6-luna"
    )

    response = api.post(URL, json=body(ids, "Smoking is a deal breaker."))

    assert response.status_code == 503
    assert response.json() == {
        "detail": "AI feedback analysis is not configured: OPENAI_API_KEY is not set."
    }
    with session_factory() as session:
        assert session.scalars(select(RejectionFeedback)).all() == []


def test_gemini_provider_returns_saved_analysis(
    ids: tuple[str, str], api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict] = []
    parsed = DemoFeedbackExtractor().extract("Smoking is a deal breaker.")

    class FakeGeminiClient:
        def __init__(self, **kwargs: object) -> None:
            self.models = self

        def generate_content(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            return SimpleNamespace(parsed=parsed)

    monkeypatch.setattr(gemini_feedback_extractor.genai, "Client", FakeGeminiClient)
    settings = Settings(FEEDBACK_EXTRACTOR="gemini", GEMINI_API_KEY="fake", GEMINI_MODEL="gemini-3.5-flash-lite")
    app.dependency_overrides[get_feedback_extractor] = lambda: create_feedback_extractor(settings)

    response = api.post(URL, json=body(ids, "Smoking is a deal breaker."))

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"id", "client_id", "profile_id", "raw_feedback", "structured_feedback"}
    assert data["structured_feedback"] == parsed.model_dump(mode="json")
    [call] = calls
    assert call["model"] == "gemini-3.5-flash-lite"
    assert call["contents"] == "Smoking is a deal breaker."


def test_unconfigured_gemini_returns_503(
    ids: tuple[str, str], api: TestClient, session_factory: sessionmaker[Session]
) -> None:
    app.dependency_overrides[get_feedback_extractor] = lambda: GeminiFeedbackExtractor(
        api_key="", model="gemini-3.5-flash-lite"
    )

    response = api.post(URL, json=body(ids, "Smoking is a deal breaker."))

    assert response.status_code == 503
    assert response.json() == {
        "detail": "AI feedback analysis is not configured: GEMINI_API_KEY is not set."
    }
    with session_factory() as session:
        assert session.scalars(select(RejectionFeedback)).all() == []


def test_provider_failure_returns_503_without_internals(ids: tuple[str, str], api: TestClient) -> None:
    class BrokenExtractor:
        def extract(self, feedback: str) -> StructuredFeedback:
            raise FeedbackExtractionError("The AI provider timed out. Please try again.")

    app.dependency_overrides[get_feedback_extractor] = BrokenExtractor

    response = api.post(URL, json=body(ids, "Smoking is a deal breaker."))

    assert response.status_code == 503
    assert response.json() == {"detail": "The AI provider timed out. Please try again."}


def test_not_found_is_checked_before_calling_extractor(
    ids: tuple[str, str], api: TestClient
) -> None:
    calls: list[str] = []

    class RecordingExtractor:
        def extract(self, feedback: str) -> StructuredFeedback:
            calls.append(feedback)
            return DemoFeedbackExtractor().extract(feedback)

    app.dependency_overrides[get_feedback_extractor] = RecordingExtractor

    response = api.post(URL, json=body((str(uuid.uuid4()), ids[1]), "Smoking is a deal breaker."))

    assert response.status_code == 404
    assert calls == []
