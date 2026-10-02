import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import Client, ClientPreference, MatchCheck, MatchConflict, Profile
from app.schemas.matching import (
    CandidateProfileInput,
    ClientPreferenceInput,
    MatchCheckRequest,
    MatchResult,
)
from app.services.match_engine import MatchEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/matches", tags=["matches"])

match_engine = MatchEngine()

# Each example is real MatchEngine output (tests/test_matches_api.py checks this).
MATCH_RESULT_EXAMPLES = {
    "pass": {
        "summary": "PASS: no conflicts",
        "value": {"decision": "PASS", "conflicts": []},
    },
    "review": {
        "summary": "REVIEW: hard preference not met",
        "value": {
            "decision": "REVIEW",
            "conflicts": [
                {
                    "kind": "VIOLATION",
                    "attribute": "location",
                    "candidate_value": "Mumbai",
                    "expected_value": "Bangalore",
                    "preference_type": "HARD",
                    "reason": "Candidate location Mumbai does not match the client's preferred location: Bangalore.",
                }
            ],
        },
    },
    "review_missing_data": {
        "summary": "REVIEW: deal-breaker cannot be verified",
        "value": {
            "decision": "REVIEW",
            "conflicts": [
                {
                    "kind": "MISSING_DATA",
                    "attribute": "smoking",
                    "candidate_value": None,
                    "expected_value": False,
                    "preference_type": "DEAL_BREAKER",
                    "reason": "Candidate smoking information is missing, so the deal-breaker cannot be verified.",
                }
            ],
        },
    },
    "block": {
        "summary": "BLOCK: deal-breaker violated",
        "value": {
            "decision": "BLOCK",
            "conflicts": [
                {
                    "kind": "VIOLATION",
                    "attribute": "smoking",
                    "candidate_value": True,
                    "expected_value": False,
                    "preference_type": "DEAL_BREAKER",
                    "reason": "Candidate smokes, while smoking is marked as a client deal-breaker.",
                }
            ],
        },
    },
}


@router.post(
    "/check",
    response_model=MatchResult,
    responses={200: {"content": {"application/json": {"examples": MATCH_RESULT_EXAMPLES}}}},
)
def check_match(request: MatchCheckRequest, db: Session = Depends(get_db)) -> MatchResult:
    try:
        client = db.get(Client, request.client_id)
        if client is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")

        profile = db.get(Profile, request.profile_id)
        if profile is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")

        preference_rows = db.scalars(
            select(ClientPreference)
            .where(ClientPreference.client_id == client.id)
            .order_by(ClientPreference.created_at, ClientPreference.attribute)
        ).all()

        result = match_engine.check(
            preferences=[ClientPreferenceInput.model_validate(row) for row in preference_rows],
            candidate=CandidateProfileInput.model_validate(profile),
        )

        db.add(
            MatchCheck(
                client=client,
                profile=profile,
                decision=result.decision,
                conflicts=[MatchConflict(**conflict.model_dump()) for conflict in result.conflicts],
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Match check failed for client %s, profile %s", request.client_id, request.profile_id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not complete the match check."
        )

    return result
