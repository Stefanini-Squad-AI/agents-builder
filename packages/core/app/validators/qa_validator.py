"""Q&A validator for completeness and consistency of project questions and answers."""

from __future__ import annotations

import re
from typing import Any, ClassVar

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.db
from app.domain.projects import Project
from app.schemas.common import ValidationIssue
from app.validators.base import BaseValidator


class QaValidator(BaseValidator):
    """Validates Q&A completeness and consistency."""

    # Critical questions that should be answered for most projects
    CRITICAL_QUESTIONS: ClassVar[dict[str, list[str]]] = {
        'deployment_environment': ['deployment', 'environment', 'deploy', 'hosting', 'infrastructure'],
        'target_users': ['users', 'audience', 'stakeholders', 'personas'],
        'performance_requirements': ['performance', 'scalability', 'throughput', 'latency', 'response time'],
        'security_requirements': ['security', 'authentication', 'authorization', 'compliance', 'privacy'],
        'integration_requirements': ['integration', 'apis', 'external systems', 'third party'],
        'data_sources': ['data', 'database', 'storage', 'persistence'],
        'business_constraints': ['constraints', 'limitations', 'budget', 'timeline', 'resources']
    }

    def validate(self, project_slug: str) -> list[ValidationIssue]:
        """Validate Q&A completeness and consistency for a project."""
        issues = []

        with app.db.session_scope() as session:
            # Load project with Q&A answers
            project_query = select(Project).where(
                Project.slug == project_slug
            ).options(
                selectinload(Project.qa_answers)
            )
            project = session.execute(project_query).scalar_one_or_none()

            if not project:
                issues.append(self.create_issue(
                    "error",
                    "qa.project_not_found",
                    f"Project '{project_slug}' not found",
                    {"project_slug": project_slug}
                ))
                return issues

            # Run Q&A validations
            issues.extend(self._validate_answer_completeness(project, project_slug))
            issues.extend(self._validate_answer_quality(project, project_slug))
            issues.extend(self._validate_answer_consistency(project, project_slug))
            issues.extend(self._validate_critical_questions(project, project_slug))

        return issues

    def _validate_answer_completeness(self, project: Project, project_slug: str) -> list[ValidationIssue]:
        """Validate that answers are not empty or trivial."""
        issues = []

        for qa_answer in project.qa_answers:
            # Check for empty answers
            if not qa_answer.answer_md or not qa_answer.answer_md.strip():
                issues.append(self.create_issue(
                    "error",
                    "qa.empty_answer",
                    f"Question '{qa_answer.question_key}' has no answer provided",
                    {
                        "project_slug": project_slug,
                        "question_key": qa_answer.question_key
                    }
                ))
                continue

            # Check for trivial answers
            answer_text = qa_answer.answer_md.strip().lower()
            trivial_answers = ['tbd', 'todo', 'n/a', 'na', 'none', 'unknown', '?', '-']

            if answer_text in trivial_answers or len(answer_text) < 5:
                issues.append(self.create_issue(
                    "warning",
                    "qa.trivial_answer",
                    f"Question '{qa_answer.question_key}' has a trivial answer: '{qa_answer.answer_md.strip()}'",
                    {
                        "project_slug": project_slug,
                        "question_key": qa_answer.question_key,
                        "answer_preview": qa_answer.answer_md.strip()[:50]
                    }
                ))

            # Check answer length (very short might be incomplete)
            if len(answer_text) < 10:
                issues.append(self.create_issue(
                    "warning",
                    "qa.short_answer",
                    f"Question '{qa_answer.question_key}' has a very short answer ({len(answer_text)} chars)",
                    {
                        "project_slug": project_slug,
                        "question_key": qa_answer.question_key,
                        "answer_length": str(len(answer_text))
                    }
                ))

        return issues

    def _validate_answer_quality(self, project: Project, project_slug: str) -> list[ValidationIssue]:
        """Validate answer quality and format."""
        issues = []

        for qa_answer in project.qa_answers:
            if not qa_answer.answer_md:
                continue

            answer_text = qa_answer.answer_md.strip()

            # Check for markdown formatting issues
            if self._has_markdown_formatting_issues(answer_text):
                issues.append(self.create_issue(
                    "warning",
                    "qa.markdown_formatting_issues",
                    f"Question '{qa_answer.question_key}' answer has potential markdown formatting issues",
                    {
                        "project_slug": project_slug,
                        "question_key": qa_answer.question_key
                    }
                ))

            # Check for very long answers (might be copy-paste dumps)
            if len(answer_text) > 2000:
                issues.append(self.create_issue(
                    "warning",
                    "qa.very_long_answer",
                    f"Question '{qa_answer.question_key}' has a very long answer ({len(answer_text)} chars)",
                    {
                        "project_slug": project_slug,
                        "question_key": qa_answer.question_key,
                        "answer_length": str(len(answer_text))
                    }
                ))

            # Check for specific answer patterns that might need attention
            if re.search(r'\b(example|sample|placeholder|lorem ipsum)\b', answer_text, re.IGNORECASE):
                issues.append(self.create_issue(
                    "warning",
                    "qa.placeholder_content",
                    f"Question '{qa_answer.question_key}' answer appears to contain placeholder content",
                    {
                        "project_slug": project_slug,
                        "question_key": qa_answer.question_key
                    }
                ))

        return issues

    def _validate_answer_consistency(self, project: Project, project_slug: str) -> list[ValidationIssue]:
        """Validate consistency between answers and project objective."""
        issues = []

        if not project.objective:
            return issues

        objective_lower = project.objective.lower()

        # Build answer content for analysis
        all_answers_text = " ".join([
            qa.answer_md.lower() for qa in project.qa_answers
            if qa.answer_md and qa.answer_md.strip()
        ])

        # Check for technology consistency
        if 'java' in objective_lower and 'python' in all_answers_text:
            issues.append(self.create_issue(
                "warning",
                "qa.technology_inconsistency",
                "Project objective mentions Java but Q&A answers mention Python - verify consistency",
                {
                    "project_slug": project_slug,
                    "inconsistency_type": "technology_mismatch"
                }
            ))

        # Check for scale consistency
        if any(word in objective_lower for word in ['enterprise', 'large', 'scale']) and any(word in all_answers_text for word in ['small', 'simple', 'minimal']):
            issues.append(self.create_issue(
                "warning",
                "qa.scale_inconsistency",
                "Project objective suggests enterprise scale but answers suggest small scale",
                {
                    "project_slug": project_slug,
                    "inconsistency_type": "scale_mismatch"
                }
            ))

        # Check for timeline consistency
        if ('urgent' in objective_lower or 'asap' in objective_lower) and any(word in all_answers_text for word in ['months', 'long term', 'future']):
            issues.append(self.create_issue(
                "warning",
                "qa.timeline_inconsistency",
                "Project objective suggests urgency but answers suggest longer timeline",
                {
                    "project_slug": project_slug,
                    "inconsistency_type": "timeline_mismatch"
                }
            ))

        return issues

    def _validate_critical_questions(self, project: Project, project_slug: str) -> list[ValidationIssue]:
        """Validate that critical questions for the project type are addressed."""
        issues = []

        # Get answered question keys
        answered_keys = {qa.question_key.lower() for qa in project.qa_answers if qa.answer_md and qa.answer_md.strip()}

        # Check each critical question category
        for category, keywords in self.CRITICAL_QUESTIONS.items():
            # Check if any answered question covers this category
            category_covered = False

            for answered_key in answered_keys:
                if any(keyword in answered_key for keyword in keywords):
                    category_covered = True
                    break

            # Also check if any answer content covers this category
            if not category_covered:
                for qa in project.qa_answers:
                    if qa.answer_md:
                        answer_lower = qa.answer_md.lower()
                        if any(keyword in answer_lower for keyword in keywords):
                            category_covered = True
                            break

            if not category_covered:
                # Determine severity based on project type/complexity
                severity = "warning"
                if len(project.qa_answers) > 5 or len(project.objective) > 100:
                    # More complex projects should address more categories
                    severity = "warning"

                issues.append(self.create_issue(
                    severity,
                    "qa.missing_critical_category",
                    f"No questions/answers address '{category}' (keywords: {', '.join(keywords[:3])})",
                    {
                        "project_slug": project_slug,
                        "missing_category": category,
                        "suggested_keywords": ",".join(keywords[:3])
                    }
                ))

        return issues

    def _has_markdown_formatting_issues(self, text: str) -> bool:
        """Check for common markdown formatting issues."""
        # Check for unmatched markdown syntax
        issues = []

        # Unmatched bold/italic markers
        if text.count('**') % 2 != 0:
            issues.append("unmatched_bold")
        if text.count('*') % 2 != 0:
            issues.append("unmatched_italic")

        # Malformed links
        if re.search(r'\[([^\]]*)\]\([^\)]*$', text):
            issues.append("malformed_link")

        # Headers without space
        if re.search(r'^#+[^\s]', text, re.MULTILINE):
            issues.append("header_no_space")

        return len(issues) > 0

    def suggest_missing_questions(self, project_slug: str) -> list[dict[str, str]]:
        """Suggest questions that might be valuable for this project.

        Returns:
            List of suggested questions with keys and descriptions
        """
        suggestions = []

        with app.db.session_scope() as session:
            project_query = select(Project).where(
                Project.slug == project_slug
            ).options(
                selectinload(Project.qa_answers)
            )
            project = session.execute(project_query).scalar_one_or_none()

            if not project:
                return suggestions

            # Get already answered question categories
            answered_categories = set()
            for qa in project.qa_answers:
                question_lower = qa.question_key.lower()
                for category, keywords in self.CRITICAL_QUESTIONS.items():
                    if any(keyword in question_lower for keyword in keywords):
                        answered_categories.add(category)

            # Suggest missing critical questions
            question_templates = {
                'deployment_environment': {
                    'key': 'deployment_environment',
                    'question': 'What is the target deployment environment?',
                    'description': 'Cloud platform, on-premise, hybrid setup'
                },
                'target_users': {
                    'key': 'target_users',
                    'question': 'Who are the primary users of this system?',
                    'description': 'End users, administrators, external partners'
                },
                'performance_requirements': {
                    'key': 'performance_requirements',
                    'question': 'What are the performance and scalability requirements?',
                    'description': 'Expected load, response times, concurrent users'
                },
                'security_requirements': {
                    'key': 'security_requirements',
                    'question': 'What are the security and compliance requirements?',
                    'description': 'Authentication, authorization, data protection'
                },
                'integration_requirements': {
                    'key': 'integration_requirements',
                    'question': 'What external systems need integration?',
                    'description': 'APIs, databases, third-party services'
                },
                'data_sources': {
                    'key': 'data_sources',
                    'question': 'What are the data sources and storage requirements?',
                    'description': 'Databases, files, external data feeds'
                },
                'business_constraints': {
                    'key': 'business_constraints',
                    'question': 'What are the key business constraints and limitations?',
                    'description': 'Budget, timeline, resource limitations'
                }
            }

            for category in self.CRITICAL_QUESTIONS:
                if category not in answered_categories and category in question_templates:
                    suggestions.append(question_templates[category])

        return suggestions

    def get_qa_statistics(self, project_slug: str) -> dict[str, Any]:
        """Get statistics about project Q&A for reporting."""
        stats = {
            "total_questions": 0,
            "answered_questions": 0,
            "empty_answers": 0,
            "trivial_answers": 0,
            "average_answer_length": 0,
            "critical_categories_covered": 0,
            "total_critical_categories": len(self.CRITICAL_QUESTIONS),
            "suggested_questions_count": 0
        }

        with app.db.session_scope() as session:
            project_query = select(Project).where(
                Project.slug == project_slug
            ).options(
                selectinload(Project.qa_answers)
            )
            project = session.execute(project_query).scalar_one_or_none()

            if not project:
                return stats

            stats["total_questions"] = len(project.qa_answers)

            answer_lengths = []
            trivial_answers = ['tbd', 'todo', 'n/a', 'na', 'none', 'unknown', '?', '-']

            for qa in project.qa_answers:
                if qa.answer_md and qa.answer_md.strip():
                    stats["answered_questions"] += 1
                    answer_length = len(qa.answer_md.strip())
                    answer_lengths.append(answer_length)

                    if qa.answer_md.strip().lower() in trivial_answers:
                        stats["trivial_answers"] += 1
                else:
                    stats["empty_answers"] += 1

            if answer_lengths:
                stats["average_answer_length"] = sum(answer_lengths) / len(answer_lengths)

            # Count covered critical categories
            answered_keys = {qa.question_key.lower() for qa in project.qa_answers}
            for _category, keywords in self.CRITICAL_QUESTIONS.items():
                for answered_key in answered_keys:
                    if any(keyword in answered_key for keyword in keywords):
                        stats["critical_categories_covered"] += 1
                        break

            stats["suggested_questions_count"] = len(self.suggest_missing_questions(project_slug))

        return stats
