from dataclasses import dataclass


@dataclass(frozen=True)
class AssessmentBaseline:
    """Monthly figures supplied by The Date Crew assessment brief.

    These are NOT measured by MatchGuard. They describe the business before the tool
    existed and are only used to frame the problem and the success metric.
    """

    profiles_shared: int = 1000
    profiles_accepted: int = 310
    contact_details_shared: int = 210
    conversations_started: int = 150
    meetings_fixed: int = 75
    meetings_completed: int = 42
    rejected_profiles: int = 690
    preference_violation_rejection_rate: float = 0.35
    matchmaker_a_acceptance_rate: float = 0.44
    matchmaker_b_acceptance_rate: float = 0.21
    search_hours_per_client_per_week: int = 2

    @property
    def estimated_preference_violation_rejections(self) -> float:
        """Rejections the brief attributes to preference violations (a derived estimate)."""
        # Rounded to one decimal so float error (241.4999...) can't flip the displayed ~242.
        return round(self.rejected_profiles * self.preference_violation_rejection_rate, 1)


ASSESSMENT_BASELINE = AssessmentBaseline()
