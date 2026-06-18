"""Context API routes.

Endpoints for managing shared migration context:
- Connections
- Business rules
- Resolved decisions
- Aggregated project context
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.projects import Project
from app.modules.migration_workbench.context.schemas import (
    BusinessRuleCreate,
    BusinessRuleUpdate,
    BusinessRuleView,
    ConnectionCreate,
    ConnectionUpdate,
    ConnectionView,
    DecisionCreate,
    DecisionView,
    ProjectContext,
)
from app.modules.migration_workbench.context.service import ContextService
from app.modules.migration_workbench.models import (
    MigrationBusinessRule,
    MigrationConnection,
    MigrationResolvedDecision,
)

router = APIRouter()


def _get_project_or_404(session: Session, project_ref: str) -> Project:
    """Get project by ID or slug."""
    try:
        project_id = uuid.UUID(project_ref)
        project = session.get(Project, project_id)
    except ValueError:
        project = session.scalar(
            select(Project).where(Project.slug == project_ref)
        )
    
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_ref} not found")
    return project


# -----------------------------------------------------------------------------
# Project Context
# -----------------------------------------------------------------------------


@router.get("/{project_ref}/context", response_model=ProjectContext)
async def get_project_context(
    project_ref: str,
    session: Session = Depends(get_session),
) -> ProjectContext:
    """Get the complete aggregated project context.
    
    This includes all packages, connections, business rules,
    and resolved decisions accumulated during the migration.
    """
    project = _get_project_or_404(session, project_ref)
    service = ContextService(session)
    return service.get_project_context(project.id)


@router.get("/{project_ref}/context/summary")
async def get_context_summary(
    project_ref: str,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Get a text summary of project context for prompts."""
    project = _get_project_or_404(session, project_ref)
    service = ContextService(session)
    summary = service.get_context_summary_for_prompt(project.id)
    return {"summary": summary}


# -----------------------------------------------------------------------------
# Connections
# -----------------------------------------------------------------------------


@router.get("/{project_ref}/connections", response_model=list[ConnectionView])
async def list_connections(
    project_ref: str,
    resolved_only: bool = False,
    session: Session = Depends(get_session),
) -> list[ConnectionView]:
    """List all connections in the project."""
    project = _get_project_or_404(session, project_ref)
    
    stmt = select(MigrationConnection).where(
        MigrationConnection.project_id == project.id
    )
    if resolved_only:
        stmt = stmt.where(MigrationConnection.resolved_at.isnot(None))
    stmt = stmt.order_by(MigrationConnection.connection_name)
    
    return [ConnectionView.model_validate(c) for c in session.scalars(stmt)]


@router.post("/{project_ref}/connections", response_model=ConnectionView, status_code=201)
async def create_connection(
    project_ref: str,
    body: ConnectionCreate,
    session: Session = Depends(get_session),
) -> ConnectionView:
    """Register a new connection (or merge with existing)."""
    project = _get_project_or_404(session, project_ref)
    service = ContextService(session)
    conn = service.register_connection(project.id, body)
    session.commit()
    session.refresh(conn)
    return ConnectionView.model_validate(conn)


@router.patch("/{project_ref}/connections/{connection_id}", response_model=ConnectionView)
async def resolve_connection(
    project_ref: str,
    connection_id: uuid.UUID,
    body: ConnectionUpdate,
    session: Session = Depends(get_session),
) -> ConnectionView:
    """Resolve a connection's target mapping."""
    _get_project_or_404(session, project_ref)  # Validate project exists
    service = ContextService(session)
    
    try:
        conn = service.resolve_connection(connection_id, body)
        session.commit()
        session.refresh(conn)
        return ConnectionView.model_validate(conn)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# -----------------------------------------------------------------------------
# Business Rules
# -----------------------------------------------------------------------------


@router.get("/{project_ref}/rules", response_model=list[BusinessRuleView])
async def list_business_rules(
    project_ref: str,
    category: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
) -> list[BusinessRuleView]:
    """List all business rules in the project."""
    project = _get_project_or_404(session, project_ref)
    
    stmt = select(MigrationBusinessRule).where(
        MigrationBusinessRule.project_id == project.id
    )
    if category:
        stmt = stmt.where(MigrationBusinessRule.category == category)
    if status:
        stmt = stmt.where(MigrationBusinessRule.status == status)
    stmt = stmt.order_by(MigrationBusinessRule.rule_id)
    
    return [BusinessRuleView.model_validate(r) for r in session.scalars(stmt)]


@router.post("/{project_ref}/rules", response_model=BusinessRuleView, status_code=201)
async def create_business_rule(
    project_ref: str,
    body: BusinessRuleCreate,
    session: Session = Depends(get_session),
) -> BusinessRuleView:
    """Register a new business rule (or merge with existing)."""
    project = _get_project_or_404(session, project_ref)
    service = ContextService(session)
    rule = service.register_business_rule(project.id, body)
    session.commit()
    session.refresh(rule)
    return BusinessRuleView.model_validate(rule)


@router.patch("/{project_ref}/rules/{rule_uuid}", response_model=BusinessRuleView)
async def update_business_rule(
    project_ref: str,
    rule_uuid: uuid.UUID,
    body: BusinessRuleUpdate,
    session: Session = Depends(get_session),
) -> BusinessRuleView:
    """Update a business rule's implementation or status."""
    _get_project_or_404(session, project_ref)
    service = ContextService(session)
    
    try:
        rule = service.update_business_rule(rule_uuid, body)
        session.commit()
        session.refresh(rule)
        return BusinessRuleView.model_validate(rule)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# -----------------------------------------------------------------------------
# Resolved Decisions
# -----------------------------------------------------------------------------


@router.get("/{project_ref}/decisions", response_model=list[DecisionView])
async def list_decisions(
    project_ref: str,
    scope: str | None = None,
    decision_type: str | None = None,
    session: Session = Depends(get_session),
) -> list[DecisionView]:
    """List all resolved decisions in the project."""
    project = _get_project_or_404(session, project_ref)
    
    stmt = select(MigrationResolvedDecision).where(
        MigrationResolvedDecision.project_id == project.id
    )
    if scope:
        stmt = stmt.where(MigrationResolvedDecision.scope == scope)
    if decision_type:
        stmt = stmt.where(MigrationResolvedDecision.decision_type == decision_type)
    stmt = stmt.order_by(MigrationResolvedDecision.resolved_at.desc())
    
    return [DecisionView.model_validate(d) for d in session.scalars(stmt)]


@router.post("/{project_ref}/decisions", response_model=DecisionView, status_code=201)
async def create_decision(
    project_ref: str,
    body: DecisionCreate,
    session: Session = Depends(get_session),
) -> DecisionView:
    """Record a new resolved decision."""
    project = _get_project_or_404(session, project_ref)
    service = ContextService(session)
    decision = service.record_decision(project.id, body)
    session.commit()
    session.refresh(decision)
    return DecisionView.model_validate(decision)


@router.get("/{project_ref}/decisions/lookup")
async def lookup_decision(
    project_ref: str,
    decision_type: str,
    scope: str = "project",
    flow_id: uuid.UUID | None = None,
    session: Session = Depends(get_session),
) -> DecisionView | dict[str, str]:
    """Look up an existing decision that could apply.
    
    Returns the decision if found, or a message if not.
    """
    project = _get_project_or_404(session, project_ref)
    service = ContextService(session)
    
    decision = service.find_resolved_decision(
        project.id, 
        decision_type, 
        scope=scope, 
        flow_id=flow_id
    )
    
    if decision:
        return DecisionView.model_validate(decision)
    return {"status": "not_found", "message": "No matching decision found"}
