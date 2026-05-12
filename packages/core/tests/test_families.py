"""Tests for template families."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import session_scope
from app.domain import register_models
from app.domain.backlog import Card, Phase
from app.families import PhaseVliFamily, get_family
from app.families._base import CardDraftContext
from app.schemas.views import CardView, PhaseView, ProjectView, SkillView


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