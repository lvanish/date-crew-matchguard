import json
from typing import Any

from app.core.enums import ConflictKind, Decision, PreferenceType
from app.schemas.matching import (
    CandidateProfileInput,
    ClientPreferenceInput,
    ConflictResult,
    MatchResult,
)

# Human-readable name for each supported attribute, used in explanations.
ATTRIBUTE_LABELS = {
    "age": "age",
    "location": "location",
    "smoking": "smoking",
    "drinking": "drinking",
    "wants_children": "children preference",
    "religion": "religion",
    "education": "education",
    "occupation": "occupation",
}

STRING_ATTRIBUTE_PLURALS = {
    "location": "locations",
    "religion": "religions",
    "education": "education levels",
    "occupation": "occupations",
}

# attribute -> value -> (what the candidate does, the trait as a noun)
BOOLEAN_PHRASES = {
    "smoking": {
        True: ("smokes", "smoking"),
        False: ("does not smoke", "not smoking"),
    },
    "drinking": {
        True: ("drinks", "drinking"),
        False: ("does not drink", "not drinking"),
    },
    "wants_children": {
        True: ("wants children", "wanting children"),
        False: ("does not want children", "not wanting children"),
    },
}

PREFERENCE_TYPE_LABELS = {
    PreferenceType.DEAL_BREAKER: "deal-breaker",
    PreferenceType.HARD: "hard preference",
    PreferenceType.SOFT: "soft preference",
}


class MatchEngine:
    """Deterministically checks a candidate profile against a client's preferences."""

    def check(
        self,
        preferences: list[ClientPreferenceInput],
        candidate: CandidateProfileInput,
    ) -> MatchResult:
        conflicts = [
            conflict
            for preference in preferences
            if (conflict := self._evaluate(preference, candidate)) is not None
        ]

        # Only a verified violation of a deal-breaker can block; missing or
        # unusable data always goes to a matchmaker for review instead.
        if any(
            c.kind == ConflictKind.VIOLATION and c.preference_type == PreferenceType.DEAL_BREAKER
            for c in conflicts
        ):
            decision = Decision.BLOCK
        elif conflicts:
            decision = Decision.REVIEW
        else:
            decision = Decision.PASS

        return MatchResult(decision=decision, conflicts=conflicts)

    def _evaluate(
        self,
        preference: ClientPreferenceInput,
        candidate: CandidateProfileInput,
    ) -> ConflictResult | None:
        attribute = preference.attribute.strip().lower()
        expected = preference.value

        def conflict(kind: ConflictKind, reason: str, candidate_value: Any = None) -> ConflictResult:
            return ConflictResult(
                kind=kind,
                attribute=preference.attribute,
                candidate_value=candidate_value,
                expected_value=expected,
                preference_type=preference.preference_type,
                reason=reason,
            )

        if attribute not in ATTRIBUTE_LABELS:
            return conflict(
                ConflictKind.UNSUPPORTED_ATTRIBUTE,
                f"Unsupported preference attribute: {preference.attribute}",
            )

        label = ATTRIBUTE_LABELS[attribute]

        if not _is_valid_preference_value(attribute, expected):
            reason = (
                f"Client {label} preference has an unsupported value format: "
                f"{json.dumps(expected)}, so it cannot be checked."
            )
            return conflict(ConflictKind.INVALID_PREFERENCE, reason)

        candidate_value = getattr(candidate, attribute)
        if isinstance(candidate_value, str) and not candidate_value.strip():
            candidate_value = None

        is_deal_breaker = preference.preference_type == PreferenceType.DEAL_BREAKER

        if candidate_value is None:
            target = "the deal-breaker" if is_deal_breaker else "the preference"
            reason = f"Candidate {label} information is missing, so {target} cannot be verified."
            return conflict(ConflictKind.MISSING_DATA, reason)

        if attribute == "age":
            reason = _age_mismatch(candidate_value, expected)
        elif attribute in BOOLEAN_PHRASES:
            reason = _boolean_mismatch(
                attribute, candidate_value, expected, preference.preference_type
            )
        else:
            reason = _string_mismatch(attribute, candidate_value, expected)

        if reason is None:
            return None

        if is_deal_breaker and attribute not in BOOLEAN_PHRASES:
            reason += " This is a client deal-breaker."

        return conflict(ConflictKind.VIOLATION, reason, candidate_value)


def _is_valid_preference_value(attribute: str, value: Any) -> bool:
    if attribute == "age":
        return _is_valid_age_range(value)
    if attribute in BOOLEAN_PHRASES:
        return isinstance(value, bool)
    return _is_non_empty_string(value) or (
        isinstance(value, list)
        and len(value) > 0
        and all(_is_non_empty_string(item) for item in value)
    )


def _is_valid_age_range(value: Any) -> bool:
    if not isinstance(value, dict) or not value or not set(value) <= {"min", "max"}:
        return False
    bounds = list(value.values())
    if not all(isinstance(b, int) and not isinstance(b, bool) for b in bounds):
        return False
    return "min" not in value or "max" not in value or value["min"] <= value["max"]


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalize(text: str) -> str:
    return text.strip().casefold()


def _age_mismatch(age: int, expected: dict[str, int]) -> str | None:
    minimum = expected.get("min")
    maximum = expected.get("max")

    if (minimum is None or age >= minimum) and (maximum is None or age <= maximum):
        return None
    if minimum is not None and maximum is not None:
        return (
            f"Candidate age {age} is outside the client's preferred range "
            f"of {minimum}-{maximum}."
        )
    if minimum is not None:
        return f"Candidate age {age} is below the client's minimum age of {minimum}."
    return f"Candidate age {age} is above the client's maximum age of {maximum}."


def _boolean_mismatch(
    attribute: str,
    candidate_value: bool,
    expected: bool,
    preference_type: PreferenceType,
) -> str | None:
    if candidate_value == expected:
        return None

    phrases = BOOLEAN_PHRASES[attribute]
    candidate_does, candidate_trait = phrases[candidate_value]

    if preference_type == PreferenceType.DEAL_BREAKER:
        return f"Candidate {candidate_does}, while {candidate_trait} is marked as a client deal-breaker."

    expected_does = phrases[expected][0]
    return (
        f"Candidate {candidate_does}, but the client prefers someone who {expected_does} "
        f"({PREFERENCE_TYPE_LABELS[preference_type]})."
    )


def _string_mismatch(attribute: str, candidate_value: str, expected: str | list[str]) -> str | None:
    options = [expected] if isinstance(expected, str) else expected

    if _normalize(candidate_value) in {_normalize(option) for option in options}:
        return None

    label = ATTRIBUTE_LABELS[attribute]
    shown = candidate_value.strip()
    if len(options) == 1:
        return (
            f"Candidate {label} {shown} does not match the client's preferred "
            f"{label}: {options[0].strip()}."
        )
    choices = ", ".join(option.strip() for option in options)
    return (
        f"Candidate {label} {shown} is not one of the client's preferred "
        f"{STRING_ATTRIBUTE_PLURALS[attribute]}: {choices}."
    )
