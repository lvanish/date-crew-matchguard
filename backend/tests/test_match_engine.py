from typing import Any

import pytest

from app.core.enums import ConflictKind, Decision, PreferenceType
from app.schemas.matching import CandidateProfileInput, ClientPreferenceInput, ConflictResult
from app.services.match_engine import MatchEngine

DEAL_BREAKER = PreferenceType.DEAL_BREAKER
HARD = PreferenceType.HARD
SOFT = PreferenceType.SOFT

VIOLATION = ConflictKind.VIOLATION
MISSING_DATA = ConflictKind.MISSING_DATA


def pref(attribute: str, value: Any, preference_type: PreferenceType) -> ClientPreferenceInput:
    return ClientPreferenceInput(attribute=attribute, value=value, preference_type=preference_type)


@pytest.fixture
def engine() -> MatchEngine:
    return MatchEngine()


@pytest.fixture
def full_candidate() -> CandidateProfileInput:
    return CandidateProfileInput(
        age=31,
        location="Noida",
        smoking=False,
        drinking=False,
        wants_children=True,
        religion="Hindu",
        education="B.Tech",
        occupation="Engineer",
    )


def test_no_conflicts_passes(engine: MatchEngine, full_candidate: CandidateProfileInput) -> None:
    preferences = [
        pref("age", {"min": 28, "max": 35}, HARD),
        pref("location", ["Delhi NCR", "Noida", "Gurgaon"], HARD),
        pref("smoking", False, DEAL_BREAKER),
        pref("drinking", False, SOFT),
        pref("wants_children", True, DEAL_BREAKER),
        pref("religion", "Hindu", HARD),
        pref("education", "B.Tech", SOFT),
        pref("occupation", "Engineer", SOFT),
    ]

    result = engine.check(preferences, full_candidate)

    assert result.decision == Decision.PASS
    assert result.conflicts == []


def test_no_preferences_passes(engine: MatchEngine) -> None:
    result = engine.check([], CandidateProfileInput())

    assert result.decision == Decision.PASS
    assert result.conflicts == []


def test_deal_breaker_violation_blocks(engine: MatchEngine) -> None:
    result = engine.check(
        [pref("smoking", False, DEAL_BREAKER)],
        CandidateProfileInput(smoking=True),
    )

    assert result.decision == Decision.BLOCK
    assert result.conflicts == [
        ConflictResult(
            kind=VIOLATION,
            attribute="smoking",
            candidate_value=True,
            expected_value=False,
            preference_type=DEAL_BREAKER,
            reason="Candidate smokes, while smoking is marked as a client deal-breaker.",
        )
    ]


def test_hard_preference_mismatch_reviews(engine: MatchEngine) -> None:
    result = engine.check(
        [pref("religion", "Hindu", HARD)],
        CandidateProfileInput(religion="Christian"),
    )

    assert result.decision == Decision.REVIEW
    assert result.conflicts == [
        ConflictResult(
            kind=VIOLATION,
            attribute="religion",
            candidate_value="Christian",
            expected_value="Hindu",
            preference_type=HARD,
            reason="Candidate religion Christian does not match the client's preferred religion: Hindu.",
        )
    ]


def test_soft_preference_mismatch_reviews(engine: MatchEngine) -> None:
    result = engine.check(
        [pref("drinking", False, SOFT)],
        CandidateProfileInput(drinking=True),
    )

    assert result.decision == Decision.REVIEW
    [conflict] = result.conflicts
    assert conflict.kind == VIOLATION
    assert conflict.attribute == "drinking"
    assert conflict.candidate_value is True
    assert conflict.expected_value is False
    assert conflict.preference_type == SOFT
    assert conflict.reason == (
        "Candidate drinks, but the client prefers someone who does not drink (soft preference)."
    )


def test_missing_deal_breaker_field_reviews_not_blocks(engine: MatchEngine) -> None:
    result = engine.check(
        [pref("smoking", False, DEAL_BREAKER)],
        CandidateProfileInput(smoking=None),
    )

    assert result.decision == Decision.REVIEW
    assert result.conflicts == [
        ConflictResult(
            kind=MISSING_DATA,
            attribute="smoking",
            candidate_value=None,
            expected_value=False,
            preference_type=DEAL_BREAKER,
            reason="Candidate smoking information is missing, so the deal-breaker cannot be verified.",
        )
    ]


