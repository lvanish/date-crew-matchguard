import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes.matches import MATCH_RESULT_EXAMPLES
from app.db.base import ConflictKind, Decision, PreferenceType
from app.main import app
from app.models import Client, ClientPreference, MatchCheck, MatchConflict, Profile
from app.schemas.matching import CandidateProfileInput, ClientPreferenceInput, MatchResult
from app.services.match_engine import MatchEngine

URL = "/api/matches/check"


def persisted_conflicts(factory: sessionmaker[Session]) -> list[dict]:
    """Stored conflicts in the same shape as the API response, sorted by attribute."""
    with factory() as session:
        rows = session.scalars(select(MatchConflict).order_by(MatchConflict.attribute)).all()
        return [
            {
                "kind": row.kind.value,
                "attribute": row.attribute,
                "candidate_value": row.candidate_value,
                "expected_value": row.expected_value,
                "preference_type": row.preference_type.value,
                "reason": row.reason,
            }
            for row in rows
        ]


def by_attribute(conflicts: list[dict]) -> list[dict]:
    return sorted(conflicts, key=lambda c: c["attribute"])


def seed(factory: sessionmaker[Session], **profile_fields) -> tuple[uuid.UUID, uuid.UUID]:
    with factory() as session:
        client = Client(
            name="Aisha",
            preferences=[
                ClientPreference(
                    attribute="smoking", value=False, preference_type=PreferenceType.DEAL_BREAKER
                ),
                ClientPreference(
                    attribute="age",
                    value={"min": 28, "max": 35},
                    preference_type=PreferenceType.HARD,
                ),
            ],
        )
        profile = Profile(name="Rahul", **profile_fields)
        session.add_all([client, profile])
        session.commit()
        return client.id, profile.id


def test_check_blocks_and_persists_conflicts(
    session_factory: sessionmaker[Session], api: TestClient
) -> None:
    client_id, profile_id = seed(session_factory, age=41, smoking=True)

    response = api.post(URL, json={"client_id": str(client_id), "profile_id": str(profile_id)})

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "BLOCK"
    assert {c["attribute"] for c in body["conflicts"]} == {"smoking", "age"}
    smoking = next(c for c in body["conflicts"] if c["attribute"] == "smoking")
    assert smoking == {
        "kind": "VIOLATION",
        "attribute": "smoking",
        "candidate_value": True,
        "expected_value": False,
        "preference_type": "DEAL_BREAKER",
        "reason": "Candidate smokes, while smoking is marked as a client deal-breaker.",
    }

    with session_factory() as session:
        check = session.scalars(select(MatchCheck)).one()
        assert check.client_id == client_id
        assert check.profile_id == profile_id
        assert check.decision == Decision.BLOCK
        conflicts = session.scalars(select(MatchConflict)).all()
        assert all(c.match_check_id == check.id for c in conflicts)
        assert {c.kind for c in conflicts} == {ConflictKind.VIOLATION}

    assert persisted_conflicts(session_factory) == by_attribute(body["conflicts"])


def test_check_persists_missing_data_kind(
    session_factory: sessionmaker[Session], api: TestClient
) -> None:
    client_id, profile_id = seed(session_factory, age=41, smoking=None)

    response = api.post(URL, json={"client_id": str(client_id), "profile_id": str(profile_id)})

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "REVIEW"
    assert {c["attribute"]: c["kind"] for c in body["conflicts"]} == {
        "smoking": "MISSING_DATA",
        "age": "VIOLATION",
    }
    assert persisted_conflicts(session_factory) == by_attribute(body["conflicts"])


def test_check_passes_and_persists_check_without_conflicts(
    session_factory: sessionmaker[Session], api: TestClient
) -> None:
    client_id, profile_id = seed(session_factory, age=30, smoking=False)

    response = api.post(URL, json={"client_id": str(client_id), "profile_id": str(profile_id)})

    assert response.status_code == 200
    assert response.json() == {"decision": "PASS", "conflicts": []}
    with session_factory() as session:
        assert session.scalars(select(MatchCheck)).one().decision == Decision.PASS
        assert session.scalars(select(MatchConflict)).all() == []


def test_unknown_client_returns_404(session_factory: sessionmaker[Session], api: TestClient) -> None:
    _, profile_id = seed(session_factory)

    response = api.post(URL, json={"client_id": str(uuid.uuid4()), "profile_id": str(profile_id)})

    assert response.status_code == 404
    assert response.json() == {"detail": "Client not found"}


def test_unknown_profile_returns_404(session_factory: sessionmaker[Session], api: TestClient) -> None:
    client_id, _ = seed(session_factory)

    response = api.post(URL, json={"client_id": str(client_id), "profile_id": str(uuid.uuid4())})

    assert response.status_code == 404
    assert response.json() == {"detail": "Profile not found"}


def test_invalid_uuid_returns_422(session_factory: sessionmaker[Session], api: TestClient) -> None:
    response = api.post(URL, json={"client_id": "not-a-uuid", "profile_id": "also-not"})

    assert response.status_code == 422


def test_database_error_rolls_back_and_returns_500(
    session_factory: sessionmaker[Session], api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client_id, profile_id = seed(session_factory, age=41, smoking=True)

    def failing_commit(self: Session) -> None:
        raise SQLAlchemyError("simulated failure")

    monkeypatch.setattr(Session, "commit", failing_commit)
    response = api.post(URL, json={"client_id": str(client_id), "profile_id": str(profile_id)})
    monkeypatch.undo()

    assert response.status_code == 500
    assert response.json() == {"detail": "Could not complete the match check."}
    with session_factory() as session:
        assert session.scalars(select(MatchCheck)).all() == []


def test_openapi_documents_one_example_per_decision() -> None:
    operation = app.openapi()["paths"][URL]["post"]
    examples = operation["responses"]["200"]["content"]["application/json"]["examples"]

    decisions = {example["value"]["decision"] for example in examples.values()}
    assert decisions == {"PASS", "REVIEW", "BLOCK"}
    assert examples["pass"]["value"] == {"decision": "PASS", "conflicts": []}
    for example in examples.values():
        MatchResult.model_validate(example["value"])


# Engine inputs that should reproduce each documented example exactly.
EXAMPLE_INPUTS = {
    "pass": ([("smoking", False, PreferenceType.DEAL_BREAKER)], {"smoking": False}),
    "review": ([("location", "Bangalore", PreferenceType.HARD)], {"location": "Mumbai"}),
    "review_missing_data": ([("smoking", False, PreferenceType.DEAL_BREAKER)], {"smoking": None}),
    "block": ([("smoking", False, PreferenceType.DEAL_BREAKER)], {"smoking": True}),
}


@pytest.mark.parametrize("name", MATCH_RESULT_EXAMPLES)
def test_openapi_examples_match_real_engine_output(name: str) -> None:
    preferences, candidate = EXAMPLE_INPUTS[name]

    result = MatchEngine().check(
        [ClientPreferenceInput(attribute=a, value=v, preference_type=t) for a, v, t in preferences],
        CandidateProfileInput(**candidate),
    )

    assert result.model_dump(mode="json") == MATCH_RESULT_EXAMPLES[name]["value"]
