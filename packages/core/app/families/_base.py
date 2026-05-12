"""Template family abstraction base classes.

Defines the contract that all template families must implement for rendering
cards, project structure, and providing LLM context for card drafting.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel

from app.llm.base import ChatPrompt
from app.schemas.common import ValidationIssue
from app.schemas.views import CardView, PhaseView, ProjectView, SkillView


class CardDraftContext(BaseModel):
    """Context provided to template families for LLM card drafting prompts."""

    project: ProjectView
    project_context: str  # Accumulated context (Q&A + tech choices + artifact summaries)
    phase: PhaseView
    card: CardView
    skills_used: list[SkillView]
    sibling_cards_in_phase: list[CardView]
    upstream_cards: list[CardView]


class GroupingReadmeContext(BaseModel):
    """Context for rendering phase/epic README files."""

    project: ProjectView
    grouping: PhaseView  # For phase-based families, this is a PhaseView
    cards: list[CardView]
    skills_referenced: list[SkillView]


class ProjectReadmeContext(BaseModel):
    """Context for rendering the top-level project README."""

    project: ProjectView
    phases: list[PhaseView]
    all_cards: list[CardView]
    all_skills: list[SkillView]


class CardExample(BaseModel):
    """A few-shot example card for LLM prompts."""

    title: str
    context_md: str
    task_md: str
    outputs_md: str
    acceptance_criteria_md: str
    explanation: str  # Why this example is relevant


class BacklogProposalContext(BaseModel):
    """Context for LLM backlog proposal prompts."""

    project: ProjectView
    project_context: str
    proposed_skills: list[SkillView]


class TemplateFamily(ABC):
    """Abstract base class for all template families.

    Template families define how to render cards and project structure,
    provide validation rules, and create LLM prompts for card drafting.
    """

    # Class-level metadata
    slug: str
    display_name: str
    grouping: Literal["phase", "epic", "flat"]
    grouping_label_singular: str
    grouping_label_plural: str
    card_filename_pattern: str
    grouping_folder_pattern: str

    @abstractmethod
    def render_card(self, card: CardView, context: CardDraftContext) -> str:
        """Render a single card to markdown.

        Args:
            card: The card to render
            context: Context including project, phase, skills, etc.

        Returns:
            Complete markdown content for the card file
        """
        ...

    @abstractmethod
    def render_grouping_readme(self, context: GroupingReadmeContext) -> str:
        """Render the README for a phase/epic folder.

        Args:
            context: Project, grouping (phase), cards, and skills

        Returns:
            Markdown content for the grouping README file
        """
        ...

    @abstractmethod
    def render_project_readme(self, context: ProjectReadmeContext) -> str:
        """Render the top-level project README.

        Args:
            context: Complete project information

        Returns:
            Markdown content for the project README file
        """
        ...

    @abstractmethod
    def draft_card_prompt(self, context: CardDraftContext) -> ChatPrompt:
        """Create an LLM prompt for drafting card sections.

        Args:
            context: Full context for card drafting

        Returns:
            ChatPrompt ready for LLM execution
        """
        ...

    @abstractmethod
    def few_shot_card_examples(self) -> list[CardExample]:
        """Provide few-shot examples for card drafting prompts.

        Returns:
            List of example cards with explanations
        """
        ...

    @abstractmethod
    def propose_backlog_prompt(self, context: BacklogProposalContext) -> ChatPrompt:
        """Create an LLM prompt for proposing a project backlog.

        Args:
            context: Project and skills context

        Returns:
            ChatPrompt for backlog proposal
        """
        ...

    @abstractmethod
    def validate_card(self, card: CardView, project: ProjectView) -> list[ValidationIssue]:
        """Validate a single card according to family rules.

        Args:
            card: Card to validate
            project: Project context

        Returns:
            List of validation issues (errors and warnings)
        """
        ...

    @abstractmethod
    def validate_project(self, project: ProjectView) -> list[ValidationIssue]:
        """Validate the entire project according to family rules.

        Args:
            project: Project to validate

        Returns:
            List of validation issues (errors and warnings)
        """
        ...

    def get_card_filename(self, card: CardView) -> str:
        """Generate the filename for a card based on the family pattern.

        Args:
            card: Card to generate filename for

        Returns:
            Filename (without extension)
        """
        # Default implementation using the pattern
        # Subclasses can override for custom logic
        title_slug = self._slugify(card.title)
        return self.card_filename_pattern.format(
            code=card.code,
            title_slug=title_slug
        )

    def get_grouping_folder_name(self, grouping: PhaseView) -> str:
        """Generate the folder name for a phase/epic based on the family pattern.

        Args:
            grouping: Phase or epic to generate folder name for

        Returns:
            Folder name
        """
        # Default implementation using the pattern
        slug = self._slugify(grouping.name)
        return self.grouping_folder_pattern.format(
            order=grouping.order_no,
            slug=slug
        )

    def _slugify(self, text: str) -> str:
        """Convert text to a URL-safe slug.

        Args:
            text: Text to slugify

        Returns:
            Slugified text (lowercase, hyphens, no special chars)
        """
        import re
        # Convert to lowercase and replace spaces/underscores with hyphens
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[-\s_]+', '-', slug)
        return slug.strip('-')
