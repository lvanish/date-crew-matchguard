from collections import Counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

import demo_checks
import seed
from app.core.enums import Decision
from app.models import (
    Client,
    ClientPreference,
    MatchCheck,
    MatchConflict,
    Profile,
    RejectionFeedback,
)

EXPECTED_IDS = {demo_checks.demo_check_id(c, p) for c, p, _, _ in seed.SCENARIOS}


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model))


def run(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        demo_checks.create_demo_checks(session)
        session.commit()


@pytest.fixture
def seeded(session_factory: sessionmaker[Session]) -> sessionmaker[Session]:
    with session_factory() as session:
        seed.seed(session)
        session.commit()
    return session_factory


def test_creates_one_check_per_scenario(seeded: sessionmaker[Session]) -> None:
    run(seeded)

    with seeded() as session:
        assert len(seed.SCENARIOS) == 19
        assert count(session, MatchCheck) == 19
        assert set(session.scalars(select(MatchCheck.id))) == EXPECTED_IDS


def test_decisions_and_conflicts_match_the_engine(seeded: sessionmaker[Session]) -> None:
    run(seeded)

    with seeded() as session:
        for client_name, profile_name, _, _ in seed.SCENARIOS:
            expected = seed.evaluate_scenario(client_name, profile_name)
            check = session.get(MatchCheck, demo_checks.demo_check_id(client_name, profile_name))

            assert check.client_id == seed.demo_id("client", client_name)
            assert check.profile_id == seed.demo_id("profile", profile_name)
            assert check.decision == expected.decision, f"{client_name} -> {profile_name}"
            assert sorted(
                (c.attribute, c.kind, c.preference_type, c.reason) for c in check.conflicts
            ) == sorted(
                (c.attribute, c.kind, c.preference_type, c.reason) for c in expected.conflicts
            ), f"{client_name} -> {profile_name}"


def test_rerunning_does_not_duplicate(seeded: sessionmaker[Session]) -> None:
    run(seeded)
    with seeded() as session:
        conflicts = count(session, MatchConflict)

    run(seeded)

    with seeded() as session:
        assert count(session, MatchCheck) == 19
        assert set(session.scalars(select(MatchCheck.id))) == EXPECTED_IDS
        assert count(session, MatchConflict) == conflicts


def test_keeps_directory_data_and_feedback(seeded: sessionmaker[Session]) -> None:
    with seeded() as session:
        session.add(
            RejectionFeedback(
                client_id=seed.demo_id("client", "Rahul"),
                profile_id=seed.demo_id("profile", "Ishita"),
                raw_feedback="I don't want a smoker.",
            )
        )
        session.commit()

    run(seeded)
    run(seeded)

    with seeded() as session:
        assert count(session, Client) == 5
        assert count(session, Profile) == 16
        assert count(session, ClientPreference) == 27
        assert count(session, RejectionFeedback) == 1


def test_leaves_unrelated_match_checks_alone(seeded: sessionmaker[Session], api: TestClient) -> None:
    # A manual check on one of the demo pairs, and one on a non-demo client.
    api.post(
        "/api/matches/check",
        json={
            "client_id": str(seed.demo_id("client", "Rahul")),
            "profile_id": str(seed.demo_id("profile", "Ishita")),
        },
    )
    with seeded() as session:
        other = Client(name="Real client")
        session.add(other)
        session.flush()
        session.add(
            MatchCheck(
                client_id=other.id,
                profile_id=seed.demo_id("profile", "Ananya"),
                decision=Decision.PASS,
            )
        )
        session.commit()
        manual_ids = set(session.scalars(select(MatchCheck.id)))

    run(seeded)
    run(seeded)

    with seeded() as session:
        ids = set(session.scalars(select(MatchCheck.id)))
        assert manual_ids <= ids
        assert ids == manual_ids | EXPECTED_IDS
        assert count(session, MatchCheck) == 21


def test_requires_seed_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        with pytest.raises(demo_checks.MissingDemoDataError, match="seed.py"):
            demo_checks.create_demo_checks(session)
        session.rollback()
        assert count(session, MatchCheck) == 0


def test_analytics_reflect_demo_checks(seeded: sessionmaker[Session], api: TestClient) -> None:
    run(seeded)
    results = [seed.evaluate_scenario(c, p) for c, p, _, _ in seed.SCENARIOS]
    decisions = Counter(r.decision for r in results)
    conflicts = [c for r in results for c in r.conflicts]

    data = api.get("/api/analytics/summary").json()

    assert data["total_checks"] == 19
    assert data["decisions"] == {
        "pass": decisions[Decision.PASS],
        "review": decisions[Decision.REVIEW],
        "block": decisions[Decision.BLOCK],
    }
    assert sum(data["conflicts"].values()) - data["conflicts"]["deal_breaker_violations"] == len(conflicts)
