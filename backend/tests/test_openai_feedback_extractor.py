from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest
from openai.lib._pydantic import to_strict_json_schema

from app.core import config
from app.core.config import Settings
from app.schemas.feedback import FeedbackAttribute, StructuredFeedback
from app.services.demo_feedback_extractor import DemoFeedbackExtractor
from app.services.feedback_extractor import FeedbackExtractionError, create_feedback_extractor
from app.services.feedback_prompt import SYSTEM_PROMPT
from app.services.gemini_feedback_extractor import GeminiFeedbackExtractor
from app.services.openai_feedback_extractor import OpenAIFeedbackExtractor

PARSED = StructuredFeedback.model_validate(
    {
        "reasons": [
            {
                "attribute": "smoking",
                "value": True,
                "preference_type": "DEAL_BREAKER",
                "kind": "VIOLATION",
                "explanation": "Client explicitly says smoking is not acceptable.",
            }
        ],
        "needs_review": False,
    }
)

REQUEST = httpx.Request("POST", "https://api.openai.com/v1/responses")


class FakeResponses:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._result = result
        self._error = error

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._result


def fake_client(result: Any = None, error: Exception | None = None) -> SimpleNamespace:
    return SimpleNamespace(responses=FakeResponses(result, error))


def test_sends_feedback_with_model_prompt_and_schema() -> None:
    client = fake_client(SimpleNamespace(output_parsed=PARSED))
    extractor = OpenAIFeedbackExtractor(api_key="unused", model="gpt-6-luna", client=client)

    result = extractor.extract("Nice profile but I don't want a smoker.")

    assert result is PARSED
    [call] = client.responses.calls
    assert call["model"] == "gpt-6-luna"
    assert call["input"] == "Nice profile but I don't want a smoker."
    assert call["instructions"] == SYSTEM_PROMPT
    assert call["text_format"] is StructuredFeedback
    assert call["temperature"] == 0
    assert call["reasoning"] == {"effort": "none"}
    assert call["store"] is False


def test_uses_configured_model() -> None:
    client = fake_client(SimpleNamespace(output_parsed=PARSED))
    extractor = OpenAIFeedbackExtractor(api_key="unused", model="my-other-model", client=client)

    extractor.extract("Smoking is a deal breaker.")

    assert client.responses.calls[0]["model"] == "my-other-model"


def test_schema_is_accepted_as_strict_structured_output() -> None:
    schema = to_strict_json_schema(StructuredFeedback)

    reason = schema["$defs"]["FeedbackReason"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"reasons", "needs_review"}
    assert set(reason["required"]) == {"attribute", "value", "preference_type", "kind", "explanation"}
    assert reason["additionalProperties"] is False


def test_prompt_forbids_match_decisions() -> None:
    assert "information extraction, not matchmaking" in SYSTEM_PROMPT
    assert "Never invent facts" in SYSTEM_PROMPT
    assert "needs_review=true" in SYSTEM_PROMPT


def test_missing_api_key_fails_cleanly() -> None:
    extractor = OpenAIFeedbackExtractor(api_key="", model="gpt-6-luna")

    with pytest.raises(FeedbackExtractionError, match="OPENAI_API_KEY is not set"):
        extractor.extract("Smoking is a deal breaker.")


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (openai.APITimeoutError(request=REQUEST), "timed out"),
        (openai.APIConnectionError(request=REQUEST), "Could not reach"),
        (
            openai.AuthenticationError(
                "Incorrect API key provided: sk-secret",
                response=httpx.Response(401, request=REQUEST),
                body=None,
            ),
            "rejected the configured API key",
        ),
        (
            openai.RateLimitError("slow down", response=httpx.Response(429, request=REQUEST), body=None),
            "rate limiting",
        ),
        (
            openai.InternalServerError("boom", response=httpx.Response(500, request=REQUEST), body=None),
            "did not return a usable result",
        ),
    ],
)
def test_sdk_errors_become_clean_application_errors(error: Exception, message: str) -> None:
    extractor = OpenAIFeedbackExtractor(api_key="unused", model="gpt-6-luna", client=fake_client(error=error))

    with pytest.raises(FeedbackExtractionError) as raised:
        extractor.extract("Smoking is a deal breaker.")

    assert message in str(raised.value)
    assert "sk-secret" not in str(raised.value)


