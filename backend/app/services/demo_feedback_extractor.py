"""Local demo fallback for rejection feedback extraction.

This is NOT AI. It is a small set of deterministic keyword rules so the app runs without
an AI provider API key. It only recognises a few phrasings for age, location, smoking,
drinking and children; everything else is returned as 'other' / UNCLEAR for review.
"""

import re
from dataclasses import dataclass

from app.schemas.feedback import (
    FeedbackAttribute,
    FeedbackKind,
    FeedbackPreferenceType,
    FeedbackReason,
    StructuredFeedback,
)

Attr = FeedbackAttribute
Strength = FeedbackPreferenceType

# Checked in this order, so hedged wording wins over absolute wording in the same clause
# ("maybe smoking is a deal breaker" is UNCLEAR, "I don't think I can move" is SOFT).
STRENGTH_PATTERNS: list[tuple[Strength, re.Pattern[str]]] = [
    (
        Strength.UNCLEAR,
        re.compile(r"\b(maybe|might|perhaps|possibly|could be|not sure|unsure|i guess)\b"),
    ),
    (
        Strength.SOFT,
        re.compile(
            r"\b(not (really )?a fan|not really|not keen|prefer|rather|a bit|too|concern(ed|s)?"
            r"|not ideal|(don't|do not) think|hesitant|worried)\b"
        ),
    ),
    (
        Strength.DEAL_BREAKER,
        re.compile(
            r"\b(deal[- ]?breaker|non[- ]?negotiable|never|absolutely not|no way|refuse"
            r"|not acceptable|unacceptable|(don't|do not|doesn't|does not|won't|will not) "
            r"(date|want|marry|accept))\b"
        ),
    ),
    (Strength.HARD, re.compile(r"\b(can't|cannot|can not|must|has to|have to)\b")),
]

KIND_FOR_STRENGTH = {
    Strength.DEAL_BREAKER: FeedbackKind.VIOLATION,
    Strength.HARD: FeedbackKind.VIOLATION,
    Strength.SOFT: FeedbackKind.PREFERENCE,
    Strength.UNCLEAR: FeedbackKind.UNCLEAR,
}

STRENGTH_RANK = {Strength.UNCLEAR: 0, Strength.SOFT: 1, Strength.HARD: 2, Strength.DEAL_BREAKER: 3}

KNOWN_LOCATIONS = [
    "Delhi NCR", "Delhi", "Noida", "Gurgaon", "Gurugram", "Mumbai", "Pune", "Bangalore",
    "Bengaluru", "Hyderabad", "Chennai", "Kolkata", "Ahmedabad", "Jaipur", "Chandigarh",
    "Lucknow", "abroad",
]

SMOKING = re.compile(r"\b(smok(e|es|er|ers|ing)|cigarettes?)\b")
DRINKING = re.compile(r"\b(drink(s|er|ers|ing)?|alcohol)\b")
NOT_DRINKING = re.compile(r"\b((doesn't|does not|don't|do not) drink|teetotal(ler)?|non-?drinker)\b")
CHILDREN = re.compile(r"\b(child(ren)?|kids?|bab(y|ies))\b")
CLIENT_NO_CHILDREN = re.compile(r"\bi (don't|do not) want (kids|children|a baby)\b")
CANDIDATE_NO_CHILDREN = re.compile(r"\b(doesn't|does not|don't|do not) want (kids|children|a baby)\b")
RELOCATION = re.compile(r"\b(move|moving|relocat\w*|shift\w*|too far|far away|distance|long[- ]distance)\b")
AGE = re.compile(r"\b(too (old|young)|older|younger|age( gap| difference)?)\b")
NUMBER = re.compile(r"\b(\d{2})\b")
CLAUSE_SPLIT = re.compile(r"[.;!?,]|\bbut\b|\band\b|\balso\b")


@dataclass
class _Match:
    attribute: Attr
    value: bool | int | str | None
    subject: str


