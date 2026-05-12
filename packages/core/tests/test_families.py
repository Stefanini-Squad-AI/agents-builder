"""Tests for template families."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import session_scope
from app.domain import register_models
from app.domain.backlog import Card, Phase
from app.domain import skills as domain_skills  # Add import for skills module
from app.families import PhaseVliFamily, get_family
from app.families._base import CardDraftContext
from app.llm import DummyProvider
from app.prompts import DraftCardPrompt, DraftSkillBodyPrompt, ProposeBacklogPrompt
from app.schemas.llm_io import DraftedCard, DraftedCardInput, DraftedResource, DraftedSkillBody, ProposedBacklog, ProposedCard, ProposedPhase
from app.schemas.views import CardView, PhaseView, ProjectContext, ProjectView, SkillView


class TestTemplateFamilies:
    """Test template family functionality."""

    def test_get_family_returns_correct_instance(self) -> None:
        family = get_family("phase_vli")
        assert isinstance(family, PhaseVliFamily)
        assert family.slug == "phase_vli"
        assert family.display_name == "Phase-based VLI"

    def test_get_family_raises_for_unknown_slug(self) -> None:
        with pytest.raises(ValueError, match="Unknown template family: 'nonexistent'"):
            get_family("nonexistent")

    def test_phase_vli_family_metadata(self) -> None:
        family = PhaseVliFamily()
        assert family.slug == "phase_vli"
        assert family.grouping == "phase"
        assert family.grouping_label_singular == "Phase"
        assert family.grouping_label_plural == "Phases"
        assert family.card_filename_pattern == "{code}-{title_slug}"
        assert family.grouping_folder_pattern == "phase-{order}-{slug}"

    def test_slugify_converts_text_correctly(self) -> None:
        family = PhaseVliFamily()
        
        assert family._slugify("Simple Text") == "simple-text"
        assert family._slugify("Complex: Text & Symbols!") == "complex-text-symbols"
        assert family._slugify("  Extra   Spaces  ") == "extra-spaces"
        assert family._slugify("under_scores") == "under-scores"
        assert family._slugify("Multiple---Hyphens") == "multiple-hyphens"

    def test_get_card_filename_generates_correct_name(self) -> None:
        from datetime import datetime
        import uuid
        
        family = PhaseVliFamily()
        
        # Mock CardView with proper required fields
        card = CardView(
            id=str(uuid.uuid4()),
            phase_id=str(uuid.uuid4()),
            code="CORP-101", 
            title="Database Schema Analysis",
            type="Task",  # Must match CardType enum
            story_points=5,
            priority=None,
            status="draft",  # Must match CardStatus enum
            human_gate=False,
            human_gate_checklist_md=None,
            context_md=None,
            task_md=None,
            outputs_md=None,
            acceptance_criteria_md=None,
            order_no=1,
            skill_slugs=[],
            depends_on_codes=[],
            parallel_with_codes=[],
            inputs=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        filename = family.get_card_filename(card)
        assert filename == "CORP-101-database-schema-analysis"


@pytest.mark.integration
class TestPhaseVliRendering:
    """Integration tests for VLI template rendering with real database data."""

    def test_render_seeded_card_golden_test(self) -> None:
        """Golden test: render a seeded VLI card and verify output format."""
        register_models()
        
        with session_scope() as session:
            # Get a seeded card with all its relationships loaded
            card_orm = session.scalars(
                select(Card)
                .options(
                    selectinload(Card.phase).selectinload(Phase.project),
                    selectinload(Card.skill_links),
                    selectinload(Card.inputs),
                    selectinload(Card.deps_out),
                    selectinload(Card.deps_in),
                )
                .where(Card.code == "CORP-101")  # VLI reference card
                .limit(1)
            ).first()
            
            if not card_orm:
                pytest.skip("No CORP-101 card found in seeded data")
            
            # Convert ORM objects to Pydantic views (simplified for test)
            card_view = CardView(
                id=str(card_orm.id),
                phase_id=str(card_orm.phase_id),
                code=card_orm.code,
                title=card_orm.title,
                type=card_orm.type,
                story_points=card_orm.story_points,
                priority=card_orm.priority,
                status=card_orm.status,
                human_gate=card_orm.human_gate,
                human_gate_checklist_md=card_orm.human_gate_checklist_md,
                context_md=card_orm.context_md,
                task_md=card_orm.task_md,
                outputs_md=card_orm.outputs_md,
                acceptance_criteria_md=card_orm.acceptance_criteria_md,
                order_no=card_orm.order_no,
                skill_slugs=[],  # Simplified for test
                depends_on_codes=[],
                parallel_with_codes=[],
                inputs=[],
                created_at=card_orm.created_at,
                updated_at=card_orm.updated_at,
            )
            
            project_view = ProjectView(
                id=str(card_orm.phase.project.id),
                tenant_id=str(card_orm.phase.project.tenant_id),
                owner_user_id=str(card_orm.phase.project.owner_user_id),
                slug=card_orm.phase.project.slug,
                name=card_orm.phase.project.name,
                objective=card_orm.phase.project.objective,
                context_md=card_orm.phase.project.context_md,
                card_code_prefix=card_orm.phase.project.card_code_prefix,
                card_template=card_orm.phase.project.card_template,
                grouping=card_orm.phase.project.grouping,
                status=card_orm.phase.project.status,
                llm_provider=card_orm.phase.project.llm_provider,
                llm_model=card_orm.phase.project.llm_model,
                llm_temperature=card_orm.phase.project.llm_temperature,
                llm_enable_reasoning=card_orm.phase.project.llm_enable_reasoning,
                created_at=card_orm.phase.project.created_at,
                updated_at=card_orm.phase.project.updated_at,
                phases=[],  # Simplified for test
            )
            
            phase_view = PhaseView(
                id=str(card_orm.phase.id),
                project_id=str(card_orm.phase.project_id),
                code=card_orm.phase.code,
                name=card_orm.phase.name,
                description_md=card_orm.phase.description_md,
                order_no=card_orm.phase.order_no,
                cards=[],  # Simplified for test
            )
            
            # Create template context
            context = CardDraftContext(
                project=project_view,
                project_context="Sample project context for testing",
                phase=phase_view,
                card=card_view,
                skills_used=[],
                sibling_cards_in_phase=[],
                upstream_cards=[],
            )
            
            # Render the card
            family = PhaseVliFamily()
            rendered = family.render_card(card_view, context)
            
            # Verify structure (golden test assertions)
            lines = rendered.split('\n')
            
            # Should start with card title
            assert lines[0].startswith(f"# {card_orm.code} — {card_orm.title}")
            
            # Should contain all required sections
            assert "## Context" in rendered
            assert "## Skills to invoke" in rendered
            assert "## Inputs" in rendered
            assert "## Task" in rendered
            assert "## Outputs" in rendered
            assert "## Acceptance criteria" in rendered
            assert "## Depends on" in rendered
            assert "## Can run in parallel with" in rendered
            assert "## Human gate after this card" in rendered
            
            # Should have proper markdown structure
            assert rendered.count('##') >= 9  # At least 9 sections
            
            # Content should be populated or have default placeholders
            if card_orm.context_md:
                assert card_orm.context_md in rendered
            else:
                assert "_Context will be added during card drafting._" in rendered
                
            # Verify it's valid markdown (no obvious syntax errors)
            assert "# " in rendered  # Has main heading
            assert not rendered.startswith("##")  # Doesn't start with subsection
            
            # Print just the first few lines to avoid Unicode issues in test output
            lines_preview = rendered.split('\n')[:5]
            print("=== RENDERED CARD PREVIEW ===")
            for line in lines_preview:
                print(repr(line))  # Use repr to avoid encoding issues
            print("=== END PREVIEW ===")
            
            # Byte-for-byte comparison would go here with a golden file
            # For now, we verify structural correctness
            assert len(rendered) > 500  # Should be substantial content
            assert rendered.endswith('\n') or not rendered.endswith(' ')  # No trailing whitespace issues


class TestDraftSkillBodyIntegrationWithTemplates:
    """Integration tests for DraftSkillBodyPrompt with template families and database."""
    
    @pytest.mark.integration
    def test_skill_body_prompt_with_seeded_data(self) -> None:
        """Test DraftSkillBodyPrompt using real seeded skills and project data."""
        register_models()
        
        with session_scope() as session:
            # Query a real skill from seeded data
            skill_query = select(
                domain_skills.Skill
            ).where(
                domain_skills.Skill.slug == "siglm-context"
            ).options(
                selectinload(domain_skills.Skill.project)
            )
            skill_orm = session.execute(skill_query).scalar_one()
            
            # Get sibling skills from same project
            siblings_query = select(
                domain_skills.Skill
            ).where(
                domain_skills.Skill.project_id == skill_orm.project_id,
                domain_skills.Skill.id != skill_orm.id
            )
            siblings_orm = session.execute(siblings_query).scalars().all()
            
            # Convert to view models
            skill_view = SkillView(
                id=skill_orm.id,
                slug=skill_orm.slug,
                name=skill_orm.name,
                description=skill_orm.description,
                kind=skill_orm.kind,
                body_md=skill_orm.body_md,
                project_id=skill_orm.project_id,
            )
            
            sibling_views = [
                SkillView(
                    id=s.id,
                    slug=s.slug,
                    name=s.name,
                    description=s.description,
                    kind=s.kind,
                    body_md=s.body_md,
                    project_id=s.project_id,
                ) for s in siblings_orm
            ]
            
            # Create project context
            project_context = ProjectContext(
                objective=skill_orm.project.objective
            )
            
            # Create prompt
            prompt = DraftSkillBodyPrompt.create(skill_view, project_context, sibling_views)
            
            # Verify prompt structure
            assert prompt.system is not None
            assert len(prompt.messages) == 1
            assert prompt.response_schema == DraftedSkillBody
            
            # Check that skill kind-specific guidance is included
            if skill_orm.kind == "context":
                assert "CONTEXT skills should include resources like" in prompt.system
                assert "Domain glossaries" in prompt.system
            
            # Check user message contains project and skill information
            user_content = prompt.messages[0].content
            assert skill_orm.slug in user_content
            assert skill_orm.name in user_content
            assert skill_orm.project.objective in user_content
            
            # Check sibling skills are referenced
            for sibling in sibling_views:
                assert sibling.slug in user_content
            
            print(f"✓ Created prompt for skill {skill_orm.slug} ({skill_orm.kind})")
            print(f"  - System prompt: {len(prompt.system)} chars")
            print(f"  - User message: {len(user_content)} chars")
            print(f"  - Sibling skills: {len(sibling_views)}")

    @pytest.mark.integration
    def test_skill_body_generation_end_to_end(self) -> None:
        """Test complete skill body generation workflow with DummyProvider."""
        register_models()
        
        with session_scope() as session:
            # Use a simple skill for testing
            skill_query = select(
                domain_skills.Skill
            ).where(
                domain_skills.Skill.slug == "cronos-role-access"
            ).options(
                selectinload(domain_skills.Skill.project)
            )
            skill_orm = session.execute(skill_query).scalar_one_or_none()
            
            if not skill_orm:
                pytest.skip("cronos-role-access skill not found in seeded data")
                
            # Convert to view model
            skill_view = SkillView(
                id=skill_orm.id,
                slug=skill_orm.slug,
                name=skill_orm.name,
                description=skill_orm.description,
                kind=skill_orm.kind,
                body_md=skill_orm.body_md,
                project_id=skill_orm.project_id,
            )
            
            # Create project context
            project_context = ProjectContext(
                objective=skill_orm.project.objective
            )
            
            # Create mock LLM response appropriate for the skill kind
            expected_resource_count = DraftSkillBodyPrompt.get_recommended_resource_count(skill_orm.kind)
            preferred_languages = DraftSkillBodyPrompt.get_preferred_languages(skill_orm.kind)
            
            mock_resources = []
            if skill_orm.kind == "authoring":
                mock_resources = [
                    DraftedResource(
                        filename="role-check-template.py",
                        language="python",
                        content="# Role checking template\ndef check_user_role(user_id: str, required_role: str) -> bool:\n    return True",
                        purpose="Template for implementing role-based access checks"
                    ),
                    DraftedResource(
                        filename="access-control-guide.md",
                        language="markdown",
                        content="# Access Control Implementation\n\n## Steps\n1. Extract user token\n2. Validate role\n3. Apply restrictions",
                        purpose="Step-by-step guide for implementing access control"
                    )
                ]
            
            mock_response = DraftedSkillBody(
                body_md=f"# {skill_orm.name}\n\nThis skill helps implement role-based access control.\n\n## Implementation\n\n```python\n# Example code\npass\n```\n\n## When to pull in sibling skills\n\n- Use other authentication skills when needed",
                resources=mock_resources,
                sibling_skills_referenced=[]
            )
            
            # Create provider and execute
            provider = DummyProvider(fixed_response=mock_response)
            prompt = DraftSkillBodyPrompt.create(skill_view, project_context, [])
            result = provider.chat(prompt)
            
            # Verify result
            assert result.parsed is not None
            assert isinstance(result.parsed, DraftedSkillBody)
            assert "role-based access control" in result.parsed.body_md
            assert "When to pull in sibling skills" in result.parsed.body_md
            
            if skill_orm.kind == "authoring":
                assert len(result.parsed.resources) == 2
                assert any(r.filename.endswith(".py") for r in result.parsed.resources)
                assert any(r.filename.endswith(".md") for r in result.parsed.resources)
            
            print(f"✓ Generated skill body for {skill_orm.slug}")
            print(f"  - Body length: {len(result.parsed.body_md)} chars")
            print(f"  - Resources: {len(result.parsed.resources)}")
            print(f"  - Sibling references: {len(result.parsed.sibling_skills_referenced)}")


class TestProposeBacklogIntegrationWithTemplates:
    """Integration tests for ProposeBacklogPrompt with template families and seeded data."""
    
    @pytest.mark.integration
    def test_backlog_proposal_with_seeded_skills(self) -> None:
        """Test ProposeBacklogPrompt using real seeded skills from a project."""
        register_models()
        
        with session_scope() as session:
            # Query all skills from a seeded project
            project_query = select(
                domain_skills.Skill.project
            ).where(
                domain_skills.Skill.slug == "siglm-context"
            ).options(
                selectinload(domain_skills.Skill.project)
            )
            project_orm = session.execute(project_query).scalar_one().project
            
            # Get all skills from this project
            skills_query = select(
                domain_skills.Skill
            ).where(
                domain_skills.Skill.project_id == project_orm.id
            )
            skills_orm = session.execute(skills_query).scalars().all()
            
            # Convert to view models
            skill_views = [
                SkillView(
                    id=s.id,
                    slug=s.slug,
                    name=s.name,
                    description=s.description,
                    kind=s.kind,
                    body_md=s.body_md,
                    project_id=s.project_id,
                ) for s in skills_orm
            ]
            
            # Create project context string
            project_context_str = f"Project: {project_orm.name}\nObjective: {project_orm.objective}"
            
            # Create prompt using VLI template family
            template_family = PhaseVliFamily()
            prompt = ProposeBacklogPrompt.create(project_context_str, skill_views, template_family)
            
            # Verify prompt structure
            assert prompt.system is not None
            assert len(prompt.messages) == 1
            assert prompt.response_schema == ProposedBacklog
            
            # Check that VLI-specific guidance is included
            assert "phase-based software delivery" in prompt.system
            assert "Example 1: Data Migration Project" in prompt.system
            assert "Example 2: Web Application Project" in prompt.system
            
            # Check user message contains project and skills
            user_content = prompt.messages[0].content
            assert project_orm.objective in user_content or "Project" in user_content
            
            # Check skills are included
            for skill in skill_views[:3]:  # Check first few skills
                assert skill.slug in user_content
            
            print(f"✓ Created backlog prompt for project {project_orm.slug}")
            print(f"  - Skills available: {len(skill_views)}")
            print(f"  - System prompt: {len(prompt.system)} chars")
            print(f"  - User message: {len(user_content)} chars")

    @pytest.mark.integration 
    def test_backlog_generation_end_to_end(self) -> None:
        """Test complete backlog generation workflow with DummyProvider and VLI template."""
        register_models()
        
        with session_scope() as session:
            # Use CORP project with VLI-style structure
            project_query = select(
                domain_skills.Skill.project
            ).where(
                domain_skills.Skill.slug == "corp-ssis-analyzer"
            ).options(
                selectinload(domain_skills.Skill.project)
            )
            project_orm = session.execute(project_query).scalar_one_or_none()
            
            if not project_orm:
                pytest.skip("corp-ssis-analyzer skill not found in seeded data")
                
            project_orm = project_orm.project
                
            # Get a few skills from this project
            skills_query = select(
                domain_skills.Skill
            ).where(
                domain_skills.Skill.project_id == project_orm.id
            ).limit(3)
            skills_orm = session.execute(skills_query).scalars().all()
            
            # Convert to view models  
            skill_views = [
                SkillView(
                    id=s.id,
                    slug=s.slug,
                    name=s.name,
                    description=s.description,
                    kind=s.kind,
                    body_md=s.body_md,
                    project_id=s.project_id,
                ) for s in skills_orm
            ]
            
            # Create mock LLM response in VLI style
            mock_response = ProposedBacklog(
                phases=[
                    ProposedPhase(
                        code="phase-1-discovery",
                        name="Discovery & Analysis",
                        description="Analyze existing SSIS packages and extract business rules",
                        cards=[
                            ProposedCard(
                                code="CORP-101",
                                title="SSIS Package Analysis",
                                type="Task",
                                story_points=5,
                                skill_slugs=["corp-ssis-analyzer"],
                                depends_on_codes=[],
                                short_scope_summary="Complete technical analysis of legacy SSIS packages with business rule extraction."
                            )
                        ]
                    ),
                    ProposedPhase(
                        code="phase-2-foundation",
                        name="Platform Foundation",
                        description="Set up Databricks platform and data models", 
                        cards=[
                            ProposedCard(
                                code="CORP-201",
                                title="Databricks Platform Setup",
                                type="Story",
                                story_points=8,
                                skill_slugs=["corp-databricks-planner"],
                                depends_on_codes=["CORP-101"],
                                short_scope_summary="Provision Unity Catalog schemas and implement Delta table structures."
                            )
                        ]
                    )
                ],
                rationale_md="Two-phase approach separates analysis from implementation for reduced risk and clear handoff points.",
                critical_path_codes=["CORP-101", "CORP-201"]
            )
            
            # Create provider and execute
            provider = DummyProvider(fixed_response=mock_response.model_dump())
            template_family = PhaseVliFamily()
            
            project_context_str = f"Migrate SSIS data pipeline to Databricks using {project_orm.objective}"
            prompt = ProposeBacklogPrompt.create(project_context_str, skill_views, template_family)
            result = provider.chat(prompt)
            
            # Verify result
            assert result.parsed is not None
            assert isinstance(result.parsed, ProposedBacklog)
            assert len(result.parsed.phases) == 2
            assert result.parsed.phases[0].code == "phase-1-discovery"
            assert result.parsed.phases[1].code == "phase-2-foundation"
            
            # Verify cards structure
            assert len(result.parsed.phases[0].cards) == 1
            assert result.parsed.phases[0].cards[0].code == "CORP-101"
            assert "corp-ssis-analyzer" in result.parsed.phases[0].cards[0].skill_slugs
            
            # Verify dependencies
            assert "CORP-101" in result.parsed.phases[1].cards[0].depends_on_codes
            assert result.parsed.critical_path_codes == ["CORP-101", "CORP-201"]
            
            print(f"✓ Generated backlog for {project_orm.slug}")
            print(f"  - Phases: {len(result.parsed.phases)}")
            print(f"  - Total cards: {sum(len(phase.cards) for phase in result.parsed.phases)}")
            print(f"  - Critical path length: {len(result.parsed.critical_path_codes)}")
            print(f"  - Rationale: {len(result.parsed.rationale_md)} chars")


class TestDraftCardIntegrationWithTemplates:
    """Integration tests for DraftCardPrompt with template families and seeded data."""
    
    @pytest.mark.integration
    def test_card_draft_with_seeded_data(self) -> None:
        """Test DraftCardPrompt using real seeded card and project data."""
        register_models()
        
        with session_scope() as session:
            # Query a real card from seeded data
            card_query = select(
                Card
            ).where(
                Card.code == "CORP-101"
            ).options(
                selectinload(Card.phase).selectinload(Phase.project),
                selectinload(Card.skills),
                selectinload(Card.inputs)
            )
            card_orm = session.execute(card_query).scalar_one_or_none()
            
            if not card_orm:
                pytest.skip("CORP-101 card not found in seeded data")
            
            # Get skills used by this card
            skill_views = [
                SkillView(
                    id=s.id,
                    slug=s.slug,
                    name=s.name,
                    description=s.description,
                    kind=s.kind,
                    body_md=s.body_md,
                    project_id=s.project_id,
                ) for s in card_orm.skills
            ]
            
            # Convert to view models
            project_view = ProjectView(
                id=card_orm.phase.project.id,
                tenant_id=card_orm.phase.project.tenant_id,
                owner_user_id=card_orm.phase.project.owner_user_id,
                slug=card_orm.phase.project.slug,
                name=card_orm.phase.project.name,
                objective=card_orm.phase.project.objective,
                card_code_prefix=card_orm.phase.project.card_code_prefix,
                card_template=card_orm.phase.project.card_template,
                grouping=card_orm.phase.project.grouping,
                status=card_orm.phase.project.status,
                llm_provider=card_orm.phase.project.llm_provider,
                llm_model=card_orm.phase.project.llm_model,
                llm_temperature=card_orm.phase.project.llm_temperature,
                created_at=card_orm.phase.project.created_at,
                updated_at=card_orm.phase.project.updated_at,
            )
            
            phase_view = PhaseView(
                id=card_orm.phase.id,
                code=card_orm.phase.code,
                name=card_orm.phase.name,
                description=card_orm.phase.description,
                order_no=card_orm.phase.order_no,
                project_id=card_orm.phase.project_id,
            )
            
            card_view = CardView(
                id=card_orm.id,
                code=card_orm.code,
                title=card_orm.title,
                phase_id=card_orm.phase_id,
                type=card_orm.type,
                story_points=card_orm.story_points,
                status=card_orm.status,
                human_gate=card_orm.human_gate,
                created_at=card_orm.created_at,
                updated_at=card_orm.updated_at,
                project_id=card_orm.project_id,
            )
            
            # Create card draft context
            from app.families._base import CardDraftContext
            context = CardDraftContext(
                project=project_view,
                project_context=f"Project: {project_view.name}\nObjective: {project_view.objective}",
                phase=phase_view,
                card=card_view,
                skills_used=skill_views,
                sibling_cards_in_phase=[card_view],
                upstream_cards=[],
            )
            
            # Create prompt using VLI template family
            template_family = PhaseVliFamily()
            prompt = DraftCardPrompt.create(context, template_family)
            
            # Verify prompt structure
            assert prompt.system is not None
            assert len(prompt.messages) == 1
            assert prompt.response_schema == DraftedCard
            
            # Check that VLI-specific guidance and examples are included
            assert "VLI (phase-based) template" in prompt.system
            assert "Example 1: Analysis Card" in prompt.system
            assert "Example 2: Implementation Card" in prompt.system
            
            # Check user message contains card and project information
            user_content = prompt.messages[0].content
            assert card_orm.code in user_content
            assert card_orm.title in user_content
            assert project_view.objective in user_content
            
            # Check skills are included
            for skill in skill_views:
                assert skill.slug in user_content
            
            print(f"✓ Created card draft prompt for {card_orm.code}")
            print(f"  - Card: {card_orm.title}")
            print(f"  - Skills: {len(skill_views)}")
            print(f"  - System prompt: {len(prompt.system)} chars")
            print(f"  - User message: {len(user_content)} chars")

    @pytest.mark.integration
    def test_card_draft_generation_end_to_end(self) -> None:
        """Test complete card drafting workflow with DummyProvider and VLI template."""
        register_models()
        
        with session_scope() as session:
            # Use SIGLM project for a different example
            card_query = select(
                Card
            ).where(
                Card.code == "SIGLM-201"
            ).options(
                selectinload(Card.phase).selectinload(Phase.project),
                selectinload(Card.skills)
            )
            card_orm = session.execute(card_query).scalar_one_or_none()
            
            if not card_orm:
                pytest.skip("SIGLM-201 card not found in seeded data")
            
            # Get skills  
            skill_views = [
                SkillView(
                    id=s.id,
                    slug=s.slug,
                    name=s.name,
                    description=s.description,
                    kind=s.kind,
                    body_md=s.body_md,
                    project_id=s.project_id,
                ) for s in card_orm.skills
            ]
            
            # Create context (simplified for testing)
            from app.families._base import CardDraftContext
            from decimal import Decimal
            
            project_view = ProjectView(
                id=card_orm.phase.project.id,
                tenant_id=card_orm.phase.project.tenant_id,
                owner_user_id=card_orm.phase.project.owner_user_id,
                slug=card_orm.phase.project.slug,
                name=card_orm.phase.project.name,
                objective=card_orm.phase.project.objective,
                card_code_prefix=card_orm.phase.project.card_code_prefix,
                card_template=card_orm.phase.project.card_template,
                grouping=card_orm.phase.project.grouping,
                status=card_orm.phase.project.status,
                llm_provider=card_orm.phase.project.llm_provider,
                llm_model=card_orm.phase.project.llm_model,
                llm_temperature=Decimal(str(card_orm.phase.project.llm_temperature)),
                created_at=card_orm.phase.project.created_at,
                updated_at=card_orm.phase.project.updated_at,
            )
            
            phase_view = PhaseView(
                id=card_orm.phase.id,
                code=card_orm.phase.code,
                name=card_orm.phase.name,
                description=card_orm.phase.description,
                order_no=card_orm.phase.order_no,
                project_id=card_orm.phase.project_id,
            )
            
            card_view = CardView(
                id=card_orm.id,
                code=card_orm.code,
                title=card_orm.title,
                phase_id=card_orm.phase_id,
                type=card_orm.type,
                story_points=card_orm.story_points,
                status=card_orm.status,
                human_gate=card_orm.human_gate,
                created_at=card_orm.created_at,
                updated_at=card_orm.updated_at,
                project_id=card_orm.project_id,
            )
            
            context = CardDraftContext(
                project=project_view,
                project_context=f"Spring Boot backend development for {project_view.objective}",
                phase=phase_view,
                card=card_view,
                skills_used=skill_views,
                sibling_cards_in_phase=[card_view],
                upstream_cards=[],
            )
            
            # Create mock LLM response for Spring Boot card
            mock_response = DraftedCard(
                context_md="Phase 2 begins the Spring Boot backend implementation. This card establishes the foundational Spring Boot application structure with essential components: OpenAPI documentation, error handling, and database connectivity. The skeleton provides the framework for subsequent development cards.",
                task_md="1. Create Maven project with Spring Boot 3.3.x and Java 17\\n2. Set up package structure: api/v1, service, repository, domain, dto, config, exception\\n3. Configure OpenAPI with SwaggerUI at /swagger-ui.html\\n4. Implement CorrelationIdFilter for request tracing with MDC\\n5. Create GlobalExceptionHandler with canonical error envelope\\n6. Set up Flyway with baseline migration for GLM schema\\n7. Configure application.yml for database connection via environment variables\\n8. Create multi-stage Dockerfile for containerized deployment",
                outputs_md="- `backend/pom.xml` with Spring Boot 3.3.x dependencies\\n- Package structure under `br/sample/siglm/` with base classes\\n- `application.yml` and `application-dev.yml` configuration files\\n- `db/migration/V001__create_schema_glm.sql` Flyway migration\\n- `Dockerfile` with optimized multi-stage build for production",
                acceptance_criteria_md="- [ ] Maven build succeeds with `mvn -B -ntp verify`\\n- [ ] Docker Compose starts backend service on port 8080\\n- [ ] `/actuator/health` returns 200 with database and application status green\\n- [ ] SwaggerUI loads at `/swagger-ui.html` showing API documentation\\n- [ ] Test 404 endpoint returns canonical error envelope with `RECURSO_NAO_ENCONTRADO`\\n- [ ] All log entries include correlationId field or empty placeholder",
                inputs=[
                    DraftedCardInput(
                        kind="skill_resource",
                        path=".agents/skills/siglm-spring-backend/SKILL.md",
                        label="Spring Boot backend conventions and patterns"
                    ),
                    DraftedCardInput(
                        kind="skill_resource",
                        path=".agents/skills/siglm-context/SKILL.md",
                        label="SIGLM project context and domain knowledge"
                    )
                ]
            )
            
            # Create provider and execute
            provider = DummyProvider(fixed_response=mock_response.model_dump())
            template_family = PhaseVliFamily()
            
            prompt = DraftCardPrompt.create(context, template_family)
            result = provider.chat(prompt)
            
            # Verify result
            assert result.parsed is not None
            assert isinstance(result.parsed, DraftedCard)
            assert "Spring Boot" in result.parsed.context_md
            assert "Maven project" in result.parsed.task_md
            assert "pom.xml" in result.parsed.outputs_md
            assert "- [ ]" in result.parsed.acceptance_criteria_md
            assert len(result.parsed.inputs) == 2
            assert all(inp.kind == "skill_resource" for inp in result.parsed.inputs)
            
            # Validate the card
            from app.prompts.draft_card import DraftCardPrompt
            warnings = DraftCardPrompt.validate_drafted_card(result.parsed, context)
            assert len(warnings) == 0  # Should be valid
            
            print(f"✓ Generated card draft for {card_orm.code}")
            print(f"  - Context: {len(result.parsed.context_md)} chars")
            print(f"  - Task: {len(result.parsed.task_md)} chars") 
            print(f"  - Outputs: {len(result.parsed.outputs_md)} chars")
            print(f"  - Acceptance criteria: {len(result.parsed.acceptance_criteria_md)} chars")
            print(f"  - Inputs: {len(result.parsed.inputs)}")
            print(f"  - Validation warnings: {len(warnings)}")