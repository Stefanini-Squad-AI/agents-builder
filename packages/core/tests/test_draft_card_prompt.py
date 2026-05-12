"""Tests for DraftCardPrompt."""

import pytest
from uuid import uuid4
from datetime import datetime, timezone

from app.enums import CardInputKind, CardStatus, CardType, Grouping, LlmProvider, ProjectStatus, SkillKind
from app.families import PhaseVliFamily
from app.families._base import CardDraftContext
from app.llm import DummyProvider
from app.prompts import DraftCardPrompt
from app.schemas.llm_io import DraftedCard, DraftedCardInput
from app.schemas.views import CardInputView, CardView, PhaseView, ProjectView, SkillView


class TestDraftCardPrompt:
    """Unit tests for DraftCardPrompt class."""

    def test_create_prompt_delegates_to_template_family(self) -> None:
        """Test that create method properly delegates to template family."""
        # Create mock context
        context = self._create_mock_context()
        template_family = PhaseVliFamily()
        
        # Call create method
        prompt = DraftCardPrompt.create(context, template_family)
        
        # Verify prompt structure
        assert prompt.system is not None
        assert len(prompt.messages) == 1
        assert prompt.response_schema == DraftedCard
        
        # Verify system prompt contains VLI-specific guidance
        assert "VLI (phase-based) template" in prompt.system
        assert "**Context**:" in prompt.system
        assert "**Task**:" in prompt.system
        assert "**Outputs**:" in prompt.system
        assert "**Acceptance Criteria**:" in prompt.system
        
        # Verify user message contains card information
        user_content = prompt.messages[0].content
        assert "TEST-101" in user_content
        assert "Test Analysis Card" in user_content
        assert "Test Project" in user_content

    def test_build_dependency_context_with_upstream_cards(self) -> None:
        """Test dependency context building with upstream cards."""
        context = self._create_mock_context()
        
        # Add upstream cards
        upstream_card = CardView(
            id=uuid4(),
            code="TEST-001",
            title="Foundation Card",
            phase_id=context.phase.id,
            type=CardType.TASK,
            story_points=3,
            status=CardStatus.DONE,
            human_gate=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            project_id=context.project.id,
        )
        context.upstream_cards = [upstream_card]
        
        dependency_text = DraftCardPrompt.build_dependency_context(context)
        
        assert "**Depends on:**" in dependency_text
        assert "TEST-001: Foundation Card" in dependency_text
        assert "provides foundational work" in dependency_text

    def test_build_dependency_context_with_parallel_cards(self) -> None:
        """Test dependency context building with parallel cards."""
        context = self._create_mock_context()
        
        # Add sibling cards (parallel in same phase)
        parallel_card = CardView(
            id=uuid4(),
            code="TEST-102",
            title="Parallel Card",
            phase_id=context.phase.id,
            type=CardType.STORY,
            story_points=5,
            status=CardStatus.READY,
            human_gate=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            project_id=context.project.id,
        )
        context.sibling_cards_in_phase = [context.card, parallel_card]  # Include self + parallel
        
        dependency_text = DraftCardPrompt.build_dependency_context(context)
        
        assert "**Runs in parallel with:**" in dependency_text
        assert "TEST-102: Parallel Card" in dependency_text

    def test_build_dependency_context_no_dependencies(self) -> None:
        """Test dependency context building with no dependencies."""
        context = self._create_mock_context()
        # Leave upstream_cards and sibling_cards empty
        
        dependency_text = DraftCardPrompt.build_dependency_context(context)
        
        assert dependency_text == "No direct dependencies within this phase."

    def test_build_skills_context(self) -> None:
        """Test skills context building."""
        skills = [
            SkillView(
                id=uuid4(),
                slug="data-analyzer",
                name="Data Analyzer",
                description="Analyze legacy data patterns and quality",
                kind=SkillKind.ANALYZER,
                body_md="# Data Analyzer\n\nAnalyze data.",
                project_id=uuid4(),
            ),
            SkillView(
                id=uuid4(),
                slug="report-generator",
                name="Report Generator", 
                description="Generate comprehensive analysis reports",
                kind=SkillKind.AUTHORING,
                body_md="# Report Generator\n\nGenerate reports.",
                project_id=uuid4(),
            )
        ]
        
        skills_text = DraftCardPrompt.build_skills_context(skills)
        
        assert "**Skills to invoke:**" in skills_text
        assert "`data-analyzer`: Data Analyzer (analyzer)" in skills_text
        assert "Analyze legacy data patterns" in skills_text
        assert "`report-generator`: Report Generator (authoring)" in skills_text
        assert "Generate comprehensive analysis reports" in skills_text

    def test_build_skills_context_empty(self) -> None:
        """Test skills context building with no skills."""
        skills_text = DraftCardPrompt.build_skills_context([])
        assert skills_text == "No specific skills assigned to this card."

    def test_suggest_card_inputs(self) -> None:
        """Test input suggestion based on skills and context."""
        context = self._create_mock_context()
        
        # Add skills of different kinds
        analyzer_skill = SkillView(
            id=uuid4(),
            slug="legacy-analyzer",
            name="Legacy System Analyzer",
            description="Analyze legacy systems",
            kind=SkillKind.ANALYZER,
            body_md="# Legacy Analyzer",
            project_id=context.project.id,
        )
        
        authoring_skill = SkillView(
            id=uuid4(),
            slug="api-builder",
            name="API Builder",
            description="Build REST APIs",
            kind=SkillKind.AUTHORING,
            body_md="# API Builder",
            project_id=context.project.id,
        )
        
        context.skills_used = [analyzer_skill, authoring_skill]
        
        # Add upstream card for artifact input
        upstream_card = CardView(
            id=uuid4(),
            code="TEST-001",
            title="Foundation Work",
            phase_id=context.phase.id,
            type=CardType.TASK,
            story_points=3,
            status=CardStatus.DONE,
            human_gate=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            project_id=context.project.id,
        )
        context.upstream_cards = [upstream_card]
        
        suggestions = DraftCardPrompt.suggest_card_inputs(context)
        
        # Check skill resource suggestions
        skill_suggestions = [s for s in suggestions if s["kind"] == "skill_resource"]
        assert len(skill_suggestions) >= 4  # 2 main skills + 2 resources
        
        # Check main skill files
        assert any(".agents/skills/legacy-analyzer/SKILL.md" in s["path"] for s in skill_suggestions)
        assert any(".agents/skills/api-builder/SKILL.md" in s["path"] for s in skill_suggestions)
        
        # Check kind-specific resources
        assert any("analysis-checklist.md" in s["path"] for s in skill_suggestions)  # analyzer
        assert any("code-template.py" in s["path"] for s in skill_suggestions)  # authoring
        
        # Check artifact suggestions from upstream
        artifact_suggestions = [s for s in suggestions if s["kind"] == "artifact"]
        assert len(artifact_suggestions) >= 1
        assert any("TEST-001-outputs" in s["path"] for s in artifact_suggestions)

    def test_validate_drafted_card_valid(self) -> None:
        """Test validation of a valid drafted card."""
        context = self._create_mock_context()
        
        drafted_card = DraftedCard(
            context_md="This card analyzes legacy data for migration planning.",
            task_md="1. Connect to legacy database\n2. Extract schema information\n3. Generate analysis report",
            outputs_md="- Database schema documentation\n- Data quality report\n- Migration recommendations",
            acceptance_criteria_md="- [ ] Schema extraction completed\n- [ ] Data quality issues identified\n- [ ] Report reviewed by stakeholder",
            inputs=[
                DraftedCardInput(
                    kind=CardInputKind.SKILL_RESOURCE,
                    path=".agents/skills/data-analyzer/SKILL.md", 
                    label="Data analysis methodology"
                )
            ]
        )
        
        # Add matching skill to context
        skill = SkillView(
            id=uuid4(),
            slug="data-analyzer",
            name="Data Analyzer",
            description="Analyze data",
            kind=SkillKind.ANALYZER,
            body_md="# Data Analyzer",
            project_id=context.project.id,
        )
        context.skills_used = [skill]
        
        warnings = DraftCardPrompt.validate_drafted_card(drafted_card, context)
        assert warnings == []  # No warnings for valid card

    def test_validate_drafted_card_empty_sections(self) -> None:
        """Test validation with empty required sections."""
        context = self._create_mock_context()
        
        drafted_card = DraftedCard(
            context_md="",  # Empty
            task_md="Some task content",
            outputs_md="",  # Empty
            acceptance_criteria_md="Some criteria",
            inputs=[]
        )
        
        warnings = DraftCardPrompt.validate_drafted_card(drafted_card, context)
        assert len(warnings) >= 2
        assert any("Context section is empty" in w for w in warnings)
        assert any("Outputs section is empty" in w for w in warnings)

    def test_validate_drafted_card_bad_acceptance_criteria(self) -> None:
        """Test validation with improperly formatted acceptance criteria."""
        context = self._create_mock_context()
        
        drafted_card = DraftedCard(
            context_md="Valid context",
            task_md="Valid task",
            outputs_md="Valid outputs",
            acceptance_criteria_md="Just plain text without checkboxes",  # Invalid format
            inputs=[]
        )
        
        warnings = DraftCardPrompt.validate_drafted_card(drafted_card, context)
        assert any("checkbox format" in w for w in warnings)

    def test_validate_drafted_card_human_gate_mismatch(self) -> None:
        """Test validation of human gate consistency."""
        context = self._create_mock_context()
        
        # Test human_gate=true but no checklist
        context.card.human_gate = True
        drafted_card = DraftedCard(
            context_md="Valid context",
            task_md="Valid task", 
            outputs_md="Valid outputs",
            acceptance_criteria_md="- [ ] Valid criteria",
            human_gate_checklist_md=None,  # Missing despite human_gate=true
            inputs=[]
        )
        
        warnings = DraftCardPrompt.validate_drafted_card(drafted_card, context)
        assert any("human_gate=true but no human gate checklist" in w for w in warnings)
        
        # Test human_gate=false but checklist provided
        context.card.human_gate = False
        drafted_card.human_gate_checklist_md = "- [ ] Unnecessary checklist"
        
        warnings = DraftCardPrompt.validate_drafted_card(drafted_card, context)
        assert any("human_gate=false but human gate checklist provided" in w for w in warnings)

    def test_validate_drafted_card_invalid_skill_references(self) -> None:
        """Test validation of skill resource references."""
        context = self._create_mock_context()
        
        # Add one skill to context
        skill = SkillView(
            id=uuid4(),
            slug="valid-skill",
            name="Valid Skill",
            description="A valid skill",
            kind=SkillKind.CONTEXT,
            body_md="# Valid Skill",
            project_id=context.project.id,
        )
        context.skills_used = [skill]
        
        drafted_card = DraftedCard(
            context_md="Valid context",
            task_md="Valid task",
            outputs_md="Valid outputs",
            acceptance_criteria_md="- [ ] Valid criteria",
            inputs=[
                DraftedCardInput(
                    kind=CardInputKind.SKILL_RESOURCE,
                    path=".agents/skills/invalid-skill/SKILL.md",  # References unknown skill
                    label="Invalid skill reference"
                )
            ]
        )
        
        warnings = DraftCardPrompt.validate_drafted_card(drafted_card, context)
        assert any("skill 'invalid-skill' not in card's skill list" in w for w in warnings)

    def _create_mock_context(self) -> CardDraftContext:
        """Create a mock CardDraftContext for testing."""
        project = ProjectView(
            id=uuid4(),
            tenant_id=uuid4(),
            owner_user_id=uuid4(),
            slug="test-project",
            name="Test Project",
            objective="Test project for unit testing",
            card_code_prefix="TEST",
            card_template="phase_vli",
            grouping=Grouping.PHASE,
            status=ProjectStatus.DRAFT,
            llm_provider=LlmProvider.ANTHROPIC,
            llm_model="claude-3-5-sonnet-20241022",
            llm_temperature=0.7,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        phase = PhaseView(
            id=uuid4(),
            code="phase-1",
            name="Analysis Phase",
            description="Analyze existing systems",
            order_no=1,
            project_id=project.id,
        )
        
        card = CardView(
            id=uuid4(),
            code="TEST-101",
            title="Test Analysis Card",
            phase_id=phase.id,
            type=CardType.TASK,
            story_points=5,
            status=CardStatus.READY,
            human_gate=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            project_id=project.id,
        )
        
        skill = SkillView(
            id=uuid4(),
            slug="test-analyzer",
            name="Test Analyzer",
            description="Analyze test data",
            kind=SkillKind.ANALYZER,
            body_md="# Test Analyzer\n\nAnalyze test data systematically.",
            project_id=project.id,
        )
        
        return CardDraftContext(
            project=project,
            project_context="Test project for analyzing legacy systems and planning migration.",
            phase=phase,
            card=card,
            skills_used=[skill],
            sibling_cards_in_phase=[card],
            upstream_cards=[],
        )


class TestDraftCardIntegration:
    """Integration tests for DraftCardPrompt with template families."""

    def test_vli_family_prompt_structure(self) -> None:
        """Test VLI family prompt structure and content."""
        context = self._create_integration_context()
        template_family = PhaseVliFamily()
        
        prompt = DraftCardPrompt.create(context, template_family)
        
        # Check system prompt has comprehensive examples  
        system_prompt = prompt.system
        assert "Example 1: Analysis Card" in system_prompt
        assert "Example 2: Implementation Card" in system_prompt
        assert "Example 3: Infrastructure Card" in system_prompt
        
        # Check different card patterns are covered
        assert "MIGRATE-101" in system_prompt  # Analysis example
        assert "API-201" in system_prompt      # Implementation example
        assert "INFRA-101" in system_prompt   # Infrastructure example
        
        # Check user message contains context
        user_content = prompt.messages[0].content
        assert "legacy-system-analyzer" in user_content
        assert "API-101" in user_content
        assert "Legacy API Analysis" in user_content

    def test_prompt_with_dummy_provider(self) -> None:
        """Test prompt execution with DummyProvider."""
        context = self._create_integration_context()
        
        # Create mock response
        mock_response = DraftedCard(
            context_md="This card analyzes the legacy API to understand current functionality and identify migration requirements for the new system.",
            task_md="1. Review existing API documentation and code\n2. Test all API endpoints for functionality\n3. Document current request/response formats\n4. Identify breaking changes needed for modernization\n5. Create compatibility matrix for client applications",
            outputs_md="- API functionality documentation (Markdown)\n- Endpoint testing results (CSV)\n- Migration compatibility report (PDF)\n- Recommended modernization plan (Markdown)",
            acceptance_criteria_md="- [ ] All API endpoints documented with examples\n- [ ] Testing results show success/failure for each endpoint\n- [ ] Compatibility report identifies all breaking changes\n- [ ] Migration plan includes timeline and risk assessment",
            inputs=[
                DraftedCardInput(
                    kind=CardInputKind.SKILL_RESOURCE,
                    path=".agents/skills/legacy-system-analyzer/SKILL.md",
                    label="Legacy system analysis methodology"
                ),
                DraftedCardInput(
                    kind=CardInputKind.EXTERNAL,
                    path="legacy/api-documentation.pdf",
                    label="Existing API documentation"
                )
            ]
        )
        
        provider = DummyProvider(fixed_response=mock_response.model_dump())
        template_family = PhaseVliFamily()
        
        prompt = DraftCardPrompt.create(context, template_family)
        result = provider.chat(prompt)
        
        # Verify result structure
        assert result.parsed is not None
        assert isinstance(result.parsed, DraftedCard)
        assert "legacy API" in result.parsed.context_md
        assert "endpoints" in result.parsed.task_md
        assert "documentation" in result.parsed.outputs_md
        assert "- [ ]" in result.parsed.acceptance_criteria_md
        assert len(result.parsed.inputs) == 2
        assert result.parsed.inputs[0].kind == CardInputKind.SKILL_RESOURCE

    @pytest.mark.integration
    def test_prompt_with_anthropic_provider(self) -> None:
        """Test prompt execution with AnthropicProvider (requires API key)."""
        pytest.skip("Integration test requires Anthropic API key - run manually")
        
        # This test would run the actual prompt against Anthropic
        # and validate that the response matches the expected format

    def _create_integration_context(self) -> CardDraftContext:
        """Create an integration test context."""
        from decimal import Decimal
        
        project = ProjectView(
            id=uuid4(),
            tenant_id=uuid4(),
            owner_user_id=uuid4(),
            slug="legacy-migration",
            name="Legacy System Migration",
            objective="Migrate legacy API system to modern cloud architecture",
            card_code_prefix="API",
            card_template="phase_vli",
            grouping=Grouping.PHASE,
            status=ProjectStatus.DRAFT,
            llm_provider=LlmProvider.ANTHROPIC,
            llm_model="claude-3-5-sonnet-20241022",
            llm_temperature=Decimal("0.7"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        phase = PhaseView(
            id=uuid4(),
            code="phase-1-discovery",
            name="Discovery & Analysis",
            description="Analyze existing legacy systems",
            order_no=1,
            project_id=project.id,
        )
        
        card = CardView(
            id=uuid4(),
            code="API-101",
            title="Legacy API Analysis",
            phase_id=phase.id,
            type=CardType.TASK,
            story_points=8,
            status=CardStatus.READY,
            human_gate=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            project_id=project.id,
        )
        
        skill = SkillView(
            id=uuid4(),
            slug="legacy-system-analyzer",
            name="Legacy System Analyzer",
            description="Systematically analyze legacy systems for migration planning",
            kind=SkillKind.ANALYZER,
            body_md="# Legacy System Analyzer\n\nComprehensive methodology for legacy system analysis.",
            project_id=project.id,
        )
        
        return CardDraftContext(
            project=project,
            project_context="Legacy system migration project focusing on API modernization with cloud-native architecture.",
            phase=phase,
            card=card,
            skills_used=[skill],
            sibling_cards_in_phase=[card],
            upstream_cards=[],
        )