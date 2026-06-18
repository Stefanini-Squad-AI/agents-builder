"""Q&A service for CLI and API operations.

Implements the 7-question discovery wizard per SPEC §11.2:
- 3 required questions (business_problem, success_definition, users_and_actors)
- 4 optional questions (must_preserve, must_change, compliance, known_gaps)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.projects import Project, ProjectQaAnswer


@dataclass
class QuestionMetadata:
    """Metadata for a standard Q&A question."""

    prompt: str
    required: bool
    placeholder: str
    order: int


@dataclass
class QaSummary:
    """Q&A answer summary for API responses."""

    project_id: UUID | None
    question_key: str
    prompt: str
    required: bool
    placeholder: str
    order: int
    answer_md: str | None
    updated_at: datetime | None
    is_answered: bool


class QaService:
    """Service for Q&A CRUD operations and management.
    
    Args:
        session: SQLAlchemy session owned by the caller. The service uses this
                 session for all DB operations but never commits — caller owns commit.
                 Pass None for methods that don't require DB access (e.g., get_standard_questions_catalog).
    """

    # Standard 7-question discovery wizard (per SPEC §11.2)
    # Keys must match _QA_KEYS in domain/projects.py
    STANDARD_QUESTIONS: dict[str, QuestionMetadata] = {
        "business_problem": QuestionMetadata(
            prompt="What business problem does this project solve?",
            required=True,
            placeholder="Describe the core business challenge this project addresses...",
            order=1,
        ),
        "success_definition": QuestionMetadata(
            prompt="What does success look like, operationally?",
            required=True,
            placeholder="Describe measurable outcomes that define project success...",
            order=2,
        ),
        "users_and_actors": QuestionMetadata(
            prompt="Who uses or interacts with this system?",
            required=True,
            placeholder="List humans, jobs, upstream/downstream systems that interact with this system...",
            order=3,
        ),
        "must_preserve": QuestionMetadata(
            prompt="What legacy behaviors must be preserved exactly?",
            required=False,
            placeholder="Describe behaviors, interfaces, or outputs that cannot change...",
            order=4,
        ),
        "must_change": QuestionMetadata(
            prompt="What current behaviors are being modernized or removed?",
            required=False,
            placeholder="Describe what will be deprecated, replaced, or significantly changed...",
            order=5,
        ),
        "compliance": QuestionMetadata(
            prompt="Are there regulatory or security constraints?",
            required=False,
            placeholder="LGPD, PCI-DSS, banking regulations, security requirements, etc...",
            order=6,
        ),
        "known_gaps": QuestionMetadata(
            prompt="What is currently unknown or undocumented?",
            required=False,
            placeholder="What needs clarification from stakeholders or further investigation...",
            order=7,
        ),
    }

    # Keys of required questions (first 3)
    REQUIRED_KEYS = ["business_problem", "success_definition", "users_and_actors"]

    def __init__(self, session: Session | None = None) -> None:
        """Initialize the Q&A service with caller's session (P2 fix)."""
        self._session = session

    def list_project_qa(self, project_slug: str) -> list[QaSummary]:
        """List all Q&A answers for a project.

        Args:
            project_slug: Project slug

        Returns:
            List of Q&A summaries ordered by question order
        """
        # Get project
        project = self._session.execute(
            select(Project).where(Project.slug == project_slug)
        ).scalar_one_or_none()

        if not project:
            return []

        # Query Q&A answers
        query = (
            select(ProjectQaAnswer)
            .where(ProjectQaAnswer.project_id == project.id)
        )

        qa_answers = self._session.execute(query).scalars().all()

        # Create summaries for all standard questions
        qa_summaries = []
        answered_keys = {qa.question_key: qa for qa in qa_answers}

        # Sort by order defined in STANDARD_QUESTIONS
        for key, meta in sorted(
            self.STANDARD_QUESTIONS.items(), key=lambda x: x[1].order
        ):
            qa_answer = answered_keys.get(key)

            qa_summary = QaSummary(
                project_id=project.id,
                question_key=key,
                prompt=meta.prompt,
                required=meta.required,
                placeholder=meta.placeholder,
                order=meta.order,
                answer_md=qa_answer.answer_md if qa_answer else None,
                updated_at=qa_answer.updated_at if qa_answer else None,
                is_answered=bool(
                    qa_answer and qa_answer.answer_md and qa_answer.answer_md.strip()
                ),
            )
            qa_summaries.append(qa_summary)

        return qa_summaries

    def get_qa_answer(self, project_slug: str, question_key: str) -> QaSummary | None:
        """Get a specific Q&A answer by project and question key.

        Args:
            project_slug: Project slug
            question_key: Question key (e.g., "business_problem")

        Returns:
            Q&A summary or None if question key invalid
        """
        if question_key not in self.STANDARD_QUESTIONS:
            return None

        meta = self.STANDARD_QUESTIONS[question_key]

        # Get project first
        project = self._session.execute(
            select(Project).where(Project.slug == project_slug)
        ).scalar_one_or_none()

        if not project:
            return None

        # Load Q&A answer
        query = select(ProjectQaAnswer).where(
            ProjectQaAnswer.project_id == project.id,
            ProjectQaAnswer.question_key == question_key,
        )

        qa_answer = self._session.execute(query).scalar_one_or_none()

        return QaSummary(
            project_id=project.id,
            question_key=question_key,
            prompt=meta.prompt,
            required=meta.required,
            placeholder=meta.placeholder,
            order=meta.order,
            answer_md=qa_answer.answer_md if qa_answer else None,
            updated_at=qa_answer.updated_at if qa_answer else None,
            is_answered=bool(
                qa_answer and qa_answer.answer_md and qa_answer.answer_md.strip()
            ),
        )

    def set_qa_answer(
        self, project_slug: str, question_key: str, answer_md: str
    ) -> QaSummary | None:
        """Set or update a Q&A answer.

        Args:
            project_slug: Project slug
            question_key: Question key
            answer_md: Answer markdown content

        Returns:
            Updated Q&A summary or None if project not found
            
        Note:
            Caller owns the commit — this method only flushes to get updated_at.
        """
        if question_key not in self.STANDARD_QUESTIONS:
            raise ValueError(
                f"Invalid question key: {question_key}. "
                f"Valid keys: {', '.join(self.STANDARD_QUESTIONS.keys())}"
            )

        meta = self.STANDARD_QUESTIONS[question_key]

        # Get project
        project = self._session.execute(
            select(Project).where(Project.slug == project_slug)
        ).scalar_one_or_none()

        if not project:
            return None

        # Find existing answer or create new one
        existing_qa = self._session.execute(
            select(ProjectQaAnswer).where(
                ProjectQaAnswer.project_id == project.id,
                ProjectQaAnswer.question_key == question_key,
            )
        ).scalar_one_or_none()

        if existing_qa:
            # Update existing
            existing_qa.answer_md = answer_md
            self._session.flush()

            return QaSummary(
                project_id=existing_qa.project_id,
                question_key=existing_qa.question_key,
                prompt=meta.prompt,
                required=meta.required,
                placeholder=meta.placeholder,
                order=meta.order,
                answer_md=existing_qa.answer_md,
                updated_at=existing_qa.updated_at,
                is_answered=bool(answer_md and answer_md.strip()),
            )
        else:
            # Create new
            new_qa = ProjectQaAnswer(
                project_id=project.id,
                question_key=question_key,
                answer_md=answer_md,
            )
            self._session.add(new_qa)
            self._session.flush()

            return QaSummary(
                project_id=new_qa.project_id,
                question_key=new_qa.question_key,
                prompt=meta.prompt,
                required=meta.required,
                placeholder=meta.placeholder,
                order=meta.order,
                answer_md=new_qa.answer_md,
                updated_at=new_qa.updated_at,
                is_answered=bool(answer_md and answer_md.strip()),
            )

    def get_qa_statistics(self, project_slug: str) -> dict[str, Any]:
        """Get Q&A statistics for a project.

        Args:
            project_slug: Project slug

        Returns:
            Dictionary with Q&A statistics
        """
        qa_answers = self.list_project_qa(project_slug)

        total = len(self.STANDARD_QUESTIONS)
        required_total = len(self.REQUIRED_KEYS)

        if not qa_answers:
            return {
                "total_questions": total,
                "answered_questions": 0,
                "completion_percentage": 0.0,
                "required_answered": 0,
                "required_total": required_total,
                "required_percentage": 0.0,
                "questions_by_status": {"answered": 0, "unanswered": total},
            }

        answered_count = sum(1 for qa in qa_answers if qa.is_answered)
        required_answered = sum(
            1 for qa in qa_answers if qa.required and qa.is_answered
        )

        return {
            "total_questions": total,
            "answered_questions": answered_count,
            "completion_percentage": (answered_count / total * 100) if total else 0.0,
            "required_answered": required_answered,
            "required_total": required_total,
            "required_percentage": (required_answered / required_total * 100)
            if required_total
            else 0.0,
            "questions_by_status": {
                "answered": answered_count,
                "unanswered": total - answered_count,
            },
        }

    def render_qa_summary(self, project_slug: str) -> str:
        """Render Q&A summary as markdown.

        Args:
            project_slug: Project slug

        Returns:
            Formatted markdown summary of all Q&A
        """
        qa_answers = self.list_project_qa(project_slug)

        if not qa_answers:
            return "# Q&A Summary\n\nNo questions found for this project."

        lines = []
        lines.append("# Q&A Summary")
        lines.append("")

        for qa in qa_answers:
            # Mark required questions
            required_marker = " ⭐" if qa.required else ""
            status_marker = "✅" if qa.is_answered else "❌"

            lines.append(f"## {qa.order}. {qa.prompt}{required_marker} {status_marker}")
            lines.append("")

            if qa.is_answered and qa.answer_md:
                lines.append(qa.answer_md)
            else:
                lines.append("*Not answered yet.*")

            lines.append("")
            lines.append("---")
            lines.append("")

        # Statistics
        stats = self.get_qa_statistics(project_slug)
        lines.append("## Summary")
        lines.append("")
        lines.append(
            f"- **Progress:** {stats['answered_questions']}/{stats['total_questions']} "
            f"questions answered ({stats['completion_percentage']:.0f}%)"
        )
        lines.append(
            f"- **Required:** {stats['required_answered']}/{stats['required_total']} "
            f"required questions answered ({stats['required_percentage']:.0f}%)"
        )

        return "\n".join(lines)

    def get_completion_status(self, project_slug: str) -> dict[str, Any]:
        """Get completion status for project planning.

        Args:
            project_slug: Project slug

        Returns:
            Dictionary with completion status and recommendations
        """
        stats = self.get_qa_statistics(project_slug)
        qa_answers = self.list_project_qa(project_slug)

        # Determine missing required questions
        missing_required = [
            qa.question_key for qa in qa_answers if qa.required and not qa.is_answered
        ]

        # Determine readiness level
        if stats["required_answered"] < stats["required_total"]:
            readiness = "blocked"
            message = "Complete required questions before proceeding"
        elif stats["answered_questions"] < 5:
            readiness = "partial"
            message = "Consider answering more questions for better results"
        else:
            readiness = "ready"
            message = "Ready for skill and card generation"

        return {
            "readiness": readiness,
            "message": message,
            "required_complete": stats["required_answered"] == stats["required_total"],
            "missing_required": missing_required,
            "recommended_next_steps": _get_next_steps(stats),
        }

    def get_standard_questions_catalog(self) -> dict[str, dict[str, Any]]:
        """Get the catalog of standard questions with metadata.

        Returns:
            Dictionary of question key -> metadata
        """
        return {
            key: {
                "prompt": meta.prompt,
                "required": meta.required,
                "placeholder": meta.placeholder,
                "order": meta.order,
            }
            for key, meta in self.STANDARD_QUESTIONS.items()
        }


def _get_next_steps(stats: dict[str, Any]) -> list[str]:
    """Get recommended next steps based on Q&A completion."""
    next_steps = []

    if stats["required_answered"] < stats["required_total"]:
        remaining = stats["required_total"] - stats["required_answered"]
        next_steps.append(f"Answer {remaining} required question(s)")

    if stats["answered_questions"] < stats["total_questions"]:
        remaining = stats["total_questions"] - stats["answered_questions"]
        if remaining > 0:
            next_steps.append(f"Complete {remaining} optional question(s) for full context")

    if stats["required_percentage"] >= 100:
        next_steps.append("Proceed to tech selection")

    if stats["completion_percentage"] >= 60:
        next_steps.append("Generate project skills and cards")

    return next_steps