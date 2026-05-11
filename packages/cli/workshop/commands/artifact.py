"""`workshop artifact ...` — async file extraction (Step 0.6: stubs)."""

from __future__ import annotations

from pathlib import Path

import typer

from workshop._common import stub

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@app.command(name="upload")
def upload(
    path: Path = typer.Argument(..., exists=True, readable=True),
    kind: str = typer.Option("doc", "--kind", help="doc / code / spec / glossary"),
    project: str = typer.Option(..., "--project", "-p"),
    no_wait: bool = typer.Option(
        False, "--no-wait", help="Do not poll until extraction completes."
    ),
) -> None:
    """Upload an artifact and (by default) wait for extraction to finish."""
    stub("artifact", "upload", "Step 0.11 (artifact upload + extract_artifact actor)")


@app.command(name="list")
def list_artifacts(project: str = typer.Option(..., "--project", "-p")) -> None:
    """List artifacts and their extraction status."""
    stub("artifact", "list", "Step 0.11")


@app.command(name="retry")
def retry(
    artifact_id: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Re-enqueue extraction for a failed artifact."""
    stub("artifact", "retry", "Step 0.11")
