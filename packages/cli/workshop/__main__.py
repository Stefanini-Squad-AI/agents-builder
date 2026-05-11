"""Typer entry point for the `workshop` CLI.

Subcommand groups are declared in `workshop.commands.*` and stitched into a
single Typer app here. In Step 0.6 only `workshop init` and `workshop db
migrate` are wired through to real behavior; the rest are explicit stubs that
print a friendly "lands in Step X.Y" message so users know what's planned.

Run `workshop --help` to see the full surface.
"""

from __future__ import annotations

import typer
from rich.console import Console

from workshop import __version__
from workshop.commands import (
    artifact,
    backlog,
    card,
    dag,
    db,
    export,
    llm_runs,
    project,
    qa,
    skill,
    tech,
)
from workshop.commands import (
    init as init_cmd,
)
from workshop.commands import (
    validate as validate_cmd,
)

console = Console()

app = typer.Typer(
    name="workshop",
    help=(
        "Agents Workshop CLI — produce .agents/ skill libraries and Jira card "
        "backlogs from a programming objective. See `workshop <group> --help` "
        "for per-group commands."
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
)


# --- Top-level commands --------------------------------------------------

app.command(name="init", help="Initialize workspace config in the current directory.")(
    init_cmd.init
)
app.command(name="validate", help="Run deterministic validators on a project.")(
    validate_cmd.validate
)
app.command(name="dag", help="Print the Mermaid DAG for a project to stdout.")(dag.dag)


# --- Command groups ------------------------------------------------------

app.add_typer(db.app, name="db", help="Database lifecycle: migrate, downgrade, seed.")
app.add_typer(project.app, name="project", help="Project lifecycle: new, list, show, edit.")
app.add_typer(qa.app, name="qa", help="Discovery Q&A wizard (7 questions).")
app.add_typer(tech.app, name="tech", help="Tech panorama: pick / add / suggest / TBD.")
app.add_typer(artifact.app, name="artifact", help="Project artifacts: upload, list, retry.")
app.add_typer(skill.app, name="skill", help="Skill library: propose, draft, list, edit.")
app.add_typer(backlog.app, name="backlog", help="Backlog: propose phases + cards.")
app.add_typer(card.app, name="card", help="Cards: list, draft, show, edit.")
app.add_typer(export.app, name="export", help="Export the .agents/ contract folder.")
app.add_typer(llm_runs.app, name="llm-runs", help="Inspect LLM call audit log.")


# --- Meta callbacks ------------------------------------------------------


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"workshop {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Print version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Root callback — wires --version as an eager flag."""


if __name__ == "__main__":
    app()
