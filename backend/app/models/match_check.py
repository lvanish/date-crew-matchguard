import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Decision

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.match_conflict import MatchConflict
    from app.models.profile import Profile


class MatchCheck(Base):
    __tablename__ = "match_checks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[Decision] = mapped_column(
        Enum(Decision, native_enum=False, length=20, validate_strings=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="match_checks")
    profile: Mapped["Profile"] = relationship(back_populates="match_checks")
    conflicts: Mapped[list["MatchConflict"]] = relationship(
        back_populates="match_check", cascade="all, delete-orphan"
    )
