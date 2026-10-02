import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.client_preference import ClientPreference
    from app.models.match_check import MatchCheck
    from app.models.rejection_feedback import RejectionFeedback


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    preferences: Mapped[list["ClientPreference"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    match_checks: Mapped[list["MatchCheck"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    rejection_feedback: Mapped[list["RejectionFeedback"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
