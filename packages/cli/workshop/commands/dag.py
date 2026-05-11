"""`workshop dag` — print Mermaid DAG (Step 0.6: stub)."""

from __future__ import annotations

import typer

from workshop._common import stub


def dag(project: str = typer.Option(..., "--project", "-p")) -> None:
    """Print the project's card dependency DAG as Mermaid (top-down)."""
    stub("dag", "", "Step 1.12 (mermaid exporter)")
