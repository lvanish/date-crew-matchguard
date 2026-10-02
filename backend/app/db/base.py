from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase

from app.core.enums import ConflictKind, Decision, PreferenceType

__all__ = ["Base", "ConflictKind", "Decision", "JSONType", "PreferenceType"]

# JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite in tests).
# none_as_null stores Python None as SQL NULL rather than the JSON literal 'null'.
JSONType = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


class Base(DeclarativeBase):
    pass
