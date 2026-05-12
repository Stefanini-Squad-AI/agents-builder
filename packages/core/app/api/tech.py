"""Tech panorama API — read-only dimension + item catalogue.

Endpoints
-  GET  /api/tech/dimensions              list all dimensions (ordered)
-  GET  /api/tech/dimensions/{slug}       single dimension with its items
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.domain.tech import TechDimension
from app.schemas.views import TechDimensionView

router = APIRouter(tags=["tech"])


def _to_view(row: TechDimension) -> TechDimensionView:
    return TechDimensionView.model_validate(row)


@router.get("/api/tech/dimensions", response_model=list[TechDimensionView])
def list_dimensions(session: Session = Depends(get_session)) -> list[TechDimensionView]:
    """Return all tech dimensions with their items, ordered by order_no."""
    rows = (
        session.execute(
            select(TechDimension)
            .options(selectinload(TechDimension.items))
            .order_by(TechDimension.order_no, TechDimension.name)
        )
        .scalars()
        .all()
    )
    return [_to_view(r) for r in rows]


@router.get("/api/tech/dimensions/{slug}", response_model=TechDimensionView)
def get_dimension(
    slug: str,
    session: Session = Depends(get_session),
) -> TechDimensionView:
    """Return a single tech dimension (with items) by slug."""
    row = session.execute(
        select(TechDimension)
        .options(selectinload(TechDimension.items))
        .where(TechDimension.slug == slug)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Dimension '{slug}' not found")
    return _to_view(row)
