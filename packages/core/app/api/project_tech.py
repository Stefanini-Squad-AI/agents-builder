"""Project tech choices API — CRUD for project-scoped tech selection.

Endpoints
-  GET    /api/projects/{slug}/tech                      list all tech choices for project
-  GET    /api/projects/{slug}/tech/stats                tech statistics
-  GET    /api/projects/{slug}/tech/summary              rendered markdown summary
-  GET    /api/projects/{slug}/tech/dimensions           all dimensions with project choices
-  GET    /api/projects/{slug}/tech/{dim_slug}           choices for a single dimension
-  PUT    /api/projects/{slug}/tech/{dim_slug}/{item}    set/update a tech choice
-  DELETE /api/projects/{slug}/tech/{dim_slug}/{item}    remove a tech choice
-  PUT    /api/projects/{slug}/tech/{dim_slug}/tbd       mark dimension as TBD
-  DELETE /api/projects/{slug}/tech/{dim_slug}/tbd       clear TBD marking
-  POST   /api/projects/{slug}/tech/{dim_slug}/custom    add a custom tech item
-  POST   /api/projects/{slug}/tech/{dim_slug}/accept    accept an LLM suggestion
-  POST   /api/projects/{slug}/tech/{dim_slug}/dismiss   dismiss an LLM suggestion
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.enums import TechChoiceRole
from app.schemas.views import TechChoiceView, TechDimensionView
from app.services.tech_service import TechChoiceSummary, TechService

router = APIRouter(tags=["project-tech"])


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class SetTechChoiceRequest(BaseModel):
    """Request to set a tech choice."""
    role: TechChoiceRole = TechChoiceRole.TARGET
    notes: str | None = None


class AddCustomItemRequest(BaseModel):
    """Request to add a custom tech item."""
    name: str = Field(..., min_length=1, max_length=100)
    role: TechChoiceRole = TechChoiceRole.TARGET
    description: str | None = None
    tags: list[str] = []
    notes: str | None = None


class MarkTbdRequest(BaseModel):
    """Request to mark dimension as TBD."""
    notes: str | None = None


class AcceptSuggestionRequest(BaseModel):
    """Request to accept an LLM suggestion."""
    item_slug: str


class DismissSuggestionRequest(BaseModel):
    """Request to dismiss an LLM suggestion."""
    item_slug: str


class TechStatsResponse(BaseModel):
    """Tech statistics response."""
    total_choices: int
    by_role: dict[str, int]
    by_source: dict[str, int]
    by_dimension: dict[str, int]
    coverage_percentage: float
    covered_dimensions: int
    total_dimensions: int
    tbd_dimensions: int
    pending_suggestions: int


class TechSummaryResponse(BaseModel):
    """Tech summary response."""
    summary_md: str


class DimensionWithChoicesResponse(BaseModel):
    """Dimension with its items and project choices."""
    id: UUID
    slug: str
    name: str
    description: str | None
    order_no: int
    items: list[dict[str, Any]]
    choices: list[TechChoiceView]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _to_view(summary: TechChoiceSummary) -> TechChoiceView:
    """Convert service summary to API view."""
    return TechChoiceView(
        id=summary.id,
        project_id=summary.project_id,
        dimension_id=summary.dimension_id,
        dimension_slug=summary.dimension_slug,
        dimension_name=summary.dimension_name,
        tech_item_id=summary.tech_item_id,
        tech_item_slug=summary.item_slug,
        tech_item_name=summary.item_name,
        role=TechChoiceRole(summary.role),
        source=summary.source,
        accepted=summary.accepted,
        llm_rationale=summary.llm_rationale,
        llm_confidence=summary.llm_confidence,
        notes=summary.notes,
        order_no=summary.order_no,
    )


def _get_service() -> TechService:
    return TechService()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/api/projects/{project_slug}/tech",
    response_model=list[TechChoiceView],
)
def list_project_tech_choices(project_slug: str) -> list[TechChoiceView]:
    """List all tech choices for a project."""
    service = _get_service()
    choices = service.list_project_tech_choices(project_slug)
    return [_to_view(c) for c in choices]


@router.get(
    "/api/projects/{project_slug}/tech/stats",
    response_model=TechStatsResponse,
)
def get_tech_stats(project_slug: str) -> TechStatsResponse:
    """Get tech selection statistics for a project."""
    service = _get_service()
    stats = service.get_tech_statistics(project_slug)
    return TechStatsResponse(**stats)


@router.get(
    "/api/projects/{project_slug}/tech/summary",
    response_model=TechSummaryResponse,
)
def get_tech_summary(project_slug: str) -> TechSummaryResponse:
    """Get rendered markdown summary of tech choices."""
    service = _get_service()
    summary_md = service.render_tech_summary(project_slug)
    return TechSummaryResponse(summary_md=summary_md)


@router.get(
    "/api/projects/{project_slug}/tech/dimensions",
    response_model=list[DimensionWithChoicesResponse],
)
def list_dimensions_with_choices(project_slug: str) -> list[DimensionWithChoicesResponse]:
    """List all dimensions with their items and project's choices."""
    service = _get_service()
    dims = service.list_dimensions_with_choices(project_slug)
    return [
        DimensionWithChoicesResponse(
            id=d.id,
            slug=d.slug,
            name=d.name,
            description=d.description,
            order_no=d.order_no,
            items=d.items,
            choices=[_to_view(c) for c in d.choices],
        )
        for d in dims
    ]


