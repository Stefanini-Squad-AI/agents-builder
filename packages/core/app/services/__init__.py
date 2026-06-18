"""Service layer for business logic orchestration.

This package contains service classes that coordinate between domain models,
external systems, and provide high-level business operations:

- ProjectService: Project CRUD operations and management
- ExportService: Project export orchestration and audit logging
- DagService: Dependency analysis and visualization
- LlmService: Language model operations and prompt execution

Usage:
    from app.services import ProjectService, ExportService, DagService
    
    # Manage projects
    project_service = ProjectService()
    project = project_service.create_project("My Project", "my-project", "Build something cool", "PROJ")
    
    # Export project
    export_service = ExportService()
    manifest = export_service.export_project("my-project", "filesystem", target_path="./output")
    
    # Generate DAG
    dag_service = DagService()
    mermaid_content = dag_service.render_dag("my-project", "mermaid")
"""

from __future__ import annotations

from app.services.card_service import CardService
from app.services.dag_service import DagService
from app.services.export_service import ExportService
from app.services.llm_service_factory import LlmServiceFactory
from app.services.project_context_service import ProjectContextService
from app.services.project_service import ProjectService
from app.services.qa_service import QaService
from app.services.skill_service import SkillService
from app.services.tech_service import TechService

__all__ = [
    "ProjectService",
    "SkillService",
    "CardService", 
    "QaService",
    "TechService",
    "LlmServiceFactory",
    "ProjectContextService",
    "ExportService", 
    "DagService",
]