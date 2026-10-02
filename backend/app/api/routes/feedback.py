import logging
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models import Client, Profile, RejectionFeedback
from app.schemas.feedback import FeedbackAnalysis, FeedbackAnalyzeRequest
from app.services.feedback_extractor import (
    FeedbackExtractionError,
    FeedbackExtractor,
    create_feedback_extractor,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@lru_cache
def get_feedback_extractor() -> FeedbackExtractor:
    return create_feedback_extractor(settings)


@router.post(
    "/analyze",
    response_model=FeedbackAnalysis,
    responses={503: {"description": "The configured AI provider is unavailable or not configured."}},
)
def analyze_feedback(
    request: FeedbackAnalyzeRequest,
    db: Session = Depends(get_db),
    extractor: FeedbackExtractor = Depends(get_feedback_extractor),
) -> FeedbackAnalysis:
    if db.get(Client, request.client_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")
    if db.get(Profile, request.profile_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")

    try:
        structured = extractor.extract(request.raw_feedback)
    except FeedbackExtractionError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error

    row = RejectionFeedback(
        client_id=request.client_id,
        profile_id=request.profile_id,
        raw_feedback=request.raw_feedback,
        structured_feedback=structured.model_dump(mode="json"),
    )
    try:
        db.add(row)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Saving rejection feedback failed for client %s", request.client_id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not save the feedback analysis."
        )

    return FeedbackAnalysis(
        id=row.id,
        client_id=row.client_id,
        profile_id=row.profile_id,
        raw_feedback=row.raw_feedback,
        structured_feedback=structured,
    )