def test_missing_normal_preference_field_reviews(engine: MatchEngine) -> None:
    result = engine.check(
        [pref("drinking", False, HARD)],
        CandidateProfileInput(),
    )

    assert result.decision == Decision.REVIEW
    [conflict] = result.conflicts
    assert conflict.kind == MISSING_DATA
    assert conflict.candidate_value is None
    assert conflict.preference_type == HARD
    assert conflict.reason == (
        "Candidate drinking information is missing, so the preference cannot be verified."
    )


def test_blank_string_is_treated_as_missing(engine: MatchEngine) -> None:
    result = engine.check(
        [pref("location", "Delhi NCR", DEAL_BREAKER)],
        CandidateProfileInput(location="   "),
    )

    assert result.decision == Decision.REVIEW
    [conflict] = result.conflicts
    assert conflict.kind == MISSING_DATA
    assert conflict.candidate_value is None
    assert "missing" in conflict.reason


def test_multiple_conflicts_are_all_reported_in_order(engine: MatchEngine) -> None:
    preferences = [
        pref("age", {"min": 28, "max": 35}, HARD),
        pref("smoking", False, SOFT),
        pref("religion", "Hindu", HARD),
        pref("occupation", "Engineer", SOFT),
        pref("location", ["Delhi NCR", "Noida"], SOFT),
    ]
    candidate = CandidateProfileInput(
        age=41, smoking=True, religion="hindu", occupation=None, location="Bangalore"
    )

    result = engine.check(preferences, candidate)

    assert result.decision == Decision.REVIEW
    assert [
        (c.kind, c.attribute, c.candidate_value, c.preference_type) for c in result.conflicts
    ] == [
        (VIOLATION, "age", 41, HARD),
        (VIOLATION, "smoking", True, SOFT),
        (MISSING_DATA, "occupation", None, SOFT),
        (VIOLATION, "location", "Bangalore", SOFT),
    ]
    assert [c.reason for c in result.conflicts] == [
        "Candidate age 41 is outside the client's preferred range of 28-35.",
        "Candidate smokes, but the client prefers someone who does not smoke (soft preference).",
        "Candidate occupation information is missing, so the preference cannot be verified.",
        "Candidate location Bangalore is not one of the client's preferred locations: Delhi NCR, Noida.",
    ]


@pytest.mark.parametrize("age", [28, 31, 35])
def test_age_inside_inclusive_range_passes(engine: MatchEngine, age: int) -> None:
    result = engine.check(
        [pref("age", {"min": 28, "max": 35}, HARD)],
        CandidateProfileInput(age=age),
    )

    assert result.decision == Decision.PASS
    assert result.conflicts == []


@pytest.mark.parametrize("age", [27, 36, 41])
def test_age_outside_range_reviews(engine: MatchEngine, age: int) -> None:
    result = engine.check(
        [pref("age", {"min": 28, "max": 35}, HARD)],
        CandidateProfileInput(age=age),
    )

    assert result.decision == Decision.REVIEW
    assert result.conflicts == [
        ConflictResult(
            kind=VIOLATION,
            attribute="age",
            candidate_value=age,
            expected_value={"min": 28, "max": 35},
            preference_type=HARD,
            reason=f"Candidate age {age} is outside the client's preferred range of 28-35.",
        )
    ]


def test_age_with_only_minimum(engine: MatchEngine) -> None:
    result = engine.check(
        [pref("age", {"min": 28}, SOFT)],
        CandidateProfileInput(age=25),
    )

    assert result.decision == Decision.REVIEW
    [conflict] = result.conflicts
    assert conflict.kind == VIOLATION
    assert conflict.reason == "Candidate age 25 is below the client's minimum age of 28."


@pytest.mark.parametrize("location", ["noida", "  NOIDA  ", "delhi ncr", "Gurgaon"])
def test_location_list_matching_is_case_insensitive(engine: MatchEngine, location: str) -> None:
    result = engine.check(
        [pref("location", ["Delhi NCR", "Noida", "Gurgaon"], DEAL_BREAKER)],
        CandidateProfileInput(location=location),
    )

    assert result.decision == Decision.PASS
    assert result.conflicts == []


def test_location_not_in_list(engine: MatchEngine) -> None:
    result = engine.check(
        [pref("location", ["Delhi NCR", "Noida", "Gurgaon"], HARD)],
        CandidateProfileInput(location="Bangalore"),
    )

    assert result.decision == Decision.REVIEW
    [conflict] = result.conflicts
    assert conflict.kind == VIOLATION
    assert conflict.reason == (
        "Candidate location Bangalore is not one of the client's preferred locations: "
        "Delhi NCR, Noida, Gurgaon."
    )


