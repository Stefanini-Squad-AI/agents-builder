"""Tests for ProposeSkillSet prompt implementation."""

import pytest

from app.llm import DummyProvider
from app.prompts.propose_skillset import ProposeSkillSetPrompt
from app.schemas.llm_io import ProposedSkillSet
from app.schemas.views import ArtifactSummary, ProjectContext, TechChoiceView


class TestProposeSkillSetPrompt:
    """Test ProposeSkillSetPrompt functionality."""
    
    def test_create_prompt_with_minimal_context(self) -> None:
        """Test creating prompt with just objective."""
        context = ProjectContext(
            objective="Modernize legacy banking system from COBOL to Java"
        )
        
        prompt = ProposeSkillSetPrompt.create(context)
        
        assert len(prompt.messages) == 1
        assert prompt.messages[0].role == "user"
        assert prompt.system is not None
        assert prompt.response_schema == ProposedSkillSet
        
        # Check that objective is in user message
        user_content = prompt.messages[0].content
        assert "Modernize legacy banking system from COBOL to Java" in user_content
        assert "**Examples from similar projects:**" in user_content
    
    def test_create_prompt_with_full_context(self) -> None:
        """Test creating prompt with complete project context."""
        context = ProjectContext(
            objective="Build a customer management system with role-based access",
            qa={
                "target_users": "Internal staff and external partners",
                "data_volume": "~10,000 customers, moderate transaction volume",
                "security_requirements": "Role-based access, audit logging required"
            },
            tech_choices_by_dimension={
                "backend_framework": [
                    TechChoiceView(
                        id="550e8400-e29b-41d4-a716-446655440001",
                        project_id="550e8400-e29b-41d4-a716-446655440000", 
                        dimension_id="550e8400-e29b-41d4-a716-446655440010",
                        dimension_slug="backend_framework",
                        dimension_name="Backend Framework",
                        tech_item_id="550e8400-e29b-41d4-a716-446655440011",
                        tech_item_slug="nestjs",
                        tech_item_name="NestJS",
                        role="target",
                        source="catalog",
                        accepted=True,
                        llm_rationale="TypeScript, good ecosystem",
                        llm_confidence=0.9,
                        created_at="2024-01-01T00:00:00Z",
                        updated_at="2024-01-01T00:00:00Z"
                    )
                ],
                "database": [
                    TechChoiceView(
                        id="550e8400-e29b-41d4-a716-446655440002",
                        project_id="550e8400-e29b-41d4-a716-446655440000", 
                        dimension_id="550e8400-e29b-41d4-a716-446655440020",
                        dimension_slug="database",
                        dimension_name="Database",
                        tech_item_id="550e8400-e29b-41d4-a716-446655440021", 
                        tech_item_slug="postgresql",
                        tech_item_name="PostgreSQL",
                        role="target",
                        source="catalog",
                        accepted=True,
                        llm_rationale="Reliable, good performance",
                        llm_confidence=0.8,
                        created_at="2024-01-01T00:00:00Z",
                        updated_at="2024-01-01T00:00:00Z"
                    )
                ]
            },
            artifact_summaries=[
                ArtifactSummary(
                    id="550e8400-e29b-41d4-a716-446655440003",
                    filename="requirements.pdf", 
                    kind="doc",
                    extraction_status="extracted",
                    size_bytes=1024000,
                    content_md_excerpt="Detailed functional requirements including user roles, permissions matrix, and API specifications. The system shall support role-based access control with the following roles: Admin, Manager, User...",
                    content_md_truncated=True
                )
            ],
            context_notes_md="This system will replace an existing Access database. Migration of ~10k customer records required."
        )
        
        prompt = ProposeSkillSetPrompt.create(context)
        user_content = prompt.messages[0].content
        
        # Check all context elements are included
        assert "Build a customer management system" in user_content
        assert "**Discovery Q&A:**" in user_content
        assert "Internal staff and external partners" in user_content
        assert "**Technology Choices:**" in user_content  
        assert "NestJS" in user_content
        assert "PostgreSQL" in user_content
        assert "**Uploaded Artifacts:**" in user_content
        assert "requirements.pdf" in user_content
        assert "**Additional Context:**" in user_content
        assert "Access database" in user_content
        
    def test_few_shot_examples_included(self) -> None:
        """Test that few-shot examples are properly included."""
        context = ProjectContext(
            objective="Migrate SSIS packages to cloud data platform"
        )
        
        prompt = ProposeSkillSetPrompt.create(context)
        user_content = prompt.messages[0].content
        
        # Check generic few-shot examples are present (8 total examples)
        # Original 5 examples
        assert "banking-domain-context" in user_content
        assert "legacy-cobol-analyzer" in user_content  
        assert "microservices-decomposer" in user_content
        assert "ai-code-analyzer" in user_content
        assert "fullstack-feature-architect" in user_content
        assert "event-architecture-designer" in user_content
        
        # Phase 3 additions (3 new examples)
        assert "spring-boot-service-architect" in user_content
        assert "junit-test-strategist" in user_content
        assert "dotnet-realtime-processor" in user_content
        assert "automotive-domain-modeler" in user_content
        assert "flask-api-architect" in user_content
        assert "telecom-network-modeler" in user_content
        assert "pytest-automation-designer" in user_content
        
        # Check example structure covers major domains (8 total)
        assert "Legacy Banking System Modernization" in user_content
        assert "Cloud-Native Microservices Platform" in user_content
        assert "AI-Powered Development Platform" in user_content
        assert "Full-Stack Web Application" in user_content
        assert "Enterprise Data Platform" in user_content
        assert "Enterprise Java Platform" in user_content
        assert "Automotive IoT System" in user_content
        assert "Telecom Network Management" in user_content
        
        # Verify old specific examples are NOT present
        assert "siglm-context" not in user_content
        assert "corp-legacy-analyzer" not in user_content
        assert "cronos-ssis-migrator" not in user_content
        
    def test_system_prompt_guidelines(self) -> None:
        """Test that system prompt includes proper guidelines."""
        context = ProjectContext(objective="Test project")
        
        prompt = ProposeSkillSetPrompt.create(context)
        system_content = prompt.system
        
        # Check skill type guidance
        assert "context" in system_content
        assert "analyzer" in system_content
        assert "authoring" in system_content
        assert "procedure" in system_content
        
        # Check quality guidelines
        assert "reusable" in system_content
        assert "distinct capability" in system_content
        assert "reference each other" in system_content
        assert "trigger scenarios" in system_content


