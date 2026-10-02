import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.match_check import MatchCheck
    from app.models.rejection_feedback import RejectionFeedback


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    age: Mapped[int | None]
    location: Mapped[str | None] = mapped_column(String(100))
    smoking: Mapped[bool | None]
    drinking: Mapped[bool | None]
    wants_children: Mapped[bool | None]
    religion: Mapped[str | None] = mapped_column(String(50))
    education: Mapped[str | None] = mapped_column(String(100))
    occupation: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match_checks: Mapped[list["MatchCheck"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    rejection_feedback: Mapped[list["RejectionFeedback"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
