"""`workshop tech ...` — tech panorama picker."""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.table import Table

# Import the tech system
try:
    from app.services.tech_service import TechService
    from app.enums import TechChoiceRole
    TECH_SERVICE_AVAILABLE = True
except ImportError:
    TECH_SERVICE_AVAILABLE = False

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


@app.command(name="list")
def list_tech(project: str = typer.Option(..., "--project", "-p")) -> None:
    """Show all dimensions and the project's current choices."""
    
    if not TECH_SERVICE_AVAILABLE:
        show_error("Tech system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        service = TechService()
        
        # Get all dimensions with catalog items
        dimensions = service.list_dimensions()
        
        # Get project choices
        project_choices = service.list_project_tech_choices(project)
        
        # Group project choices by dimension
        choices_by_dim = {}
        for choice in project_choices:
            dim_slug = choice.dimension_slug
            if dim_slug not in choices_by_dim:
                choices_by_dim[dim_slug] = []
            choices_by_dim[dim_slug].append(choice)
        
        console.print(f"🔧 [bold]Tech Panorama for '{project}'[/bold]")
        console.print()
        
        # Display each dimension
        for dimension in dimensions:
            dim_slug = dimension["slug"]
            dim_choices = choices_by_dim.get(dim_slug, [])
            
            # Status indicator
            if dim_choices:
                status = "✅"
                choice_count = f"({len(dim_choices)} choices)"
            else:
                status = "❌"
                choice_count = "(not configured)"
            
            console.print(f"## {status} {dimension['name']} {choice_count}")
            console.print(f"   {dimension['description']}")
            
            if dim_choices:
                # Show current choices
                for choice in dim_choices:
                    role_emoji = {
                        TechChoiceRole.TARGET.value: "🎯",
                        TechChoiceRole.LEGACY.value: "⏳",
                        TechChoiceRole.OPTIONAL.value: "⚪",
                        TechChoiceRole.MUST_AVOID.value: "🚫",
                        TechChoiceRole.TBD.value: "❓"
                    }.get(choice.role, "")
                    
                    source_note = " (custom)" if choice.source == "user_added" else ""
                    
                    console.print(f"   • {role_emoji} {choice.item_name}{source_note}")
                    if choice.rationale_md:
                        console.print(f"     [dim]{choice.rationale_md[:100]}...[/dim]")
            else:
                # Show available catalog items (first few)
                if dimension["items"]:
                    console.print("   [dim]Available: " + ", ".join(item["name"] for item in dimension["items"][:5]))
                    if len(dimension["items"]) > 5:
                        console.print(f"   [dim]... and {len(dimension['items']) - 5} more[/dim]")
            
            console.print()
        
        # Show statistics
        stats = service.get_tech_statistics(project)
        console.print(f"📊 [bold]Summary:[/bold] {stats['covered_dimensions']}/{stats['total_dimensions']} dimensions configured ({stats['coverage_percentage']:.0f}%)")
        
        if stats['by_role']:
            role_summary = ", ".join(f"{count} {role}" for role, count in stats['by_role'].items())
            console.print(f"🏷️  [bold]By role:[/bold] {role_summary}")
        
        console.print()
        console.print("💡 [dim]Use 'workshop tech pick' to configure dimensions[/dim]")
        
    except Exception as e:
        show_error("Failed to list tech panorama", str(e))
        raise typer.Exit(1)


@app.command(name="pick")
def pick(
    dimension: str = typer.Argument(...),
    item_slug: str = typer.Argument(...),
    role: str = typer.Option("target", "--role", help="target / legacy / optional / must-avoid"),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Pick a catalog item for a dimension."""
    
    if not TECH_SERVICE_AVAILABLE:
        show_error("Tech system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    # Validate role
    valid_roles = ["target", "legacy", "optional", "must-avoid"]
    if role not in valid_roles:
        show_error(f"Invalid role '{role}'. Choose from: {', '.join(valid_roles)}")
        raise typer.Exit(1)
    
    # Map role to enum
    role_map = {
        "target": TechChoiceRole.TARGET,
        "legacy": TechChoiceRole.LEGACY,
        "optional": TechChoiceRole.OPTIONAL,
        "must-avoid": TechChoiceRole.MUST_AVOID
    }
    
    try:
        service = TechService()
        
        # Set the tech choice
        tech_choice = service.set_tech_choice(
            project, 
            dimension, 
            item_slug, 
            None,  # No free form name
            role_map[role]
        )
        
        if tech_choice:
            show_success(f"Set {tech_choice.item_name} as {role} for {tech_choice.dimension_name}")
        else:
            show_error("Failed to set tech choice - project not found")
            raise typer.Exit(1)
        
    except ValueError as e:
        show_error("Invalid selection", str(e))
        raise typer.Exit(1)
    except Exception as e:
        show_error("Failed to pick tech item", str(e))
        raise typer.Exit(1)


@app.command(name="add")
def add(
    dimension: str = typer.Argument(...),
    name: str = typer.Argument(..., help="Free-form item name"),
    role: str = typer.Option("target", "--role"),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Add a custom item to a dimension (becomes is_custom=true)."""
    
    if not TECH_SERVICE_AVAILABLE:
        show_error("Tech system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    # Validate role
    valid_roles = ["target", "legacy", "optional", "must-avoid"]
    if role not in valid_roles:
        show_error(f"Invalid role '{role}'. Choose from: {', '.join(valid_roles)}")
        raise typer.Exit(1)
    
    # Map role to enum
    role_map = {
        "target": TechChoiceRole.TARGET,
        "legacy": TechChoiceRole.LEGACY,
        "optional": TechChoiceRole.OPTIONAL,
        "must-avoid": TechChoiceRole.MUST_AVOID
    }
    
    try:
        service = TechService()
        
        # Set the custom tech choice
        tech_choice = service.set_tech_choice(
            project, 
            dimension, 
            None,  # No catalog item slug
            name,  # Free form name
            role_map[role]
        )
        
        if tech_choice:
            show_success(f"Added custom tech '{name}' as {role} for {dimension}")
        else:
            show_error("Failed to add custom tech choice - project not found")
            raise typer.Exit(1)
        
    except ValueError as e:
        show_error("Invalid input", str(e))
        raise typer.Exit(1)
    except Exception as e:
        show_error("Failed to add custom tech item", str(e))
        raise typer.Exit(1)


@app.command(name="tbd")
def mark_tbd(
    dimension: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Mark a dimension as TBD (decide later)."""
    
    if not TECH_SERVICE_AVAILABLE:
        show_error("Tech system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        service = TechService()
        
        # Set TBD choice
        tech_choice = service.set_tech_choice(
            project, 
            dimension, 
            None,  # No catalog item slug
            "To Be Determined",  # Placeholder name
            TechChoiceRole.TBD
        )
        
        if tech_choice:
            show_success(f"Marked {tech_choice.dimension_name} as TBD")
        else:
            show_error("Failed to mark dimension as TBD - project not found")
            raise typer.Exit(1)
        
    except ValueError as e:
        show_error("Invalid dimension", str(e))
        raise typer.Exit(1)
    except Exception as e:
        show_error("Failed to mark dimension as TBD", str(e))
        raise typer.Exit(1)


@app.command(name="suggest")
def suggest(
    dimension: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Ask the LLM to propose items for a single dimension (`SuggestTechStack` prompt)."""
    
    # Import LLM functionality
    try:
        from workshop._llm_utils import (
            create_llm_service_for_project,
            load_project_context,
            run_llm_prompt,
            show_llm_error,
            show_llm_success
        )
        from app.prompts import SuggestTechStackPrompt
        from app.services import TechService
        import app.db
    except ImportError:
        show_error("LLM system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    console.print(f"🔧 [bold]Getting tech suggestions for dimension '{dimension}' in project '{project}'[/bold]")
    
    # Validate dimension exists
    tech_service = TechService()
    dimensions = tech_service.list_dimensions()
    
    dimension_data = None
    for dim in dimensions:
        if dim["slug"] == dimension:
            dimension_data = dim
            break
    
    if not dimension_data:
        show_error(f"Dimension '{dimension}' not found")
        console.print("Available dimensions:")
        for dim in dimensions:
            console.print(f"  [cyan]{dim['slug']}[/cyan]: {dim['name']}")
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
        # Create prompt for specific dimension
        prompt = SuggestTechStackPrompt.create(context, dimension)
        
        # Run LLM
        result = run_llm_prompt(
            llm_service, 
            prompt, 
            f"Tech Suggestions for {dimension_data['name']}"
        )
        
        if not result or not result.parsed:
            show_llm_error("Failed to generate tech suggestions")
            raise typer.Exit(1)
        
        # Show results
        suggestions = result.parsed.suggestions
        show_llm_success(f"Generated {len(suggestions)} suggestions for {dimension_data['name']}")
        
        console.print(f"🔧 [bold]Tech Suggestions for {dimension_data['name']}:[/bold]")
        console.print(f"📝 {dimension_data['description']}")
        console.print()
        
        # Show reasoning summary if available
        if hasattr(result.parsed, 'reasoning_summary') and result.parsed.reasoning_summary:
            console.print("🧠 [bold]AI Reasoning:[/bold]")
            console.print(f"   {result.parsed.reasoning_summary}")
            console.print()
        
        # Display suggestions in a table
        from rich.table import Table
        
        table = Table(title=f"Suggestions for {dimension_data['name']}")
        table.add_column("Technology", style="cyan")
        table.add_column("Role", style="blue")
        table.add_column("Confidence", justify="center", style="green")
        table.add_column("Rationale", style="white")
        
        for suggestion in suggestions:
            # Determine technology name
            tech_name = suggestion.catalog_slug if suggestion.catalog_slug else suggestion.free_form_name
            
            # Confidence indicator
            confidence_display = f"{suggestion.confidence}%" if suggestion.confidence else "N/A"
            
            # Truncate long rationale
            rationale = suggestion.rationale
            if len(rationale) > 80:
                rationale = rationale[:77] + "..."
            
            table.add_row(
                tech_name,
                suggestion.role,
                confidence_display,
                rationale
            )
        
        console.print(table)
        console.print()
        
        # Show commands to apply suggestions
        console.print("💡 [bold]To apply these suggestions:[/bold]")
        for suggestion in suggestions[:3]:  # Show first 3
            tech_name = suggestion.catalog_slug if suggestion.catalog_slug else suggestion.free_form_name
            
            if suggestion.catalog_slug:
                cmd = f"workshop tech pick {dimension} {suggestion.catalog_slug} --role {suggestion.role.lower()} --project {project}"
            else:
                cmd = f"workshop tech add {dimension} \"{suggestion.free_form_name}\" --role {suggestion.role.lower()} --project {project}"
            
            console.print(f"   [dim]{cmd}[/dim]")
        
        if len(suggestions) > 3:
            console.print(f"   [dim]... and {len(suggestions) - 3} more suggestions above[/dim]")
        
    except Exception as e:
        show_llm_error("Tech suggestion failed", str(e))
        if "--debug" in sys.argv:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


@app.command(name="summary")
def summary(project: str = typer.Option(..., "--project", "-p")) -> None:
    """Display full tech panorama summary as markdown."""
    
    if not TECH_SERVICE_AVAILABLE:
        show_error("Tech system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        service = TechService()
        tech_markdown = service.render_tech_summary(project)
        console.print(tech_markdown)
        
    except Exception as e:
        show_error("Failed to generate tech summary", str(e))
        raise typer.Exit(1)


@app.command(name="dimensions")
def show_dimensions() -> None:
    """Show all available tech dimensions and catalog items."""
    
    if not TECH_SERVICE_AVAILABLE:
        show_error("Tech system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        service = TechService()
        dimensions = service.list_dimensions()
        
        console.print("🔧 [bold]Available Tech Dimensions[/bold]")
        console.print()
        
        for dimension in dimensions:
            console.print(f"## {dimension['name']} ({dimension['slug']})")
            console.print(f"   {dimension['description']}")
            console.print(f"   [bold]{len(dimension['items'])} items available[/bold]")
            
            # Show first few items
            if dimension['items']:
                items_preview = ", ".join(item['name'] for item in dimension['items'][:8])
                console.print(f"   [dim]Items: {items_preview}")
                if len(dimension['items']) > 8:
                    console.print(f"   [dim]... and {len(dimension['items']) - 8} more[/dim]")
            
            console.print()
        
        console.print("💡 [dim]Use 'workshop tech pick <dimension> <item>' to select items[/dim]")
        
    except Exception as e:
        show_error("Failed to show tech dimensions", str(e))
        raise typer.Exit(1)