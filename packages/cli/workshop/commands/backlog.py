"""`workshop backlog ...` — phase-organized backlog (Step 0.6: stubs)."""

from __future__ import annotations

import typer

from workshop._common import stub

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@app.command(name="propose")
def propose(project: str = typer.Option(..., "--project", "-p")) -> None:
    """Run the `ProposeBacklog` LLM prompt — proposes phases + cards + deps."""
    stub("backlog", "propose", "Step 1.8")
