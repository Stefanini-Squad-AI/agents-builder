"""`workshop export ...` — write the .agents/ contract folder (Step 0.6: stubs)."""

from __future__ import annotations

from pathlib import Path

import typer

from workshop._common import stub

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@app.callback(invoke_without_command=True)
def export(
    ctx: typer.Context,
    project: str = typer.Option(..., "--project", "-p"),
    target: str = typer.Option(
        "filesystem",
        "--target",
        help="filesystem | zip | jira_csv (jira_csv lands in P5+)",
    ),
    path: Path | None = typer.Option(None, "--path", help="Output path for filesystem export."),
    out: Path | None = typer.Option(
        None, "--out", help="Output file for zip export (default: ./<slug>.zip)."
    ),
) -> None:
    """Export the .agents/ folder (filesystem, zip, or jira_csv)."""
    if ctx.invoked_subcommand is None:
        stub("export", "", "Step 1.12 (exporters)")
