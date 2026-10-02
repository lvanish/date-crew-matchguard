import enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

# StructuredFeedback is the structured-output schema for Gemini and OpenAI. OpenAI's strict
# mode is the tightest, so keep it to features Structured Outputs supports: every field
# required, no defaults, no length constraints.


class FeedbackAttribute(str, enum.Enum):
    AGE = "age"
    LOCATION = "location"
    SMOKING = "smoking"
    DRINKING = "drinking"
    WANTS_CHILDREN = "wants_children"
    RELIGION = "religion"
    EDUCATION = "education"
    OCCUPATION = "occupation"
    OTHER = "other"


class FeedbackPreferenceType(str, enum.Enum):
    DEAL_BREAKER = "DEAL_BREAKER"
    HARD = "HARD"
    SOFT = "SOFT"
    UNCLEAR = "UNCLEAR"


class FeedbackKind(str, enum.Enum):
    VIOLATION = "VIOLATION"
    PREFERENCE = "PREFERENCE"
    UNCLEAR = "UNCLEAR"


class AgeRange(BaseModel):
    min: int | None = Field(description="Youngest acceptable age, or null if not stated.")
    max: int | None = Field(description="Oldest acceptable age, or null if not stated.")


class FeedbackReason(BaseModel):
    attribute: FeedbackAttribute = Field(
        description="The profile attribute the reason is about; 'other' if none fits."
    )
    value: bool | int | str | list[str] | AgeRange | None = Field(
        description=(
            "The attribute value the client objects to, as stated in the feedback: true for "
            "smoking/drinking when the client rejects smokers/drinkers, a place name for "
            "location, an age or age range for age. Null when the feedback does not say."
        )
    )
    preference_type: FeedbackPreferenceType = Field(
        description="How strongly the client holds this preference, judged only from the wording."
    )
    kind: FeedbackKind = Field(
        description=(
            "VIOLATION: the candidate breaks a clearly stated requirement. PREFERENCE: a softer "
            "stated preference. UNCLEAR: the statement is ambiguous."
        )
    )
    explanation: str = Field(
        description="One neutral sentence citing what in the feedback supports this reason."
    )


class StructuredFeedback(BaseModel):
    reasons: list[FeedbackReason] = Field(
        description="Every distinct rejection reason in the feedback, in the order mentioned."
    )
    needs_review: bool = Field(
        description="True if any reason is ambiguous or the feedback could not be mapped."
    )

    @model_validator(mode="after")
    def _flag_uncertainty(self) -> "StructuredFeedback":
        # Never let an extractor hide uncertainty: anything unclear, unmapped or empty
        # must go to a matchmaker regardless of what needs_review was returned as.
        if not self.reasons or any(
            reason.kind == FeedbackKind.UNCLEAR
            or reason.preference_type == FeedbackPreferenceType.UNCLEAR
            or reason.attribute == FeedbackAttribute.OTHER
            for reason in self.reasons
        ):
            self.needs_review = True
        return self


MAX_FEEDBACK_LENGTH = 5000


class FeedbackAnalyzeRequest(BaseModel):
    client_id: UUID
    profile_id: UUID
    raw_feedback: str = Field(max_length=MAX_FEEDBACK_LENGTH)

    @field_validator("raw_feedback")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("raw_feedback must not be empty")
        return value


class FeedbackAnalysis(BaseModel):
    id: UUID
    client_id: UUID
    profile_id: UUID
    raw_feedback: str
    structured_feedback: StructuredFeedback