def test_diagnostic_log_has_error_details_but_no_secrets(caplog: pytest.LogCaptureFixture) -> None:
    fake_key = "sk-proj-FAKEtestKEY1234567890"
    request = httpx.Request(
        "POST", "https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {fake_key}"}
    )
    response = httpx.Response(429, request=request, headers={"x-request-id": "req_abc123"})
    error = openai.RateLimitError(
        f"You exceeded your current quota (key {fake_key}).",
        response=response,
        body={"code": "insufficient_quota", "type": "insufficient_quota", "message": "quota"},
    )
    extractor = OpenAIFeedbackExtractor(api_key=fake_key, model="gpt-6-luna", client=fake_client(error=error))

    with caplog.at_level("WARNING"), pytest.raises(FeedbackExtractionError):
        extractor.extract("Smoking is a deal breaker.")

    log = caplog.text
    assert "exception=RateLimitError" in log
    assert "status=429" in log
    assert "code=insufficient_quota" in log
    assert "type=insufficient_quota" in log
    assert "request_id=req_abc123" in log
    assert "message=You exceeded your current quota" in log
    assert fake_key not in log
    assert "FAKEtestKEY" not in log
    assert "Bearer" not in log
    assert "Authorization" not in log


def test_diagnostic_log_marks_missing_fields_unknown(caplog: pytest.LogCaptureFixture) -> None:
    error = openai.APIConnectionError(request=REQUEST)
    extractor = OpenAIFeedbackExtractor(api_key="unused", model="gpt-6-luna", client=fake_client(error=error))

    with caplog.at_level("WARNING"), pytest.raises(FeedbackExtractionError):
        extractor.extract("Smoking is a deal breaker.")

    assert "status=unknown" in caplog.text
    assert "code=unknown" in caplog.text
    assert "type=unknown" in caplog.text
    assert "request_id=unknown" in caplog.text


@pytest.mark.parametrize("result", [SimpleNamespace(output_parsed=None), SimpleNamespace()])
def test_missing_parsed_output_fails_cleanly(result: Any) -> None:
    extractor = OpenAIFeedbackExtractor(api_key="unused", model="gpt-6-luna", client=fake_client(result))

    with pytest.raises(FeedbackExtractionError, match="did not return a usable result"):
        extractor.extract("Smoking is a deal breaker.")


def test_invalid_structured_output_fails_cleanly() -> None:
    try:
        StructuredFeedback.model_validate({"reasons": "nope", "needs_review": False})
    except Exception as validation_error:
        error = validation_error
    extractor = OpenAIFeedbackExtractor(api_key="unused", model="gpt-6-luna", client=fake_client(error=error))

    with pytest.raises(FeedbackExtractionError, match="did not return a usable result"):
        extractor.extract("Smoking is a deal breaker.")


def test_factory_selects_provider() -> None:
    demo = create_feedback_extractor(Settings(FEEDBACK_EXTRACTOR="demo"))
    real = create_feedback_extractor(
        Settings(FEEDBACK_EXTRACTOR="openai", OPENAI_API_KEY="", OPENAI_MODEL="gpt-6-luna")
    )
    gemini = create_feedback_extractor(
        Settings(FEEDBACK_EXTRACTOR="gemini", GEMINI_API_KEY="", GEMINI_MODEL="gemini-3.5-flash-lite")
    )

    assert isinstance(demo, DemoFeedbackExtractor)
    assert isinstance(real, OpenAIFeedbackExtractor)
    assert real.model == "gpt-6-luna"
    assert isinstance(gemini, GeminiFeedbackExtractor)
    assert gemini.model == "gemini-3.5-flash-lite"


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown FEEDBACK_EXTRACTOR 'magic'"):
        create_feedback_extractor(Settings(FEEDBACK_EXTRACTOR="magic"))


def test_default_provider_is_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEEDBACK_EXTRACTOR", raising=False)

    assert config._feedback_extractor() == "gemini"


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEEDBACK_EXTRACTOR", "magic")

    with pytest.raises(ValueError, match="FEEDBACK_EXTRACTOR must be one of demo, openai, gemini"):
        config._feedback_extractor()


def test_api_key_is_not_in_settings_repr() -> None:
    settings = Settings(OPENAI_API_KEY="sk-should-not-appear")

    assert "sk-should-not-appear" not in repr(settings)


def test_parsed_result_keeps_enum_types() -> None:
    assert PARSED.reasons[0].attribute is FeedbackAttribute.SMOKING
