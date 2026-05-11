"""`workshop tech ...` — tech panorama picker (Step 0.6: stubs)."""

from __future__ import annotations

import typer

from workshop._common import stub

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@app.command(name="list")
def list_tech(project: str = typer.Option(..., "--project", "-p")) -> None:
    """Show all dimensions and the project's current choices."""
    stub("tech", "list", "Step 1.13")


@app.command(name="pick")
def pick(
    dimension: str = typer.Argument(...),
    item_slug: str = typer.Argument(...),
    role: str = typer.Option("target", "--role", help="target / legacy / optional / must-avoid"),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Pick a catalog item for a dimension."""
    stub("tech", "pick", "Step 1.13")


@app.command(name="add")
def add(
    dimension: str = typer.Argument(...),
    name: str = typer.Argument(..., help="Free-form item name"),
    role: str = typer.Option("target", "--role"),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Add a custom item to a dimension (becomes is_custom=true)."""
    stub("tech", "add", "Step 1.13")


@app.command(name="tbd")
def mark_tbd(
    dimension: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Mark a dimension as TBD (decide later)."""
    stub("tech", "tbd", "Step 1.13")


@app.command(name="suggest")
def suggest(
    dimension: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Ask the LLM to propose items for a single dimension (`SuggestTechStack` prompt)."""
    stub("tech", "suggest", "Step 1.10 + 1.13 (needs LLM provider wired)")
