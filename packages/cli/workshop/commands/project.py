"""`workshop project ...` — project lifecycle (Step 0.6: stubs only)."""

from __future__ import annotations

import typer

from workshop._common import stub

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@app.command(name="new")
def new() -> None:
    """Interactive wizard to create a new project (identity + Q&A + tech + artifacts)."""
    stub("project", "new", "Step 1.13 (CLI wiring; needs LLM + extractors)")


@app.command(name="list")
def list_projects() -> None:
    """List projects in this workspace."""
    stub("project", "list", "Step 1.13")


@app.command(name="show")
def show(slug: str = typer.Argument(..., help="Project slug.")) -> None:
    """Show project overview."""
    stub("project", "show", "Step 1.13")


@app.command(name="edit")
def edit(slug: str = typer.Argument(..., help="Project slug.")) -> None:
    """Edit project settings (provider, model, temperature, name, prefix)."""
    stub("project", "edit", "Step 1.13")


@app.command(name="set-context")
def set_context(slug: str = typer.Argument(..., help="Project slug.")) -> None:
    """Append free-form context to the project (reads from $EDITOR or stdin)."""
    stub("project", "set-context", "Step 1.13")
