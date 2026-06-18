"""`workshop skill ...` — skill library."""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.table import Table

# Import the skill system
try:
    from app.services.skill_service import SkillService
    SKILL_SERVICE_AVAILABLE = True
except ImportError:
    SKILL_SERVICE_AVAILABLE = False

from workshop._common import stub

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")
console = Console()


def show_error(message: str, details: str | None = None) -> None:
    """Display error message."""
    console.print(f"❌ {message}", style="bold red")
    if details:
        console.print(f"   {details}", style="dim red")


def show_success(message: str) -> None:
    """Display success message."""
    console.print(f"✅ {message}", style="bold green")


@app.command(name="propose")
def propose(project: str = typer.Option(..., "--project", "-p")) -> None:
    """Run the `ProposeSkillSet` LLM prompt — proposes 5..10 skills."""
    
    # Import LLM functionality
    try:
        from workshop._llm_utils import (
            check_project_readiness, 
            create_llm_service_for_project,
            load_project_context,
            run_llm_prompt,
            show_llm_error,
            show_llm_success
        )
        from app.prompts import ProposeSkillsetPrompt
        from app.services import SkillService
        import app.db
    except ImportError:
        show_error("LLM system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    console.print(f"🎨 [bold]Proposing skills for project '{project}'[/bold]")
    
    # Check project readiness
    if not check_project_readiness(project):
        raise typer.Exit(1)
    
    # Load project context
    context = load_project_context(project)
    if not context:
        raise typer.Exit(1)
    
    # Create LLM service
    llm_service = create_llm_service_for_project(project)
    if not llm_service:
        raise typer.Exit(1)
    
    try:
        # Create prompt
        prompt = ProposeSkillsetPrompt.create(context)
        
        # Run LLM
        result = run_llm_prompt(
            llm_service, 
            prompt, 
            "Skill Proposal Generation"
        )
        
        if not result or not result.parsed:
            show_llm_error("Failed to generate skill proposals")
            raise typer.Exit(1)
        
        # Save skills to database
        skill_service = SkillService()
        saved_skills = []
        
        with app.db.session_scope() as session:
            # Get project for skill creation
            from sqlalchemy import select
            from app.domain.projects import Project
            
            project_record = session.execute(
                select(Project).where(Project.slug == project)
            ).scalar_one_or_none()
            
            if not project_record:
                show_llm_error(f"Project '{project}' not found")
                raise typer.Exit(1)
            
            # Create skill records
            for proposed_skill in result.parsed.skills:
                from app.domain.skills import Skill
                
                skill = Skill(
                    project_id=project_record.id,
                    slug=proposed_skill.slug,
                    name=proposed_skill.name,
                    description=proposed_skill.description,
                    kind=proposed_skill.kind,
                    trigger_phrases=proposed_skill.trigger_phrases,
                    body_md=""  # Will be filled later with draft command
                )
                
                session.add(skill)
                saved_skills.append(proposed_skill)
            
            session.commit()
        
        # Show results
        show_llm_success(f"Generated {len(saved_skills)} skills for project '{project}'")
        
        console.print("📋 [bold]Proposed Skills:[/bold]")
        
        from rich.table import Table
        table = Table()
        table.add_column("Slug", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Kind", style="blue")
        table.add_column("Triggers", style="dim")
        
        for skill in saved_skills:
            trigger_count = len(skill.trigger_phrases) if skill.trigger_phrases else 0
            table.add_row(
                skill.slug,
                skill.name,
                skill.kind,
                str(trigger_count)
            )
        
        console.print(table)
        console.print()
        console.print("💡 [dim]Use 'workshop skill draft <slug>' to generate content for each skill[/dim]")
        
    except Exception as e:
        show_llm_error("Skill proposal failed", str(e))
        if "--debug" in sys.argv:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


@app.command(name="list")
def list_skills(project: str = typer.Option(..., "--project", "-p")) -> None:
    """List skills in the project."""
    
    if not SKILL_SERVICE_AVAILABLE:
        show_error("Skill system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        service = SkillService()
        skills = service.list_project_skills(project)
        
        if not skills:
            console.print(f"📚 No skills found in project '{project}'")
            console.print("💡 Generate skills with: [bold]workshop skill propose --project " + project + "[/bold]")
            return
        
        # Display skills table
        table = Table(title=f"📚 Skills in '{project}'")
        table.add_column("Slug", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Kind", style="blue")
        table.add_column("Triggers", justify="right", style="dim")
        table.add_column("Content", justify="center")
        table.add_column("Resources", justify="right", style="green")
        
        for skill in skills:
            # Content status
            has_content = "✅" if (skill.body_md and skill.body_md.strip()) else "❌"
            
            # Trigger phrases count
            trigger_count = len(skill.trigger_phrases)
            
            table.add_row(
                skill.slug,
                skill.name,
                skill.kind,
                str(trigger_count),
                has_content,
                str(skill.resource_count)
            )
        
        console.print(table)
        
        # Show statistics
        stats = service.get_skills_statistics(project)
        console.print()
        console.print(f"📊 [bold]Summary:[/bold] {stats['total_skills']} skills, {stats['completion_percentage']:.0f}% with content")
        
        if stats['by_kind']:
            kind_summary = ", ".join(f"{count} {kind}" for kind, count in stats['by_kind'].items())
            console.print(f"🏷️  [bold]By kind:[/bold] {kind_summary}")
        
    except Exception as e:
        show_error("Failed to list skills", str(e))
        raise typer.Exit(1)


@app.command(name="draft")
def draft(
    skill_slug: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
    force: bool = typer.Option(False, "--force", help="Overwrite the existing body if any."),
) -> None:
    """Run the `DraftSkillBody` LLM prompt to fill in a proposed skill."""
    
    # Import LLM functionality
    try:
        from workshop._llm_utils import (
            create_llm_service_for_project,
            load_project_context,
            run_llm_prompt,
            show_llm_error,
            show_llm_success
        )
        from app.prompts import DraftSkillBodyPrompt
        from app.services import SkillService
        import app.db
    except ImportError:
        show_error("LLM system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    console.print(f"📝 [bold]Drafting content for skill '{skill_slug}' in project '{project}'[/bold]")
    
    # Get the skill
    skill_service = SkillService()
    skill = skill_service.get_skill(project, skill_slug)
    
    if not skill:
        show_error(f"Skill '{skill_slug}' not found in project '{project}'")
        console.print("💡 List available skills: [bold]workshop skill list --project " + project + "[/bold]")
        raise typer.Exit(1)
    
    # Check if skill already has content
    if skill.body_md and skill.body_md.strip() and not force:
        console.print(f"⚠️  Skill '{skill_slug}' already has content. Use --force to overwrite.")
        console.print("💡 Current content preview:")
        preview = skill.body_md[:200] + "..." if len(skill.body_md) > 200 else skill.body_md
        console.print(f"[dim]{preview}[/dim]")
        raise typer.Exit(1)
    
    # Load project context
    context = load_project_context(project)
    if not context:
        raise typer.Exit(1)
    
    # Create LLM service
    llm_service = create_llm_service_for_project(project)
    if not llm_service:
        raise typer.Exit(1)
    
    try:
        # Create skill context for the prompt
        from app.families._base import SkillDraftContext
        
        skill_context = SkillDraftContext(
            skill_slug=skill.slug,
            skill_name=skill.name,
            skill_description=skill.description,
            skill_kind=skill.kind,
            trigger_phrases=skill.trigger_phrases or []
        )
        
        # Create prompt
        prompt = DraftSkillBodyPrompt.create(context, skill_context)
        
        # Run LLM
        result = run_llm_prompt(
            llm_service, 
            prompt, 
            f"Skill Content Generation for '{skill.name}'"
        )
        
        if not result or not result.parsed:
            show_llm_error("Failed to generate skill content")
            raise typer.Exit(1)
        
        # Update skill with generated content
        updated_skill = skill_service.update_skill_body(
            project, 
            skill_slug, 
            result.parsed.body_md
        )
        
        if not updated_skill:
            show_llm_error("Failed to save skill content")
            raise typer.Exit(1)
        
        # Show results
        show_llm_success(f"Generated content for skill '{skill.name}'")
        
        console.print("📄 [bold]Generated Content Preview:[/bold]")
        # Show first few lines of the generated content
        lines = result.parsed.body_md.split('\n')
        preview_lines = lines[:10]  # First 10 lines
        
        for line in preview_lines:
            console.print(line)
        
        if len(lines) > 10:
            console.print(f"[dim]... and {len(lines) - 10} more lines[/dim]")
        
        console.print()
        console.print("💡 [dim]Use 'workshop skill show " + skill_slug + "' to view the complete skill[/dim]")
        
        # Show resources if generated
        if hasattr(result.parsed, 'resources') and result.parsed.resources:
            console.print(f"📚 [bold]Also generated {len(result.parsed.resources)} resources[/bold]")
            for resource in result.parsed.resources:
                console.print(f"   • {resource.filename} ({resource.language})")
        
    except Exception as e:
        show_llm_error("Skill drafting failed", str(e))
        if "--debug" in sys.argv:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


@app.command(name="show")
def show(
    skill_slug: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Render the full SKILL.md (frontmatter + body) to stdout."""
    
    if not SKILL_SERVICE_AVAILABLE:
        show_error("Skill system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        service = SkillService()
        skill = service.get_skill(project, skill_slug)
        
        if not skill:
            show_error(f"Skill '{skill_slug}' not found in project '{project}'")
            console.print("💡 List available skills: [bold]workshop skill list --project " + project + "[/bold]")
            raise typer.Exit(1)
        
        # Render and display SKILL.md
        skill_markdown = service.render_skill_markdown(skill)
        console.print(skill_markdown)
        
    except Exception as e:
        show_error("Failed to show skill", str(e))
        raise typer.Exit(1)


@app.command(name="edit")
def edit(
    skill_slug: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Open $EDITOR on the skill body."""
    
    if not SKILL_SERVICE_AVAILABLE:
        show_error("Skill system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        # Import editing utilities
        from workshop._editing import open_editor
        
        service = SkillService()
        skill = service.get_skill(project, skill_slug)
        
        if not skill:
            show_error(f"Skill '{skill_slug}' not found in project '{project}'")
            raise typer.Exit(1)
        
        console.print(f"📝 Editing skill: {skill.name}")
        
        # Current content or template
        current_content = skill.body_md or """## Guidelines

Add specific guidance for this skill here.

## Conventions

Define any coding conventions, patterns, or standards.

## Resources

List useful resources, examples, or references.

## Examples

Provide concrete examples of how to apply this skill.
"""
        
        try:
            # Open editor
            from workshop._utils import open_editor
            
            new_content = open_editor(
                content=current_content,
                file_extension=".md"
            )
            
            # Update skill
            updated_skill = service.update_skill_body(project, skill_slug, new_content)
            
            if updated_skill:
                show_success(f"Skill '{skill_slug}' updated successfully!")
            else:
                show_error("Failed to update skill")
                raise typer.Exit(1)
                
        except RuntimeError as e:
            console.print(f"⚠️  Skill editing cancelled: {e}", style="yellow")
        
    except Exception as e:
        show_error("Failed to edit skill", str(e))
        if "--debug" in sys.argv:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)
