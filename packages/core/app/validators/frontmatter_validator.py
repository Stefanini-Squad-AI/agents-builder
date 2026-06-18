"""Frontmatter validator for YAML structure and field validation."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.db
from app.domain.backlog import Card, Phase
from app.domain.projects import Project
from app.domain.skills import Skill
from app.enums import CardStatus, CardType, Priority, SkillKind
from app.schemas.common import ValidationIssue
from app.validators.base import BaseValidator


class FrontmatterValidator(BaseValidator):
    """Validates YAML frontmatter structure and required fields."""

    def validate(self, project_slug: str) -> list[ValidationIssue]:
        """Validate frontmatter structure for all project entities."""
        issues = []

        with app.db.session_scope() as session:
            # Load project with skills and cards
            project_query = select(Project).where(
                Project.slug == project_slug
            ).options(
                selectinload(Project.phases).selectinload(Phase.cards),
                selectinload(Project.skills)
            )
            project = session.execute(project_query).scalar_one_or_none()

            if not project:
                issues.append(self.create_issue(
                    "error",
                    "frontmatter.project_not_found",
                    f"Project '{project_slug}' not found",
                    {"project_slug": project_slug}
                ))
                return issues

            # Validate project frontmatter
            issues.extend(self._validate_project_frontmatter(project, project_slug))

            # Validate skill frontmatter
            for skill in project.skills:
                issues.extend(self._validate_skill_frontmatter(skill, project_slug))

            # Validate card frontmatter
            for phase in project.phases:
                for card in phase.cards:
                    issues.extend(self._validate_card_frontmatter(card, phase, project_slug))

        return issues

    def _validate_project_frontmatter(self, project: Project, project_slug: str) -> list[ValidationIssue]:
        """Validate project-level frontmatter requirements."""
        issues = []

        # Check required project fields
        if not project.name or not project.name.strip():
            issues.append(self.create_issue(
                "error",
                "frontmatter.project_missing_name",
                "Project name is required and cannot be empty",
                {"project_slug": project_slug}
            ))

        if not project.objective or not project.objective.strip():
            issues.append(self.create_issue(
                "error",
                "frontmatter.project_missing_objective",
                "Project objective is required and cannot be empty",
                {"project_slug": project_slug}
            ))

        # Validate slug format (kebab-case)
        if not self._is_valid_slug(project.slug):
            issues.append(self.create_issue(
                "error",
                "frontmatter.project_invalid_slug",
                f"Project slug '{project.slug}' must be kebab-case (lowercase with hyphens)",
                {"project_slug": project_slug}
            ))

        # Validate card code prefix
        if not project.card_code_prefix or not project.card_code_prefix.strip():
            issues.append(self.create_issue(
                "error",
                "frontmatter.project_missing_code_prefix",
                "Project card_code_prefix is required",
                {"project_slug": project_slug}
            ))
        elif not re.match(r'^[A-Z][A-Z0-9-]*$', project.card_code_prefix):
            issues.append(self.create_issue(
                "warning",
                "frontmatter.project_invalid_code_prefix",
                f"Card code prefix '{project.card_code_prefix}' should be uppercase letters/numbers/hyphens",
                {"project_slug": project_slug, "code_prefix": project.card_code_prefix}
            ))

        return issues

    def _validate_skill_frontmatter(self, skill: Skill, project_slug: str) -> list[ValidationIssue]:
        """Validate skill frontmatter structure."""
        issues = []

        # Check required skill fields
        if not skill.name or not skill.name.strip():
            issues.append(self.create_issue(
                "error",
                "frontmatter.skill_missing_name",
                f"Skill '{skill.slug}' is missing required name field",
                {"project_slug": project_slug, "skill_slug": skill.slug}
            ))

        if not skill.description or not skill.description.strip():
            issues.append(self.create_issue(
                "error",
                "frontmatter.skill_missing_description",
                f"Skill '{skill.slug}' is missing required description field",
                {"project_slug": project_slug, "skill_slug": skill.slug}
            ))

        # Validate slug format
        if not self._is_valid_slug(skill.slug):
            issues.append(self.create_issue(
                "error",
                "frontmatter.skill_invalid_slug",
                f"Skill slug '{skill.slug}' must be kebab-case (lowercase with hyphens)",
                {"project_slug": project_slug, "skill_slug": skill.slug}
            ))

        # Validate skill kind
        if skill.kind not in [kind.value for kind in SkillKind]:
            issues.append(self.create_issue(
                "error",
                "frontmatter.skill_invalid_kind",
                f"Skill '{skill.slug}' has invalid kind: {skill.kind}",
                {"project_slug": project_slug, "skill_slug": skill.slug, "kind": skill.kind}
            ))

        # Validate body_md is present
        if not skill.body_md or not skill.body_md.strip():
            issues.append(self.create_issue(
                "error",
                "frontmatter.skill_missing_body",
                f"Skill '{skill.slug}' is missing required body markdown",
                {"project_slug": project_slug, "skill_slug": skill.slug}
            ))

        return issues

    def _validate_card_frontmatter(self, card: Card, phase: Phase, project_slug: str) -> list[ValidationIssue]:
        """Validate card frontmatter structure."""
        issues = []

        # Check required card fields
        if not card.code or not card.code.strip():
            issues.append(self.create_issue(
                "error",
                "frontmatter.card_missing_code",
                "Card is missing required code field",
                {"project_slug": project_slug, "phase_code": phase.code, "card_id": str(card.id)}
            ))

        if not card.title or not card.title.strip():
            issues.append(self.create_issue(
                "error",
                "frontmatter.card_missing_title",
                f"Card '{card.code}' is missing required title field",
                {"project_slug": project_slug, "card_code": card.code}
            ))

        # Validate card code format (should match project prefix)
        if card.code:
            expected_prefix = card.phase.project.card_code_prefix
            if not card.code.startswith(expected_prefix):
                issues.append(self.create_issue(
                    "warning",
                    "frontmatter.card_code_wrong_prefix",
                    f"Card '{card.code}' should start with project prefix '{expected_prefix}'",
                    {
                        "project_slug": project_slug,
                        "card_code": card.code,
                        "expected_prefix": expected_prefix
                    }
                ))

            # Check code format (prefix + number)
            suffix = card.code[len(expected_prefix):] if card.code.startswith(expected_prefix) else card.code
            if suffix and not re.match(r'^-?\d+$', suffix):
                issues.append(self.create_issue(
                    "warning",
                    "frontmatter.card_code_invalid_format",
                    f"Card code '{card.code}' should follow pattern '{expected_prefix}-###'",
                    {"project_slug": project_slug, "card_code": card.code}
                ))

        # Validate enums
        if card.type not in [ctype.value for ctype in CardType]:
            issues.append(self.create_issue(
                "error",
                "frontmatter.card_invalid_type",
                f"Card '{card.code}' has invalid type: {card.type}",
                {"project_slug": project_slug, "card_code": card.code, "type": card.type}
            ))

        if card.status not in [status.value for status in CardStatus]:
            issues.append(self.create_issue(
                "error",
                "frontmatter.card_invalid_status",
                f"Card '{card.code}' has invalid status: {card.status}",
                {"project_slug": project_slug, "card_code": card.code, "status": card.status}
            ))

        if card.priority and card.priority not in [priority.value for priority in Priority]:
            issues.append(self.create_issue(
                "error",
                "frontmatter.card_invalid_priority",
                f"Card '{card.code}' has invalid priority: {card.priority}",
                {"project_slug": project_slug, "card_code": card.code, "priority": card.priority}
            ))

        # Validate story points
        if card.story_points is not None:
            if card.story_points < 0:
                issues.append(self.create_issue(
                    "warning",
                    "frontmatter.card_negative_story_points",
                    f"Card '{card.code}' has negative story points: {card.story_points}",
                    {"project_slug": project_slug, "card_code": card.code}
                ))
            elif card.story_points > 100:
                issues.append(self.create_issue(
                    "warning",
                    "frontmatter.card_excessive_story_points",
                    f"Card '{card.code}' has unusually high story points: {card.story_points}",
                    {"project_slug": project_slug, "card_code": card.code}
                ))

        # Validate human gate consistency
        if card.human_gate and not card.human_gate_checklist_md:
            issues.append(self.create_issue(
                "error",
                "frontmatter.card_human_gate_missing_checklist",
                f"Card '{card.code}' has human_gate=true but no checklist provided",
                {"project_slug": project_slug, "card_code": card.code}
            ))
        elif not card.human_gate and card.human_gate_checklist_md:
            issues.append(self.create_issue(
                "warning",
                "frontmatter.card_human_gate_unnecessary_checklist",
                f"Card '{card.code}' has human_gate=false but checklist provided",
                {"project_slug": project_slug, "card_code": card.code}
            ))

        # Validate markdown sections exist (basic check)
        if card.status not in [CardStatus.DRAFT.value]:  # Draft cards can have empty sections
            if not card.context_md or not card.context_md.strip():
                issues.append(self.create_issue(
                    "warning",
                    "frontmatter.card_missing_context",
                    f"Card '{card.code}' is missing context section",
                    {"project_slug": project_slug, "card_code": card.code}
                ))

            if not card.task_md or not card.task_md.strip():
                issues.append(self.create_issue(
                    "warning",
                    "frontmatter.card_missing_task",
                    f"Card '{card.code}' is missing task section",
                    {"project_slug": project_slug, "card_code": card.code}
                ))

            if not card.acceptance_criteria_md or not card.acceptance_criteria_md.strip():
                issues.append(self.create_issue(
                    "warning",
                    "frontmatter.card_missing_acceptance_criteria",
                    f"Card '{card.code}' is missing acceptance criteria section",
                    {"project_slug": project_slug, "card_code": card.code}
                ))

        return issues

    def _is_valid_slug(self, slug: str) -> bool:
        """Check if a slug follows kebab-case format."""
        if not slug:
            return False
        return bool(re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', slug))

    def _validate_yaml_structure(self, yaml_content: str, entity_type: str, entity_id: str) -> list[ValidationIssue]:
        """Validate YAML structure (for future use with exported files)."""
        issues = []

        # This would be used when validating actual exported YAML files
        # For now, we validate the database fields that would become YAML

        try:
            import yaml
            parsed = yaml.safe_load(yaml_content)

            if not isinstance(parsed, dict):
                issues.append(self.create_issue(
                    "error",
                    f"frontmatter.{entity_type}_yaml_not_dict",
                    f"YAML frontmatter must be a dictionary for {entity_type} {entity_id}",
                    {f"{entity_type}_id": entity_id}
                ))

        except yaml.YAMLError as e:
            issues.append(self.create_issue(
                "error",
                f"frontmatter.{entity_type}_yaml_invalid",
                f"Invalid YAML syntax in {entity_type} {entity_id}: {e!s}",
                {f"{entity_type}_id": entity_id}
            ))

        return issues

    def get_frontmatter_statistics(self, project_slug: str) -> dict[str, Any]:
        """Get statistics about project frontmatter for reporting."""
        stats = {
            "total_skills": 0,
            "skills_missing_fields": 0,
            "total_cards": 0,
            "cards_missing_fields": 0,
            "cards_with_human_gates": 0,
            "draft_cards": 0,
            "completed_cards": 0
        }

        with app.db.session_scope() as session:
            project_query = select(Project).where(
                Project.slug == project_slug
            ).options(
                selectinload(Project.phases).selectinload(Phase.cards),
                selectinload(Project.skills)
            )
            project = session.execute(project_query).scalar_one_or_none()

            if not project:
                return stats

            # Count skills
            for skill in project.skills:
                stats["total_skills"] += 1
                if not skill.name or not skill.description or not skill.body_md:
                    stats["skills_missing_fields"] += 1

            # Count cards
            for phase in project.phases:
                for card in phase.cards:
                    stats["total_cards"] += 1

                    if not card.code or not card.title:
                        stats["cards_missing_fields"] += 1

                    if card.human_gate:
                        stats["cards_with_human_gates"] += 1

                    if card.status == CardStatus.DRAFT.value:
                        stats["draft_cards"] += 1
                    elif card.status == CardStatus.DONE.value:
                        stats["completed_cards"] += 1

        return stats
