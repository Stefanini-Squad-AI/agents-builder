"""`workshop project ...` — project lifecycle."""

from __future__ import annotations

import sys

import typer

# Import the project system
try:
    from app.services.project_service import ProjectService
    PROJECT_SERVICE_AVAILABLE = True
except ImportError:
    PROJECT_SERVICE_AVAILABLE = False

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table

console = Console()


def show_error(message: str, details: str | None = None) -> None:
    """Display error message."""
    console.print(f"❌ {message}", style="bold red")
    if details:
        console.print(f"   {details}", style="dim red")


def show_success(message: str) -> None:
    """Display success message."""
    console.print(f"✅ {message}", style="bold green")


def show_warning(message: str) -> None:
    """Display warning message."""
    console.print(f"⚠️  {message}", style="bold yellow")


def display_projects_table(projects) -> None:
    """Display projects in a formatted table."""
    if not projects:
        console.print("📂 No projects found.")
        console.print("💡 Create one with: [bold]workshop project new[/bold]")
        return
    
    table = Table(title="📋 Projects")
    table.add_column("Slug", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Cards", justify="right", style="green")
    table.add_column("Skills", justify="right", style="blue")
    table.add_column("Created", style="dim")
    
    for project in projects:
        table.add_row(
            project.slug,
            project.name,
            str(project.card_count),
            str(project.skill_count),
            project.created_at.strftime("%Y-%m-%d") if project.created_at else ""
        )
    
    console.print(table)


def display_project_summary(summary) -> None:
    """Display detailed project summary."""
    project = summary["project"]
    
    console.print(f"📋 [bold]{project.name}[/bold] ({project.slug})")
    console.print(f"🎯 {project.objective}")
    console.print()
    
    if hasattr(project, "context_md") and project.context_md:
        console.print("📝 [bold]Context[/bold]")
        console.print(project.context_md[:200] + "..." if len(project.context_md) > 200 else project.context_md)
        console.print()
    
    # Summary stats
    if "qa" in summary:
        qa = summary["qa"]
        console.print(f"❓ [bold]Q&A:[/bold] {qa['answered_questions']}/7 answered ({qa['completion_percentage']:.0f}%)")
    
    if "tech" in summary:
        tech = summary["tech"]
        console.print(f"🔧 [bold]Tech:[/bold] {tech['chosen_dimensions']}/13 dimensions ({tech['completion_percentage']:.0f}%)")
    
    if "skills" in summary:
        skills = summary["skills"]
        console.print(f"🎨 [bold]Skills:[/bold] {skills['total_count']} skills")
    
    console.print()
    console.print("💡 [dim]Use 'workshop project edit' to modify settings[/dim]")

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@app.command(name="new")
def new() -> None:
    """Interactive wizard to create a new project (identity + Q&A + tech + artifacts)."""
    
    if not PROJECT_SERVICE_AVAILABLE:
        show_error("Project system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        # Simple project creation
        console.print("🚀 [bold]Creating a new project...[/bold]")
        
        name = Prompt.ask("Project name", default="My Project")
        slug = Prompt.ask("Project slug", default=name.lower().replace(" ", "-"))
        objective = Prompt.ask("Project objective", default="Describe what this project aims to achieve")
        prefix = Prompt.ask("Card code prefix (2-8 uppercase chars)", default="PROJ")
        
        settings = {
            "name": name,
            "slug": slug, 
            "objective": objective,
            "card_code_prefix": prefix,
            "llm_provider": "anthropic",
            "llm_model": "claude-3-5-sonnet-20241022",
            "llm_temperature": 0.7
        }
        
        # Create project
        service = ProjectService()
        project = service.create_project(**settings)
        
        show_success(f"Project '{project.slug}' created successfully!")
        
        # Show next steps
        typer.echo("\n💡 Next steps:")
        typer.echo(f"   - View project: workshop project show {project.slug}")
        typer.echo(f"   - Add Q&A answers: workshop qa list --project {project.slug}")
        typer.echo(f"   - Configure tech: workshop tech list --project {project.slug}")
        typer.echo(f"   - Generate skills: workshop skill propose --project {project.slug}")
        
    except ValueError as e:
        show_error("Project creation failed", str(e))
        raise typer.Exit(1)
    except Exception as e:
        show_error("Unexpected error during project creation", str(e))
        if "--debug" in sys.argv:
            import traceback
            typer.echo(traceback.format_exc())
        raise typer.Exit(1)


@app.command(name="list")
def list_projects() -> None:
    """List projects in this workspace."""
    
    if not PROJECT_SERVICE_AVAILABLE:
        show_error("Project system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        service = ProjectService()
        projects = service.list_projects()
        
        # Convert to dict format for table display
        project_data = []
        for project in projects:
            project_data.append({
                "slug": project.slug,
                "name": project.name,
                "card_count": project.card_count,
                "skill_count": project.skill_count,
                "created_at": project.created_at.isoformat() if project.created_at else ""
            })
        
        display_projects_table(project_data)
        
    except Exception as e:
        show_error("Failed to list projects", str(e))
        raise typer.Exit(1)


@app.command(name="show")
def show(slug: str = typer.Argument(..., help="Project slug.")) -> None:
    """Show project overview."""
    
    if not PROJECT_SERVICE_AVAILABLE:
        show_error("Project system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        service = ProjectService()
        summary = service.get_project_summary(slug)
        
        if not summary:
            show_error(f"Project '{slug}' not found")
            typer.echo("💡 List available projects: workshop project list")
            raise typer.Exit(1)
        
        display_project_summary(summary)
        
    except Exception as e:
        show_error("Failed to show project", str(e))
        raise typer.Exit(1)


@app.command(name="edit")
def edit(slug: str = typer.Argument(..., help="Project slug.")) -> None:
    """Edit project settings (provider, model, temperature, name, prefix)."""
    
    if not PROJECT_SERVICE_AVAILABLE:
        show_error("Project system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        service = ProjectService()
        project = service.get_project_by_slug(slug)
        
        if not project:
            show_error(f"Project '{slug}' not found")
            raise typer.Exit(1)
        
        typer.echo(f"📝 Editing project: {project.name}")
        typer.echo("💡 Press Enter to keep current values")
        typer.echo()
        
        # Interactive editing
        from rich.prompt import Prompt
        
        new_name = Prompt.ask("Project name", default=project.name)
        new_objective = Prompt.ask("Objective", default=project.objective)
        new_prefix = Prompt.ask("Card code prefix", default=project.card_code_prefix)
        new_provider = Prompt.ask("LLM provider", default=project.llm_provider)
        new_model = Prompt.ask("LLM model", default=project.llm_model)
        new_temperature = float(Prompt.ask("Temperature", default=str(project.llm_temperature)))
        
        # Update project
        updated_project = service.update_project(
            slug,
            name=new_name,
            objective=new_objective,
            card_code_prefix=new_prefix,
            llm_provider=new_provider,
            llm_model=new_model,
            llm_temperature=new_temperature
        )
        
        if updated_project:
            show_success(f"Project '{slug}' updated successfully!")
        else:
            show_error("Failed to update project")
            raise typer.Exit(1)
        
    except ValueError as e:
        show_error("Invalid input", str(e))
        raise typer.Exit(1)
    except Exception as e:
        show_error("Failed to edit project", str(e))
        raise typer.Exit(1)


@app.command(name="set-context")
def set_context(slug: str = typer.Argument(..., help="Project slug.")) -> None:
    """Append free-form context to the project (reads from $EDITOR or stdin)."""
    
    if not PROJECT_SERVICE_AVAILABLE:
        show_error("Project system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        service = ProjectService()
        project = service.get_project_by_slug(slug)
        
        if not project:
            show_error(f"Project '{slug}' not found")
            raise typer.Exit(1)
        
        # Simple context input for now
        console.print(f"📝 Current context for '{project.name}':")
        if project.context_md:
            console.print(project.context_md)
        else:
            console.print("(No context set)")
        
        console.print()
        new_context = Prompt.ask("Enter new context (or press Enter to keep current)")
        
        if new_context.strip():
            # Update project context
            updated_project = service.update_project(slug, context_md=new_context)
            
            if updated_project:
                show_success("Project context updated successfully!")
            else:
                show_error("Failed to update project context")
                raise typer.Exit(1)
        else:
            console.print("Context unchanged.")
            
    except Exception as e:
        show_error("Failed to set project context", str(e))
        raise typer.Exit(1)
