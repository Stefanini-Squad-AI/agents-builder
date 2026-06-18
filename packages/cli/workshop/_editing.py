"""Interactive editing utilities for CLI commands."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table


console = Console()


def open_editor(content: str = "", file_extension: str = ".md", editor_hint: str = "") -> str:
    """Open $EDITOR with content and return the edited result.
    
    Args:
        content: Initial content to populate in editor
        file_extension: File extension for temporary file
        editor_hint: Optional hint about what's being edited
        
    Returns:
        Edited content from the editor
        
    Raises:
        RuntimeError: If editor fails or is cancelled
    """
    # Get editor from environment (prefer EDITOR, fall back to common editors)
    editor = os.environ.get('EDITOR')
    
    if not editor:
        # Try common editors
        for candidate in ['code', 'vim', 'nano', 'notepad']:
            if _command_exists(candidate):
                editor = candidate
                break
    
    if not editor:
        raise RuntimeError(
            "No editor found. Set EDITOR environment variable or install vim/nano/code."
        )
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(
        mode='w+', 
        suffix=file_extension, 
        delete=False, 
        encoding='utf-8'
    ) as temp_file:
        temp_file.write(content)
        temp_file.flush()
        temp_path = Path(temp_file.name)
    
    try:
        # Display hint if provided
        if editor_hint:
            console.print(f"📝 Opening editor for: {editor_hint}")
        
        console.print(f"🔧 Using editor: {editor}")
        console.print("💾 Save and close the editor to continue...")
        
        # Open editor
        result = subprocess.run([editor, str(temp_path)], check=False)
        
        if result.returncode != 0:
            raise RuntimeError(f"Editor exited with code {result.returncode}")
        
        # Read back the edited content
        edited_content = temp_path.read_text(encoding='utf-8')
        
        # Check if content was actually edited (not just opened and closed)
        if edited_content.strip() == content.strip():
            if not Confirm.ask("No changes detected. Use the original content?"):
                raise RuntimeError("Editing cancelled by user")
        
        return edited_content
    
    finally:
        # Clean up temporary file
        temp_path.unlink(missing_ok=True)


def prompt_for_project_settings() -> dict[str, Any]:
    """Interactive wizard for project creation settings.
    
    Returns:
        Dictionary with project configuration
    """
    console.print("🚀 [bold]Creating a new project...[/bold]")
    console.print()
    
    # Basic project info
    console.print("📝 [bold]Project Details[/bold]")
    name = Prompt.ask("Project name", default="My Project")
    
    # Auto-generate slug from name
    suggested_slug = _name_to_slug(name)
    slug = Prompt.ask("Project slug", default=suggested_slug)
    
    # Validate slug format
    while not _is_valid_slug(slug):
        console.print("❌ Invalid slug format. Use lowercase letters, numbers, and hyphens only.")
        slug = Prompt.ask("Project slug (kebab-case)")
    
    objective = Prompt.ask("Project objective", default="Describe what this project aims to achieve")
    
    # Auto-generate card prefix from name
    suggested_prefix = _name_to_prefix(name)
    card_code_prefix = Prompt.ask("Card code prefix", default=suggested_prefix)
    
    # Validate prefix format
    while not _is_valid_prefix(card_code_prefix):
        console.print("❌ Invalid prefix format. Use 2-8 uppercase letters/numbers.")
        card_code_prefix = Prompt.ask("Card code prefix (uppercase)")
    
    console.print()
    
    # LLM Configuration
    console.print("🤖 [bold]LLM Configuration[/bold]")
    
    llm_providers = [
        ("anthropic", "Anthropic (Claude)"),
        ("openai", "OpenAI (GPT)"), 
        ("bedrock", "AWS Bedrock"),
        ("ollama", "Ollama (Local)")
    ]
    
    console.print("Available providers:")
    for i, (code, name) in enumerate(llm_providers, 1):
        console.print(f"  {i}. {name}")
    
    provider_choice = Prompt.ask(
        "Choose provider", 
        choices=[str(i) for i in range(1, len(llm_providers) + 1)],
        default="1"
    )
    
    llm_provider = llm_providers[int(provider_choice) - 1][0]
    
    # Model selection based on provider
    if llm_provider == "anthropic":
        llm_model = Prompt.ask("Model", default="claude-3-5-sonnet-20241022")
    elif llm_provider == "openai":
        llm_model = Prompt.ask("Model", default="gpt-4-turbo-preview")
    elif llm_provider == "bedrock":
        llm_model = Prompt.ask("Model", default="anthropic.claude-3-5-sonnet-20241022-v2:0")
    else:  # ollama
        llm_model = Prompt.ask("Model", default="llama3.1:8b")
    
    llm_temperature = float(Prompt.ask("Temperature (0.0-2.0)", default="0.7"))
    
    console.print()
    
    # Optional context
    add_context = Confirm.ask("Add project context now?", default=False)
    context_md = ""
    
    if add_context:
        try:
            context_md = open_editor(
                content="# Project Context\n\nAdd any relevant background, constraints, or additional information here...\n",
                editor_hint="Project context"
            )
        except RuntimeError as e:
            console.print(f"⚠️  Context editing failed: {e}")
            console.print("You can add context later with: workshop project set-context")
    
    return {
        "name": name,
        "slug": slug,
        "objective": objective,
        "card_code_prefix": card_code_prefix,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "llm_temperature": llm_temperature,
        "context_md": context_md if context_md.strip() else None
    }


def display_projects_table(projects: list[dict[str, Any]]) -> None:
    """Display projects in a formatted table.
    
    Args:
        projects: List of project data dictionaries
    """
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
            project.get("slug", ""),
            project.get("name", ""),
            str(project.get("card_count", 0)),
            str(project.get("skill_count", 0)),
            project.get("created_at", "").split("T")[0] if project.get("created_at") else ""
        )
    
    console.print(table)


def display_project_summary(summary: dict[str, Any]) -> None:
    """Display detailed project summary.
    
    Args:
        summary: Project summary data from ProjectService
    """
    project = summary["project"]
    
    console.print(f"📋 [bold]{project.get('name')}[/bold] ({project.get('slug')})")
    console.print(f"🎯 {project.get('objective', 'No objective set')}")
    console.print()
    
    if project.get("context_md"):
        console.print("📝 [bold]Context[/bold]")
        console.print(project["context_md"])
        console.print()
    
    # Q&A Status
    qa = summary["qa"]
    qa_progress = qa["completion_percentage"]
    console.print(f"❓ [bold]Q&A:[/bold] {qa['answered_questions']}/7 questions answered ({qa_progress:.0f}%)")
    
    # Tech Choices Status  
    tech = summary["tech"]
    tech_progress = tech["completion_percentage"]
    console.print(f"🔧 [bold]Tech:[/bold] {tech['chosen_dimensions']}/13 dimensions chosen ({tech_progress:.0f}%)")
    
    # Skills Summary
    skills = summary["skills"]
    console.print(f"🎨 [bold]Skills:[/bold] {skills['total_count']} skills")
    if skills["by_kind"]:
        kind_summary = ", ".join(f"{count} {kind}" for kind, count in skills["by_kind"].items())
        console.print(f"    {kind_summary}")
    
    # Phases Summary
    phases = summary["phases"]
    if phases:
        console.print()
        console.print("📊 [bold]Phases[/bold]")
        
        phase_table = Table()
        phase_table.add_column("Phase", style="cyan")
        phase_table.add_column("Cards", justify="right")
        phase_table.add_column("Completed", justify="right", style="green")
        phase_table.add_column("Progress", justify="right")
        
        for phase in phases:
            progress = f"{phase['completion_percentage']:.0f}%"
            phase_table.add_row(
                f"{phase['code']}: {phase['name']}",
                str(phase['card_count']),
                str(phase['completed_count']),
                progress
            )
        
        console.print(phase_table)
    
    console.print()
    console.print("💡 [dim]Use 'workshop project edit' to modify settings[/dim]")


def confirm_action(message: str, default: bool = False) -> bool:
    """Interactive confirmation prompt.
    
    Args:
        message: Confirmation message
        default: Default response
        
    Returns:
        User's confirmation choice
    """
    return Confirm.ask(message, default=default)


def show_error(message: str, details: str | None = None) -> None:
    """Display error message with optional details.
    
    Args:
        message: Main error message
        details: Optional error details
    """
    console.print(f"❌ {message}", style="bold red")
    if details:
        console.print(f"   {details}", style="dim red")


def show_success(message: str, details: str | None = None) -> None:
    """Display success message with optional details.
    
    Args:
        message: Main success message
        details: Optional additional details
    """
    console.print(f"✅ {message}", style="bold green")
    if details:
        console.print(f"   {details}", style="dim green")


def show_warning(message: str, details: str | None = None) -> None:
    """Display warning message with optional details.
    
    Args:
        message: Main warning message
        details: Optional warning details  
    """
    console.print(f"⚠️  {message}", style="bold yellow")
    if details:
        console.print(f"   {details}", style="dim yellow")


# Helper functions

def _command_exists(command: str) -> bool:
    """Check if a command exists in PATH."""
    return subprocess.run(
        ["where" if os.name == "nt" else "which", command],
        capture_output=True,
        check=False
    ).returncode == 0


def _name_to_slug(name: str) -> str:
    """Convert project name to slug."""
    import re
    slug = name.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)  # Remove special chars
    slug = re.sub(r'[-\s_]+', '-', slug)  # Replace spaces/underscores with hyphens
    return slug.strip('-')


def _name_to_prefix(name: str) -> str:
    """Convert project name to card code prefix."""
    import re
    # Take first letters of words, max 4 chars
    words = re.findall(r'\w+', name.upper())
    if len(words) == 1:
        return words[0][:4]
    else:
        return ''.join(word[0] for word in words[:4])


def _is_valid_slug(slug: str) -> bool:
    """Validate slug format."""
    import re
    return bool(re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', slug))


def _is_valid_prefix(prefix: str) -> bool:
    """Validate card code prefix format."""
    import re
    return bool(re.match(r'^[A-Z0-9]{2,8}$', prefix))