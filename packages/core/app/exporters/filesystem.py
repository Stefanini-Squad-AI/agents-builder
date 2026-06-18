"""Filesystem exporter for generating .agents/ directory structure."""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.db
from app.domain.backlog import Card, Phase
from app.domain.projects import Project
from app.domain.skills import Skill
from app.enums import ExportKind
from app.exporters.base import BaseExporter, ExportError, ExportManifest
from app.families._base import (
    CardDraftContext,
    GroupingReadmeContext,
    ProjectReadmeContext,
    TemplateFamily,
)
from app.families.phase_vli.family import PhaseVliFamily
from app.schemas.views import (
    CardLinkView,
    CardView,
    PhaseView,
    ProjectView,
    SkillView,
)
from app.view_mappers import card_to_view, skill_to_view


class FilesystemExporter(BaseExporter):
    """Exports projects to filesystem .agents/ directory structure."""

    def __init__(self, target_path: Path) -> None:
        """Initialize filesystem exporter.
        
        Args:
            target_path: Directory where .agents/ folder will be created
        """
        super().__init__()
        self.target_path = Path(target_path)
        self.agents_path = self.target_path / ".agents"

    def export_project(self, project_slug: str) -> ExportManifest:
        """Export a complete project to filesystem.
        
        Args:
            project_slug: Project to export
            
        Returns:
            Manifest of exported files
        """
        self._start_export(project_slug)
        
        try:
            # Load project data
            project_data = self._load_project_data(project_slug)
            if not project_data:
                raise ExportError(f"Project '{project_slug}' not found", project_slug)
            
            project, phases, cards, skills = project_data
            
            # Convert to view models
            project_view = self._to_project_view(project)
            phase_views = [self._to_phase_view(phase) for phase in phases]
            card_views = [card_to_view(card) for card in cards]
            skill_views = [skill_to_view(skill) for skill in skills]
            
            # Get template family (default to PhaseVli for now)
            template_family = PhaseVliFamily()
            
            # Precompute cross-card link targets (code -> resolved link) so
            # rendered cards/READMEs point at the actual on-disk files.
            card_links = self._build_card_links(
                template_family, phase_views, card_views
            )
            
            # Create export directory structure
            self._create_directory_structure(template_family, phase_views)
            
            # Export project README
            self._export_project_readme(
                template_family, project_view, phase_views, card_views, skill_views
            )
            
            # Export skills
            self._export_skills(skill_views, template_family)
            
            # Export cards by phase
            for phase_view in phase_views:
                phase_cards = [c for c in card_views if c.phase_id == phase_view.id]
                self._export_phase(
                    template_family,
                    project_view,
                    phase_view,
                    phase_cards,
                    skill_views,
                    card_links,
                )
            
            return self._finish_export(project_slug, ExportKind.FILESYSTEM.value)
            
        except Exception as e:
            if isinstance(e, ExportError):
                raise
            raise ExportError(f"Export failed: {str(e)}", project_slug, e) from e

    def _write_file(self, relative_path: str, content: str | bytes) -> None:
        """Write a file to the filesystem export destination."""
        full_path = self.agents_path / relative_path
        
        # Ensure parent directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        if isinstance(content, str):
            full_path.write_text(content, encoding='utf-8')
        else:
            full_path.write_bytes(content)
        
        # Track the file
        self._add_file(relative_path, content)

    def _load_project_data(
        self, project_slug: str
    ) -> tuple[Project, list[Phase], list[Card], list[Skill]] | None:
        """Load complete project data with all relationships."""
        with app.db.session_scope() as session:
            # Load project with all relationships
            project_query = select(Project).where(
                Project.slug == project_slug
            ).options(
                selectinload(Project.phases).selectinload(Phase.cards).selectinload(Card.skill_links),
                selectinload(Project.phases).selectinload(Phase.cards).selectinload(Card.deps_out),
                selectinload(Project.phases).selectinload(Phase.cards).selectinload(Card.inputs),
                selectinload(Project.skills).selectinload(Skill.resources),
            )
            
            result = session.execute(project_query)
            project = result.scalar_one_or_none()
            
            if not project:
                return None
            
            # Flatten collections for easier processing
            phases = list(project.phases)
            cards = []
            for phase in phases:
                cards.extend(phase.cards)
            skills = list(project.skills)
            
            return project, phases, cards, skills

    def _create_directory_structure(
        self, template_family: TemplateFamily, phases: list[PhaseView]
    ) -> None:
        """Create the basic directory structure."""
        # Create main directories - these are created relative to agents_path
        main_dirs = [
            self.agents_path / "skills",
            self.agents_path / "jira-cards",
        ]
        
        for dir_path in main_dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create phase directories
        for phase in phases:
            folder_name = template_family.get_grouping_folder_name(phase)
            phase_path = self.agents_path / "jira-cards" / folder_name
            phase_path.mkdir(parents=True, exist_ok=True)

    def _export_project_readme(
        self,
        template_family: TemplateFamily,
        project: ProjectView,
        phases: list[PhaseView],
        cards: list[CardView],
        skills: list[SkillView]
    ) -> None:
        """Export the main project README."""
        context = ProjectReadmeContext(
            project=project,
            phases=phases,
            all_cards=cards,
            all_skills=skills
        )
        
        readme_content = template_family.render_project_readme(context)
        self._write_file("README.md", readme_content)

    def _export_skills(self, skills: list[SkillView], template_family: TemplateFamily) -> None:
        """Export all project skills."""
        for skill in skills:
            # Create skill directory
            skill_dir = f"skills/{skill.slug}"
            
            # Export SKILL.md
            skill_content = self._render_skill_file(skill)
            self._write_file(f"{skill_dir}/SKILL.md", skill_content)
            
            # Export resources if any
            if skill.resources:
                resources_dir = f"{skill_dir}/resources"
                for resource in skill.resources:
                    if resource.filename and resource.content:
                        resource_path = f"{resources_dir}/{resource.filename}"
                        self._write_file(resource_path, resource.content)

    def _build_card_links(
        self,
        template_family: TemplateFamily,
        phases: list[PhaseView],
        cards: list[CardView],
    ) -> dict[str, CardLinkView]:
        """Build a code -> link-target map using the same folder/filename logic
        that creates the files, so all cross-card links resolve correctly."""
        phase_by_id = {phase.id: phase for phase in phases}
        links: dict[str, CardLinkView] = {}
        for card in cards:
            phase = phase_by_id.get(card.phase_id)
            if not phase:
                continue
            links[card.code] = CardLinkView(
                code=card.code,
                title=card.title,
                phase_folder=template_family.get_grouping_folder_name(phase),
                filename=template_family.get_card_filename(card),
            )
        return links

    def _export_phase(
        self,
        template_family: TemplateFamily,
        project: ProjectView,
        phase: PhaseView,
        cards: list[CardView],
        all_skills: list[SkillView],
        card_links: dict[str, CardLinkView],
    ) -> None:
        """Export a phase with its cards and README."""
        folder_name = template_family.get_grouping_folder_name(phase)
        phase_dir = f"jira-cards/{folder_name}"
        
        # Export phase README
        referenced_skills = self._get_skills_referenced_by_cards(cards, all_skills)
        readme_context = GroupingReadmeContext(
            project=project,
            grouping=phase,
            cards=cards,
            skills_referenced=referenced_skills,
            card_links=card_links,
        )
        
        readme_content = template_family.render_grouping_readme(readme_context)
        self._write_file(f"{phase_dir}/README.md", readme_content)
        
        # Export individual cards
        for card in sorted(cards, key=lambda c: c.order_no or 0):
            card_skills = self._get_skills_for_card(card, all_skills)
            sibling_cards = [c for c in cards if c.id != card.id]

            depends_on_links = [
                card_links[code] for code in card.depends_on_codes if code in card_links
            ]
            parallel_with_links = [
                card_links[code] for code in card.parallel_with_codes if code in card_links
            ]

            card_context = CardDraftContext(
                project=project,
                project_context="",
                phase=phase,
                card=card,
                skills_used=card_skills,
                sibling_cards_in_phase=sibling_cards,
                upstream_cards=[],
                depends_on_links=depends_on_links,
                parallel_with_links=parallel_with_links,
            )
            
            card_content = template_family.render_card(card, card_context)
            card_filename = template_family.get_card_filename(card)
            self._write_file(f"{phase_dir}/{card_filename}.md", card_content)

    def _render_skill_file(self, skill: SkillView) -> str:
        """Render a skill to its SKILL.md format."""
        lines = []
        
        # YAML frontmatter
        lines.append("---")
        lines.append(f"name: {skill.name}")
        lines.append(f"description: {skill.description}")
        lines.append(f"kind: {skill.kind}")
        lines.append("---")
        lines.append("")
        
        # Body content
        if skill.body_md:
            lines.append(skill.body_md)
        else:
            lines.append("_Skill content will be added during development._")
        
        return "\n".join(lines)

    def _get_skills_referenced_by_cards(
        self, cards: list[CardView], all_skills: list[SkillView]
    ) -> list[SkillView]:
        """Get all skills referenced by the given cards (by slug)."""
        referenced_slugs: set[str] = set()
        for card in cards:
            referenced_slugs.update(card.skill_slugs)

        return [skill for skill in all_skills if skill.slug in referenced_slugs]

    def _get_skills_for_card(self, card: CardView, all_skills: list[SkillView]) -> list[SkillView]:
        """Get skills assigned to a specific card (by slug, preserving card order)."""
        by_slug = {skill.slug: skill for skill in all_skills}
        return [by_slug[slug] for slug in card.skill_slugs if slug in by_slug]

    def _to_project_view(self, project: Project) -> ProjectView:
        """Convert Project ORM to ProjectView."""
        return ProjectView.model_validate(project)

    def _to_phase_view(self, phase: Phase) -> PhaseView:
        """Convert Phase ORM to PhaseView (cards are built separately)."""
        return PhaseView(
            id=phase.id,
            project_id=phase.project_id,
            code=phase.code,
            name=phase.name,
            description_md=phase.description_md,
            order_no=phase.order_no,
        )