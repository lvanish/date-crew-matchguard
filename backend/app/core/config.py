import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/matchguard"
DEFAULT_OPENAI_MODEL = "gpt-6-luna"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
DEFAULT_FEEDBACK_EXTRACTOR = "gemini"
FEEDBACK_EXTRACTORS = ("demo", "openai", "gemini")
DEFAULT_CORS_ORIGINS = "http://localhost:5173"


def _cors_origins() -> tuple[str, ...]:
    raw = os.getenv("CORS_ORIGINS", "").strip() or DEFAULT_CORS_ORIGINS
    # Browsers send Origin without a trailing slash, so "https://x.app/" would never match.
    origins = tuple(dict.fromkeys(o.strip().rstrip("/") for o in raw.split(",") if o.strip()))
    if "*" in origins:
        raise ValueError("CORS_ORIGINS must list explicit origins; '*' is not allowed.")
    return origins or (DEFAULT_CORS_ORIGINS,)


def _feedback_extractor() -> str:
    value = os.getenv("FEEDBACK_EXTRACTOR", "").strip().lower() or DEFAULT_FEEDBACK_EXTRACTOR
    if value not in FEEDBACK_EXTRACTORS:
        raise ValueError(
            f"FEEDBACK_EXTRACTOR must be one of {', '.join(FEEDBACK_EXTRACTORS)}; got {value!r}."
        )
    return value


@dataclass(frozen=True)
class Settings:
    DATABASE_URL: str = field(default_factory=lambda: os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL)
    CORS_ORIGINS: tuple[str, ...] = field(default_factory=_cors_origins)
    FEEDBACK_EXTRACTOR: str = field(default_factory=_feedback_extractor)
    OPENAI_API_KEY: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "").strip(), repr=False
    )
    OPENAI_MODEL: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_OPENAI_MODEL
    )
    GEMINI_API_KEY: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip(), repr=False
    )
    GEMINI_MODEL: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_GEMINI_MODEL
    )


settings = Settings()
