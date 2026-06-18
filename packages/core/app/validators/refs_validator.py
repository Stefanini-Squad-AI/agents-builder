"""References validator for skill links, input paths, and cross-references."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.db
from app.domain.backlog import Card, CardInput, CardSkill, Phase
from app.domain.projects import Project
from app.domain.skills import Skill, SkillResource
from app.enums import CardInputKind
from app.schemas.common import ValidationIssue
from app.validators.base import BaseValidator


class ReferencesValidator(BaseValidator):
    """Validates cross-references between project entities."""

    def validate(self, project_slug: str) -> list[ValidationIssue]:
        """Validate all references within a project."""
        issues = []

        with app.db.session_scope() as session:
            # Load project with full reference structure
            project_query = select(Project).where(
                Project.slug == project_slug
            ).options(
                selectinload(Project.phases).selectinload(Phase.cards).selectinload(Card.skill_links).selectinload(CardSkill.skill),
                selectinload(Project.phases).selectinload(Phase.cards).selectinload(Card.inputs),
                selectinload(Project.skills).selectinload(Skill.resources)
            )
            project = session.execute(project_query).scalar_one_or_none()

            if not project:
                issues.append(self.create_issue(
                    "error",
                    "refs.project_not_found",
                    f"Project '{project_slug}' not found",
                    {"project_slug": project_slug}
                ))
                return issues

            # Run reference validations
            issues.extend(self._validate_card_skill_references(project, project_slug))
            issues.extend(self._validate_card_input_references(project, project_slug))
            issues.extend(self._validate_unused_skills(project, project_slug))
            issues.extend(self._validate_skill_resource_references(project, project_slug))

        return issues

    def _validate_card_skill_references(self, project: Project, project_slug: str) -> list[ValidationIssue]:
        """Validate that cards reference existing skills."""
        issues = []

        # Build skill lookup
        project_skills = {skill.id: skill for skill in project.skills}

        for phase in project.phases:
            for card in phase.cards:
                if not card.skill_links:
                    issues.append(self.create_issue(
                        "warning",
                        "refs.card_no_skills",
                        f"Card {card.code} has no associated skills",
                        {
                            "project_slug": project_slug,
                            "card_code": card.code,
                            "phase_code": phase.code
                        }
                    ))
                    continue

                for skill_link in card.skill_links:
                    if skill_link.skill_id not in project_skills:
                        issues.append(self.create_issue(
                            "error",
                            "refs.card_invalid_skill",
                            f"Card {card.code} references non-existent skill ID: {skill_link.skill_id}",
                            {
                                "project_slug": project_slug,
                                "card_code": card.code,
                                "skill_id": str(skill_link.skill_id)
                            }
                        ))

        return issues

    def _validate_card_input_references(self, project: Project, project_slug: str) -> list[ValidationIssue]:
        """Validate card input path references."""
        issues = []

        # Build skill resources lookup for skill_resource inputs
        skill_resources = {}
        for skill in project.skills:
            for resource in skill.resources:
                resource_path = f".agents/skills/{skill.slug}/resources/{resource.filename}"
                skill_resources[resource_path] = resource

        for phase in project.phases:
            for card in phase.cards:
                for input_item in card.inputs:
                    issues.extend(self._validate_single_input(
                        input_item, card, phase, project_slug, skill_resources
                    ))

        return issues

    def _validate_single_input(
        self,
        input_item: CardInput,
        card: Card,
        phase: Phase,
        project_slug: str,
        skill_resources: dict[str, SkillResource]
    ) -> list[ValidationIssue]:
        """Validate a single card input."""
        issues = []

        if input_item.kind == CardInputKind.SKILL_RESOURCE:
            # Validate skill resource path
            if not input_item.path.startswith(".agents/skills/"):
                issues.append(self.create_issue(
                    "error",
                    "refs.invalid_skill_resource_path",
                    f"Skill resource path must start with '.agents/skills/': {input_item.path}",
                    {
                        "project_slug": project_slug,
                        "card_code": card.code,
                        "input_path": input_item.path
                    }
                ))
            elif input_item.path not in skill_resources:
                issues.append(self.create_issue(
                    "error",
                    "refs.missing_skill_resource",
                    f"Card {card.code} references non-existent skill resource: {input_item.path}",
                    {
                        "project_slug": project_slug,
                        "card_code": card.code,
                        "input_path": input_item.path
                    }
                ))

        elif input_item.kind == CardInputKind.ARTIFACT:
            # Validate artifact path (should be under data/projects/{project_slug}/artifacts/)
            expected_prefix = f"data/projects/{project_slug}/artifacts/"
            if not input_item.path.startswith(expected_prefix):
                issues.append(self.create_issue(
                    "warning",
                    "refs.invalid_artifact_path",
                    f"Artifact path should start with '{expected_prefix}': {input_item.path}",
                    {
                        "project_slug": project_slug,
                        "card_code": card.code,
                        "input_path": input_item.path
                    }
                ))
            else:
                # Check if artifact file exists (if we're in a filesystem context)
                full_path = Path(input_item.path)
                if not full_path.exists():
                    issues.append(self.create_issue(
                        "warning",
                        "refs.missing_artifact_file",
                        f"Card {card.code} references artifact file that doesn't exist: {input_item.path}",
                        {
                            "project_slug": project_slug,
                            "card_code": card.code,
                            "input_path": input_item.path
                        }
                    ))

        elif input_item.kind == CardInputKind.EXTERNAL:
            # Validate external reference format (basic URL or path format check)
            if not input_item.path.strip():
                issues.append(self.create_issue(
                    "error",
                    "refs.empty_external_path",
                    f"Card {card.code} has empty external reference path",
                    {
                        "project_slug": project_slug,
                        "card_code": card.code
                    }
                ))
            elif input_item.path.startswith(("http://", "https://")) and " " in input_item.path:
                # Basic URL validation - could be enhanced with actual URL parsing
                issues.append(self.create_issue(
                    "warning",
                    "refs.invalid_url_format",
                    f"External URL contains spaces: {input_item.path}",
                    {
                        "project_slug": project_slug,
                        "card_code": card.code,
                        "input_path": input_item.path
                    }
                ))

        return issues

    def _validate_unused_skills(self, project: Project, project_slug: str) -> list[ValidationIssue]:
        """Find skills that aren't used by any card."""
        issues = []

        # Collect used skill IDs
        used_skill_ids = set()
        for phase in project.phases:
            for card in phase.cards:
                for skill_link in card.skill_links:
                    used_skill_ids.add(skill_link.skill_id)

        # Check each skill
        for skill in project.skills:
            if skill.id not in used_skill_ids:
                issues.append(self.create_issue(
                    "warning",
                    "refs.unused_skill",
                    f"Skill '{skill.slug}' is not used by any card",
                    {
                        "project_slug": project_slug,
                        "skill_slug": skill.slug,
                        "skill_name": skill.name
                    }
                ))

        return issues

    def _validate_skill_resource_references(self, project: Project, project_slug: str) -> list[ValidationIssue]:
        """Validate skill resources are properly structured."""
        issues = []

        for skill in project.skills:
            # Check skill has resources
            if not skill.resources:
                issues.append(self.create_issue(
                    "warning",
                    "refs.skill_no_resources",
                    f"Skill '{skill.slug}' has no resources defined",
                    {
                        "project_slug": project_slug,
                        "skill_slug": skill.slug
                    }
                ))
                continue

            # Validate resource filenames
            for resource in skill.resources:
                if not resource.filename:
                    issues.append(self.create_issue(
                        "error",
                        "refs.empty_resource_filename",
                        f"Skill '{skill.slug}' has resource with empty filename",
                        {
                            "project_slug": project_slug,
                            "skill_slug": skill.slug,
                            "resource_id": str(resource.id)
                        }
                    ))

                # Check for duplicate resource filenames within skill
                resource_filenames = [r.filename for r in skill.resources if r.filename]
                if len(resource_filenames) != len(set(resource_filenames)):
                    duplicates = [fn for fn in resource_filenames if resource_filenames.count(fn) > 1]
                    issues.append(self.create_issue(
                        "warning",
                        "refs.duplicate_resource_filename",
                        f"Skill '{skill.slug}' has duplicate resource filenames: {', '.join(set(duplicates))}",
                        {
                            "project_slug": project_slug,
                            "skill_slug": skill.slug,
                            "duplicate_filenames": ",".join(set(duplicates))
                        }
                    ))

        return issues

    def get_reference_statistics(self, project_slug: str) -> dict[str, int]:
        """Get statistics about project references for reporting.

        Returns:
            Dictionary with counts of various reference types
        """
        stats = {
            "total_cards": 0,
            "cards_with_skills": 0,
            "cards_with_inputs": 0,
            "total_skill_links": 0,
            "total_inputs": 0,
            "skill_resource_inputs": 0,
            "artifact_inputs": 0,
            "external_inputs": 0,
            "unused_skills": 0
        }

        with app.db.session_scope() as session:
            project_query = select(Project).where(
                Project.slug == project_slug
            ).options(
                selectinload(Project.phases).selectinload(Phase.cards).selectinload(Card.skill_links),
                selectinload(Project.phases).selectinload(Phase.cards).selectinload(Card.inputs),
                selectinload(Project.skills)
            )
            project = session.execute(project_query).scalar_one_or_none()

            if not project:
                return stats

            # Count cards and references
            used_skill_ids = set()
            for phase in project.phases:
                for card in phase.cards:
                    stats["total_cards"] += 1

                    if card.skill_links:
                        stats["cards_with_skills"] += 1
                        stats["total_skill_links"] += len(card.skill_links)
                        for skill_link in card.skill_links:
                            used_skill_ids.add(skill_link.skill_id)

                    if card.inputs:
                        stats["cards_with_inputs"] += 1
                        stats["total_inputs"] += len(card.inputs)

                        for input_item in card.inputs:
                            if input_item.kind == CardInputKind.SKILL_RESOURCE:
                                stats["skill_resource_inputs"] += 1
                            elif input_item.kind == CardInputKind.ARTIFACT:
                                stats["artifact_inputs"] += 1
                            elif input_item.kind == CardInputKind.EXTERNAL:
                                stats["external_inputs"] += 1

            # Count unused skills
            stats["unused_skills"] = len([skill for skill in project.skills if skill.id not in used_skill_ids])

        return stats
