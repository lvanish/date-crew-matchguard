import logging
import re
from typing import Any

import openai
from pydantic import ValidationError

from app.schemas.feedback import StructuredFeedback
from app.services.feedback_extractor import FeedbackExtractionError
from app.services.feedback_prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 2
MAX_LOGGED_MESSAGE_LENGTH = 500

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-*]+"),
    re.compile(r"(?i)bearer\s+\S+"),
)


class OpenAIFeedbackExtractor:
    """LLM extraction via the OpenAI Responses API with Structured Outputs."""

    def __init__(self, api_key: str, model: str, client: Any | None = None) -> None:
        self._model = model
        self._api_key = api_key
        # `client` lets tests inject a fake; otherwise build the real one only if a key exists,
        # so the app can start without credentials and fail cleanly on first use.
        if client is not None:
            self._client = client
        elif api_key:
            self._client = openai.OpenAI(
                api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=MAX_RETRIES
            )
        else:
            self._client = None

    @property
    def model(self) -> str:
        return self._model

    def extract(self, feedback: str) -> StructuredFeedback:
        if self._client is None:
            raise FeedbackExtractionError(
                "AI feedback analysis is not configured: OPENAI_API_KEY is not set."
            )

        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=SYSTEM_PROMPT,
                input=feedback,
                text_format=StructuredFeedback,
                # Extraction should be repeatable: no reasoning, no sampling variance.
                # gpt-6-luna only accepts temperature when reasoning effort is "none".
                reasoning={"effort": "none"},
                temperature=0,
                # Client feedback is personal data; don't keep it on OpenAI's side.
                store=False,
            )
        except openai.APITimeoutError as error:
            raise self._fail("The AI provider timed out. Please try again.", error) from error
        except openai.APIConnectionError as error:
            raise self._fail("Could not reach the AI provider. Please try again.", error) from error
        except openai.AuthenticationError as error:
            raise self._fail("The AI provider rejected the configured API key.", error) from error
        except openai.RateLimitError as error:
            raise self._fail("The AI provider is rate limiting requests. Please try again later.", error) from error
        except (openai.OpenAIError, ValidationError) as error:
            raise self._fail("The AI provider did not return a usable result.", error) from error

        parsed = getattr(response, "output_parsed", None)
        if not isinstance(parsed, StructuredFeedback):
            # Refusals and incomplete responses come back without parsed output.
            raise self._fail("The AI provider did not return a usable result.", None)
        return parsed

    def _fail(self, message: str, error: Exception | None) -> FeedbackExtractionError:
        # Only read known scalar attributes: str(error), error.request and error.response
        # can carry headers or the key itself.
        logger.warning(
            "OpenAI feedback extraction failed (model=%s):\n"
            "exception=%s\nstatus=%s\ncode=%s\ntype=%s\nrequest_id=%s\nmessage=%s",
            self._model,
            type(error).__name__ if error else "no parsed output",
            _field(error, "status_code"),
            _field(error, "code"),
            _field(error, "type"),
            _field(error, "request_id"),
            self._sanitize(_field(error, "message")),
        )
        return FeedbackExtractionError(message)

    def _sanitize(self, text: str) -> str:
        if self._api_key:
            text = text.replace(self._api_key, "[REDACTED]")
        for pattern in _SECRET_PATTERNS:
            text = pattern.sub("[REDACTED]", text)
        text = " ".join(text.split())
        return text[:MAX_LOGGED_MESSAGE_LENGTH]


def _field(error: Exception | None, name: str) -> str:
    value = getattr(error, name, None) if error is not None else None
    if value is None or isinstance(value, (dict, list, tuple)):
        return "unknown"
    text = str(value).strip()
    return text or "unknown"
