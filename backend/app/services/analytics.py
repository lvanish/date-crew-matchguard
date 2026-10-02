"""Read-only aggregates over saved match checks. Never produces or changes a decision."""

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.assessment import ASSESSMENT_BASELINE
from app.core.enums import ConflictKind, Decision, PreferenceType
from app.models import MatchCheck, MatchConflict
from app.schemas.analytics import (
    AnalyticsSummary,
    AssessmentBaselineRead,
    ConflictCounts,
    DecisionCounts,
    DecisionRates,
)


def rate(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def get_analytics_summary(db: Session) -> AnalyticsSummary:
    decisions: Counter[Decision] = Counter(
        dict(db.execute(select(MatchCheck.decision, func.count()).group_by(MatchCheck.decision)).all())
    )
    total = sum(decisions.values())

    conflicts: Counter[tuple[ConflictKind, PreferenceType]] = Counter()
    rows = db.execute(
        select(MatchConflict.kind, MatchConflict.preference_type, func.count()).group_by(
            MatchConflict.kind, MatchConflict.preference_type
        )
    )
    for kind, preference_type, count in rows:
        conflicts[(kind, preference_type)] = count

    def kind_total(kind: ConflictKind) -> int:
        return sum(count for (k, _), count in conflicts.items() if k == kind)

    return AnalyticsSummary(
        total_checks=total,
        decisions=DecisionCounts(
            pass_=decisions[Decision.PASS],
            review=decisions[Decision.REVIEW],
            block=decisions[Decision.BLOCK],
        ),
        decision_rates=DecisionRates(
            pass_=rate(decisions[Decision.PASS], total),
            review=rate(decisions[Decision.REVIEW], total),
            block=rate(decisions[Decision.BLOCK], total),
        ),
        conflicts=ConflictCounts(
            violations=kind_total(ConflictKind.VIOLATION),
            deal_breaker_violations=conflicts[(ConflictKind.VIOLATION, PreferenceType.DEAL_BREAKER)],
            missing_data=kind_total(ConflictKind.MISSING_DATA),
            unsupported_attributes=kind_total(ConflictKind.UNSUPPORTED_ATTRIBUTE),
            invalid_preferences=kind_total(ConflictKind.INVALID_PREFERENCE),
        ),
        assessment_baseline=AssessmentBaselineRead.model_validate(ASSESSMENT_BASELINE),
    )