@router.get(
    "/api/projects/{project_slug}/tech/{dimension_slug}",
    response_model=list[TechChoiceView],
)
def get_dimension_choices(
    project_slug: str,
    dimension_slug: str,
) -> list[TechChoiceView]:
    """Get tech choices for a specific dimension."""
    service = _get_service()
    choices = service.get_dimension_choices(project_slug, dimension_slug)
    return [_to_view(c) for c in choices]


@router.put(
    "/api/projects/{project_slug}/tech/{dimension_slug}/{item_slug}",
    response_model=TechChoiceView,
)
def set_tech_choice(
    project_slug: str,
    dimension_slug: str,
    item_slug: str,
    request: SetTechChoiceRequest,
) -> TechChoiceView:
    """Set or update a tech choice from the catalog."""
    service = _get_service()
    try:
        choice = service.set_tech_choice(
            project_slug=project_slug,
            dimension_slug=dimension_slug,
            item_slug=item_slug,
            role=request.role,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    if not choice:
        raise HTTPException(status_code=404, detail=f"Project '{project_slug}' not found")
    
    return _to_view(choice)


@router.delete(
    "/api/projects/{project_slug}/tech/{dimension_slug}/{item_slug}",
    status_code=204,
)
def remove_tech_choice(
    project_slug: str,
    dimension_slug: str,
    item_slug: str,
) -> None:
    """Remove a tech choice."""
    service = _get_service()
    removed = service.remove_tech_choice(project_slug, dimension_slug, item_slug)
    if not removed:
        raise HTTPException(status_code=404, detail="Tech choice not found")


@router.put(
    "/api/projects/{project_slug}/tech/{dimension_slug}/tbd",
    response_model=TechChoiceView,
)
def mark_dimension_tbd(
    project_slug: str,
    dimension_slug: str,
    request: MarkTbdRequest,
) -> TechChoiceView:
    """Mark a dimension as TBD (to be determined)."""
    service = _get_service()
    try:
        choice = service.mark_dimension_tbd(
            project_slug=project_slug,
            dimension_slug=dimension_slug,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    if not choice:
        raise HTTPException(status_code=404, detail=f"Project '{project_slug}' not found")
    
    return _to_view(choice)


@router.delete(
    "/api/projects/{project_slug}/tech/{dimension_slug}/tbd",
    status_code=204,
)
def clear_dimension_tbd(
    project_slug: str,
    dimension_slug: str,
) -> None:
    """Clear TBD marking from a dimension."""
    service = _get_service()
    cleared = service.clear_dimension_tbd(project_slug, dimension_slug)
    if not cleared:
        raise HTTPException(status_code=404, detail="TBD marking not found")


@router.post(
    "/api/projects/{project_slug}/tech/{dimension_slug}/custom",
    response_model=TechChoiceView,
    status_code=201,
)
def add_custom_item(
    project_slug: str,
    dimension_slug: str,
    request: AddCustomItemRequest,
) -> TechChoiceView:
    """Add a custom tech item and select it for the project."""
    service = _get_service()
    try:
        choice = service.add_custom_item(
            project_slug=project_slug,
            dimension_slug=dimension_slug,
            name=request.name,
            role=request.role,
            description=request.description,
            tags=request.tags,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    if not choice:
        raise HTTPException(status_code=404, detail=f"Project '{project_slug}' not found")
    
    return _to_view(choice)


@router.post(
    "/api/projects/{project_slug}/tech/{dimension_slug}/accept",
    response_model=TechChoiceView,
)
def accept_suggestion(
    project_slug: str,
    dimension_slug: str,
    request: AcceptSuggestionRequest,
) -> TechChoiceView:
    """Accept an LLM-suggested tech choice."""
    service = _get_service()
    choice = service.accept_suggestion(
        project_slug=project_slug,
        dimension_slug=dimension_slug,
        item_slug=request.item_slug,
    )
    if not choice:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    
    return _to_view(choice)


@router.post(
    "/api/projects/{project_slug}/tech/{dimension_slug}/dismiss",
    status_code=204,
)
def dismiss_suggestion(
    project_slug: str,
    dimension_slug: str,
    request: DismissSuggestionRequest,
) -> None:
    """Dismiss (delete) an LLM-suggested tech choice."""
    service = _get_service()
    dismissed = service.dismiss_suggestion(
        project_slug=project_slug,
        dimension_slug=dimension_slug,
        item_slug=request.item_slug,
    )
    if not dismissed:
        raise HTTPException(status_code=404, detail="Suggestion not found")
