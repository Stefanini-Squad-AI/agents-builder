"""Shared CLI helpers: repo discovery, project resolution, subprocess wrappers,
and a lightweight HTTP client that talks to the running API server.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import httpx
import typer
from rich.console import Console

console = Console()

# Default API base URL — overridden by the NEXT_PUBLIC_API_URL env var or
# by calling `api_base()` with an explicit value from --api-url flags.
_DEFAULT_API_BASE = "http://localhost:8000"


def api_base() -> str:
    """Return the API server base URL, respecting NEXT_PUBLIC_API_URL if set."""
    return os.environ.get("NEXT_PUBLIC_API_URL", _DEFAULT_API_BASE).rstrip("/")


def api_get(path: str, *, timeout: float = 10.0) -> httpx.Response:
    """GET `path` against the running API. Raises on non-2xx."""
    url = f"{api_base()}{path}"
    try:
        r = httpx.get(url, timeout=timeout)
    except httpx.ConnectError:
        console.print(
            f"[red]Cannot reach API server at {api_base()}.[/red] "
            "Is `uvicorn app.main:app` running?"
        )
        raise typer.Exit(1) from None
    if not r.is_success:
        console.print(f"[red]API error {r.status_code}:[/red] {r.text}")
        raise typer.Exit(1)
    return r


def api_post(
    path: str,
    *,
    json: object | None = None,
    files: httpx._types.RequestFiles | None = None,
    data: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> httpx.Response:
    """POST `path` against the running API. Raises on non-2xx."""
    url = f"{api_base()}{path}"
    try:
        r = httpx.post(url, json=json, files=files, data=data, timeout=timeout)
    except httpx.ConnectError:
        console.print(
            f"[red]Cannot reach API server at {api_base()}.[/red] "
            "Is `uvicorn app.main:app` running?"
        )
        raise typer.Exit(1) from None
    if not r.is_success:
        console.print(f"[red]API error {r.status_code}:[/red] {r.text}")
        raise typer.Exit(1)
    return r


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
