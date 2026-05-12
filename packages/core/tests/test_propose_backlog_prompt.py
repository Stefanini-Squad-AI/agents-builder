"""Tests for ProposeBacklogPrompt."""

import pytest
from uuid import uuid4

from app.enums import CardType, SkillKind
from app.families import PhaseVliFamily
from app.llm import DummyProvider
from app.prompts import ProposeBacklogPrompt
from app.schemas.llm_io import ProposedBacklog, ProposedCard, ProposedPhase
from app.schemas.views import ProjectContext, SkillView


class TestProposeBacklogPrompt:
    """Unit tests for ProposeBacklogPrompt class."""

    def test_create_prompt_delegates_to_template_family(self) -> None:
        """Test that create method properly delegates to template family."""
        # Create mock data
        project_context = ProjectContext(
            objective="Build microservices platform"
        )
        
        skills = [
            SkillView(
                id=uuid4(),
                slug="api-architect",
                name="API Architect",
                description="Design REST APIs",
                kind=SkillKind.AUTHORING,
                body_md="# API Architect\n\nDesign APIs.",
                project_id=uuid4(),
            ),
            SkillView(
                id=uuid4(),
                slug="system-analyzer",
                name="System Analyzer",
                description="Analyze existing systems",
                kind=SkillKind.ANALYZER,
                body_md="# System Analyzer\n\nAnalyze systems.",
                project_id=uuid4(),
            )
        ]
        
        template_family = PhaseVliFamily()
        
        # Call create method 
        project_context_str = "Build microservices platform with authentication and monitoring"
        prompt = ProposeBacklogPrompt.create(project_context_str, skills, template_family)
        
        # Verify prompt structure
        assert prompt.system is not None
        assert len(prompt.messages) == 1
        assert prompt.response_schema == ProposedBacklog
        
        # Verify system prompt contains VLI-specific guidance
        assert "phase-based software delivery" in prompt.system
        assert "Discovery → Design → Implementation" in prompt.system
        assert "Example 1: Data Migration Project" in prompt.system
        
        # Verify user message contains project and skills
        user_content = prompt.messages[0].content
        assert "microservices platform" in user_content
        assert "api-architect" in user_content
        assert "system-analyzer" in user_content

    def test_get_skill_categories(self) -> None:
        """Test skill categorization by kind."""
        skills = [
            SkillView(
                id=uuid4(),
                slug="context-1",
                name="Context Skill 1",
                description="Context skill",
                kind=SkillKind.CONTEXT,
                body_md="# Context 1",
                project_id=uuid4(),
            ),
            SkillView(
                id=uuid4(),
                slug="context-2",
                name="Context Skill 2", 
                description="Another context skill",
                kind=SkillKind.CONTEXT,
                body_md="# Context 2",
                project_id=uuid4(),
            ),
            SkillView(
                id=uuid4(),
                slug="analyzer-1",
                name="Analyzer Skill",
                description="Analyzer skill",
                kind=SkillKind.ANALYZER,
                body_md="# Analyzer 1",
                project_id=uuid4(),
            ),
        ]
        
        categories = ProposeBacklogPrompt.get_skill_categories(skills)
        
        # Check categorization
        assert "context" in categories
        assert "analyzer" in categories
        assert len(categories["context"]) == 2
        assert len(categories["analyzer"]) == 1
        
        # Check skill assignment
        assert categories["context"][0].slug == "context-1"
        assert categories["context"][1].slug == "context-2"
        assert categories["analyzer"][0].slug == "analyzer-1"

    def test_format_skills_summary(self) -> None:
        """Test skills summary formatting."""
        skills = [
            SkillView(
                id=uuid4(),
                slug="api-builder",
                name="API Builder",
                description="Build APIs",
                kind=SkillKind.AUTHORING,
                body_md="# API Builder",
                project_id=uuid4(),
            ),
            SkillView(
                id=uuid4(),
                slug="data-analyzer",
                name="Data Analyzer",
                description="Analyze data",
                kind=SkillKind.ANALYZER,
                body_md="# Data Analyzer",
                project_id=uuid4(),
            ),
        ]
        
        summary = ProposeBacklogPrompt.format_skills_summary(skills)
        
        # Check formatting
        assert "**Authoring**: `api-builder`" in summary
        assert "**Analyzer**: `data-analyzer`" in summary
        assert summary.count("\n") == 1  # Two lines

    def test_format_skills_summary_empty_list(self) -> None:
        """Test skills summary formatting with empty list."""
        summary = ProposeBacklogPrompt.format_skills_summary([])
        assert summary == ""

    def test_validate_proposed_backlog_valid(self) -> None:
        """Test backlog validation with valid backlog."""
        # Create valid backlog
        backlog = ProposedBacklog(
            phases=[
                ProposedPhase(
                    code="phase-1",
                    name="Phase 1",
                    description="First phase",
                    cards=[
                        ProposedCard(
                            code="PROJ-101",
                            title="First Card",
                            type=CardType.TASK,
                            story_points=3,
                            skill_slugs=["skill-1"],
                            depends_on_codes=[],
                            short_scope_summary="First card work"
                        )
                    ]
                ),
                ProposedPhase(
                    code="phase-2",
                    name="Phase 2",
                    description="Second phase",
                    cards=[
                        ProposedCard(
                            code="PROJ-201",
                            title="Second Card",
                            type=CardType.STORY,
                            story_points=5,
                            skill_slugs=["skill-1"],
                            depends_on_codes=["PROJ-101"],
                            short_scope_summary="Second card work"
                        )
                    ]
                )
            ],
            rationale_md="Two-phase project with dependency flow",
            critical_path_codes=["PROJ-101", "PROJ-201"]
        )
        
        available_skills = [
            SkillView(
                id=uuid4(),
                slug="skill-1",
                name="Skill 1",
                description="First skill",
                kind=SkillKind.CONTEXT,
                body_md="# Skill 1",
                project_id=uuid4(),
            )
        ]
        
        warnings = ProposeBacklogPrompt.validate_proposed_backlog(backlog, available_skills)
        assert warnings == []  # No warnings for valid backlog

    def test_validate_proposed_backlog_unknown_skills(self) -> None:
        """Test backlog validation with unknown skill references."""
        backlog = ProposedBacklog(
            phases=[
                ProposedPhase(
                    code="phase-1",
                    name="Phase 1", 
                    description="First phase",
                    cards=[
                        ProposedCard(
                            code="PROJ-101",
                            title="First Card",
                            type=CardType.TASK,
                            story_points=3,
                            skill_slugs=["unknown-skill"],
                            depends_on_codes=[],
                            short_scope_summary="First card work"
                        )
                    ]
                ),
                ProposedPhase(
                    code="phase-2",
                    name="Phase 2",
                    description="Second phase",
                    cards=[
                        ProposedCard(
                            code="PROJ-201",
                            title="Second Card",
                            type=CardType.STORY,
                            story_points=5,
                            skill_slugs=[],
                            depends_on_codes=[],
                            short_scope_summary="Second card work"
                        )
                    ]
                )
            ],
            rationale_md="Test backlog",
            critical_path_codes=[]
        )
        
        available_skills = []
        
        warnings = ProposeBacklogPrompt.validate_proposed_backlog(backlog, available_skills)
        assert len(warnings) == 1
        assert "unknown skill: unknown-skill" in warnings[0]

    def test_validate_proposed_backlog_unknown_dependencies(self) -> None:
        """Test backlog validation with unknown card dependencies."""
        backlog = ProposedBacklog(
            phases=[
                ProposedPhase(
                    code="phase-1",
                    name="Phase 1",
                    description="First phase", 
                    cards=[
                        ProposedCard(
                            code="PROJ-101",
                            title="First Card",
                            type=CardType.TASK,
                            story_points=3,
                            skill_slugs=[],
                            depends_on_codes=["PROJ-999"],  # Unknown dependency
                            parallel_with_codes=["PROJ-888"],  # Unknown parallel
                            short_scope_summary="First card work"
                        )
                    ]
                ),
                ProposedPhase(
                    code="phase-2",
                    name="Phase 2",
                    description="Second phase",
                    cards=[
                        ProposedCard(
                            code="PROJ-201",
                            title="Second Card",
                            type=CardType.STORY,
                            story_points=5,
                            skill_slugs=[],
                            depends_on_codes=[],
                            short_scope_summary="Second card work"
                        )
                    ]
                )
            ],
            rationale_md="Test backlog",
            critical_path_codes=["PROJ-999"]  # Unknown critical path
        )
        
        available_skills = []
        
        warnings = ProposeBacklogPrompt.validate_proposed_backlog(backlog, available_skills)
        assert len(warnings) == 3
        assert any("depends on unknown card: PROJ-999" in w for w in warnings)
        assert any("parallel with unknown card: PROJ-888" in w for w in warnings)
        assert any("Critical path references unknown card: PROJ-999" in w for w in warnings)


