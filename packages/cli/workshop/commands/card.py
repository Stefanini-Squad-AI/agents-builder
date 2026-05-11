"""`workshop card ...` — card management (Step 0.6: stubs)."""

from __future__ import annotations

import typer

from workshop._common import stub

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@app.command(name="list")
def list_cards(
    project: str = typer.Option(..., "--project", "-p"),
    phase: str | None = typer.Option(None, "--phase", help="Filter by phase code."),
) -> None:
    """List cards (optionally filtered by phase)."""
    stub("card", "list", "Step 1.13")


@app.command(name="draft")
def draft(
    card_code: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Run the `DraftCard` LLM prompt for one card."""
    stub("card", "draft", "Step 1.9")


@app.command(name="show")
def show(
    card_code: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Render the full card markdown to stdout."""
    stub("card", "show", "Step 1.13")


@app.command(name="edit")
def edit(
    card_code: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
    section: str | None = typer.Option(
        None,
        "--section",
        help="Edit one section only: context, task, outputs, ac, gate.",
    ),
) -> None:
    """Open $EDITOR on a card (full body or one section)."""
    stub("card", "edit", "Step 1.13")
