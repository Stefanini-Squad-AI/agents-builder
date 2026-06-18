"""`workshop export ...` — write the .agents/ contract folder."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

# Import the export system  
try:
    from app.services import ExportService
    from app.services.export_service import ValidationError
    EXPORT_SERVICE_AVAILABLE = True
except ImportError:
    EXPORT_SERVICE_AVAILABLE = False

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
    validate: bool = typer.Option(
        True, "--validate/--no-validate", help="Run validation before export."
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Treat validation warnings as errors."
    ),
    force: bool = typer.Option(
        False, "--force", help="Force export even if validation fails."
    ),
) -> None:
    """Export the .agents/ folder (filesystem, zip, or jira_csv)."""
    if ctx.invoked_subcommand is None:
        
        if not EXPORT_SERVICE_AVAILABLE:
            typer.echo("❌ Export system not available. Ensure core package is installed.", err=True)
            raise typer.Exit(1)
        
        try:
            # Set up default paths
            if target == "filesystem":
                if not path:
                    path = Path(f"./{project}-export")
                typer.echo(f"🚀 Exporting project '{project}' to filesystem at: {path}")
            elif target == "zip":
                if not out:
                    out = Path(f"./{project}.zip")
                typer.echo(f"🚀 Exporting project '{project}' to ZIP file: {out}")
            elif target == "jira_csv":
                typer.echo("❌ Jira CSV export is planned for P5+ release", err=True)
                raise typer.Exit(1)
            else:
                typer.echo(f"❌ Unsupported export target: {target}", err=True)
                raise typer.Exit(1)
            
            # Prepare export configuration
            export_service = ExportService()
            
            # Perform export
            manifest = export_service.export_project(
                project_slug=project,
                export_kind=target,
                target_path=path,
                output_file=out,
                validate_before_export=validate and not force,
                validation_strict=strict
            )
            
            # Display results
            typer.echo("✅ Export completed successfully!")
            typer.echo(f"   📁 Files exported: {manifest.total_files}")
            typer.echo(f"   📊 Total size: {_format_bytes(manifest.total_size_bytes)}")
            typer.echo(f"   ⏱️  Duration: {manifest.duration_seconds:.2f}s")
            
            if target == "filesystem":
                typer.echo(f"   📂 Location: {path}/.agents/")
                typer.echo(f"   🌟 Open README.md in '{path}/.agents/' to get started")
            elif target == "zip":
                typer.echo(f"   📦 ZIP file: {out}")
                typer.echo(f"   🌟 Extract and open .agents/README.md to get started")
        
        except ValidationError as e:
            typer.echo(f"❌ Export validation failed:", err=True)
            typer.echo(f"   Project: {e.project_slug}", err=True)
            typer.echo(f"   Issues: {len(e.validation_issues)}", err=True)
            
            # Show first few validation issues
            for i, issue in enumerate(e.validation_issues[:5]):
                severity_icon = "🔴" if issue.severity.value == "error" else "🟡"
                typer.echo(f"   {severity_icon} [{issue.code}] {issue.message}", err=True)
            
            if len(e.validation_issues) > 5:
                remaining = len(e.validation_issues) - 5
                typer.echo(f"   ... and {remaining} more issues", err=True)
            
            typer.echo(f"\n💡 Fix validation issues or use --force to export anyway", err=True)
            typer.echo(f"💡 Run 'workshop validate --project {project}' for detailed validation report", err=True)
            raise typer.Exit(1)
        
        except Exception as e:
            typer.echo(f"❌ Export failed: {str(e)}", err=True)
            if "--debug" in sys.argv:
                import traceback
                typer.echo(traceback.format_exc(), err=True)
            raise typer.Exit(1)


def _format_bytes(bytes_count: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} TB"
