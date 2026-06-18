"""`workshop qa ...` — Q&A wizard."""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.table import Table

# Import the Q&A system
try:
    from app.services.qa_service import QaService
    QA_SERVICE_AVAILABLE = True
except ImportError:
    QA_SERVICE_AVAILABLE = False

from rich.prompt import Prompt

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
def list_answers(project: str = typer.Option(..., "--project", "-p")) -> None:
    """Show the 7 Q&A questions and their current answers for a project."""

    if not QA_SERVICE_AVAILABLE:
        show_error("Q&A system not available. Ensure core package is installed.")
        raise typer.Exit(1)

    try:
        service = QaService()
        qa_answers = service.list_project_qa(project)

        if not qa_answers:
            console.print(f"❓ No Q&A found for project '{project}'")
            return

        # Display Q&A table
        table = Table(title=f"❓ Q&A for '{project}'")
        table.add_column("Key", style="cyan")
        table.add_column("Question", style="white")
        table.add_column("Status", justify="center")
        table.add_column("Required", justify="center", style="yellow")

        for qa in qa_answers:
            status = "✅" if qa.is_answered else "❌"
            required = "⭐" if qa.required else ""

            # Truncate long questions for display
            question_display = qa.prompt
            if len(question_display) > 60:
                question_display = question_display[:57] + "..."

            table.add_row(qa.question_key, question_display, status, required)

        console.print(table)

        # Show statistics
        stats = service.get_qa_statistics(project)
        console.print()
        console.print(
            f"📊 [bold]Progress:[/bold] {stats['answered_questions']}/{stats['total_questions']} "
            f"questions answered ({stats['completion_percentage']:.0f}%)"
        )
        console.print(
            f"⭐ [bold]Required:[/bold] {stats['required_answered']}/{stats['required_total']} "
            f"required questions answered ({stats['required_percentage']:.0f}%)"
        )

        # Show completion status
        status = service.get_completion_status(project)
        if status["readiness"] == "blocked":
            console.print(f"🚫 [bold red]Status:[/bold red] {status['message']}")
        elif status["readiness"] == "partial":
            console.print(f"⚠️  [bold yellow]Status:[/bold yellow] {status['message']}")
        else:
            console.print(f"✅ [bold green]Status:[/bold green] {status['message']}")

        # Show next steps
        if status.get("recommended_next_steps"):
            console.print()
            console.print("💡 [bold]Next steps:[/bold]")
            for step in status["recommended_next_steps"]:
                console.print(f"   • {step}")

    except Exception as e:
        show_error("Failed to list Q&A", str(e))
        raise typer.Exit(1)


@app.command(name="set")
def set_answer(
    question_key: str = typer.Argument(
        ...,
        help=(
            "One of: business_problem, success_definition, users_and_actors, "
            "must_preserve, must_change, compliance, known_gaps."
        ),
    ),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Set or update an answer (opens $EDITOR)."""

    if not QA_SERVICE_AVAILABLE:
        show_error("Q&A system not available. Ensure core package is installed.")
        raise typer.Exit(1)

    try:
        service = QaService()

        # Validate question key
        if question_key not in service.STANDARD_QUESTIONS:
            show_error(f"Invalid question key: {question_key}")
            console.print("Valid question keys:")
            for key, meta in service.STANDARD_QUESTIONS.items():
                required = " (required)" if meta.required else ""
                console.print(f"  [cyan]{key}[/cyan]: {meta.prompt}{required}")
            raise typer.Exit(1)

        # Get current answer if it exists
        current_qa = service.get_qa_answer(project, question_key)
        if not current_qa:
            show_error(f"Project '{project}' not found")
            raise typer.Exit(1)

        console.print(f"📝 [bold]Question:[/bold] {current_qa.prompt}")

        if current_qa.is_answered:
            console.print("[bold]Current answer:[/bold]")
            console.print(current_qa.answer_md)
            console.print()

        # Get answer interactively
        default_answer = current_qa.answer_md if current_qa.is_answered else ""

        # Try to use editor, fall back to prompt
        try:
            from workshop._utils import open_editor

            console.print("📝 Opening editor for answer...")
            new_answer = open_editor(content=default_answer, file_extension=".md")
        except (ImportError, RuntimeError):
            # Fall back to simple text input
            console.print("💡 Enter answer (use Ctrl+D or Ctrl+Z when done):")
            lines = []
            try:
                while True:
                    line = input()
                    lines.append(line)
            except EOFError:
                pass
            new_answer = "\n".join(lines)

            if not new_answer.strip() and default_answer:
                new_answer = default_answer

        if not new_answer.strip():
            console.print("⚠️  No answer provided. Cancelled.", style="yellow")
            return

        # Save answer
        updated_qa = service.set_qa_answer(project, question_key, new_answer)

        if updated_qa:
            show_success(f"Answer for '{question_key}' saved successfully!")

            # Show updated statistics
            stats = service.get_qa_statistics(project)
            console.print(
                f"📊 Progress: {stats['answered_questions']}/{stats['total_questions']} "
                "questions answered"
            )
        else:
            show_error("Failed to save answer")
            raise typer.Exit(1)

    except ValueError as e:
        show_error("Invalid input", str(e))
        raise typer.Exit(1)
    except Exception as e:
        show_error("Failed to set Q&A answer", str(e))
        if "--debug" in sys.argv:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1)


@app.command(name="summary")
def summary(project: str = typer.Option(..., "--project", "-p")) -> None:
    """Display full Q&A summary as markdown."""
    
    if not QA_SERVICE_AVAILABLE:
        show_error("Q&A system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        service = QaService()
        qa_markdown = service.render_qa_summary(project)
        console.print(qa_markdown)
        
    except Exception as e:
        show_error("Failed to generate Q&A summary", str(e))
        raise typer.Exit(1)