"""`workshop qa ...` — discovery Q&A wizard (Step 0.6: stubs)."""

from __future__ import annotations

import typer

from workshop._common import stub

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@app.command(name="list")
def list_answers(project: str = typer.Option(..., "--project", "-p")) -> None:
    """Show the 7 Q&A questions and their current answers for a project."""
    stub("qa", "list", "Step 1.13")


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
    stub("qa", "set", "Step 1.13")