class TestProposeSkillSetIntegration:
    """Integration tests with real LLM providers."""
    
    def test_prompt_with_dummy_provider(self) -> None:
        """Test prompt execution with DummyProvider."""
        context = ProjectContext(
            objective="Create a REST API for inventory management",
            qa={"complexity": "Medium complexity, ~20 endpoints"},
            tech_choices_by_dimension={},
            artifact_summaries=[],
            context_notes_md=""
        )
        
        # Create a valid mock response for ProposedSkillSet
        mock_response = {
            "skills": [
                {
                    "slug": "inventory-context",
                    "name": "Inventory Domain Context",
                    "description": "Domain knowledge for inventory management including business rules, data models, and API patterns. Use when working with inventory-related features.",
                    "kind": "context",
                    "rationale": "Inventory systems have specific domain concepts that need centralized documentation",
                    "sibling_refs": ["inventory-api-generator"]
                },
                {
                    "slug": "inventory-api-generator", 
                    "name": "Inventory API Generator",
                    "description": "Generate REST endpoints for inventory operations (CRUD, search, reporting). Use when adding new inventory API endpoints.",
                    "kind": "authoring",
                    "rationale": "REST APIs follow consistent patterns that can be automated",
                    "sibling_refs": ["inventory-context"]
                },
                {
                    "slug": "inventory-data-analyzer",
                    "name": "Inventory Data Analyzer", 
                    "description": "Analyze existing inventory data structures and relationships. Use when assessing current inventory system or planning migrations.",
                    "kind": "analyzer",
                    "rationale": "Data analysis is needed before implementing new inventory features",
                    "sibling_refs": ["inventory-context"]
                },
                {
                    "slug": "inventory-deployment",
                    "name": "Inventory API Deployment",
                    "description": "Deploy and configure inventory API services including database setup and monitoring. Use for production deployments.",
                    "kind": "procedure", 
                    "rationale": "Deployment requires specific operational steps and configurations",
                    "sibling_refs": ["inventory-api-generator"]
                },
                {
                    "slug": "inventory-testing",
                    "name": "Inventory API Testing",
                    "description": "Generate comprehensive test suites for inventory API endpoints including unit and integration tests. Use when adding test coverage.",
                    "kind": "authoring",
                    "rationale": "API testing requires consistent patterns and good coverage",
                    "sibling_refs": ["inventory-api-generator"]
                }
            ],
            "coverage_notes": "Covers inventory domain knowledge, API development, data analysis, deployment, and testing aspects",
            "gaps": ["Performance monitoring", "Security audit procedures"]
        }
        
        prompt = ProposeSkillSetPrompt.create(context)
        provider = DummyProvider(fixed_response=mock_response)
        
        # DummyProvider should handle the prompt without errors
        result = provider.chat(prompt)
        
        # Basic validation of DummyProvider response structure
        assert result.parsed is not None
        assert isinstance(result.parsed, ProposedSkillSet)
        
        # The DummyProvider returns a mock ProposedSkillSet
        skill_set = result.parsed
        assert isinstance(skill_set, ProposedSkillSet)
        assert len(skill_set.skills) == 5  # Our mock has exactly 5 skills
        
        # Check skill kinds are valid and diverse
        valid_kinds = {"context", "analyzer", "authoring", "procedure"}
        skill_kinds = {skill.kind for skill in skill_set.skills}
        assert all(kind in valid_kinds for kind in skill_kinds)
        assert len(skill_kinds) >= 3  # Should have at least 3 different skill types
        
        # Validate skill structure
        for skill in skill_set.skills:
            assert len(skill.slug) > 0
            assert len(skill.name) > 0
            assert len(skill.description) > 0
            assert len(skill.rationale) > 0
            assert skill.slug.startswith("inventory")  # Should be project-prefixed
        
        # Validate coverage information
        assert len(skill_set.coverage_notes) > 0
        assert isinstance(skill_set.gaps, list)
    
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
        # context = ProjectContext(
        #     objective="Build a microservices-based e-commerce platform",
        #     qa={"scale": "High traffic, 1M+ users expected"},
        #     tech_choices_by_dimension={
        #         "architecture": [TechChoiceView(name="Microservices", ...)]
        #     }
        # )
        # 
        # prompt = ProposeSkillSetPrompt.create(context)
        # provider = AnthropicProvider(api_key=settings.anthropic_api_key)
        # 
        # result = provider.chat(prompt)
        # 
        # assert result.success is True
        # skill_set = result.parsed_output
        # assert len(skill_set.skills) >= 5
        # assert len(skill_set.skills) <= 10
        # 
        # # Validate realistic skill proposals for e-commerce
        # skill_names = [skill.name.lower() for skill in skill_set.skills]
        # # Should include context skills for domain knowledge
        # assert any("context" in skill.kind for skill in skill_set.skills)
        # # Should include analyzer skills for assessment  
        # assert any("analyzer" in skill.kind for skill in skill_set.skills)
        # # Should include authoring skills for implementation
        # assert any("authoring" in skill.kind for skill in skill_set.skills)