import logging
from typing import Any

import httpx
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.schemas.feedback import StructuredFeedback
from app.services.feedback_extractor import FeedbackExtractionError
from app.services.feedback_prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_MS = 30_000
MAX_ATTEMPTS = 3


class GeminiFeedbackExtractor:
    """LLM extraction via the Gemini API (google-genai) with structured output."""

    def __init__(self, api_key: str, model: str, client: Any | None = None) -> None:
        self._model = model
        # `client` lets tests inject a fake; otherwise build the real one only if a key exists,
        # so the app can start without credentials and fail cleanly on first use.
        if client is not None:
            self._client = client
        elif api_key:
            self._client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    timeout=REQUEST_TIMEOUT_MS,
                    retry_options=types.HttpRetryOptions(attempts=MAX_ATTEMPTS),
                ),
            )
        else:
            self._client = None

    @property
    def model(self) -> str:
        return self._model

    def extract(self, feedback: str) -> StructuredFeedback:
        if self._client is None:
            raise FeedbackExtractionError(
                "AI feedback analysis is not configured: GEMINI_API_KEY is not set."
            )

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=feedback,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=StructuredFeedback,
                    # Simple extraction: keep reasoning (and latency) to the minimum.
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
                ),
            )
        except httpx.TimeoutException as error:
            raise self._fail("The AI provider timed out. Please try again.", error) from error
        except httpx.TransportError as error:
            raise self._fail("Could not reach the AI provider. Please try again.", error) from error
        except errors.APIError as error:
            raise self._fail(_api_error_message(error), error) from error
        except ValidationError as error:
            raise self._fail("The AI provider did not return a usable result.", error) from error

        parsed = getattr(response, "parsed", None)
        if not isinstance(parsed, StructuredFeedback):
            # Blocked, truncated or schema-mismatched responses come back without parsed output.
            raise self._fail("The AI provider did not return a usable result.", None)
        return parsed

    def _fail(self, message: str, error: Exception | None) -> FeedbackExtractionError:
        # str(error) on google-genai errors includes the full response body; log scalars only.
        logger.warning(
            "Gemini feedback extraction failed (provider=gemini, model=%s): "
            "exception=%s status=%s code=%s",
            self._model,
            type(error).__name__ if error else "no parsed output",
            _field(error, "code"),
            _field(error, "status"),
        )
        return FeedbackExtractionError(message)


def _api_error_message(error: errors.APIError) -> str:
    code = getattr(error, "code", None)
    status = getattr(error, "status", None)
    if code in (401, 403) or (code == 400 and "API key" in (getattr(error, "message", None) or "")):
        return "The AI provider rejected the configured API key."
    if code == 429 or status == "RESOURCE_EXHAUSTED":
        return "The AI provider is rate limiting requests. Please try again later."
    if isinstance(error, errors.ServerError):
        return "The AI provider is unavailable. Please try again later."
    return "The AI provider did not return a usable result."


def _field(error: Exception | None, name: str) -> str:
    value = getattr(error, name, None) if error is not None else None
    if value is None or isinstance(value, (dict, list, tuple)):
        return "unknown"
    return str(value).strip() or "unknown"
