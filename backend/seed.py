"""Load deterministic demo data for MatchGuard.

Run from the backend/ directory:

    python seed.py

Safe to re-run: demo records have fixed IDs, and only those records (plus the match
checks and feedback attached to them) are deleted before the data is recreated.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Decision, PreferenceType
from app.db.database import SessionLocal, init_db
from app.models import Client, ClientPreference, Profile
from app.schemas.matching import CandidateProfileInput, ClientPreferenceInput, MatchResult
from app.services.match_engine import MatchEngine

DEAL_BREAKER = PreferenceType.DEAL_BREAKER
HARD = PreferenceType.HARD
SOFT = PreferenceType.SOFT

DEMO_NAMESPACE = uuid.UUID("6f1c2b8e-3d4a-4b5c-9e7f-0a1b2c3d4e5f")


def demo_id(kind: str, name: str) -> uuid.UUID:
    return uuid.uuid5(DEMO_NAMESPACE, f"{kind}:{name}")


CLIENT_PREFERENCES: dict[str, list[tuple[str, Any, PreferenceType]]] = {
    "Rahul": [
        ("age", {"min": 26, "max": 32}, HARD),
        ("location", ["Delhi NCR", "Noida", "Gurgaon"], HARD),
        ("smoking", False, DEAL_BREAKER),
        ("drinking", False, SOFT),
        ("wants_children", True, DEAL_BREAKER),
        ("religion", "Hindu", SOFT),
    ],
    "Priya": [
        ("age", {"min": 28, "max": 36}, HARD),
        ("location", ["Mumbai", "Pune"], HARD),
        ("smoking", False, DEAL_BREAKER),
        ("drinking", False, SOFT),
        ("education", ["MBA", "M.Tech", "MBBS", "LLB"], HARD),
        ("occupation", ["Doctor", "Engineer", "Lawyer"], SOFT),
    ],
    "Arjun": [
        ("age", {"min": 25, "max": 31}, SOFT),
        ("location", "Bangalore", HARD),
        ("religion", "Hindu", DEAL_BREAKER),
        ("wants_children", True, HARD),
        ("education", ["B.Tech", "M.Tech", "MBA"], SOFT),
    ],
    "Sneha": [
        ("age", {"min": 30, "max": 38}, HARD),
        ("location", ["Delhi NCR", "Gurgaon"], SOFT),
        ("smoking", False, DEAL_BREAKER),
        ("drinking", False, DEAL_BREAKER),
        ("religion", ["Hindu", "Sikh"], HARD),
    ],
    "Karan": [
        ("age", {"min": 24, "max": 30}, HARD),
        ("location", ["Hyderabad", "Bangalore", "Chennai"], SOFT),
        ("smoking", False, HARD),
        ("wants_children", False, DEAL_BREAKER),
        ("occupation", ["Doctor", "Engineer", "Designer"], SOFT),
    ],
}

PROFILE_FIELDS = (
    "age", "location", "smoking", "drinking", "wants_children", "religion", "education", "occupation"
)

# name, then PROFILE_FIELDS in order. None means the candidate did not share it.
PROFILES: list[tuple[Any, ...]] = [
    ("Ananya", 28, "Noida", False, False, True, "Hindu", "MBA", "Product Manager"),
    ("Meera", 30, "Gurgaon", False, True, True, "Hindu", "B.Tech", "Engineer"),
    ("Kavya", 27, "Delhi NCR", None, False, True, "Hindu", "MBBS", "Doctor"),
    ("Ishita", 29, "Delhi NCR", True, False, True, "Hindu", "B.Com", "Chartered Accountant"),
    ("Riya", 35, "Mumbai", True, True, False, "Christian", "BA", "Journalist"),
    ("Divya", 27, "Bangalore", False, False, True, "Hindu", "M.Tech", "Engineer"),
    ("Neha", 29, "Pune", False, None, True, "Hindu", "B.Tech", "Designer"),
    ("Sana", 26, "Hyderabad", False, True, False, "Muslim", "MBBS", "Doctor"),
    ("Tanvi", 32, "Kolkata", False, False, False, "Hindu", "MA", "Teacher"),
    ("Aditya", 31, "Mumbai", False, False, True, "Hindu", "MBA", "Lawyer"),
    ("Rohan", 33, "Pune", False, True, True, "Hindu", "M.Tech", "Engineer"),
    ("Vikram", 34, "Mumbai", True, False, True, "Jain", "MBBS", "Doctor"),
    ("Nikhil", 29, "Mumbai", False, False, True, "Hindu", None, None),
    ("Harpreet", 35, "Gurgaon", False, False, True, "Sikh", "MBA", "Banker"),
    ("Siddharth", 37, "Bangalore", False, None, True, "Hindu", "B.Tech", "Entrepreneur"),
    ("Amit", 40, "Delhi NCR", True, True, True, "Christian", "B.Com", "Sales Manager"),
]

# Intended demo pairings: (client, profile, expected decision, what it demonstrates).
SCENARIOS: list[tuple[str, str, Decision, str]] = [
    ("Rahul", "Ananya", Decision.PASS, "every preference satisfied"),
    ("Rahul", "Meera", Decision.REVIEW, "soft preference conflict (drinks)"),
    ("Rahul", "Kavya", Decision.REVIEW, "missing smoking data on a deal-breaker"),
    ("Rahul", "Ishita", Decision.BLOCK, "smoking deal-breaker"),
    ("Rahul", "Riya", Decision.BLOCK, "six conflicts, two deal-breakers"),
    ("Priya", "Aditya", Decision.PASS, "every preference satisfied"),
    ("Priya", "Rohan", Decision.REVIEW, "soft preference conflict (drinks)"),
    ("Priya", "Nikhil", Decision.REVIEW, "missing education and occupation"),
    ("Priya", "Vikram", Decision.BLOCK, "smoking deal-breaker"),
    ("Arjun", "Divya", Decision.PASS, "every preference satisfied"),
    ("Arjun", "Neha", Decision.REVIEW, "hard preference conflict (location)"),
    ("Arjun", "Sana", Decision.BLOCK, "religion deal-breaker plus three other conflicts"),
    ("Sneha", "Harpreet", Decision.PASS, "list match on location and religion"),
    ("Sneha", "Siddharth", Decision.REVIEW, "missing drinking data plus soft location conflict"),
    ("Sneha", "Rohan", Decision.BLOCK, "drinking deal-breaker"),
    ("Sneha", "Amit", Decision.BLOCK, "four conflicts, two deal-breakers"),
    ("Karan", "Sana", Decision.PASS, "every preference satisfied"),
    ("Karan", "Tanvi", Decision.REVIEW, "hard age conflict plus two soft conflicts"),
    ("Karan", "Divya", Decision.BLOCK, "children deal-breaker"),
]


def profile_data(row: tuple[Any, ...]) -> dict[str, Any]:
    name, *values = row
    return {"name": name, **dict(zip(PROFILE_FIELDS, values, strict=True))}


def clear_demo_data(session: Session) -> None:
    client_ids = [demo_id("client", name) for name in CLIENT_PREFERENCES]
    profile_ids = [demo_id("profile", row[0]) for row in PROFILES]

    # ORM deletes so relationship cascades also remove preferences, match checks,
    # conflicts and feedback, regardless of database-level foreign key support.
    for client in session.scalars(select(Client).where(Client.id.in_(client_ids))):
        session.delete(client)
    for profile in session.scalars(select(Profile).where(Profile.id.in_(profile_ids))):
        session.delete(profile)
    session.flush()


def seed(session: Session) -> dict[str, int]:
    """Replace the demo records in one transaction. The caller commits."""
    clear_demo_data(session)

    for client_name, preferences in CLIENT_PREFERENCES.items():
        session.add(
            Client(
                id=demo_id("client", client_name),
                name=client_name,
                preferences=[
                    ClientPreference(
                        id=demo_id("preference", f"{client_name}:{attribute}"),
                        attribute=attribute,
                        value=value,
                        preference_type=preference_type,
                    )
                    for attribute, value, preference_type in preferences
                ],
            )
        )

    for row in PROFILES:
        data = profile_data(row)
        session.add(Profile(id=demo_id("profile", data["name"]), **data))

    session.flush()
    return {
        "clients": len(CLIENT_PREFERENCES),
        "profiles": len(PROFILES),
        "preferences": sum(len(p) for p in CLIENT_PREFERENCES.values()),
    }


def evaluate_scenario(client_name: str, profile_name: str) -> MatchResult:
    """Run the engine on the seed definitions directly, without the database."""
    preferences = [
        ClientPreferenceInput(attribute=a, value=v, preference_type=t)
        for a, v, t in CLIENT_PREFERENCES[client_name]
    ]
    row = next(r for r in PROFILES if r[0] == profile_name)
    candidate = CandidateProfileInput(**profile_data(row))
    return MatchEngine().check(preferences, candidate)


def main() -> None:
    init_db()
    with SessionLocal() as session:
        counts = seed(session)
        session.commit()

    print("Seed complete")
    print(f"Clients: {counts['clients']}")
    print(f"Profiles: {counts['profiles']}")
    print(f"Preferences: {counts['preferences']}")
    print()
    print("Demo scenarios (client -> profile: decision, what it shows):")
    for client_name, profile_name, expected, note in SCENARIOS:
        actual = evaluate_scenario(client_name, profile_name).decision
        flag = "" if actual == expected else f"  [expected {expected.value}]"
        print(f"  {client_name} -> {profile_name}: {actual.value}, {note}{flag}")


if __name__ == "__main__":
    main()
