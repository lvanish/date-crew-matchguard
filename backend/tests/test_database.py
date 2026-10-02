from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app.db.base import ConflictKind
from app.db.database import init_db
from app.models import MatchConflict

# match_conflicts as it was created before the kind column existed.
OLD_MATCH_CONFLICTS = """
CREATE TABLE match_conflicts (
    id CHAR(32) NOT NULL PRIMARY KEY,
    match_check_id CHAR(32) NOT NULL,
    attribute VARCHAR(50) NOT NULL,
    candidate_value JSON,
    expected_value JSON,
    preference_type VARCHAR(20) NOT NULL,
    reason TEXT NOT NULL
)
"""

OLD_ROWS = [
    ("smoking", "Candidate smokes, while smoking is marked as a client deal-breaker.", "VIOLATION"),
    ("drinking", "Candidate drinking information is missing, so the preference cannot be verified.", "MISSING_DATA"),
    ("age", 'Client age preference has an unsupported value format: 30, so it cannot be checked.', "INVALID_PREFERENCE"),
    ("height", "Unsupported preference attribute: height", "UNSUPPORTED_ATTRIBUTE"),
]


def test_init_db_adds_and_backfills_kind_on_existing_table() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text(OLD_MATCH_CONFLICTS))
        for index, (attribute, reason, _) in enumerate(OLD_ROWS):
            connection.execute(
                text(
                    "INSERT INTO match_conflicts "
                    "(id, match_check_id, attribute, preference_type, reason) "
                    "VALUES (:id, :check_id, :attribute, 'DEAL_BREAKER', :reason)"
                ),
                {"id": f"{index:032x}", "check_id": "0" * 32, "attribute": attribute, "reason": reason},
            )

    init_db(engine)

    assert "kind" in {c["name"] for c in inspect(engine).get_columns("match_conflicts")}
    with Session(engine) as session:
        kinds = {row.attribute: row.kind for row in session.scalars(select(MatchConflict))}
    assert kinds == {attribute: ConflictKind(kind) for attribute, _, kind in OLD_ROWS}
    engine.dispose()


def test_init_db_is_idempotent() -> None:
    engine = create_engine("sqlite://")

    init_db(engine)
    init_db(engine)

    assert "kind" in {c["name"] for c in inspect(engine).get_columns("match_conflicts")}
    engine.dispose()
