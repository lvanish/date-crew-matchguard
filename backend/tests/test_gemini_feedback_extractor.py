import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from google.genai import errors, types

from app.schemas.feedback import FeedbackPreferenceType, StructuredFeedback
from app.services.feedback_extractor import FeedbackExtractionError
from app.services.feedback_prompt import SYSTEM_PROMPT
from app.services.gemini_feedback_extractor import GeminiFeedbackExtractor

PAYLOAD = {
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
PARSED = StructuredFeedback.model_validate(PAYLOAD)


def sdk_response(text: str) -> types.GenerateContentResponse:
    """A response built by the real SDK, so `parsed` comes from its own schema handling."""
    raw = {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}]}
    return types.GenerateContentResponse._from_response(
        response=raw, kwargs={"config": {"response_schema": StructuredFeedback}}
    )


class FakeModels:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._result = result
        self._error = error

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._result


def fake_client(result: Any = None, error: Exception | None = None) -> SimpleNamespace:
    return SimpleNamespace(models=FakeModels(result, error))


def api_error(cls: type[errors.APIError], code: int, status: str, message: str) -> errors.APIError:
    return cls(code, {"error": {"code": code, "status": status, "message": message}})


def test_sends_feedback_with_prompt_and_structured_output_schema() -> None:
    client = fake_client(SimpleNamespace(parsed=PARSED))
    extractor = GeminiFeedbackExtractor(api_key="unused", model="gemini-3.5-flash-lite", client=client)

    result = extractor.extract("Nice profile but I don't want a smoker.")

    assert result is PARSED
    [call] = client.models.calls
    assert call["model"] == "gemini-3.5-flash-lite"
    assert call["contents"] == "Nice profile but I don't want a smoker."
    config = call["config"]
    assert config.system_instruction == SYSTEM_PROMPT
    assert config.response_mime_type == "application/json"
    assert config.response_schema is StructuredFeedback
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL
    assert not config.tools


def test_uses_configured_model() -> None:
    client = fake_client(SimpleNamespace(parsed=PARSED))
    extractor = GeminiFeedbackExtractor(api_key="unused", model="my-other-model", client=client)

    extractor.extract("Smoking is a deal breaker.")

    assert client.models.calls[0]["model"] == "my-other-model"


def test_sdk_parsed_json_becomes_structured_feedback() -> None:
    client = fake_client(sdk_response(json.dumps(PAYLOAD)))
    extractor = GeminiFeedbackExtractor(api_key="unused", model="gemini-3.5-flash-lite", client=client)

    result = extractor.extract("Smoking is a deal breaker.")

    assert isinstance(result, StructuredFeedback)
    assert result.reasons[0].preference_type is FeedbackPreferenceType.DEAL_BREAKER
    assert result.needs_review is False


@pytest.mark.parametrize(
    "result",
    [
        sdk_response(json.dumps({"reasons": "nope"})),
        sdk_response("not json"),
        SimpleNamespace(parsed=None),
        SimpleNamespace(parsed={"reasons": [], "needs_review": False}),
    ],
)
def test_unusable_structured_output_fails_cleanly(result: Any) -> None:
    extractor = GeminiFeedbackExtractor(
        api_key="unused", model="gemini-3.5-flash-lite", client=fake_client(result)
    )

    with pytest.raises(FeedbackExtractionError, match="did not return a usable result"):
        extractor.extract("Smoking is a deal breaker.")


def test_missing_api_key_fails_cleanly() -> None:
    extractor = GeminiFeedbackExtractor(api_key="", model="gemini-3.5-flash-lite")

    with pytest.raises(FeedbackExtractionError, match="GEMINI_API_KEY is not set"):
        extractor.extract("Smoking is a deal breaker.")


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (httpx.ReadTimeout("slow"), "timed out"),
        (httpx.ConnectError("down"), "Could not reach"),
        (api_error(errors.ClientError, 400, "INVALID_ARGUMENT", "API key not valid."), "rejected the configured API key"),
        (api_error(errors.ClientError, 403, "PERMISSION_DENIED", "denied"), "rejected the configured API key"),
        (api_error(errors.ClientError, 429, "RESOURCE_EXHAUSTED", "quota"), "rate limiting"),
        (api_error(errors.ServerError, 503, "UNAVAILABLE", "overloaded"), "unavailable"),
        (api_error(errors.ClientError, 400, "INVALID_ARGUMENT", "bad schema"), "did not return a usable result"),
    ],
)
def test_sdk_errors_become_clean_application_errors(error: Exception, message: str) -> None:
    extractor = GeminiFeedbackExtractor(
        api_key="unused", model="gemini-3.5-flash-lite", client=fake_client(error=error)
    )

    with pytest.raises(FeedbackExtractionError) as raised:
        extractor.extract("Smoking is a deal breaker.")

    assert message in str(raised.value)
    assert "INVALID_ARGUMENT" not in str(raised.value)


def test_failure_log_is_safe(caplog: pytest.LogCaptureFixture) -> None:
    fake_key = "AIzaFAKEtestKEY1234567890"
    error = api_error(errors.ClientError, 429, "RESOURCE_EXHAUSTED", f"Quota exceeded for key {fake_key}")
    extractor = GeminiFeedbackExtractor(
        api_key=fake_key, model="gemini-3.5-flash-lite", client=fake_client(error=error)
    )

    with caplog.at_level("WARNING"), pytest.raises(FeedbackExtractionError) as raised:
        extractor.extract("Smoking is a deal breaker.")

    log = caplog.text
    assert "provider=gemini" in log
    assert "model=gemini-3.5-flash-lite" in log
    assert "exception=ClientError" in log
    assert "status=429" in log
    assert "code=RESOURCE_EXHAUSTED" in log
    assert fake_key not in log
    assert fake_key not in str(raised.value)
