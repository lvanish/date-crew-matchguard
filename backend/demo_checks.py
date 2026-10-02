"""Persist real MatchEngine checks for the demo scenarios defined in seed.py.

Run from the backend/ directory, after seed.py:

    python demo_checks.py

Each scenario check has a fixed ID, so re-running replaces only those checks (and their
conflicts). Clients, profiles, preferences, rejection feedback and any other match checks
are left alone. These are deterministic demo scenarios, not business results.
"""

import sys
import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Decision
from app.db.database import SessionLocal, init_db
from app.models import Client, ClientPreference, MatchCheck, MatchConflict, Profile
from app.schemas.matching import CandidateProfileInput, ClientPreferenceInput
from app.services.match_engine import MatchEngine
from seed import SCENARIOS, demo_id


class MissingDemoDataError(RuntimeError):
    pass


def demo_check_id(client_name: str, profile_name: str) -> uuid.UUID:
    return demo_id("check", f"{client_name}:{profile_name}")


def clear_demo_checks(session: Session) -> None:
    ids = [demo_check_id(client, profile) for client, profile, _, _ in SCENARIOS]
    # ORM deletes so the relationship cascade also removes conflicts on SQLite.
    for check in session.scalars(select(MatchCheck).where(MatchCheck.id.in_(ids))):
        session.delete(check)
    session.flush()


def create_demo_checks(session: Session) -> list[MatchCheck]:
    """Replace the demo scenario checks in one transaction. The caller commits."""
    clear_demo_checks(session)
    engine = MatchEngine()
    checks = []

    for client_name, profile_name, _, _ in SCENARIOS:
        client = session.get(Client, demo_id("client", client_name))
        profile = session.get(Profile, demo_id("profile", profile_name))
        if client is None or profile is None:
            raise MissingDemoDataError(
                f"Demo client {client_name!r} or profile {profile_name!r} not found. "
                "Run `python seed.py` first."
            )

        preference_rows = session.scalars(
            select(ClientPreference)
            .where(ClientPreference.client_id == client.id)
            .order_by(ClientPreference.created_at, ClientPreference.attribute)
        ).all()
        result = engine.check(
            preferences=[ClientPreferenceInput.model_validate(row) for row in preference_rows],
            candidate=CandidateProfileInput.model_validate(profile),
        )

        check = MatchCheck(
            id=demo_check_id(client_name, profile_name),
            client=client,
            profile=profile,
            decision=result.decision,
            conflicts=[MatchConflict(**conflict.model_dump()) for conflict in result.conflicts],
        )
        session.add(check)
        checks.append(check)

    session.flush()
    return checks


def main() -> None:
    init_db()
    with SessionLocal() as session:
        try:
            checks = create_demo_checks(session)
        except MissingDemoDataError as error:
            sys.exit(str(error))
        session.commit()

        decisions = Counter(check.decision for check in checks)
        mismatches = [
            f"  {client} -> {profile}: got {check.decision.value}, seed.py expects {expected.value}"
            for (client, profile, expected, _), check in zip(SCENARIOS, checks, strict=True)
            if check.decision != expected
        ]

        print("Demo checks created")
        print("-------------------")
        print(f"Total: {len(checks)}")
        for decision in Decision:
            print(f"{decision.value}: {decisions[decision]}")
        print(f"Conflicts: {sum(len(check.conflicts) for check in checks)}")
        print()
        print("Deterministic demo scenarios, not business results.")
        if mismatches:
            print("Warning: some decisions differ from the expectations in seed.py:")
            print("\n".join(mismatches))


if __name__ == "__main__":
    main()