class DemoFeedbackExtractor:
    """Deterministic keyword-based stand-in for the LLM extractor (local demo only)."""

    def extract(self, feedback: str) -> StructuredFeedback:
        reasons: dict[Attr, FeedbackReason] = {}

        for clause in _clauses(feedback):
            strength, phrase = _strength(clause)
            for match in _topics(clause, has_strength=phrase is not None):
                reason = _reason(match, strength, phrase)
                existing = reasons.get(match.attribute)
                if existing is None or STRENGTH_RANK[strength] > STRENGTH_RANK[existing.preference_type]:
                    reasons[match.attribute] = reason

        if not reasons:
            return StructuredFeedback(
                reasons=[
                    FeedbackReason(
                        attribute=Attr.OTHER,
                        value=None,
                        preference_type=Strength.UNCLEAR,
                        kind=FeedbackKind.UNCLEAR,
                        explanation=(
                            "The demo rules did not recognise a supported rejection reason; "
                            "a matchmaker should read the feedback."
                        ),
                    )
                ],
                needs_review=True,
            )

        return StructuredFeedback(reasons=list(reasons.values()), needs_review=False)


def _clauses(feedback: str) -> list[str]:
    text = feedback.lower().replace("\u2019", "'")
    return [clause.strip() for clause in CLAUSE_SPLIT.split(text) if clause.strip()]


def _strength(clause: str) -> tuple[Strength, str | None]:
    for strength, pattern in STRENGTH_PATTERNS:
        found = pattern.search(clause)
        if found:
            return strength, found.group(0)
    return Strength.UNCLEAR, None


def _topics(clause: str, has_strength: bool) -> list[_Match]:
    matches: list[_Match] = []

    if SMOKING.search(clause):
        matches.append(_Match(Attr.SMOKING, True, "a partner who smokes"))

    if DRINKING.search(clause):
        if NOT_DRINKING.search(clause):
            # "doesn't drink" could describe either person, so don't guess a direction.
            matches.append(_Match(Attr.DRINKING, None, "drinking"))
        else:
            matches.append(_Match(Attr.DRINKING, True, "a partner who drinks"))

    if CHILDREN.search(clause):
        if CLIENT_NO_CHILDREN.search(clause):
            matches.append(_Match(Attr.WANTS_CHILDREN, True, "a partner who wants children"))
        elif CANDIDATE_NO_CHILDREN.search(clause):
            matches.append(_Match(Attr.WANTS_CHILDREN, False, "a partner who does not want children"))
        else:
            matches.append(_Match(Attr.WANTS_CHILDREN, None, "children"))

    city = next(
        (name for name in KNOWN_LOCATIONS if re.search(rf"\b{re.escape(name.lower())}\b", clause)),
        None,
    )
    if RELOCATION.search(clause) or (city and has_strength):
        subject = f"relocating to {city}" if city else "the candidate's location"
        matches.append(_Match(Attr.LOCATION, city, subject))

    if AGE.search(clause):
        number = NUMBER.search(clause)
        matches.append(
            _Match(Attr.AGE, int(number.group(1)) if number else None, "the candidate's age")
        )

    return matches


def _reason(match: _Match, strength: Strength, phrase: str | None) -> FeedbackReason:
    quoted = f' ("{phrase}")' if phrase else ""
    explanation = {
        Strength.DEAL_BREAKER: f"Feedback explicitly rules out {match.subject}{quoted}.",
        Strength.HARD: f"Feedback states a firm objection to {match.subject}{quoted}.",
        Strength.SOFT: f"Feedback expresses a mild concern about {match.subject}{quoted}.",
        Strength.UNCLEAR: (
            f"Feedback is tentative about {match.subject}{quoted}; confirm with the client."
            if phrase
            else f"Feedback mentions {match.subject} but not how much it matters; confirm with the client."
        ),
    }[strength]

    return FeedbackReason(
        attribute=match.attribute,
        value=match.value,
        preference_type=strength,
        kind=KIND_FOR_STRENGTH[strength],
        explanation=explanation,
    )
