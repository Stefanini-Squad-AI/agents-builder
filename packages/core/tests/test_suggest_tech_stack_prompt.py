"""Tests for SuggestTechStackPrompt."""

import pytest
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, timezone

from app.enums import ArtifactKind, ExtractionStatus, Grouping, LlmProvider, ProjectStatus, TechChoiceRole, TechChoiceSource
from app.llm import DummyProvider
from app.prompts import SuggestTechStackPrompt
from app.schemas.llm_io import SuggestedTechForDimension, SuggestedTechItem
from app.schemas.views import (
    ArtifactSummary, ProjectContext, QaAnswerView, TechChoiceView, 
    TechDimensionView, TechItemView
)


class TestSuggestTechStackPrompt:
    """Unit tests for SuggestTechStackPrompt class."""

    def test_create_prompt_basic_structure(self) -> None:
        """Test basic prompt creation and structure."""
        project_context = self._create_mock_project_context()
        dimension = self._create_mock_dimension("languages")
        
        prompt = SuggestTechStackPrompt.create(project_context, dimension)
        
        # Verify prompt structure
        assert prompt.system is not None
        assert len(prompt.messages) == 1
        assert prompt.response_schema == SuggestedTechForDimension
        
        # Check system prompt contains dimension-specific info
        assert "Linguagens" in prompt.system  # dimension name
        assert "Programming languages" in prompt.system  # dimension description
        assert "Available Catalog Items" in prompt.system
        assert "python" in prompt.system.lower()  # catalog item
        
        # Check user message contains project info
        user_content = prompt.messages[0].content
        assert "Migrate legacy COBOL system" in user_content  # project objective
        assert "**Target Dimension:** Linguagens" in user_content
        assert "**Project Context:**" in user_content

    def test_create_prompt_with_existing_choices(self) -> None:
        """Test prompt creation with existing tech choices for context."""
        project_context = self._create_mock_project_context()
        dimension = self._create_mock_dimension("databases")
        
        # Add existing choices
        existing_choices = [
            TechChoiceView(
                id=uuid4(),
                project_id=uuid4(),
                dimension_id=uuid4(),
                dimension_slug="languages",
                dimension_name="Linguagens",
                tech_item_id=uuid4(),
                tech_item_slug="java",
                tech_item_name="Java",
                role=TechChoiceRole.TARGET,
                source=TechChoiceSource.CATALOG,
                llm_confidence=Decimal("0.9"),
            ),
            TechChoiceView(
                id=uuid4(),
                project_id=uuid4(),
                dimension_id=uuid4(),
                dimension_slug="backend_framework",
                dimension_name="Frameworks backend",
                tech_item_id=uuid4(),
                tech_item_slug="spring-boot",
                tech_item_name="Spring Boot",
                role=TechChoiceRole.TARGET,
                source=TechChoiceSource.CATALOG,
                llm_confidence=Decimal("0.85"),
            )
        ]
        
        prompt = SuggestTechStackPrompt.create(project_context, dimension, existing_choices)
        
        user_content = prompt.messages[0].content
        assert "**Current Technology Choices:**" in user_content
        assert "Java (target)" in user_content
        assert "Spring Boot (target)" in user_content
        # Check that dimensions are listed
        assert "Linguagens" in user_content or "Languages" in user_content
        assert "Frameworks backend" in user_content

    def test_create_prompt_no_existing_choices(self) -> None:
        """Test prompt creation with no existing choices."""
        project_context = self._create_mock_project_context()
        dimension = self._create_mock_dimension("frontend_framework")
        
        prompt = SuggestTechStackPrompt.create(project_context, dimension, [])
        
        user_content = prompt.messages[0].content
        assert "**Current Technology Choices:** None selected yet" in user_content

    def test_format_catalog_items_with_tags(self) -> None:
        """Test catalog items formatting with tag-based categorization."""
        items = [
            TechItemView(
                id=uuid4(),
                dimension_id=uuid4(),
                slug="python",
                name="Python",
                description="High-level programming language",
                tags=["scripting", "async", "ml"],
                is_custom=False
            ),
            TechItemView(
                id=uuid4(),
                dimension_id=uuid4(),
                slug="java",
                name="Java", 
                description="Enterprise programming language",
                tags=["enterprise", "jvm"],
                is_custom=False
            ),
            TechItemView(
                id=uuid4(),
                dimension_id=uuid4(),
                slug="go",
                name="Go",
                description="Systems programming language",
                tags=["scripting", "performance"],
                is_custom=False
            )
        ]
        
        formatted = SuggestTechStackPrompt._format_catalog_items(items)
        
        # Should be organized by first tag (category)
        assert "**Scripting:**" in formatted
        assert "**Enterprise:**" in formatted
        assert "`python`: Python [scripting, async, ml]" in formatted
        assert "`java`: Java [enterprise, jvm]" in formatted
        assert "`go`: Go [scripting, performance]" in formatted

    def test_format_catalog_items_no_tags(self) -> None:
        """Test catalog items formatting without tags."""
        items = [
            TechItemView(
                id=uuid4(),
                dimension_id=uuid4(),
                slug="custom-lang",
                name="Custom Language",
                description="Custom internal language",
                tags=[],
                is_custom=True
            )
        ]
        
        formatted = SuggestTechStackPrompt._format_catalog_items(items)
        
        assert "**Other:**" in formatted
        assert "`custom-lang`: Custom Language" in formatted

    def test_format_catalog_items_empty(self) -> None:
        """Test catalog items formatting with empty list."""
        formatted = SuggestTechStackPrompt._format_catalog_items([])
        assert formatted == "No catalog items available for this dimension."

    def test_group_choices_by_dimension(self) -> None:
        """Test grouping tech choices by dimension."""
        choices = [
            TechChoiceView(
                id=uuid4(),
                project_id=uuid4(),
                dimension_id=uuid4(),
                dimension_slug="languages",
                dimension_name="Linguagens",
                tech_item_id=uuid4(),
                tech_item_slug="python",
                tech_item_name="Python",
                role=TechChoiceRole.TARGET,
                source=TechChoiceSource.CATALOG,
            ),
            TechChoiceView(
                id=uuid4(),
                project_id=uuid4(),
                dimension_id=uuid4(),
                dimension_slug="languages",
                dimension_name="Linguagens", 
                tech_item_id=uuid4(),
                tech_item_slug="java",
                tech_item_name="Java",
                role=TechChoiceRole.LEGACY,
                source=TechChoiceSource.CATALOG,
            ),
            TechChoiceView(
                id=uuid4(),
                project_id=uuid4(),
                dimension_id=uuid4(),
                dimension_slug="databases",
                dimension_name="Databases",
                tech_item_id=uuid4(),
                tech_item_slug="postgresql",
                tech_item_name="PostgreSQL",
                role=TechChoiceRole.TARGET,
                source=TechChoiceSource.CATALOG,
            )
        ]
        
        groups = SuggestTechStackPrompt._group_choices_by_dimension(choices)
        
        assert len(groups) == 2
        assert "Linguagens" in groups
        assert "Databases" in groups
        assert len(groups["Linguagens"]) == 2
        assert len(groups["Databases"]) == 1

    def test_validate_suggestions_valid(self) -> None:
        """Test validation of valid suggestions."""
        dimension = self._create_mock_dimension("languages")
        suggestions = SuggestedTechForDimension(
            dimension_slug="languages",
            items=[
                SuggestedTechItem(
                    catalog_slug="python",
                    free_form_name=None,
                    role=TechChoiceRole.TARGET,
                    rationale="Excellent for rapid development and has strong ML libraries",
                    confidence=0.9
                ),
                SuggestedTechItem(
                    catalog_slug=None,
                    free_form_name="Rust",
                    role=TechChoiceRole.OPTIONAL,
                    rationale="High-performance systems language for performance-critical components",
                    confidence=0.7
                )
            ],
            reasoning_summary="Python provides rapid development capabilities while Rust offers performance optimization opportunities."
        )
        
        warnings = SuggestTechStackPrompt.validate_suggestions(suggestions, dimension)
        assert warnings == []  # Should be valid

    def test_validate_suggestions_dimension_mismatch(self) -> None:
        """Test validation with dimension slug mismatch."""
        dimension = self._create_mock_dimension("languages")
        suggestions = SuggestedTechForDimension(
            dimension_slug="databases",  # Wrong dimension
            items=[],
            reasoning_summary="Test summary"
        )
        
        warnings = SuggestTechStackPrompt.validate_suggestions(suggestions, dimension)
        assert len(warnings) >= 1
        assert any("Dimension slug mismatch" in w for w in warnings)

    def test_validate_suggestions_unknown_catalog_slug(self) -> None:
        """Test validation with unknown catalog slug."""
        dimension = self._create_mock_dimension("languages") 
        suggestions = SuggestedTechForDimension(
            dimension_slug="languages",
            items=[
                SuggestedTechItem(
                    catalog_slug="nonexistent-lang",  # Unknown slug
                    free_form_name=None,
                    role=TechChoiceRole.TARGET,
                    rationale="Test rationale",
                    confidence=0.8
                )
            ],
            reasoning_summary="Test summary"
        )
        
        warnings = SuggestTechStackPrompt.validate_suggestions(suggestions, dimension)
        assert any("Unknown catalog slug" in w for w in warnings)

    def test_validate_suggestions_mutual_exclusivity(self) -> None:
        """Test validation of catalog_slug and free_form_name mutual exclusivity."""
        dimension = self._create_mock_dimension("languages")
        suggestions = SuggestedTechForDimension(
            dimension_slug="languages",
            items=[
                SuggestedTechItem(
                    catalog_slug="python",
                    free_form_name="Python Custom",  # Both set - invalid
                    role=TechChoiceRole.TARGET,
                    rationale="Test rationale",
                    confidence=0.8
                ),
                SuggestedTechItem(
                    catalog_slug=None,
                    free_form_name=None,  # Neither set - invalid
                    role=TechChoiceRole.TARGET,
                    rationale="Test rationale",
                    confidence=0.7
                )
            ],
            reasoning_summary="Test summary"
        )
        
        warnings = SuggestTechStackPrompt.validate_suggestions(suggestions, dimension)
        assert any("both catalog_slug" in w and "free_form_name" in w for w in warnings)
        assert any("neither catalog_slug nor free_form_name" in w for w in warnings)

    def test_validate_suggestions_confidence_extremes(self) -> None:
        """Test validation of extreme confidence scores."""
        dimension = self._create_mock_dimension("languages")
        
        # Very low confidence
        low_suggestions = SuggestedTechForDimension(
            dimension_slug="languages",
            items=[
                SuggestedTechItem(
                    catalog_slug="python",
                    free_form_name=None,
                    role=TechChoiceRole.TARGET,
                    rationale="Test",
                    confidence=0.1  # Very low
                )
            ],
            reasoning_summary="Test"
        )
        
        warnings = SuggestTechStackPrompt.validate_suggestions(low_suggestions, dimension)
        assert any("Average confidence is very low" in w for w in warnings)
        
        # Very high confidence  
        high_suggestions = SuggestedTechForDimension(
            dimension_slug="languages",
            items=[
                SuggestedTechItem(
                    catalog_slug="python",
                    free_form_name=None,
                    role=TechChoiceRole.TARGET,
                    rationale="Test",
                    confidence=0.99  # Very high
                )
            ],
            reasoning_summary="Test"
        )
        
        warnings = SuggestTechStackPrompt.validate_suggestions(high_suggestions, dimension)
        assert any("unusually high" in w for w in warnings)

    def test_validate_suggestions_no_target_role(self) -> None:
        """Test validation when no TARGET role is provided."""
        dimension = self._create_mock_dimension("languages")
        suggestions = SuggestedTechForDimension(
            dimension_slug="languages",
            items=[
                SuggestedTechItem(
                    catalog_slug="python",
                    free_form_name=None,
                    role=TechChoiceRole.OPTIONAL,  # No TARGET
                    rationale="Test rationale",
                    confidence=0.8
                )
            ],
            reasoning_summary="Test summary"
        )
        
        warnings = SuggestTechStackPrompt.validate_suggestions(suggestions, dimension)
        assert any("No TARGET role suggestions" in w for w in warnings)

    def test_suggest_prompt_optimizations(self) -> None:
        """Test prompt optimization suggestions."""
        # Minimal context
        minimal_context = ProjectContext(
            objective="",  # Empty objective
            qa={},  # No Q&A
            tech_choices_by_dimension={},  # No tech choices
            artifact_summaries=[]  # No artifacts
        )
        
        dimension = self._create_mock_dimension("databases")
        optimizations = SuggestTechStackPrompt.suggest_prompt_optimizations(minimal_context, dimension)
        
        assert len(optimizations) >= 3
        assert any("project objective" in opt for opt in optimizations)
        assert any("existing tech choices" in opt for opt in optimizations)
        assert any("Q&A questions" in opt for opt in optimizations)

    def test_suggest_prompt_optimizations_dimension_specific(self) -> None:
        """Test dimension-specific optimization suggestions."""
        project_context = self._create_mock_project_context()
        
        # Database dimension without data requirements
        db_dimension = self._create_mock_dimension("databases")
        db_optimizations = SuggestTechStackPrompt.suggest_prompt_optimizations(project_context, db_dimension)
        # Should suggest clarifying data requirements since "data" not in objective
        
        # Languages dimension without artifacts
        lang_dimension = self._create_mock_dimension("languages")
        lang_optimizations = SuggestTechStackPrompt.suggest_prompt_optimizations(project_context, lang_dimension)
        # May suggest providing artifacts for technical understanding

    def _create_mock_project_context(self) -> ProjectContext:
        """Create a mock ProjectContext for testing."""
        return ProjectContext(
            objective="Migrate legacy COBOL system to modern cloud-native architecture using Java and Spring Boot",
            qa={
                "business_driver": "Cost reduction and improved maintainability"
            },
            tech_choices_by_dimension={
                "languages": [
                    TechChoiceView(
                        id=uuid4(),
                        project_id=uuid4(),
                        dimension_id=uuid4(),
                        dimension_slug="languages",
                        dimension_name="Linguagens",
                        tech_item_id=uuid4(),
                        tech_item_slug="cobol",
                        tech_item_name="COBOL",
                        role=TechChoiceRole.LEGACY,
                        source=TechChoiceSource.CATALOG,
                    )
                ]
            },
            artifact_summaries=[
                ArtifactSummary(
                    id=uuid4(),
                    filename="legacy-system-analysis.pdf",
                    kind=ArtifactKind.DOC,
                    extraction_status=ExtractionStatus.EXTRACTED,
                    size_bytes=50000,
                    content_md_excerpt="Analysis of existing COBOL codebase shows approximately 200,000 lines..."
                )
            ]
        )

    def _create_mock_dimension(self, slug: str) -> TechDimensionView:
        """Create a mock TechDimensionView for testing.""" 
        if slug == "languages":
            return TechDimensionView(
                id=uuid4(),
                slug="languages",
                name="Linguagens",
                description="Programming languages targeted by this project (or being migrated from).",
                order_no=1,
                items=[
                    TechItemView(
                        id=uuid4(),
                        dimension_id=uuid4(),
                        slug="python",
                        name="Python",
                        description="High-level programming language",
                        tags=["scripting", "async", "ml", "backend"],
                        is_custom=False
                    ),
                    TechItemView(
                        id=uuid4(),
                        dimension_id=uuid4(),
                        slug="java",
                        name="Java",
                        description="Enterprise programming language",
                        tags=["enterprise", "jvm", "backend"],
                        is_custom=False
                    ),
                    TechItemView(
                        id=uuid4(),
                        dimension_id=uuid4(),
                        slug="javascript",
                        name="JavaScript", 
                        description="Web programming language",
                        tags=["web", "frontend", "backend"],
                        is_custom=False
                    )
                ]
            )
        elif slug == "databases":
            return TechDimensionView(
                id=uuid4(),
                slug="databases",
                name="Databases",
                description="Database systems for data persistence and management.",
                order_no=5,
                items=[
                    TechItemView(
                        id=uuid4(),
                        dimension_id=uuid4(),
                        slug="postgresql",
                        name="PostgreSQL",
                        description="Advanced open-source relational database",
                        tags=["relational", "sql", "open-source"],
                        is_custom=False
                    ),
                    TechItemView(
                        id=uuid4(),
                        dimension_id=uuid4(),
                        slug="mongodb",
                        name="MongoDB",
                        description="Document-oriented NoSQL database",
                        tags=["nosql", "document", "json"],
                        is_custom=False
                    )
                ]
            )
        else:
            return TechDimensionView(
                id=uuid4(),
                slug=slug,
                name=slug.replace("_", " ").title(),
                description=f"Mock dimension for {slug}",
                order_no=1,
                items=[]
            )


