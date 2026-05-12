"""`workshop artifact ...` — upload files and track async extraction."""

from __future__ import annotations

import time
from pathlib import Path

import typer
from rich.table import Table

from workshop._common import api_get, api_post, console

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")

_POLL_INTERVAL = 1.5  # seconds between status polls
_POLL_TIMEOUT = 120   # give up after 2 minutes


@app.command(name="upload")
def upload(
    path: Path = typer.Argument(..., exists=True, readable=True, help="File to upload"),
    kind: str = typer.Option("doc", "--kind", "-k", help="doc / code / spec / glossary"),
    project: str = typer.Option(..., "--project", "-p", help="Project UUID"),
    no_wait: bool = typer.Option(
        False, "--no-wait", help="Return immediately without polling for completion."
    ),
) -> None:
    """Upload an artifact and (by default) wait for extraction to finish."""
    with path.open("rb") as fh:
        resp = api_post(
            f"/api/projects/{project}/artifacts",
            files={"file": (path.name, fh, "application/octet-stream")},
            data={"kind": kind},
            timeout=60.0,
        )
    artifact = resp.json()
    artifact_id: str = artifact["id"]
    console.print(
        f"[green]Uploaded[/green] {path.name} "
        f"([dim]{artifact['size_bytes']} bytes[/dim]) → id=[cyan]{artifact_id}[/cyan]"
    )

    if no_wait:
        console.print(f"[dim]Status:[/dim] {artifact['extraction_status']}")
        return

    # Poll until terminal state
    deadline = time.monotonic() + _POLL_TIMEOUT
    last_status = artifact["extraction_status"]
    while last_status not in ("extracted", "failed"):
        if time.monotonic() > deadline:
            console.print("[yellow]Timed out waiting for extraction.[/yellow]")
            raise typer.Exit(1)
        time.sleep(_POLL_INTERVAL)
        poll = api_get(f"/api/artifacts/{artifact_id}")
        last_status = poll.json()["extraction_status"]
        console.print(f"  [dim]status:[/dim] {last_status}", end="\r")

    console.print()  # newline after \r overwrite
    if last_status == "extracted":
        excerpt = poll.json().get("content_md_excerpt") or ""
        truncated = poll.json().get("content_md_truncated", False)
        preview = excerpt[:300].strip()
        if preview:
            console.print("[dim]--- excerpt ---[/dim]")
            console.print(preview)
            if truncated:
                console.print("[dim](content truncated)[/dim]")
        console.print("[green]Extraction complete.[/green]")
    else:
        console.print("[red]Extraction failed.[/red]")
        raise typer.Exit(1)


@app.command(name="list")
def list_artifacts(
    project: str = typer.Option(..., "--project", "-p", help="Project UUID"),
) -> None:
    """List artifacts for a project and their extraction status."""
    rows = api_get(f"/api/projects/{project}/artifacts").json()
    if not rows:
        console.print("[dim]No artifacts for this project.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan", no_wrap=True, max_width=36)
    table.add_column("Filename")
    table.add_column("Kind")
    table.add_column("Status")
    table.add_column("Size")
    for r in rows:
        table.add_row(
            r["id"],
            r["filename"],
            r["kind"],
            r["extraction_status"],
            str(r["size_bytes"]),
        )
    console.print(table)


@app.command(name="retry")
def retry(
    artifact_id: str = typer.Argument(..., help="Artifact UUID"),
) -> None:
    """Re-enqueue extraction for a failed artifact."""
    resp = api_post(f"/api/artifacts/{artifact_id}/retry")
    a = resp.json()
    console.print(
        f"[green]Queued[/green] {a['filename']} (id={a['id']}) → status: {a['extraction_status']}"
    )
