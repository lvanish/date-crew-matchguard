import pytest

from app.schemas.feedback import (
    FeedbackAttribute,
    FeedbackKind,
    FeedbackPreferenceType,
    StructuredFeedback,
)
from app.services.demo_feedback_extractor import DemoFeedbackExtractor

A = FeedbackAttribute
P = FeedbackPreferenceType
K = FeedbackKind


def summary(result: StructuredFeedback) -> list[tuple]:
    return [(r.attribute, r.value, r.preference_type, r.kind) for r in result.reasons]


@pytest.fixture
def extractor() -> DemoFeedbackExtractor:
    return DemoFeedbackExtractor()


@pytest.mark.parametrize(
    "feedback",
    ["Smoking is a deal breaker.", "She doesn't want a smoker.", "I don't date smokers."],
)
def test_smoking_deal_breaker(extractor: DemoFeedbackExtractor, feedback: str) -> None:
    result = extractor.extract(feedback)

    assert summary(result) == [(A.SMOKING, True, P.DEAL_BREAKER, K.VIOLATION)]
    assert result.needs_review is False
    assert "rules out a partner who smokes" in result.reasons[0].explanation


@pytest.mark.parametrize("feedback", ["I'm not really a fan of smokers.", "Not a fan of smokers."])
def test_soft_smoking_preference(extractor: DemoFeedbackExtractor, feedback: str) -> None:
    result = extractor.extract(feedback)

    assert summary(result) == [(A.SMOKING, True, P.SOFT, K.PREFERENCE)]
    assert result.needs_review is False


def test_drinking_concern(extractor: DemoFeedbackExtractor) -> None:
    result = extractor.extract("Drinking is a concern.")

    assert summary(result) == [(A.DRINKING, True, P.SOFT, K.PREFERENCE)]
    assert result.needs_review is False


def test_doesnt_drink_is_recognised_but_left_for_review(extractor: DemoFeedbackExtractor) -> None:
    result = extractor.extract("He doesn't drink.")

    assert summary(result) == [(A.DRINKING, None, P.UNCLEAR, K.UNCLEAR)]
    assert result.needs_review is True


@pytest.mark.parametrize(
    ("feedback", "expected"),
    [
        ("She's nice but Bangalore is too far.", (A.LOCATION, "Bangalore", P.SOFT, K.PREFERENCE)),
        ("I can't move to Bangalore.", (A.LOCATION, "Bangalore", P.HARD, K.VIOLATION)),
        ("I don't think I can move to Mumbai.", (A.LOCATION, "Mumbai", P.SOFT, K.PREFERENCE)),
    ],
)
def test_location(extractor: DemoFeedbackExtractor, feedback: str, expected: tuple) -> None:
    result = extractor.extract(feedback)

    assert summary(result) == [expected]
    assert result.needs_review is False


@pytest.mark.parametrize(
    ("feedback", "value"),
    [("He doesn't want children.", False), ("I don't want children.", True)],
)
def test_children(extractor: DemoFeedbackExtractor, feedback: str, value: bool) -> None:
    result = extractor.extract(feedback)

    assert summary(result) == [(A.WANTS_CHILDREN, value, P.DEAL_BREAKER, K.VIOLATION)]
    assert result.needs_review is False


def test_age(extractor: DemoFeedbackExtractor) -> None:
    result = extractor.extract("He seemed too old for me.")

    assert summary(result) == [(A.AGE, None, P.SOFT, K.PREFERENCE)]


def test_multiple_reasons(extractor: DemoFeedbackExtractor) -> None:
    result = extractor.extract(
        "Great profile, but I don't want someone who smokes "
        "and I don't think I can move to Bangalore."
    )

    assert summary(result) == [
        (A.SMOKING, True, P.DEAL_BREAKER, K.VIOLATION),
        (A.LOCATION, "Bangalore", P.SOFT, K.PREFERENCE),
    ]
    assert result.needs_review is False


def test_repeated_attribute_keeps_strongest_statement(extractor: DemoFeedbackExtractor) -> None:
    result = extractor.extract("Maybe smoking is an issue. Actually smoking is a deal breaker.")

    assert summary(result) == [(A.SMOKING, True, P.DEAL_BREAKER, K.VIOLATION)]


def test_ambiguous_statement_needs_review(extractor: DemoFeedbackExtractor) -> None:
    result = extractor.extract("Maybe smoking could be an issue.")

    assert summary(result) == [(A.SMOKING, True, P.UNCLEAR, K.UNCLEAR)]
    assert result.needs_review is True


def test_ambiguity_in_one_reason_flags_whole_result(extractor: DemoFeedbackExtractor) -> None:
    result = extractor.extract("Smoking is a deal breaker, and maybe the distance is a problem.")

    assert [r.preference_type for r in result.reasons] == [P.DEAL_BREAKER, P.UNCLEAR]
    assert result.needs_review is True


@pytest.mark.parametrize("feedback", ["Not feeling the vibe.", "Great profile!", "Her family seemed rude."])
def test_unknown_statement_is_other_and_unclear(extractor: DemoFeedbackExtractor, feedback: str) -> None:
    result = extractor.extract(feedback)

    assert summary(result) == [(A.OTHER, None, P.UNCLEAR, K.UNCLEAR)]
    assert result.needs_review is True


@pytest.mark.parametrize(
    "feedback",
    [
        "Smoking is a deal breaker.",
        "Not a fan of smokers.",
        "Drinking is a concern.",
        "She's nice but Bangalore is too far.",
        "He doesn't want children.",
        "Maybe smoking could be an issue.",
        "Not feeling the vibe.",
        "Too old, smokes, and can't move to Pune.",
    ],
)
def test_outputs_validate_against_schema(extractor: DemoFeedbackExtractor, feedback: str) -> None:
    result = extractor.extract(feedback)

    round_tripped = StructuredFeedback.model_validate_json(result.model_dump_json())
    assert round_tripped == result
    assert all(reason.explanation for reason in result.reasons)


def test_curly_apostrophes_are_understood(extractor: DemoFeedbackExtractor) -> None:
    result = extractor.extract("I don\u2019t date smokers.")

    assert summary(result) == [(A.SMOKING, True, P.DEAL_BREAKER, K.VIOLATION)]


def test_schema_forces_review_when_extractor_claims_otherwise() -> None:
    result = StructuredFeedback.model_validate(
        {
            "reasons": [
                {
                    "attribute": "other",
                    "value": None,
                    "preference_type": "UNCLEAR",
                    "kind": "UNCLEAR",
                    "explanation": "Unclear.",
                }
            ],
            "needs_review": False,
        }
    )

    assert result.needs_review is True


def test_schema_forces_review_for_empty_reasons() -> None:
    assert StructuredFeedback(reasons=[], needs_review=False).needs_review is True


def test_schema_rejects_unknown_attribute() -> None:
    with pytest.raises(ValueError):
        StructuredFeedback.model_validate(
            {
                "reasons": [
                    {
                        "attribute": "height",
                        "value": None,
                        "preference_type": "SOFT",
                        "kind": "PREFERENCE",
                        "explanation": "x",
                    }
                ],
                "needs_review": False,
            }
        )
