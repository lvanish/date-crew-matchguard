from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registers all models on Base.metadata)
from app.core.config import settings
from app.db.base import Base

# create_engine is lazy: no connection is opened until the first query.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


def init_db(bind: Engine = engine) -> None:
    Base.metadata.create_all(bind=bind)
    _add_match_conflict_kind(bind)


def _add_match_conflict_kind(bind: Engine) -> None:
    """Development-only upgrade (no migrations yet): add match_conflicts.kind if missing.

    create_all never alters existing tables. Existing rows are backfilled from their
    reason text, which MatchEngine generates with a fixed wording for each kind.
    """
    columns = {column["name"] for column in inspect(bind).get_columns("match_conflicts")}
    if "kind" in columns:
        return

    with bind.begin() as connection:
        connection.execute(text("ALTER TABLE match_conflicts ADD COLUMN kind VARCHAR(30)"))
        connection.execute(
            text(
                """
                UPDATE match_conflicts SET kind = CASE
                    WHEN reason LIKE 'Unsupported preference attribute%' THEN 'UNSUPPORTED_ATTRIBUTE'
                    WHEN reason LIKE '%unsupported value format%' THEN 'INVALID_PREFERENCE'
                    WHEN reason LIKE '%information is missing%' THEN 'MISSING_DATA'
                    ELSE 'VIOLATION'
                END
                """
            )
        )
        if bind.dialect.name == "postgresql":
            connection.execute(text("ALTER TABLE match_conflicts ALTER COLUMN kind SET NOT NULL"))


if __name__ == "__main__":
    init_db()
    print("Database tables are up to date.")