def test_unsupported_attribute_reviews(engine: MatchEngine) -> None:
    result = engine.check(
        [pref("height", {"min": 170}, DEAL_BREAKER)],
        CandidateProfileInput(),
    )

    assert result.decision == Decision.REVIEW
    assert result.conflicts == [
        ConflictResult(
            kind=ConflictKind.UNSUPPORTED_ATTRIBUTE,
            attribute="height",
            candidate_value=None,
            expected_value={"min": 170},
            preference_type=DEAL_BREAKER,
            reason="Unsupported preference attribute: height",
        )
    ]


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("age", 30),
        ("age", {"min": 40, "max": 30}),
        ("age", {"from": 28}),
        ("smoking", "no"),
        ("location", []),
        ("religion", 7),
    ],
)
def test_invalid_preference_value_reviews(engine: MatchEngine, attribute: str, value: Any) -> None:
    candidate = CandidateProfileInput(age=31, smoking=True, location="Noida", religion="Hindu")

    result = engine.check([pref(attribute, value, DEAL_BREAKER)], candidate)

    assert result.decision == Decision.REVIEW
    [conflict] = result.conflicts
    assert conflict.kind == ConflictKind.INVALID_PREFERENCE
    assert conflict.candidate_value is None
    assert conflict.expected_value == value
    assert "unsupported value format" in conflict.reason


def test_multiple_deal_breakers_block(engine: MatchEngine) -> None:
    result = engine.check(
        [
            pref("smoking", False, DEAL_BREAKER),
            pref("wants_children", True, DEAL_BREAKER),
        ],
        CandidateProfileInput(smoking=True, wants_children=False),
    )

    assert result.decision == Decision.BLOCK
    assert [c.reason for c in result.conflicts] == [
        "Candidate smokes, while smoking is marked as a client deal-breaker.",
        "Candidate does not want children, while not wanting children is marked as a client deal-breaker.",
    ]
    assert all(c.kind == VIOLATION for c in result.conflicts)
    assert all(c.preference_type == DEAL_BREAKER for c in result.conflicts)


def test_deal_breaker_plus_hard_conflict_blocks(engine: MatchEngine) -> None:
    result = engine.check(
        [
            pref("age", {"min": 28, "max": 35}, HARD),
            pref("religion", "Hindu", DEAL_BREAKER),
        ],
        CandidateProfileInput(age=41, religion="Muslim"),
    )

    assert result.decision == Decision.BLOCK
    assert [(c.kind, c.attribute, c.preference_type) for c in result.conflicts] == [
        (VIOLATION, "age", HARD),
        (VIOLATION, "religion", DEAL_BREAKER),
    ]
    assert result.conflicts[1].reason == (
        "Candidate religion Muslim does not match the client's preferred religion: Hindu. "
        "This is a client deal-breaker."
    )


def test_hard_and_soft_mismatches_never_block(engine: MatchEngine) -> None:
    result = engine.check(
        [
            pref("smoking", False, HARD),
            pref("drinking", False, HARD),
            pref("age", {"min": 28, "max": 35}, SOFT),
            pref("location", "Delhi NCR", HARD),
        ],
        CandidateProfileInput(smoking=True, drinking=True, age=50, location="Mumbai"),
    )

    assert result.decision == Decision.REVIEW
    assert len(result.conflicts) == 4
    assert all(c.kind == VIOLATION for c in result.conflicts)


def test_missing_deal_breaker_with_hard_mismatch_reviews(engine: MatchEngine) -> None:
    result = engine.check(
        [
            pref("smoking", False, DEAL_BREAKER),
            pref("age", {"min": 28, "max": 35}, HARD),
        ],
        CandidateProfileInput(smoking=None, age=40),
    )

    assert result.decision == Decision.REVIEW
    assert [(c.kind, c.attribute) for c in result.conflicts] == [
        (MISSING_DATA, "smoking"),
        (VIOLATION, "age"),
    ]


@pytest.mark.parametrize(
    ("preference", "kind"),
    [
        (pref("height", 180, DEAL_BREAKER), ConflictKind.UNSUPPORTED_ATTRIBUTE),
        (pref("smoking", "never", DEAL_BREAKER), ConflictKind.INVALID_PREFERENCE),
        (pref("drinking", False, DEAL_BREAKER), MISSING_DATA),
    ],
)
def test_only_violations_can_block(
    engine: MatchEngine, preference: ClientPreferenceInput, kind: ConflictKind
) -> None:
    result = engine.check([preference], CandidateProfileInput(smoking=True))

    assert result.decision == Decision.REVIEW
    assert [c.kind for c in result.conflicts] == [kind]
