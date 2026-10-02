from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base, ConflictKind, Decision, PreferenceType
from app.models import (
    Client,
    ClientPreference,
    MatchCheck,
    MatchConflict,
    Profile,
    RejectionFeedback,
)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_all_models_are_importable() -> None:
    models = [Client, ClientPreference, Profile, MatchCheck, MatchConflict, RejectionFeedback]

    assert all(issubclass(model, Base) for model in models)


def test_metadata_contains_all_tables() -> None:
    assert set(Base.metadata.tables) == {
        "clients",
        "client_preferences",
        "profiles",
        "match_checks",
        "match_conflicts",
        "rejection_feedback",
    }


def test_client_has_preferences(session: Session) -> None:
    client = Client(name="Aisha")
    client.preferences = [
        ClientPreference(
            attribute="age",
            value={"min": 28, "max": 35},
            preference_type=PreferenceType.HARD,
        ),
        ClientPreference(
            attribute="smoking",
            value=False,
            preference_type=PreferenceType.DEAL_BREAKER,
        ),
        ClientPreference(
            attribute="location",
            value=["Delhi NCR", "Noida", "Gurgaon"],
            preference_type=PreferenceType.SOFT,
        ),
    ]
    session.add(client)
    session.commit()
    session.expire_all()

    saved = session.get(Client, client.id)

    assert saved is not None
    assert saved.created_at is not None
    values = {pref.attribute: pref.value for pref in saved.preferences}
    assert values == {
        "age": {"min": 28, "max": 35},
        "smoking": False,
        "location": ["Delhi NCR", "Noida", "Gurgaon"],
    }
    assert all(pref.client_id == client.id for pref in saved.preferences)


def test_match_check_has_conflicts(session: Session) -> None:
    client = Client(name="Aisha")
    profile = Profile(name="Rahul", age=40, smoking=True)
    check = MatchCheck(client=client, profile=profile, decision=Decision.BLOCK)
    check.conflicts = [
        MatchConflict(
            kind=ConflictKind.VIOLATION,
            attribute="smoking",
            candidate_value=True,
            expected_value=False,
            preference_type=PreferenceType.DEAL_BREAKER,
            reason="Candidate smokes; client does not accept smokers.",
        ),
        MatchConflict(
            kind=ConflictKind.MISSING_DATA,
            attribute="religion",
            candidate_value=None,
            expected_value="Hindu",
            preference_type=PreferenceType.SOFT,
            reason="Candidate religion is unknown.",
        ),
    ]
    session.add(check)
    session.commit()
    session.expire_all()

    saved = session.get(MatchCheck, check.id)

    assert saved is not None
    assert saved.decision == Decision.BLOCK
    assert saved.client.name == "Aisha"
    assert saved.profile.name == "Rahul"
    assert {c.attribute for c in saved.conflicts} == {"smoking", "religion"}
    unknown = next(c for c in saved.conflicts if c.attribute == "religion")
    assert unknown.candidate_value is None
    assert unknown.kind == ConflictKind.MISSING_DATA