class TestProposeBacklogIntegration:
    """Integration tests for ProposeBacklogPrompt with template families."""

    def test_vli_family_prompt_structure(self) -> None:
        """Test VLI family prompt structure and content."""
        project_context = ProjectContext(
            objective="Migrate legacy system to cloud platform"
        )
        
        skills = [
            SkillView(
                id=uuid4(),
                slug="legacy-analyzer",
                name="Legacy System Analyzer",
                description="Analyze legacy COBOL systems",
                kind=SkillKind.ANALYZER,
                body_md="# Legacy Analyzer",
                project_id=uuid4(),
            ),
            SkillView(
                id=uuid4(),
                slug="cloud-architect",
                name="Cloud Platform Architect",
                description="Design cloud architectures",
                kind=SkillKind.AUTHORING,
                body_md="# Cloud Architect",
                project_id=uuid4(),
            ),
        ]
        
        template_family = PhaseVliFamily()
        project_context_str = "Migrate legacy system to cloud platform with modern architecture"
        prompt = ProposeBacklogPrompt.create(project_context_str, skills, template_family)
        
        # Check system prompt has diverse examples
        system_prompt = prompt.system
        assert "Example 1: Data Migration Project" in system_prompt
        assert "Example 2: Web Application Project" in system_prompt
        assert "Example 3: Platform Enhancement Project" in system_prompt
        
        # Check different project patterns are mentioned
        assert "Discovery → Design → Implementation → Testing → Deployment" in system_prompt
        assert "Analysis → Foundation → Implementation → Validation → Cutover" in system_prompt
        assert "Planning → Backend → Frontend → Integration → Launch" in system_prompt
        
        # Check user message contains skills
        user_content = prompt.messages[0].content
        assert "legacy-analyzer" in user_content
        assert "cloud-architect" in user_content
        assert "Migrate legacy system" in user_content

    def test_prompt_with_dummy_provider(self) -> None:
        """Test prompt execution with DummyProvider."""
        project_context = ProjectContext(
            objective="Build customer portal"
        )
        
        skills = [
            SkillView(
                id=uuid4(),
                slug="portal-designer",
                name="Portal Designer",
                description="Design customer portals",
                kind=SkillKind.AUTHORING,
                body_md="# Portal Designer",
                project_id=uuid4(),
            )
        ]
        
        # Create mock response
        mock_response = ProposedBacklog(
            phases=[
                ProposedPhase(
                    code="phase-1-design",
                    name="Design Phase",
                    description="Design the customer portal",
                    cards=[
                        ProposedCard(
                            code="PORTAL-101",
                            title="Portal UI/UX Design",
                            type=CardType.TASK,
                            story_points=5,
                            skill_slugs=["portal-designer"],
                            depends_on_codes=[],
                            short_scope_summary="Create wireframes and mockups for customer portal interface."
                        )
                    ]
                ),
                ProposedPhase(
                    code="phase-2-implementation",
                    name="Implementation Phase", 
                    description="Implement the customer portal",
                    cards=[
                        ProposedCard(
                            code="PORTAL-201",
                            title="Portal Backend Implementation",
                            type=CardType.STORY,
                            story_points=8,
                            skill_slugs=["portal-designer"],
                            depends_on_codes=["PORTAL-101"],
                            short_scope_summary="Build backend API and database for customer portal."
                        )
                    ]
                )
            ],
            rationale_md="Two-phase approach separating design from implementation for clear deliverables.",
            critical_path_codes=["PORTAL-101", "PORTAL-201"]
        )
        
        provider = DummyProvider(fixed_response=mock_response.model_dump())
        template_family = PhaseVliFamily()
        
        project_context_str = "Build customer portal with modern UI/UX and backend integration"
        prompt = ProposeBacklogPrompt.create(project_context_str, skills, template_family)
        result = provider.chat(prompt)
        
        # Verify result structure
        assert result.parsed is not None
        assert isinstance(result.parsed, ProposedBacklog)
        assert len(result.parsed.phases) == 2
        assert result.parsed.phases[0].code == "phase-1-design"
        assert result.parsed.phases[1].code == "phase-2-implementation"
        assert len(result.parsed.phases[0].cards) == 1
        assert result.parsed.phases[0].cards[0].code == "PORTAL-101"
        assert "portal-designer" in result.parsed.phases[0].cards[0].skill_slugs

    @pytest.mark.integration
    def test_prompt_with_anthropic_provider(self) -> None:
        """Test prompt execution with AnthropicProvider (requires API key)."""
        pytest.skip("Integration test requires Anthropic API key - run manually")
        
        # This test would run the actual prompt against Anthropic
        # and validate that the response matches the expected format
        #
        # from app.llm import AnthropicProvider
        # from app.settings import Settings
        # 
        # settings = Settings()
        # if not settings.anthropic_api_key:
        #     pytest.skip("ANTHROPIC_API_KEY not configured")
        # 
        # project_context = ProjectContext(
        #     objective="Build e-commerce API with authentication"
        # )
        # 
        # skills = [
        #     SkillView(
        #         slug="api-architect",
        #         name="API Architect",
        #         description="Design REST APIs with authentication",
        #         kind=SkillKind.AUTHORING
        #     ),
        #     SkillView(
        #         slug="security-implementer", 
        #         name="Security Implementer",
        #         description="Implement OAuth2 and JWT security",
        #         kind=SkillKind.PROCEDURE
        #     )
        # ]
        # 
        # provider = AnthropicProvider(settings)
        # template_family = PhaseVliFamily()
        # prompt = ProposeBacklogPrompt.create(project_context, skills, template_family)
        # result = provider.chat(prompt)
        # 
        # assert result.parsed is not None
        # assert isinstance(result.parsed, ProposedBacklog)
        # assert len(result.parsed.phases) >= 2  # Should create multi-phase backlog
        # assert all(len(phase.cards) >= 1 for phase in result.parsed.phases)
        # assert len(result.parsed.critical_path_codes) >= 1