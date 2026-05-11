"""`workshop validate` — run all deterministic validators (Step 0.6: stub)."""

from __future__ import annotations

import typer

from workshop._common import stub


def validate(
    project: str = typer.Option(..., "--project", "-p"),
    strict: bool = typer.Option(
        False, "--strict", help="Treat warnings as errors (non-zero exit)."
    ),
) -> None:
    """Run DAG / refs / frontmatter / paths / Q&A validators."""
    stub("validate", "", "Step 1.11")
