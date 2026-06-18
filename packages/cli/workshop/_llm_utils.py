"""Utilities for LLM operations in CLI commands."""

from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from typing import Any, TypeVar

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

# Import core LLM functionality
try:
    from app.llm.base import ProviderNotConfigured
    from app.llm.service import LLMService
    from app.services.llm_service_factory import LlmServiceFactory
    from app.services.project_context_service import ProjectContextService
    from app.schemas.views import ProjectContext
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

console = Console()
T = TypeVar('T')


def show_llm_error(message: str, details: str | None = None) -> None:
    """Display LLM-specific error message."""
    console.print(f"🤖 [bold red]{message}[/bold red]")
    if details:
        console.print(f"   [dim red]{details}[/dim red]")


def show_llm_success(message: str, details: str | None = None) -> None:
    """Display LLM success message."""
    console.print(f"🤖 [bold green]{message}[/bold green]")
    if details:
        console.print(f"   [dim green]{details}[/dim green]")


def show_llm_warning(message: str, details: str | None = None) -> None:
    """Display LLM warning message."""
    console.print(f"🤖 [bold yellow]{message}[/bold yellow]")
    if details:
        console.print(f"   [dim yellow]{details}[/dim yellow]")


@contextmanager
def llm_progress(task_description: str):
    """Context manager for showing progress during LLM operations.
    
    Args:
        task_description: Description of the task being performed
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task(task_description, total=None)
        yield progress


def validate_llm_availability() -> bool:
    """Check if LLM functionality is available.
    
    Returns:
        True if LLM components can be imported and used
    """
    if not LLM_AVAILABLE:
        show_llm_error(
            "LLM functionality not available", 
            "Ensure core package is installed with LLM dependencies"
        )
        return False
    return True


def create_llm_service_for_project(project_slug: str) -> LLMService | None:
    """Create LLM service for a project with error handling.
    
    Args:
        project_slug: Project slug
        
    Returns:
        Configured LLMService or None if failed
    """
    if not validate_llm_availability():
        return None
    
    try:
        factory = LlmServiceFactory()
        
        with llm_progress(f"Configuring LLM for project '{project_slug}'..."):
            import app.db
            with app.db.session_scope() as session:
                return factory.create_for_project(project_slug, session)
                
    except ValueError as e:
        show_llm_error("Project configuration error", str(e))
        return None
    except ProviderNotConfigured as e:
        show_llm_error("LLM provider not configured", str(e))
        console.print("💡 [dim]Configure your LLM provider credentials in environment variables[/dim]")
        return None
    except Exception as e:
        show_llm_error("Failed to create LLM service", str(e))
        if "--debug" in sys.argv:
            import traceback
            console.print(traceback.format_exc())
        return None


def load_project_context(project_slug: str) -> ProjectContext | None:
    """Load project context with error handling.
    
    Args:
        project_slug: Project slug
        
    Returns:
        ProjectContext or None if failed
    """
    if not validate_llm_availability():
        return None
    
    try:
        context_service = ProjectContextService()
        
        with llm_progress(f"Loading context for project '{project_slug}'..."):
            context = context_service.load_project_context(project_slug)
            
        if not context:
            show_llm_error(f"Project '{project_slug}' not found")
            return None
            
        return context
        
    except Exception as e:
        show_llm_error("Failed to load project context", str(e))
        return None


def check_project_readiness(project_slug: str) -> bool:
    """Check if project is ready for AI generation.
    
    Args:
        project_slug: Project slug
        
    Returns:
        True if ready for AI operations
    """
    if not validate_llm_availability():
        return False
    
    try:
        context_service = ProjectContextService()
        readiness = context_service.validate_project_readiness_for_ai(project_slug)
        
        if not readiness["ready"]:
            show_llm_warning("Project not ready for AI generation", readiness["reason"])
            return False
        
        # Show recommendations if any
        if "recommendations" in readiness and readiness["recommendations"]:
            console.print("💡 [bold]Recommendations for better results:[/bold]")
            for rec in readiness["recommendations"]:
                console.print(f"   • {rec}")
            console.print()
        
        return True
        
    except Exception as e:
        show_llm_error("Failed to check project readiness", str(e))
        return False


def run_llm_prompt(
    llm_service: LLMService, 
    prompt: Any, 
    operation_name: str,
    show_cost: bool = True
) -> Any:
    """Run an LLM prompt with progress indication and error handling.
    
    Args:
        llm_service: Configured LLM service
        prompt: LLM prompt to execute
        operation_name: Human-readable name for the operation
        show_cost: Whether to show cost information
        
    Returns:
        LLM result or None if failed
    """
    start_time = time.time()
    
    try:
        with llm_progress(f"Running {operation_name}..."):
            result = llm_service.run(prompt)
        
        # Show completion info
        duration = time.time() - start_time
        console.print(f"✅ {operation_name} completed in {duration:.1f}s")
        
        if show_cost and result.cost is not None:
            console.print(f"💰 Cost: ${result.cost:.4f}")
        
        if result.total_tokens:
            console.print(f"🔢 Tokens: {result.total_tokens}")
        
        console.print()
        return result
        
    except Exception as e:
        show_llm_error(f"{operation_name} failed", str(e))
        return None


def format_llm_result_summary(result: Any) -> str:
    """Format LLM result for display.
    
    Args:
        result: LLM result object
        
    Returns:
        Formatted summary string
    """
    if not result:
        return "No result"
    
    lines = []
    
    # Basic info
    if hasattr(result, 'total_tokens') and result.total_tokens:
        lines.append(f"Tokens: {result.total_tokens}")
    
    if hasattr(result, 'cost') and result.cost:
        lines.append(f"Cost: ${result.cost:.4f}")
    
    # Content preview based on result type
    if hasattr(result, 'parsed') and result.parsed:
        parsed = result.parsed
        
        if hasattr(parsed, 'skills') and parsed.skills:
            lines.append(f"Generated {len(parsed.skills)} skills")
        
        if hasattr(parsed, 'phases') and parsed.phases:
            total_cards = sum(len(phase.cards) for phase in parsed.phases)
            lines.append(f"Generated {len(parsed.phases)} phases with {total_cards} cards")
        
        if hasattr(parsed, 'suggestions') and parsed.suggestions:
            lines.append(f"Generated {len(parsed.suggestions)} technology suggestions")
    
    return " • ".join(lines) if lines else "Completed successfully"


def show_provider_status() -> None:
    """Show status of available LLM providers."""
    if not validate_llm_availability():
        return
    
    try:
        factory = LlmServiceFactory()
        providers = factory.list_available_providers()
        
        console.print("🤖 [bold]LLM Provider Status[/bold]")
        console.print()
        
        for provider in providers:
            status_icon = "✅" if provider["configured"] else "❌"
            console.print(f"{status_icon} [bold]{provider['name']}[/bold]")
            
            if not provider["configured"] and provider.get("error"):
                console.print(f"   [dim red]{provider['error']}[/dim red]")
        
        console.print()
        
    except Exception as e:
        show_llm_error("Failed to check provider status", str(e))