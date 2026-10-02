from collections import Counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

import seed
from app.core.assessment import ASSESSMENT_BASELINE, AssessmentBaseline
from app.core.enums import ConflictKind, Decision, PreferenceType
from app.models import Client, MatchCheck, MatchConflict, Profile
from app.services.analytics import rate

ZERO_DECISIONS = {"pass": 0, "review": 0, "block": 0}


def summary(api: TestClient) -> dict:
    response = api.get("/api/analytics/summary")
    assert response.status_code == 200
    return response.json()


def run_all_scenarios(session_factory: sessionmaker[Session], api: TestClient) -> None:
    with session_factory() as session:
        seed.seed(session)
        session.commit()
    for client_name, profile_name, _, _ in seed.SCENARIOS:
        response = api.post(
            "/api/matches/check",
            json={
                "client_id": str(seed.demo_id("client", client_name)),
                "profile_id": str(seed.demo_id("profile", profile_name)),
            },
        )
        assert response.status_code == 200


def add_check(session: Session, decision: Decision, conflicts: list[tuple[ConflictKind, PreferenceType]]) -> None:
    client = Client(name="Client")
    profile = Profile(name="Profile")
    session.add_all([client, profile])
    session.flush()
    session.add(
        MatchCheck(
            client_id=client.id,
            profile_id=profile.id,
            decision=decision,
            conflicts=[
                MatchConflict(kind=kind, attribute="smoking", preference_type=preference_type, reason="r")
                for kind, preference_type in conflicts
            ],
        )
    )


def test_empty_database_returns_zeros(session_factory: sessionmaker[Session], api: TestClient) -> None:
    data = summary(api)

    assert data["total_checks"] == 0
    assert data["decisions"] == ZERO_DECISIONS
    assert data["decision_rates"] == {"pass": 0.0, "review": 0.0, "block": 0.0}
    assert data["conflicts"] == {
        "violations": 0,
        "deal_breaker_violations": 0,
        "missing_data": 0,
        "unsupported_attributes": 0,
        "invalid_preferences": 0,
    }


def test_rate_never_divides_by_zero() -> None:
    assert rate(0, 0) == 0.0
    assert rate(5, 0) == 0.0
    assert rate(1, 3) == 0.3333


def test_seeded_checks_produce_matching_aggregates(
    session_factory: sessionmaker[Session], api: TestClient
) -> None:
    run_all_scenarios(session_factory, api)
    results = [seed.evaluate_scenario(c, p) for c, p, _, _ in seed.SCENARIOS]
    decisions = Counter(r.decision for r in results)
    conflicts = [c for r in results for c in r.conflicts]

    data = summary(api)

    assert data["total_checks"] == len(seed.SCENARIOS)
    assert data["decisions"] == {
        "pass": decisions[Decision.PASS],
        "review": decisions[Decision.REVIEW],
        "block": decisions[Decision.BLOCK],
    }
    assert data["conflicts"]["violations"] == sum(c.kind == ConflictKind.VIOLATION for c in conflicts)
    assert data["conflicts"]["deal_breaker_violations"] == sum(
        c.kind == ConflictKind.VIOLATION and c.preference_type == PreferenceType.DEAL_BREAKER
        for c in conflicts
    )
    assert data["conflicts"]["missing_data"] == sum(c.kind == ConflictKind.MISSING_DATA for c in conflicts)
    # Every BLOCK comes from at least one deal-breaker violation.
    assert data["conflicts"]["deal_breaker_violations"] >= data["decisions"]["block"] > 0


def test_counts_come_from_the_database(session_factory: sessionmaker[Session], api: TestClient) -> None:
    run_all_scenarios(session_factory, api)

    with session_factory() as session:
        saved = session.scalar(select(func.count()).select_from(MatchCheck))

    assert summary(api)["total_checks"] == saved
    assert summary(api)["total_checks"] == saved  # reading does not create rows


def test_decision_rates_sum_to_one(session_factory: sessionmaker[Session], api: TestClient) -> None:
    run_all_scenarios(session_factory, api)

    data = summary(api)
    rates = data["decision_rates"]

    assert sum(rates.values()) == pytest.approx(1.0, abs=0.0002)
    for key, count in data["decisions"].items():
        assert rates[key] == round(count / data["total_checks"], 4)


def test_conflict_kind_counts(session_factory: sessionmaker[Session], api: TestClient) -> None:
    with session_factory() as session:
        add_check(
            session,
            Decision.BLOCK,
            [
                (ConflictKind.VIOLATION, PreferenceType.DEAL_BREAKER),
                (ConflictKind.VIOLATION, PreferenceType.HARD),
                (ConflictKind.VIOLATION, PreferenceType.SOFT),
            ],
        )
        add_check(
            session,
            Decision.REVIEW,
            [
                (ConflictKind.MISSING_DATA, PreferenceType.DEAL_BREAKER),
                (ConflictKind.MISSING_DATA, PreferenceType.SOFT),
                (ConflictKind.UNSUPPORTED_ATTRIBUTE, PreferenceType.HARD),
                (ConflictKind.INVALID_PREFERENCE, PreferenceType.SOFT),
            ],
        )
        add_check(session, Decision.PASS, [])
        session.commit()

    data = summary(api)

    assert data["total_checks"] == 3
    assert data["decisions"] == {"pass": 1, "review": 1, "block": 1}
    assert data["decision_rates"] == {"pass": 0.3333, "review": 0.3333, "block": 0.3333}
    assert data["conflicts"] == {
        "violations": 3,
        "deal_breaker_violations": 1,  # missing data on a deal-breaker is not a violation
        "missing_data": 2,
        "unsupported_attributes": 1,
        "invalid_preferences": 1,
    }


def test_assessment_baseline_estimate_is_about_242() -> None:
    estimate = ASSESSMENT_BASELINE.estimated_preference_violation_rejections

    assert estimate == pytest.approx(690 * 0.35)
    assert round(estimate) == 242
    assert AssessmentBaseline(rejected_profiles=0).estimated_preference_violation_rejections == 0


def test_summary_includes_assessment_baseline(session_factory: sessionmaker[Session], api: TestClient) -> None:
    baseline = summary(api)["assessment_baseline"]

    assert baseline["profiles_shared"] == 1000
    assert baseline["rejected_profiles"] == 690
    assert baseline["preference_violation_rejection_rate"] == 0.35
    assert baseline["estimated_preference_violation_rejections"] == 241.5


def test_summary_endpoint_is_read_only(api: TestClient) -> None:
    assert api.post("/api/analytics/summary").status_code == 405
