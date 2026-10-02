from pydantic import BaseModel, ConfigDict, Field


class DecisionCounts(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pass_: int = Field(alias="pass")
    review: int
    block: int


class DecisionRates(BaseModel):
    """Share of all checks with each decision, from 0 to 1 (4 decimals)."""

    model_config = ConfigDict(populate_by_name=True)

    pass_: float = Field(alias="pass")
    review: float
    block: float


class ConflictCounts(BaseModel):
    violations: int = Field(description="Conflicts of kind VIOLATION, any preference type.")
    deal_breaker_violations: int = Field(description="VIOLATION conflicts on a DEAL_BREAKER.")
    missing_data: int
    unsupported_attributes: int
    invalid_preferences: int


class AssessmentBaselineRead(BaseModel):
    """Figures supplied by the assessment brief, per month. Not measured by MatchGuard."""

    model_config = ConfigDict(from_attributes=True)

    profiles_shared: int
    profiles_accepted: int
    contact_details_shared: int
    conversations_started: int
    meetings_fixed: int
    meetings_completed: int
    rejected_profiles: int
    preference_violation_rejection_rate: float
    matchmaker_a_acceptance_rate: float
    matchmaker_b_acceptance_rate: float
    search_hours_per_client_per_week: int
    estimated_preference_violation_rejections: float = Field(
        description="rejected_profiles × preference_violation_rejection_rate. A derived "
        "estimate of avoidable rejections, not an observed MatchGuard result."
    )


class AnalyticsSummary(BaseModel):
    total_checks: int = Field(description="Match checks saved in the database.")
    decisions: DecisionCounts
    decision_rates: DecisionRates
    conflicts: ConflictCounts
    assessment_baseline: AssessmentBaselineRead
