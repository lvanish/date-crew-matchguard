import pytest

from app.core.config import DEFAULT_GEMINI_MODEL, DEFAULT_OPENAI_MODEL, Settings

FAKE_OPENAI_KEY = "sk-test-not-a-real-key"
FAKE_GEMINI_KEY = "AIza-test-not-a-real-key"
ENV_NAMES = (
    "CORS_ORIGINS",
    "DATABASE_URL",
    "FEEDBACK_EXTRACTOR",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_reads_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEEDBACK_EXTRACTOR", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "my-model")
    monkeypatch.setenv("GEMINI_MODEL", "my-gemini-model")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")

    settings = Settings()

    assert settings.FEEDBACK_EXTRACTOR == "openai"
    assert settings.OPENAI_MODEL == "my-model"
    assert settings.GEMINI_MODEL == "my-gemini-model"
    assert settings.DATABASE_URL == "sqlite://"


@pytest.mark.parametrize("provider", ["demo", "openai", "gemini", " Gemini "])
def test_accepts_every_supported_provider(monkeypatch: pytest.MonkeyPatch, provider: str) -> None:
    monkeypatch.setenv("FEEDBACK_EXTRACTOR", provider)

    assert Settings().FEEDBACK_EXTRACTOR == provider.strip().lower()


def test_unknown_provider_fails_at_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEEDBACK_EXTRACTOR", "magic")

    with pytest.raises(ValueError, match="FEEDBACK_EXTRACTOR must be one of demo, openai, gemini"):
        Settings()


def test_defaults_without_environment() -> None:
    settings = Settings()

    assert settings.FEEDBACK_EXTRACTOR == "gemini"
    assert settings.GEMINI_MODEL == DEFAULT_GEMINI_MODEL == "gemini-3.5-flash-lite"
    assert settings.GEMINI_API_KEY == ""
    assert settings.OPENAI_MODEL == DEFAULT_OPENAI_MODEL == "gpt-6-luna"
    assert settings.OPENAI_API_KEY == ""
    assert settings.DATABASE_URL.startswith("postgresql+psycopg://")


def test_cors_origins_default_to_local_frontend() -> None:
    assert Settings().CORS_ORIGINS == ("http://localhost:5173",)


@pytest.mark.parametrize("raw", ["", "   ", " , ,"])
def test_blank_cors_origins_fall_back_to_default(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("CORS_ORIGINS", raw)

    assert Settings().CORS_ORIGINS == ("http://localhost:5173",)


def test_cors_origins_accept_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS",
        " http://localhost:5173 , https://example.vercel.app/,,https://example.vercel.app",
    )

    assert Settings().CORS_ORIGINS == ("http://localhost:5173", "https://example.vercel.app")


def test_cors_wildcard_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,*")

    with pytest.raises(ValueError, match="'\\*' is not allowed"):
        Settings()


def test_api_keys_are_not_exposed_by_repr_or_str(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_OPENAI_KEY)
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_GEMINI_KEY)

    settings = Settings()

    assert settings.OPENAI_API_KEY == FAKE_OPENAI_KEY
    assert settings.GEMINI_API_KEY == FAKE_GEMINI_KEY
    for text in (repr(settings), str(settings)):
        assert FAKE_OPENAI_KEY not in text
        assert FAKE_GEMINI_KEY not in text
