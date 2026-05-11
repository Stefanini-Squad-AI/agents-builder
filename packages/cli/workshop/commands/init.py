"""`workshop init` — initialize workspace config in the current directory.

Creates a `.workshop` marker file plus a per-user `data/` directory if the
repo doesn't already have one. Idempotent and safe to re-run.
"""

from __future__ import annotations

import typer
from rich.console import Console

from workshop._common import find_repo_root

console = Console()


def init(
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite an existing .workshop marker if present."
    ),
) -> None:
    """Initialize workspace config (idempotent)."""
    root = find_repo_root()

    marker = root / ".workshop"
    if marker.exists() and not force:
        console.print(
            f"[dim].workshop already exists at {marker} — nothing to do "
            f"(use --force to overwrite).[/dim]"
        )
    else:
        marker.write_text(
            "# Marker for workshop CLI — created by `workshop init`.\n"
            "# Indicates this directory is the workspace root.\n",
            encoding="utf-8",
        )
        console.print(f"[green]Wrote[/green] {marker}")

    data = root / "data"
    if not data.exists():
        data.mkdir()
        (data / ".gitkeep").touch()
        console.print(f"[green]Created[/green] {data}/")

    env_example = root / ".env.example"
    env_file = root / ".env"
    if env_example.exists() and not env_file.exists():
        console.print(
            f"[yellow]Hint:[/yellow] copy [bold]{env_example.name}[/bold] to "
            f"[bold].env[/bold] and fill in your secrets before running real commands."
        )

    console.print("[green]Workshop initialized.[/green]")
