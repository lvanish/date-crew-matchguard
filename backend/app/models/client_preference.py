import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType, PreferenceType

if TYPE_CHECKING:
    from app.models.client import Client


class ClientPreference(Base):
    __tablename__ = "client_preferences"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    attribute: Mapped[str] = mapped_column(String(50))
    # Shape depends on the attribute: a range dict, bool, string, or list of strings.
    value: Mapped[Any] = mapped_column(JSONType)
    preference_type: Mapped[PreferenceType] = mapped_column(
        Enum(PreferenceType, native_enum=False, length=20, validate_strings=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="preferences")
