"""Q&A API — project discovery questions.

Endpoints:
- GET  /api/projects/{slug}/qa                  list all Q&A for project
- GET  /api/projects/{slug}/qa/{question_key}   get single answer
- PUT  /api/projects/{slug}/qa/{question_key}   set/update answer
- GET  /api/projects/{slug}/qa/stats            completion statistics
- GET  /api/projects/{slug}/qa/summary          rendered markdown summary
- GET  /api/projects/{slug}/qa/readiness        check project readiness
- GET  /api/qa/standard-questions               questions catalog (global)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.services.qa_service import QaService, QaSummary

router = APIRouter(tags=["qa"])


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------


class QaAnswerResponse(BaseModel):
    """Response for a single Q&A answer."""

    project_id: str | None
    question_key: str
    prompt: str
    required: bool
    placeholder: str
    order: int
    answer_md: str | None
    updated_at: str | None
    is_answered: bool


class SetQaAnswerRequest(BaseModel):
    """Request to set/update a Q&A answer."""

    answer_md: str = Field(..., min_length=0, max_length=10000)


class QaStatsResponse(BaseModel):
    """Q&A completion statistics."""

    total_questions: int
    answered_questions: int
    completion_percentage: float
    required_answered: int
    required_total: int
    required_percentage: float
    questions_by_status: dict[str, int]


class QaSummaryResponse(BaseModel):
    """Rendered Q&A summary."""

    summary_md: str
    completion_status: dict[str, Any]


class QaReadinessResponse(BaseModel):
    """Project readiness based on Q&A."""

    ready: bool
    readiness: str
    message: str
    missing_required: list[str]
    recommended_next_steps: list[str]


class QuestionMetadataResponse(BaseModel):
    """Metadata for a standard question."""

    prompt: str
    required: bool
    placeholder: str
    order: int


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _qa_summary_to_response(qa: QaSummary) -> QaAnswerResponse:
    """Convert QaSummary to API response."""
    return QaAnswerResponse(
        project_id=str(qa.project_id) if qa.project_id else None,
        question_key=qa.question_key,
        prompt=qa.prompt,
        required=qa.required,
        placeholder=qa.placeholder,
        order=qa.order,
        answer_md=qa.answer_md,
        updated_at=qa.updated_at.isoformat() if qa.updated_at else None,
        is_answered=qa.is_answered,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/qa/standard-questions", response_model=dict[str, QuestionMetadataResponse])
def get_standard_questions() -> dict[str, QuestionMetadataResponse]:
    """Get the catalog of standard questions with metadata (no DB access)."""
    service = QaService()  # No session needed for this endpoint
    catalog = service.get_standard_questions_catalog()
    return {
        key: QuestionMetadataResponse(**meta) for key, meta in catalog.items()
    }


@router.get("/api/projects/{slug}/qa", response_model=list[QaAnswerResponse])
def list_project_qa(
    slug: str,
    session: Session = Depends(get_session),
) -> list[QaAnswerResponse]:
    """List all Q&A answers for a project."""
    service = QaService(session)
    qa_list = service.list_project_qa(slug)

    if not qa_list:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    return [_qa_summary_to_response(qa) for qa in qa_list]


@router.get("/api/projects/{slug}/qa/stats", response_model=QaStatsResponse)
def get_qa_stats(
    slug: str,
    session: Session = Depends(get_session),
) -> QaStatsResponse:
    """Get Q&A completion statistics for a project."""
    service = QaService(session)

    # Check project exists by getting qa list
    qa_list = service.list_project_qa(slug)
    if not qa_list:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    stats = service.get_qa_statistics(slug)
    return QaStatsResponse(**stats)


@router.get("/api/projects/{slug}/qa/summary", response_model=QaSummaryResponse)
def get_qa_summary(
    slug: str,
    session: Session = Depends(get_session),
) -> QaSummaryResponse:
    """Get rendered Q&A summary as markdown."""
    service = QaService(session)

    # Check project exists
    qa_list = service.list_project_qa(slug)
    if not qa_list:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    summary_md = service.render_qa_summary(slug)
    completion_status = service.get_completion_status(slug)

    return QaSummaryResponse(
        summary_md=summary_md,
        completion_status={
            "overall": completion_status["readiness"],
            "missing_keys": completion_status["missing_required"],
        },
    )


@router.get("/api/projects/{slug}/qa/readiness", response_model=QaReadinessResponse)
def check_qa_readiness(
    slug: str,
    session: Session = Depends(get_session),
) -> QaReadinessResponse:
    """Check project readiness based on Q&A completion."""
    service = QaService(session)

    # Check project exists
    qa_list = service.list_project_qa(slug)
    if not qa_list:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    status = service.get_completion_status(slug)

    return QaReadinessResponse(
        ready=status["required_complete"],
        readiness=status["readiness"],
        message=status["message"],
        missing_required=status["missing_required"],
        recommended_next_steps=status["recommended_next_steps"],
    )


@router.get(
    "/api/projects/{slug}/qa/{question_key}", response_model=QaAnswerResponse
)
def get_qa_answer(
    slug: str,
    question_key: str,
    session: Session = Depends(get_session),
) -> QaAnswerResponse:
    """Get a specific Q&A answer."""
    service = QaService(session)
    qa = service.get_qa_answer(slug, question_key)

    if qa is None:
        # Check if it's an invalid key vs project not found
        if question_key not in service.STANDARD_QUESTIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid question key: {question_key}. "
                f"Valid keys: {', '.join(service.STANDARD_QUESTIONS.keys())}",
            )
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    return _qa_summary_to_response(qa)


@router.put(
    "/api/projects/{slug}/qa/{question_key}", response_model=QaAnswerResponse
)
def set_qa_answer(
    slug: str,
    question_key: str,
    request: SetQaAnswerRequest,
    session: Session = Depends(get_session),
) -> QaAnswerResponse:
    """Set or update a Q&A answer."""
    service = QaService(session)

    # Validate question key first
    if question_key not in service.STANDARD_QUESTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid question key: {question_key}. "
            f"Valid keys: {', '.join(service.STANDARD_QUESTIONS.keys())}",
        )

    qa = service.set_qa_answer(slug, question_key, request.answer_md)

    if qa is None:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    return _qa_summary_to_response(qa)
