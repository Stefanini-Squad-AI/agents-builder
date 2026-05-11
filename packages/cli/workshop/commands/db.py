"""`workshop db ...` — database lifecycle.

In Step 0.6 we shell out to Alembic via `uv run alembic ...` from
`packages/core`. This keeps the CLI itself free of SQLAlchemy imports (the
heavyweight DB layer lives in workshop-core) and lets the user run the
migrations the same way Alembic recommends.

`workshop db seed` is a stub until Step 0.7 (tech catalog) + 0.8 (reference
PoCs) land.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from workshop._common import find_repo_root, run_subprocess

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")
console = Console()


def _core_dir() -> Path:
    return find_repo_root() / "packages" / "core"


@app.command()
def migrate() -> None:
    """Apply all pending Alembic migrations (`alembic upgrade head`)."""
    rc = run_subprocess(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=_core_dir(),
        description="alembic upgrade head",
    )
    raise typer.Exit(rc)


@app.command()
def downgrade(
    revision: str = typer.Argument(
        "-1",
        help="Target revision (default: '-1' = previous; pass 'base' to revert all).",
    ),
) -> None:
    """Revert migrations down to a target revision."""
    rc = run_subprocess(
        ["uv", "run", "alembic", "downgrade", revision],
        cwd=_core_dir(),
        description=f"alembic downgrade {revision}",
    )
    raise typer.Exit(rc)


@app.command()
def revision(
    message: str = typer.Option(..., "--message", "-m", help="Migration description."),
    autogenerate: bool = typer.Option(
        True,
        "--autogenerate/--manual",
        help="Generate the migration by diffing the ORM (default) or write an empty one.",
    ),
) -> None:
    """Create a new Alembic migration revision."""
    cmd = ["uv", "run", "alembic", "revision"]
    if autogenerate:
        cmd.append("--autogenerate")
    cmd.extend(["-m", message])
    rc = run_subprocess(
        cmd,
        cwd=_core_dir(),
        description=f"alembic revision {'--autogenerate ' if autogenerate else ''}-m '{message}'",
    )
    raise typer.Exit(rc)


@app.command()
def current() -> None:
    """Show the current revision applied to the database."""
    rc = run_subprocess(
        ["uv", "run", "alembic", "current"],
        cwd=_core_dir(),
        description="alembic current",
    )
    raise typer.Exit(rc)


@app.command()
def history() -> None:
    """Show the migration history."""
    rc = run_subprocess(
        ["uv", "run", "alembic", "history", "--verbose"],
        cwd=_core_dir(),
        description="alembic history",
    )
    raise typer.Exit(rc)


@app.command()
def seed() -> None:
    """Load the tech catalog + three reference PoCs into the database.

    Idempotent: re-running inserts only missing rows. Existing reference
    projects are left untouched (drop them manually to force a re-seed).
    """
    # Imports are deferred so that `workshop --help` does not pay the cost
    # of loading SQLAlchemy + every ORM module just to print help text.
    from app.db import session_scope
    from app.seed.seeder import seed_reference_pocs, seed_tech_catalog

    with session_scope() as session:
        tech_report = seed_tech_catalog(session)
    console.print(
        f"[green]Tech catalog:[/green] "
        f"inserted {tech_report['dimensions_inserted']} dimensions, "
        f"{tech_report['items_inserted']} items"
    )

    with session_scope() as session:
        poc_report = seed_reference_pocs(session)
    for slug, counts in poc_report.items():
        if counts.get("already_present"):
            console.print(f"[dim]{slug}: already present (skipped)[/dim]")
        else:
            console.print(
                f"[green]{slug}:[/green] "
                f"{counts['skills']} skills, "
                f"{counts['phases']} phases, "
                f"{counts['cards']} cards, "
                f"{counts['qa_answers']} qa, "
                f"{counts['tech_choices']} tech"
            )
    console.print("[green]Seed complete.[/green]")
