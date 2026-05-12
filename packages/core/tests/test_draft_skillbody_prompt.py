"""Tests for DraftSkillBodyPrompt."""

import pytest
from uuid import uuid4

from app.enums import SkillKind, SkillResourceLanguage
from app.llm import DummyProvider
from app.prompts import DraftSkillBodyPrompt
from app.schemas.llm_io import DraftedResource, DraftedSkillBody
from app.schemas.views import ProjectContext, SkillView


class TestDraftSkillBodyPrompt:
    """Unit tests for DraftSkillBodyPrompt class."""

    def test_create_prompt_with_context_skill(self) -> None:
        """Test prompt creation for a context skill."""
        skill = SkillView(
            id=uuid4(),
            slug="banking-context",
            name="Banking Domain Context",
            description="Canonical knowledge base for banking systems",
            kind=SkillKind.CONTEXT,
            body_md="# Banking Context\n\nThis is a banking context skill.",
            project_id=uuid4(),
        )
        
        context = ProjectContext(
            objective="Modernize banking system"
        )
        
        sibling_skills = [
            SkillView(
                id=uuid4(),
                slug="cobol-analyzer",
                name="COBOL Code Analyzer",
                description="Analyze legacy COBOL code",
                kind=SkillKind.ANALYZER,
                body_md="# COBOL Analyzer\n\nAnalyze COBOL code.",
                project_id=uuid4(),
            )
        ]
        
        prompt = DraftSkillBodyPrompt.create(skill, context, sibling_skills)
        
        # Check system prompt includes context-specific guidance
        assert "Context skills should include resources like" in prompt.system
        assert "Domain glossaries" in prompt.system
        assert "Reference documentation" in prompt.system
        
        # Check user message contains skill information
        user_content = prompt.messages[0].content
        assert "banking-context" in user_content
        assert "Banking Domain Context" in user_content
        assert "context" in user_content
        assert "cobol-analyzer" in user_content
        
        # Check response schema is correct
        assert prompt.response_schema == DraftedSkillBody

    def test_create_prompt_with_analyzer_skill(self) -> None:
        """Test prompt creation for an analyzer skill."""
        skill = SkillView(
            id=uuid4(),
            slug="code-analyzer",
            name="Legacy Code Analyzer", 
            description="Analyze existing code patterns",
            kind=SkillKind.ANALYZER,
            body_md="# Legacy Code Analyzer\n\nAnalyze code patterns.",
            project_id=uuid4(),
        )
        
        context = ProjectContext(
            objective="Analyze legacy system"
        )
        
        prompt = DraftSkillBodyPrompt.create(skill, context, [])
        
        # Check analyzer-specific guidance
        assert "Analyzer skills should include resources like" in prompt.system
        assert "Analysis checklists" in prompt.system
        assert "SQL queries for data profiling" in prompt.system

    def test_create_prompt_with_authoring_skill(self) -> None:
        """Test prompt creation for an authoring skill."""
        skill = SkillView(
            id=uuid4(),
            slug="api-builder",
            name="REST API Builder",
            description="Build REST APIs using FastAPI",
            kind=SkillKind.AUTHORING,
            body_md="# REST API Builder\n\nBuild APIs with FastAPI.",
            project_id=uuid4(),
        )
        
        context = ProjectContext(
            objective="Build web application"
        )
        
        prompt = DraftSkillBodyPrompt.create(skill, context, [])
        
        # Check authoring-specific guidance
        assert "Authoring skills should include resources like" in prompt.system
        assert "Code templates and examples" in prompt.system
        assert "Implementation guides" in prompt.system

    def test_create_prompt_with_procedure_skill(self) -> None:
        """Test prompt creation for a procedure skill."""
        skill = SkillView(
            id=uuid4(),
            slug="deployment-process",
            name="Deployment Process",
            description="Standard deployment workflow",
            kind=SkillKind.PROCEDURE,
            body_md="# Deployment Process\n\nStandardized deployment workflow.",
            project_id=uuid4(),
        )
        
        context = ProjectContext(
            objective="Standardize deployment"
        )
        
        prompt = DraftSkillBodyPrompt.create(skill, context, [])
        
        # Check procedure-specific guidance
        assert "Procedure skills should include resources like" in prompt.system
        assert "Step-by-step checklists" in prompt.system
        assert "Workflow templates" in prompt.system

    def test_system_prompt_general_guidelines(self) -> None:
        """Test that system prompt includes general guidelines."""
        skill = SkillView(
            id=uuid4(),
            slug="test-skill",
            name="Test Skill",
            description="Test description",
            kind=SkillKind.CONTEXT,
            body_md="# Test Skill\n\nTest skill body.",
            project_id=uuid4(),
        )
        
        context = ProjectContext(objective="Test project")
        
        prompt = DraftSkillBodyPrompt.create(skill, context, [])
        
        # Check general guidance
        assert "markdown body content" in prompt.system
        assert "When to pull in sibling skills" in prompt.system
        assert "body_md" in prompt.system
        assert "resources" in prompt.system
        assert "sibling_skills_referenced" in prompt.system

    def test_user_message_includes_sibling_skills(self) -> None:
        """Test that user message includes sibling skills for reference."""
        skill = SkillView(
            id=uuid4(),
            slug="main-skill",
            name="Main Skill",
            description="Main skill description",
            kind=SkillKind.CONTEXT,
            body_md="# Main Skill\n\nMain skill body.",
            project_id=uuid4(),
        )
        
        context = ProjectContext(objective="Test project")
        
        siblings = [
            SkillView(
                id=uuid4(),
                slug="helper-skill-1",
                name="Helper Skill 1",
                description="Helper description",
                kind=SkillKind.ANALYZER,
                body_md="# Helper Skill 1\n\nHelper skill body.",
                project_id=uuid4(),
            ),
            SkillView(
                id=uuid4(),
                slug="helper-skill-2",
                name="Helper Skill 2",
                description="Another helper",
                kind=SkillKind.PROCEDURE,
                body_md="# Helper Skill 2\n\nAnother helper body.",
                project_id=uuid4(),
            )
        ]
        
        prompt = DraftSkillBodyPrompt.create(skill, context, siblings)
        user_content = prompt.messages[0].content
        
        # Check sibling skills are listed
        assert "helper-skill-1" in user_content
        assert "Helper Skill 1" in user_content
        assert "analyzer" in user_content
        assert "helper-skill-2" in user_content
        assert "Helper Skill 2" in user_content
        assert "procedure" in user_content

    def test_user_message_with_no_sibling_skills(self) -> None:
        """Test that user message handles empty sibling skills list."""
        skill = SkillView(
            id=uuid4(),
            slug="lone-skill",
            name="Lone Skill",
            description="A skill without siblings",
            kind=SkillKind.CONTEXT,
            body_md="# Lone Skill\n\nA skill without siblings.",
            project_id=uuid4(),
        )
        
        context = ProjectContext(objective="Isolated test")
        
        prompt = DraftSkillBodyPrompt.create(skill, context, [])
        user_content = prompt.messages[0].content
        
        # Check it mentions no siblings available
        assert "No sibling skills available" in user_content

    def test_get_recommended_resource_count(self) -> None:
        """Test recommended resource count for different skill kinds."""
        assert DraftSkillBodyPrompt.get_recommended_resource_count(SkillKind.CONTEXT) == 2
        assert DraftSkillBodyPrompt.get_recommended_resource_count(SkillKind.ANALYZER) == 3
        assert DraftSkillBodyPrompt.get_recommended_resource_count(SkillKind.AUTHORING) == 2
        assert DraftSkillBodyPrompt.get_recommended_resource_count(SkillKind.PROCEDURE) == 3

    def test_get_preferred_languages(self) -> None:
        """Test preferred resource languages for different skill kinds."""
        context_langs = DraftSkillBodyPrompt.get_preferred_languages(SkillKind.CONTEXT)
        assert SkillResourceLanguage.MARKDOWN in context_langs
        assert SkillResourceLanguage.YAML in context_langs
        assert SkillResourceLanguage.PLAIN in context_langs
        
        analyzer_langs = DraftSkillBodyPrompt.get_preferred_languages(SkillKind.ANALYZER)
        assert SkillResourceLanguage.MARKDOWN in analyzer_langs
        assert SkillResourceLanguage.SQL in analyzer_langs
        assert SkillResourceLanguage.YAML in analyzer_langs
        
        authoring_langs = DraftSkillBodyPrompt.get_preferred_languages(SkillKind.AUTHORING)
        assert SkillResourceLanguage.PYTHON in authoring_langs
        assert SkillResourceLanguage.SQL in authoring_langs
        assert SkillResourceLanguage.YAML in authoring_langs
        assert SkillResourceLanguage.MARKDOWN in authoring_langs
        
        procedure_langs = DraftSkillBodyPrompt.get_preferred_languages(SkillKind.PROCEDURE)
        assert SkillResourceLanguage.MARKDOWN in procedure_langs
        assert SkillResourceLanguage.YAML in procedure_langs
        assert SkillResourceLanguage.PLAIN in procedure_langs


