from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue

from app.core.enums import ConflictKind, Decision, PreferenceType


class CandidateProfileInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    age: int | None = None
    location: str | None = None
    smoking: bool | None = None
    drinking: bool | None = None
    wants_children: bool | None = None
    religion: str | None = None
    education: str | None = None
    occupation: str | None = None


class ClientPreferenceInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attribute: str
    value: JsonValue
    preference_type: PreferenceType


class ConflictResult(BaseModel):
    kind: ConflictKind
    attribute: str
    candidate_value: JsonValue = None
    expected_value: JsonValue = None
    preference_type: PreferenceType
    reason: str


class MatchResult(BaseModel):
    decision: Decision
    conflicts: list[ConflictResult]


class MatchCheckRequest(BaseModel):
    client_id: UUID
    profile_id: UUID
