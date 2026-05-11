"""`workshop llm-runs ...` — LLM audit log (Step 0.6: stubs)."""

from __future__ import annotations

import typer

from workshop._common import stub

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@app.callback(invoke_without_command=True)
def list_runs(
    ctx: typer.Context,
    project: str = typer.Option(..., "--project", "-p"),
    kind: str | None = typer.Option(
        None, "--kind", help="Filter by run kind (propose_skill_set, draft_card, ...)."
    ),
    last: int = typer.Option(20, "--last", "-n", help="Show last N runs."),
) -> None:
    """List recent LLM calls for a project."""
    if ctx.invoked_subcommand is None:
        stub("llm-runs", "", "Step 1.4 (LLMService audit log)")


@app.command(name="show")
def show(
    run_id: str = typer.Argument(..., help="UUID of the LLM run."),
) -> None:
    """Show the full prompt, response, and reasoning (if any) for a run."""
    stub("llm-runs", "show", "Step 1.4")
