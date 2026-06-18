"""Paths validator for naming conventions and file structure."""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.db
from app.domain.backlog import Card, Phase
from app.domain.projects import Project
from app.domain.skills import Skill
from app.schemas.common import ValidationIssue
from app.validators.base import BaseValidator


class PathsValidator(BaseValidator):
    """Validates file paths, naming conventions, and directory structure."""

    def validate(self, project_slug: str) -> list[ValidationIssue]:
        """Validate paths and naming conventions for a project."""
        issues = []

        with app.db.session_scope() as session:
            # Load project with full structure
            project_query = select(Project).where(
                Project.slug == project_slug
            ).options(
                selectinload(Project.phases).selectinload(Phase.cards),
                selectinload(Project.skills).selectinload(Skill.resources)
            )
            project = session.execute(project_query).scalar_one_or_none()

            if not project:
                issues.append(self.create_issue(
                    "error",
                    "paths.project_not_found",
                    f"Project '{project_slug}' not found",
                    {"project_slug": project_slug}
                ))
                return issues

            # Validate project-level paths
            issues.extend(self._validate_project_paths(project, project_slug))

            # Validate skill paths and naming
            for skill in project.skills:
                issues.extend(self._validate_skill_paths(skill, project_slug))

            # Validate phase and card paths
            for phase in project.phases:
                issues.extend(self._validate_phase_paths(phase, project_slug))
                for card in phase.cards:
                    issues.extend(self._validate_card_paths(card, phase, project_slug))

            # Validate overall structure consistency
            issues.extend(self._validate_structure_consistency(project, project_slug))

        return issues

    def _validate_project_paths(self, project: Project, project_slug: str) -> list[ValidationIssue]:
        """Validate project-level path conventions."""
        issues = []

        # Validate project slug format for filesystem use
        if not self._is_valid_filesystem_name(project.slug):
            issues.append(self.create_issue(
                "error",
                "paths.project_invalid_filesystem_slug",
                f"Project slug '{project.slug}' contains characters invalid for filesystem paths",
                {"project_slug": project_slug}
            ))

        # Check project slug length (filesystem limits)
        if len(project.slug) > 100:
            issues.append(self.create_issue(
                "warning",
                "paths.project_slug_too_long",
                f"Project slug '{project.slug}' is very long ({len(project.slug)} chars), may cause path issues",
                {"project_slug": project_slug, "slug_length": str(len(project.slug))}
            ))

        return issues

    def _validate_skill_paths(self, skill: Skill, project_slug: str) -> list[ValidationIssue]:
        """Validate skill path conventions."""
        issues = []

        # Validate skill slug for filesystem use
        if not self._is_valid_filesystem_name(skill.slug):
            issues.append(self.create_issue(
                "error",
                "paths.skill_invalid_filesystem_slug",
                f"Skill slug '{skill.slug}' contains characters invalid for filesystem paths",
                {"project_slug": project_slug, "skill_slug": skill.slug}
            ))

        # Validate expected skill directory structure

        # Check skill resource paths
        resource_filenames = set()
        for resource in skill.resources:
            if not resource.filename:
                continue

            # Check for duplicate filenames
            if resource.filename in resource_filenames:
                issues.append(self.create_issue(
                    "error",
                    "paths.skill_duplicate_resource_filename",
                    f"Skill '{skill.slug}' has duplicate resource filename: {resource.filename}",
                    {
                        "project_slug": project_slug,
                        "skill_slug": skill.slug,
                        "filename": resource.filename
                    }
                ))
            resource_filenames.add(resource.filename)

            # Validate resource filename format
            if not self._is_valid_filename(resource.filename):
                issues.append(self.create_issue(
                    "error",
                    "paths.skill_invalid_resource_filename",
                    f"Skill '{skill.slug}' has invalid resource filename: {resource.filename}",
                    {
                        "project_slug": project_slug,
                        "skill_slug": skill.slug,
                        "filename": resource.filename
                    }
                ))

            # Check resource path would be under resources/

            # Validate resource file extension matches language
            if resource.language and resource.filename:
                expected_extensions = self._get_expected_extensions(resource.language)
                actual_extension = Path(resource.filename).suffix.lower()

                if expected_extensions and actual_extension not in expected_extensions:
                    issues.append(self.create_issue(
                        "warning",
                        "paths.skill_resource_extension_mismatch",
                        f"Resource '{resource.filename}' has extension '{actual_extension}' but language is '{resource.language}'",
                        {
                            "project_slug": project_slug,
                            "skill_slug": skill.slug,
                            "filename": resource.filename,
                            "language": resource.language,
                            "expected_extensions": ",".join(expected_extensions)
                        }
                    ))

        return issues

    def _validate_phase_paths(self, phase: Phase, project_slug: str) -> list[ValidationIssue]:
        """Validate phase path conventions."""
        issues = []

        # Validate phase code for filesystem use
        if not self._is_valid_filesystem_name(phase.code):
            issues.append(self.create_issue(
                "error",
                "paths.phase_invalid_filesystem_code",
                f"Phase code '{phase.code}' contains characters invalid for filesystem paths",
                {"project_slug": project_slug, "phase_code": phase.code}
            ))

        return issues

    def _validate_card_paths(self, card: Card, phase: Phase, project_slug: str) -> list[ValidationIssue]:
        """Validate card path conventions."""
        issues = []

        # Validate card code for filesystem use
        if card.code and not self._is_valid_filesystem_name(card.code):
            issues.append(self.create_issue(
                "error",
                "paths.card_invalid_filesystem_code",
                f"Card code '{card.code}' contains characters invalid for filesystem paths",
                {"project_slug": project_slug, "card_code": card.code}
            ))

        # Check card code follows expected pattern
        if card.code:
            expected_pattern = rf"^{re.escape(card.phase.project.card_code_prefix)}-?\d+$"
            if not re.match(expected_pattern, card.code):
                issues.append(self.create_issue(
                    "warning",
                    "paths.card_code_nonstandard_format",
                    f"Card code '{card.code}' doesn't follow standard pattern (PREFIX-###)",
                    {
                        "project_slug": project_slug,
                        "card_code": card.code,
                        "expected_pattern": f"{card.phase.project.card_code_prefix}-###"
                    }
                ))

        return issues

    def _validate_structure_consistency(self, project: Project, project_slug: str) -> list[ValidationIssue]:
        """Validate overall directory structure consistency."""
        issues = []

        # Check for naming collisions
        entity_names = {}

        # Collect all entity names that would become filesystem paths
        entity_names["project"] = project.slug

        for skill in project.skills:
            if skill.slug in entity_names:
                issues.append(self.create_issue(
                    "error",
                    "paths.naming_collision",
                    f"Naming collision: skill slug '{skill.slug}' conflicts with {entity_names[skill.slug]}",
                    {"project_slug": project_slug, "skill_slug": skill.slug}
                ))
            entity_names[skill.slug] = f"skill '{skill.slug}'"

        for phase in project.phases:
            if phase.code in entity_names:
                issues.append(self.create_issue(
                    "error",
                    "paths.naming_collision",
                    f"Naming collision: phase code '{phase.code}' conflicts with {entity_names[phase.code]}",
                    {"project_slug": project_slug, "phase_code": phase.code}
                ))
            entity_names[phase.code] = f"phase '{phase.code}'"

            for card in phase.cards:
                if card.code and card.code in entity_names:
                    issues.append(self.create_issue(
                        "error",
                        "paths.naming_collision",
                        f"Naming collision: card code '{card.code}' conflicts with {entity_names[card.code]}",
                        {"project_slug": project_slug, "card_code": card.code}
                    ))
                if card.code:
                    entity_names[card.code] = f"card '{card.code}'"

        # Validate expected export directory structure would be valid
        max_path_length = self._calculate_max_path_length(project)
        if max_path_length > 250:  # Leave buffer for filesystem limits
            issues.append(self.create_issue(
                "warning",
                "paths.max_path_length_exceeded",
                f"Exported paths may exceed filesystem limits (max calculated: {max_path_length} chars)",
                {"project_slug": project_slug, "max_path_length": str(max_path_length)}
            ))

        return issues

    def _is_valid_filesystem_name(self, name: str) -> bool:
        """Check if a name is valid for use in filesystem paths."""
        if not name:
            return False

        # Check for invalid characters (Windows + Unix)
        invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
        if re.search(invalid_chars, name):
            return False

        # Check for reserved names (Windows)
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        if name.upper() in reserved_names:
            return False

        # Check for names ending with dots or spaces (Windows)
        return not (name.endswith('.') or name.endswith(' '))

    def _is_valid_filename(self, filename: str) -> bool:
        """Check if a filename is valid."""
        if not filename or filename in ['.', '..']:
            return False

        return self._is_valid_filesystem_name(filename)

    def _get_expected_extensions(self, language: str) -> list[str]:
        """Get expected file extensions for a given language."""
        extension_map = {
            'markdown': ['.md', '.markdown'],
            'python': ['.py'],
            'sql': ['.sql'],
            'yaml': ['.yml', '.yaml'],
            'json': ['.json'],
            'javascript': ['.js'],
            'typescript': ['.ts'],
            'java': ['.java'],
            'shell': ['.sh', '.bash'],
            'dockerfile': ['.dockerfile'],
            'plain': ['.txt', '.text'],
        }

        return extension_map.get(language.lower(), [])

    def _calculate_max_path_length(self, project: Project) -> int:
        """Calculate the maximum expected path length for export."""
        base_path = f"data/projects/{project.slug}/.agents"
        max_length = len(base_path)

        # Check skills paths
        for skill in project.skills:
            skill_path = f"{base_path}/skills/{skill.slug}/SKILL.md"
            max_length = max(max_length, len(skill_path))

            for resource in skill.resources:
                if resource.filename:
                    resource_path = f"{base_path}/skills/{skill.slug}/resources/{resource.filename}"
                    max_length = max(max_length, len(resource_path))

        # Check cards paths
        for phase in project.phases:
            for card in phase.cards:
                if card.code:
                    card_path = f"{base_path}/jira-cards/{phase.code}/{card.code}.md"
                    max_length = max(max_length, len(card_path))

        return max_length

    def get_path_statistics(self, project_slug: str) -> dict[str, any]:
        """Get statistics about project paths for reporting."""
        stats = {
            "project_slug_length": 0,
            "max_skill_slug_length": 0,
            "max_phase_code_length": 0,
            "max_card_code_length": 0,
            "total_resource_files": 0,
            "estimated_max_export_path_length": 0,
            "naming_collisions": 0
        }

        with app.db.session_scope() as session:
            project_query = select(Project).where(
                Project.slug == project_slug
            ).options(
                selectinload(Project.phases).selectinload(Phase.cards),
                selectinload(Project.skills).selectinload(Skill.resources)
            )
            project = session.execute(project_query).scalar_one_or_none()

            if not project:
                return stats

            stats["project_slug_length"] = len(project.slug)

            # Collect all names for collision detection
            all_names = [project.slug]

            for skill in project.skills:
                stats["max_skill_slug_length"] = max(stats["max_skill_slug_length"], len(skill.slug))
                stats["total_resource_files"] += len(skill.resources)
                all_names.append(skill.slug)

            for phase in project.phases:
                stats["max_phase_code_length"] = max(stats["max_phase_code_length"], len(phase.code))
                all_names.append(phase.code)

                for card in phase.cards:
                    if card.code:
                        stats["max_card_code_length"] = max(stats["max_card_code_length"], len(card.code))
                        all_names.append(card.code)

            # Count naming collisions
            stats["naming_collisions"] = len(all_names) - len(set(all_names))

            # Calculate estimated max path length
            stats["estimated_max_export_path_length"] = self._calculate_max_path_length(project)

        return stats
