from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

import seed
from app.core.enums import ConflictKind, Decision, PreferenceType
from app.models import Client, ClientPreference, MatchCheck, Profile


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_seed_creates_expected_records(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        counts = seed.seed(session)
        session.commit()

        assert counts == {"clients": 5, "profiles": 16, "preferences": 27}
        assert count(session, Client) == 5
        assert count(session, Profile) == 16
        assert count(session, ClientPreference) == 27
        assert set(session.scalars(select(Client.name))) == {
            "Rahul", "Priya", "Arjun", "Sneha", "Karan"
        }


def test_seed_is_repeatable_and_clears_attached_match_checks(
    session_factory: sessionmaker[Session], api: TestClient
) -> None:
    with session_factory() as session:
        seed.seed(session)
        session.commit()
        first_ids = set(session.scalars(select(Profile.id)))

    api.post(
        "/api/matches/check",
        json={
            "client_id": str(seed.demo_id("client", "Rahul")),
            "profile_id": str(seed.demo_id("profile", "Riya")),
        },
    )

    with session_factory() as session:
        assert count(session, MatchCheck) == 1
        seed.seed(session)
        session.commit()

        assert set(session.scalars(select(Profile.id))) == first_ids
        assert count(session, Client) == 5
        assert count(session, ClientPreference) == 27
        assert count(session, MatchCheck) == 0


def test_seed_keeps_non_demo_records(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        session.add(Client(name="Real client"))
        session.commit()

        seed.seed(session)
        session.commit()

        assert count(session, Client) == 6


def test_seed_covers_every_preference_attribute() -> None:
    attributes = {a for prefs in seed.CLIENT_PREFERENCES.values() for a, _, _ in prefs}

    assert attributes == {
        "age", "location", "smoking", "drinking", "wants_children",
        "religion", "education", "occupation",
    }


def test_scenarios_produce_documented_decisions() -> None:
    for client_name, profile_name, expected, note in seed.SCENARIOS:
        result = seed.evaluate_scenario(client_name, profile_name)
        assert result.decision == expected, f"{client_name} -> {profile_name} ({note})"

    assert {s[2] for s in seed.SCENARIOS} == {Decision.PASS, Decision.REVIEW, Decision.BLOCK}


def test_scenarios_cover_required_situations() -> None:
    results = [seed.evaluate_scenario(c, p) for c, p, _, _ in seed.SCENARIOS]
    conflicts = [conflict for r in results for conflict in r.conflicts]

    assert any(c.kind == ConflictKind.MISSING_DATA for c in conflicts)
    assert any(
        c.kind == ConflictKind.MISSING_DATA and c.preference_type == PreferenceType.DEAL_BREAKER
        for c in conflicts
    )
    assert any(
        c.kind == ConflictKind.VIOLATION and c.preference_type == PreferenceType.DEAL_BREAKER
        for c in conflicts
    )
    assert any(
        c.kind == ConflictKind.VIOLATION and c.preference_type == PreferenceType.SOFT
        for c in conflicts
    )
    assert any(len(r.conflicts) > 1 and r.decision == Decision.REVIEW for r in results)
    assert any(len(r.conflicts) > 1 and r.decision == Decision.BLOCK for r in results)


def test_scenarios_through_api_match_seed_definitions(
    session_factory: sessionmaker[Session], api: TestClient
) -> None:
    with session_factory() as session:
        seed.seed(session)
        session.commit()

    for client_name, profile_name, expected, _ in seed.SCENARIOS:
        response = api.post(
            "/api/matches/check",
            json={
                "client_id": str(seed.demo_id("client", client_name)),
                "profile_id": str(seed.demo_id("profile", profile_name)),
            },
        )
        assert response.status_code == 200
        assert response.json()["decision"] == expected.value, f"{client_name} -> {profile_name}"
