import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, ConflictKind, JSONType, PreferenceType

if TYPE_CHECKING:
    from app.models.match_check import MatchCheck


class MatchConflict(Base):
    __tablename__ = "match_conflicts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    match_check_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("match_checks.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ConflictKind] = mapped_column(
        Enum(ConflictKind, native_enum=False, length=30, validate_strings=True)
    )
    attribute: Mapped[str] = mapped_column(String(50))
    candidate_value: Mapped[Any | None] = mapped_column(JSONType)
    expected_value: Mapped[Any | None] = mapped_column(JSONType)
    preference_type: Mapped[PreferenceType] = mapped_column(
        Enum(PreferenceType, native_enum=False, length=20, validate_strings=True)
    )
    reason: Mapped[str] = mapped_column(Text)

    match_check: Mapped["MatchCheck"] = relationship(back_populates="conflicts")
