from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue

from app.core.enums import PreferenceType


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class PreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attribute: str
    value: JsonValue
    preference_type: PreferenceType


class ClientDetail(ClientRead):
    preferences: list[PreferenceRead]


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    age: int | None
    location: str | None
    smoking: bool | None
    drinking: bool | None
    wants_children: bool | None
    religion: str | None
    education: str | None
    occupation: str | None
