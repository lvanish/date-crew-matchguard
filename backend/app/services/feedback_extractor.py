from typing import Protocol

from app.core.config import Settings
from app.schemas.feedback import StructuredFeedback


class FeedbackExtractionError(Exception):
    """The configured extractor could not produce structured feedback.

    The message is safe to show to API clients; provider details stay in the cause.
    """


class FeedbackExtractor(Protocol):
    """Turns free-text rejection feedback into structured reasons. Never makes match decisions."""

    def extract(self, feedback: str) -> StructuredFeedback: ...


def create_feedback_extractor(settings: Settings) -> FeedbackExtractor:
    provider = settings.FEEDBACK_EXTRACTOR
    if provider == "gemini":
        from app.services.gemini_feedback_extractor import GeminiFeedbackExtractor

        return GeminiFeedbackExtractor(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)

    if provider == "openai":
        from app.services.openai_feedback_extractor import OpenAIFeedbackExtractor

        return OpenAIFeedbackExtractor(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)

    if provider == "demo":
        from app.services.demo_feedback_extractor import DemoFeedbackExtractor

        return DemoFeedbackExtractor()

    raise ValueError(f"Unknown FEEDBACK_EXTRACTOR {provider!r}; expected demo, openai or gemini.")