class TestSuggestTechStackIntegration:
    """Integration tests for SuggestTechStackPrompt."""

    def test_prompt_with_dummy_provider(self) -> None:
        """Test prompt execution with DummyProvider."""
        project_context = self._create_integration_context()
        dimension = self._create_integration_dimension()
        
        # Create mock response
        mock_response = SuggestedTechForDimension(
            dimension_slug="backend_framework",
            items=[
                SuggestedTechItem(
                    catalog_slug="spring-boot",
                    free_form_name=None,
                    role=TechChoiceRole.TARGET,
                    rationale="Excellent choice for enterprise Java applications with strong ecosystem and Spring framework integration. Provides production-ready features out of the box.",
                    confidence=0.9
                ),
                SuggestedTechItem(
                    catalog_slug="quarkus",
                    free_form_name=None,
                    role=TechChoiceRole.OPTIONAL,
                    rationale="Cloud-native Java framework optimized for containerization and fast startup times. Good alternative for microservices.",
                    confidence=0.75
                ),
                SuggestedTechItem(
                    catalog_slug=None,
                    free_form_name="Legacy COBOL Runtime",
                    role=TechChoiceRole.LEGACY,
                    rationale="Current legacy system runtime that needs to be gradually replaced during migration.",
                    confidence=1.0
                )
            ],
            reasoning_summary="Spring Boot provides the best migration path from COBOL to modern Java architecture, with Quarkus as an alternative for cloud-native deployments. Legacy runtime identified for migration planning."
        )
        
        provider = DummyProvider(fixed_response=mock_response.model_dump())
        
        prompt = SuggestTechStackPrompt.create(project_context, dimension)
        result = provider.chat(prompt)
        
        # Verify result structure
        assert result.parsed is not None
        assert isinstance(result.parsed, SuggestedTechForDimension)
        assert result.parsed.dimension_slug == "backend_framework"
        assert len(result.parsed.items) == 3
        
        # Check item details
        target_item = next(item for item in result.parsed.items if item.role == TechChoiceRole.TARGET)
        assert target_item.catalog_slug == "spring-boot"
        assert target_item.confidence == 0.9
        assert "enterprise Java" in target_item.rationale
        
        legacy_item = next(item for item in result.parsed.items if item.role == TechChoiceRole.LEGACY)
        assert legacy_item.free_form_name == "Legacy COBOL Runtime"
        assert legacy_item.catalog_slug is None
        
        # Validate suggestions
        warnings = SuggestTechStackPrompt.validate_suggestions(result.parsed, dimension)
        assert len(warnings) == 0  # Should be valid

    @pytest.mark.integration
    def test_integration_with_seeded_tech_catalog(self) -> None:
        """Test prompt generation with real seeded tech catalog data."""
        # This would require database setup - mark as integration test
        pytest.skip("Integration test requires seeded database - for demo only")
        
        # Example of how this would work with real data:
        # with session_scope() as session:
        #     # Query real dimension with catalog items
        #     dimension_query = select(TechDimension).where(
        #         TechDimension.slug == "languages"
        #     ).options(selectinload(TechDimension.items))
        #     dimension_orm = session.execute(dimension_query).scalar_one_or_none()
        #     
        #     if dimension_orm:
        #         # Convert to view model
        #         dimension_view = TechDimensionView(...)
        #         # Test with real catalog data
        #         prompt = SuggestTechStackPrompt.create(context, dimension_view)
        #         assert len(dimension_view.items) > 0
        
    @pytest.mark.integration
    def test_prompt_with_anthropic_provider(self) -> None:
        """Test prompt execution with AnthropicProvider (requires API key)."""
        pytest.skip("Integration test requires Anthropic API key - run manually")

    def _create_integration_context(self) -> ProjectContext:
        """Create an integration test context."""
        return ProjectContext(
            objective="Migrate legacy COBOL mainframe system to modern cloud-native microservices architecture using Java ecosystem with emphasis on scalability and maintainability",
            qa={
                "deployment_environment": "AWS cloud with Kubernetes orchestration",
                "performance_requirements": "Handle 10,000 concurrent users with sub-200ms response times"
            },
            tech_choices_by_dimension={
                "languages": [
                    TechChoiceView(
                        id=uuid4(),
                        project_id=uuid4(),
                        dimension_id=uuid4(),
                        dimension_slug="languages",
                        dimension_name="Linguagens",
                        tech_item_id=uuid4(),
                        tech_item_slug="java",
                        tech_item_name="Java",
                        role=TechChoiceRole.TARGET,
                        source=TechChoiceSource.CATALOG,
                        llm_confidence=Decimal("0.95"),
                    ),
                    TechChoiceView(
                        id=uuid4(),
                        project_id=uuid4(),
                        dimension_id=uuid4(),
                        dimension_slug="languages",
                        dimension_name="Linguagens",
                        tech_item_id=uuid4(),
                        tech_item_slug="cobol",
                        tech_item_name="COBOL",
                        role=TechChoiceRole.LEGACY,
                        source=TechChoiceSource.CATALOG,
                        llm_confidence=Decimal("1.0"),
                    )
                ]
            },
            artifact_summaries=[
                ArtifactSummary(
                    id=uuid4(),
                    filename="mainframe-analysis.md",
                    kind=ArtifactKind.DOC,
                    extraction_status=ExtractionStatus.EXTRACTED,
                    size_bytes=75000,
                    content_md_excerpt="Legacy system processes 50,000 transactions daily with complex business rules embedded in COBOL programs..."
                )
            ]
        )

    def _create_integration_dimension(self) -> TechDimensionView:
        """Create an integration test dimension."""
        return TechDimensionView(
            id=uuid4(),
            slug="backend_framework",
            name="Frameworks backend",
            description="Server-side frameworks targeted (or being modernized from).",
            order_no=2,
            items=[
                TechItemView(
                    id=uuid4(),
                    dimension_id=uuid4(),
                    slug="spring-boot",
                    name="Spring Boot",
                    description="Comprehensive Java framework for enterprise applications",
                    tags=["java", "jvm", "enterprise"],
                    is_custom=False
                ),
                TechItemView(
                    id=uuid4(),
                    dimension_id=uuid4(),
                    slug="quarkus",
                    name="Quarkus",
                    description="Cloud-native Java framework",
                    tags=["java", "jvm", "native", "microservices"],
                    is_custom=False
                ),
                TechItemView(
                    id=uuid4(),
                    dimension_id=uuid4(),
                    slug="micronaut",
                    name="Micronaut", 
                    description="Modern JVM framework for microservices",
                    tags=["java", "jvm", "microservices", "graalvm"],
                    is_custom=False
                )
            ]
        )