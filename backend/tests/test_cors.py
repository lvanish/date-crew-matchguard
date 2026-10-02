from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def preflight(origin: str):
    return client.options(
        "/api/clients",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )


def test_configured_origin_is_allowed() -> None:
    origin = settings.CORS_ORIGINS[0]

    response = preflight(origin)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"


def test_unlisted_origin_is_not_allowed() -> None:
    response = preflight("https://not-allowed.example")

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
