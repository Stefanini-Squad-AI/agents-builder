"""Projects API — listing, detail, and creation.

Endpoints
-  GET   /api/projects                     list all projects (newest first)
-  POST  /api/projects                     create a new project
-  GET   /api/projects/{project_ref}       single project by ID or slug
"""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.identity import Tenant, User
from app.domain.projects import Project
from app.enums import CardTemplate, Grouping, LlmProvider, ProjectStatus, ProjectType
from app.defaults import DEFAULT_LLM_MODEL, DEFAULT_LLM_PROVIDER
from app.schemas.views import ProjectView

router = APIRouter(tags=["projects"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    """Request body for creating a new project."""
    name: str = Field(..., min_length=1, max_length=200, description="Project name")
    objective: str = Field(..., min_length=10, description="Project objective/description")
    card_code_prefix: str = Field(
        ..., 
        min_length=2, 
        max_length=8, 
        pattern=r"^[A-Z0-9]+$",
        description="Code prefix for cards (e.g., PROJ for PROJ-001)"
    )
    context_md: str | None = Field(default=None, description="Optional initial project context (markdown)")
    project_type: ProjectType = Field(default=ProjectType.APPLICATION)
    source_technology: str | None = Field(default=None, max_length=32)
    target_technology: str | None = Field(default=None, max_length=32)
    card_template: CardTemplate = Field(default=CardTemplate.PHASE_VLI)
    llm_provider: LlmProvider = Field(default=DEFAULT_LLM_PROVIDER)
    llm_model: str = Field(default=DEFAULT_LLM_MODEL)


def _slugify(name: str) -> str:
    """Convert a project name to a URL-safe slug."""
    # Lowercase, replace spaces/special chars with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower())
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    return slug or "project"


def _generate_code_prefix(name: str) -> str:
    """Generate a card code prefix from the project name."""
    # Take first letters of words, uppercase, max 4 chars
    words = name.split()
    if len(words) >= 2:
        prefix = "".join(w[0].upper() for w in words[:4])
    else:
        # Single word: take first 4 chars
        prefix = name[:4].upper()
    # Ensure it's alphanumeric only
    prefix = re.sub(r"[^A-Z0-9]", "", prefix)
    return prefix[:4] if len(prefix) >= 2 else "PROJ"


def _get_default_tenant_and_user(session: Session) -> tuple[Tenant, User]:
    """Get or create the default tenant and user for the MVP."""
    tenant = session.execute(
        select(Tenant).where(Tenant.name == "default")
    ).scalar_one_or_none()
    
    if tenant is None:
        tenant = Tenant(name="default")
        session.add(tenant)
        session.flush()
    
    user = session.execute(
        select(User).where(User.email == "local@workshop")
    ).scalar_one_or_none()
    
    if user is None:
        from app.enums import UserRole
        user = User(email="local@workshop", name="Local", role=UserRole.OWNER.value)
        session.add(user)
        session.flush()
    
    return tenant, user


def _to_view(row: Project) -> ProjectView:
    return ProjectView.model_validate(row)


def _get_project_by_ref(session: Session, project_ref: str) -> Project | None:
    """Fetch project by UUID or slug."""
    # Try UUID first
    try:
        project_uuid = uuid.UUID(project_ref)
        return session.get(Project, project_uuid)
    except ValueError:
        pass
    
    # Fall back to slug lookup
    return session.execute(
        select(Project).where(Project.slug == project_ref)
    ).scalar_one_or_none()


@router.get("/api/projects", response_model=list[ProjectView])
def list_projects(session: Session = Depends(get_session)) -> list[ProjectView]:
    """Return all projects ordered by creation date descending."""
    rows = (
        session.execute(select(Project).order_by(Project.created_at.desc()))
        .scalars()
        .all()
    )
    return [_to_view(r) for r in rows]


@router.post("/api/projects", response_model=ProjectView, status_code=201)
def create_project(
    body: ProjectCreate,
    session: Session = Depends(get_session),
) -> ProjectView:
    """Create a new project."""
    tenant, user = _get_default_tenant_and_user(session)
    
    # Generate slug from name
    base_slug = _slugify(body.name)
    slug = base_slug
    
    # Ensure unique slug
    counter = 1
    while session.execute(
        select(Project).where(Project.slug == slug)
    ).scalar_one_or_none() is not None:
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    # Generate or validate code prefix
    code_prefix = body.card_code_prefix
    
    project = Project(
        tenant_id=tenant.id,
        owner_user_id=user.id,
        slug=slug,
        name=body.name,
        objective=body.objective,
        context_md=body.context_md,
        card_code_prefix=code_prefix,
        card_template=body.card_template.value,
        grouping=Grouping.PHASE.value,
        status=ProjectStatus.DRAFT.value,
        project_type=body.project_type.value,
        source_technology=body.source_technology,
        target_technology=body.target_technology,
        llm_provider=body.llm_provider.value,
        llm_model=body.llm_model,
    )
    session.add(project)
    session.flush()
    
    return _to_view(project)


@router.get("/api/projects/{project_ref}", response_model=ProjectView)
def get_project(
    project_ref: str,
    session: Session = Depends(get_session),
) -> ProjectView:
    """Return a single project by ID (UUID) or slug."""
    row = _get_project_by_ref(session, project_ref)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Project {project_ref} not found")
    return _to_view(row)