class TestDraftSkillBodyIntegration:
    """Integration tests for DraftSkillBodyPrompt with LLM providers."""

    def test_prompt_with_dummy_provider(self) -> None:
        """Test prompt execution with DummyProvider."""
        skill = SkillView(
            id=uuid4(),
            slug="test-skill",
            name="Test Integration Skill",
            description="A skill for testing LLM integration",
            kind=SkillKind.AUTHORING,
            body_md="# Test Integration Skill\n\nTesting LLM integration.",
            project_id=uuid4(),
        )
        
        context = ProjectContext(
            objective="Test LLM integration"
        )
        
        # Create mock response
        mock_response = DraftedSkillBody(
            body_md="# Test Skill\n\nThis is a test skill for integration testing.\n\n## When to pull in sibling skills\n\n- Use other skills when needed",
            resources=[
                DraftedResource(
                    filename="test-template.py",
                    language=SkillResourceLanguage.PYTHON,
                    content="# Test template\nprint('Hello, world!')",
                    purpose="Example Python template for testing"
                )
            ],
            sibling_skills_referenced=[]
        )
        
        provider = DummyProvider(fixed_response=mock_response.model_dump())
        
        prompt = DraftSkillBodyPrompt.create(skill, context, [])
        result = provider.chat(prompt)
        
        # Verify result structure
        assert result.parsed is not None
        assert isinstance(result.parsed, DraftedSkillBody)
        assert result.parsed.body_md == mock_response.body_md
        assert len(result.parsed.resources) == 1
        assert result.parsed.resources[0].filename == "test-template.py"
        assert result.parsed.resources[0].language == SkillResourceLanguage.PYTHON

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
        # skill = SkillView(
        #     slug="api-designer",
        #     name="REST API Designer", 
        #     description="Design REST APIs using OpenAPI",
        #     kind=SkillKind.AUTHORING,
        #     rationale="Need consistent API design patterns"
        # )
        # 
        # context = ProjectContext(
        #     objective="Build e-commerce API"
        # )
        # 
        # provider = AnthropicProvider(settings)
        # prompt = DraftSkillBodyPrompt.create(skill, context, [])
        # result = provider.chat(prompt)
        # 
        # assert result.parsed is not None
        # assert isinstance(result.parsed, DraftedSkillBody)
        # assert len(result.parsed.body_md) > 100  # Substantial content
        # assert "When to pull in sibling skills" in result.parsed.body_md
        # assert len(result.parsed.resources) >= 1  # Should include resources