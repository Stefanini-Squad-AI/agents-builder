"""Export API — Validation, preview, and export.

Endpoints:
- POST /api/projects/{slug}/validate           validate project
- GET  /api/projects/{slug}/export/preview     get export tree structure
- POST /api/projects/{slug}/export/zip         download zip archive
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.domain.backlog import Card, Phase
from app.domain.projects import Project
from app.domain.skills import Skill
from app.enums import ExportKind
from app.exporters import create_exporter
from app.exporters.base import ExportManifest
from app.schemas.common import ValidationIssue, ValidationSeverity
from app.validators import validate_project, get_validation_summary

router = APIRouter(tags=["export"])


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class ValidationResponse(BaseModel):
    """Response from project validation."""

    valid: bool
    error_count: int
    warning_count: int
    issues: list[dict[str, Any]]


class ExportTreeNode(BaseModel):
    """A node in the export tree."""

    name: str
    type: str  # "file" or "directory"
    size: int | None = None
    children: list["ExportTreeNode"] = Field(default_factory=list)


class ExportPreviewResponse(BaseModel):
    """Response from export preview."""

    tree: list[ExportTreeNode]
    total_files: int
    total_size_bytes: int


class ExportHistoryItem(BaseModel):
    """An export history entry."""

    id: UUID
    kind: str
    created_at: str
    file_count: int
    size_bytes: int


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def _get_project_by_slug(session: Session, slug: str) -> Project:
    """Get project by slug or raise 404."""
    project = session.execute(
        select(Project).where(Project.slug == slug)
    ).scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")

    return project


def _build_export_tree(project_slug: str, session: Session) -> tuple[list[ExportTreeNode], int, int]:
    """Build a preview of the export tree structure.
    
    Returns (tree, total_files, total_bytes).
    """
    # Load project with relationships
    project = session.execute(
        select(Project)
        .where(Project.slug == project_slug)
        .options(
            selectinload(Project.phases).selectinload(Phase.cards),
            selectinload(Project.skills).selectinload(Skill.resources),
        )
    ).scalar_one_or_none()

    if not project:
        return [], 0, 0

    total_files = 0
    total_bytes = 0

    # Build skills subtree
    skills_children: list[ExportTreeNode] = []
    for skill in sorted(project.skills, key=lambda s: s.order_no):
        skill_children: list[ExportTreeNode] = []
        
        # SKILL.md file (estimate size)
        skill_md_size = len(skill.body_md or "") + 200  # frontmatter overhead
        skill_children.append(ExportTreeNode(
            name="SKILL.md",
            type="file",
            size=skill_md_size,
        ))
        total_files += 1
        total_bytes += skill_md_size

        # Resources folder if has resources
        if skill.resources:
            resources_children: list[ExportTreeNode] = []
            for resource in sorted(skill.resources, key=lambda r: r.order_no):
                resource_size = len(resource.content or "")
                resources_children.append(ExportTreeNode(
                    name=resource.filename,
                    type="file",
                    size=resource_size,
                ))
                total_files += 1
                total_bytes += resource_size

            skill_children.append(ExportTreeNode(
                name="resources",
                type="directory",
                children=resources_children,
            ))

        skills_children.append(ExportTreeNode(
            name=skill.slug,
            type="directory",
            children=skill_children,
        ))

    # Build jira-cards subtree
    jira_children: list[ExportTreeNode] = []
    
    for phase in sorted(project.phases, key=lambda p: p.order_no):
        phase_children: list[ExportTreeNode] = []
        
        # Phase README.md
        readme_size = 500  # estimate
        phase_children.append(ExportTreeNode(
            name="README.md",
            type="file",
            size=readme_size,
        ))
        total_files += 1
        total_bytes += readme_size

        # Card files
        for card in sorted(phase.cards, key=lambda c: c.order_no):
            card_size = sum(len(s or "") for s in [
                card.context_md, card.task_md, card.outputs_md, 
                card.acceptance_criteria_md, card.human_gate_checklist_md
            ]) + 300  # frontmatter overhead
            
            # Sanitize title for filename
            title_slug = (card.title or "untitled").lower()
            title_slug = "".join(c if c.isalnum() or c == "-" else "-" for c in title_slug)
            title_slug = "-".join(filter(None, title_slug.split("-")))[:50]
            
            phase_children.append(ExportTreeNode(
                name=f"{card.code}-{title_slug}.md",
                type="file",
                size=card_size,
            ))
            total_files += 1
            total_bytes += card_size

        # Create phase folder name
        phase_name_slug = (phase.name or phase.code).lower()
        phase_name_slug = "".join(c if c.isalnum() or c == "-" else "-" for c in phase_name_slug)
        phase_name_slug = "-".join(filter(None, phase_name_slug.split("-")))[:50]

        jira_children.append(ExportTreeNode(
            name=f"{phase.code}-{phase_name_slug}",
            type="directory",
            children=phase_children,
        ))

    # Project README.md in jira-cards
    project_readme_size = 2000  # estimate for mermaid diagram
    jira_children.append(ExportTreeNode(
        name="README.md",
        type="file",
        size=project_readme_size,
    ))
    total_files += 1
    total_bytes += project_readme_size

    # Build .agents root
    agents_children: list[ExportTreeNode] = [
        ExportTreeNode(name="skills", type="directory", children=skills_children),
        ExportTreeNode(name="jira-cards", type="directory", children=jira_children),
    ]

    # MANIFEST.json
    manifest_size = 500  # estimate
    agents_children.append(ExportTreeNode(
        name="MANIFEST.json",
        type="file",
        size=manifest_size,
    ))
    total_files += 1
    total_bytes += manifest_size

    root = [ExportTreeNode(name=".agents", type="directory", children=agents_children)]

    return root, total_files, total_bytes


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/api/projects/{slug}/validate",
    response_model=ValidationResponse,
)
def validate_project_endpoint(
    slug: str,
    session: Session = Depends(get_session),
) -> ValidationResponse:
    """Run all validators on a project.
    
    Returns validation status and any issues found.
    """
    # Verify project exists
    _get_project_by_slug(session, slug)

    # Run validation
    issues = validate_project(slug)
    summary = get_validation_summary(issues)

    # Convert issues to dict format
    issues_dict = [
        {
            "severity": issue.severity.value,
            "code": issue.code,
            "message": issue.message,
            "location": issue.location,
        }
        for issue in issues
    ]

    return ValidationResponse(
        valid=summary["error_count"] == 0,
        error_count=summary["error_count"],
        warning_count=summary["warning_count"],
        issues=issues_dict,
    )


@router.get(
    "/api/projects/{slug}/export/preview",
    response_model=ExportPreviewResponse,
)
def get_export_preview(
    slug: str,
    session: Session = Depends(get_session),
) -> ExportPreviewResponse:
    """Get a preview of the export tree structure.
    
    Returns the directory/file structure that would be created on export.
    """
    # Verify project exists
    _get_project_by_slug(session, slug)

    # Build tree
    tree, total_files, total_bytes = _build_export_tree(slug, session)

    return ExportPreviewResponse(
        tree=tree,
        total_files=total_files,
        total_size_bytes=total_bytes,
    )


@router.post(
    "/api/projects/{slug}/export/zip",
)
def export_zip(
    slug: str,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Export project as a ZIP archive.
    
    Returns a streaming ZIP file download.
    """
    # Verify project exists
    project = _get_project_by_slug(session, slug)

    # Create temporary file for ZIP
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp_path = Path(tmp.name)

    try:
        # Create ZIP exporter and export
        exporter = create_exporter(ExportKind.ZIP, output_file=tmp_path)
        manifest = exporter.export_project(slug)

        # Read the ZIP file
        zip_data = tmp_path.read_bytes()

        # Create streaming response
        return StreamingResponse(
            io.BytesIO(zip_data),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{slug}.agents.zip"',
                "Content-Length": str(len(zip_data)),
            },
        )

    finally:
        # Clean up temp file
        try:
            tmp_path.unlink()
        except Exception:
            pass
