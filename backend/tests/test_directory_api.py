import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import seed
from app.models import Client, Profile

PROFILE_KEYS = {
    "id",
    "name",
    "age",
    "location",
    "smoking",
    "drinking",
    "wants_children",
    "religion",
    "education",
    "occupation",
}


def test_clients_empty(session_factory: sessionmaker[Session], api: TestClient) -> None:
    response = api.get("/api/clients")

    assert response.status_code == 200
    assert response.json() == []


def test_clients_returns_id_and_name(session_factory: sessionmaker[Session], api: TestClient) -> None:
    with session_factory() as session:
        client = Client(name="Test Client")
        session.add(client)
        session.commit()

    response = api.get("/api/clients")

    assert response.status_code == 200
    assert response.json() == [{"id": str(client.id), "name": "Test Client"}]


def test_clients_returns_seeded_clients_sorted(
    session_factory: sessionmaker[Session], api: TestClient
) -> None:
    with session_factory() as session:
        seed.seed(session)
        session.commit()

    response = api.get("/api/clients")

    assert response.status_code == 200
    body = response.json()
    assert [c["name"] for c in body] == ["Arjun", "Karan", "Priya", "Rahul", "Sneha"]
    assert all(set(c) == {"id", "name"} for c in body)
    assert {c["name"]: c["id"] for c in body}["Rahul"] == str(seed.demo_id("client", "Rahul"))


def test_profiles_returns_all_ui_fields(
    session_factory: sessionmaker[Session], api: TestClient
) -> None:
    with session_factory() as session:
        profile = Profile(name="Test Profile", age=30, location="Pune", smoking=False)
        session.add(profile)
        session.commit()

    response = api.get("/api/profiles")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(profile.id),
            "name": "Test Profile",
            "age": 30,
            "location": "Pune",
            "smoking": False,
            "drinking": None,
            "wants_children": None,
            "religion": None,
            "education": None,
            "occupation": None,
        }
    ]


def test_profiles_returns_seeded_profiles(
    session_factory: sessionmaker[Session], api: TestClient
) -> None:
    with session_factory() as session:
        seed.seed(session)
        session.commit()

    response = api.get("/api/profiles")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == len(seed.PROFILES)
    assert all(set(p) == PROFILE_KEYS for p in body)
    names = [p["name"] for p in body]
    assert names == sorted(names)
    kavya = next(p for p in body if p["name"] == "Kavya")
    assert kavya["smoking"] is None
    assert kavya["location"] == "Delhi NCR"


def test_client_detail_returns_sorted_preferences(
    session_factory: sessionmaker[Session], api: TestClient
) -> None:
    with session_factory() as session:
        seed.seed(session)
        session.commit()
    rahul_id = seed.demo_id("client", "Rahul")

    response = api.get(f"/api/clients/{rahul_id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "name", "preferences"}
    assert body["id"] == str(rahul_id)
    assert body["name"] == "Rahul"
    assert [p["attribute"] for p in body["preferences"]] == [
        "age", "drinking", "location", "religion", "smoking", "wants_children"
    ]


def test_client_detail_preference_fields(
    session_factory: sessionmaker[Session], api: TestClient
) -> None:
    with session_factory() as session:
        seed.seed(session)
        session.commit()

    response = api.get(f"/api/clients/{seed.demo_id('client', 'Rahul')}")

    preferences = {p["attribute"]: p for p in response.json()["preferences"]}
    assert all(set(p) == {"attribute", "value", "preference_type"} for p in preferences.values())
    assert preferences["age"] == {
        "attribute": "age",
        "value": {"min": 26, "max": 32},
        "preference_type": "HARD",
    }
    assert preferences["smoking"] == {
        "attribute": "smoking",
        "value": False,
        "preference_type": "DEAL_BREAKER",
    }
    assert preferences["location"]["value"] == ["Delhi NCR", "Noida", "Gurgaon"]


def test_client_detail_without_preferences(
    session_factory: sessionmaker[Session], api: TestClient
) -> None:
    with session_factory() as session:
        client = Client(name="New Client")
        session.add(client)
        session.commit()

    response = api.get(f"/api/clients/{client.id}")

    assert response.status_code == 200
    assert response.json() == {"id": str(client.id), "name": "New Client", "preferences": []}


def test_client_detail_unknown_client_returns_404(
    session_factory: sessionmaker[Session], api: TestClient
) -> None:
    response = api.get(f"/api/clients/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Client not found"}


def test_client_detail_invalid_id_returns_422(
    session_factory: sessionmaker[Session], api: TestClient
) -> None:
    response = api.get("/api/clients/not-a-uuid")

    assert response.status_code == 422
