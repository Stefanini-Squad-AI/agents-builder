"""Shared CLI helpers: repo discovery, project resolution, subprocess wrappers.

Intentionally minimal in Step 0.6 — only what the wired commands (`init`,
`db migrate`) actually need. Helpers for the still-stubbed commands land
alongside their implementations in later steps.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import typer
from rich.console import Console

console = Console()


def find_repo_root(start: Path | None = None) -> Path:
    """Walk upward from `start` (default: cwd) until we hit the workspace root.

    The workspace root is the directory containing a `pyproject.toml` with a
    `[tool.uv.workspace]` table. Falls back to the start directory and raises
    a friendly typer.Exit if nothing is found within 12 levels.
    """
    cur = (start or Path.cwd()).resolve()
    for _ in range(12):
        candidate = cur / "pyproject.toml"
        if candidate.exists():
            try:
                text = candidate.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                text = ""
            if "[tool.uv.workspace]" in text:
                return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    console.print(
        "[red]Could not locate Agents Workshop repo root.[/red] "
        "Run from inside the repository (any subdirectory works)."
    )
    raise typer.Exit(2)


def stub(group: str, command: str, lands_in: str) -> None:
    """Print a friendly 'not yet implemented' message and exit cleanly."""
    console.print(
        f"[yellow]Stub:[/yellow] [bold]workshop {group} {command}[/bold] "
        f"is not implemented yet.\nLands in [cyan]{lands_in}[/cyan]."
    )
    raise typer.Exit(0)


def run_subprocess(
    cmd: list[str],
    *,
    cwd: Path,
    description: str,
    env: dict[str, str] | None = None,
) -> int:
    """Run `cmd` in `cwd`, streaming output. Returns exit code."""
    console.print(f"[dim]$ {' '.join(cmd)}  ({description})[/dim]")
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    result = subprocess.run(cmd, cwd=str(cwd), env=full_env, check=False)
    return result.returncode
