"""`workshop skill ...` — skill library (Step 0.6: stubs)."""

from __future__ import annotations

import typer

from workshop._common import stub

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@app.command(name="propose")
def propose(project: str = typer.Option(..., "--project", "-p")) -> None:
    """Run the `ProposeSkillSet` LLM prompt — proposes 5..10 skills."""
    stub("skill", "propose", "Step 1.6")


@app.command(name="list")
def list_skills(project: str = typer.Option(..., "--project", "-p")) -> None:
    """List skills in the project."""
    stub("skill", "list", "Step 1.13")


@app.command(name="draft")
def draft(
    skill_slug: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
    force: bool = typer.Option(False, "--force", help="Overwrite the existing body if any."),
) -> None:
    """Run the `DraftSkillBody` LLM prompt to fill in a proposed skill."""
    stub("skill", "draft", "Step 1.7")


@app.command(name="show")
def show(
    skill_slug: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Render the full SKILL.md (frontmatter + body) to stdout."""
    stub("skill", "show", "Step 1.13")


@app.command(name="edit")
def edit(
    skill_slug: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Open $EDITOR on the skill body."""
    stub("skill", "edit", "Step 1.13")
