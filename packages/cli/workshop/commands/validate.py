"""`workshop validate` — run all deterministic validators."""

from __future__ import annotations

import sys

import typer

# Import the validation system
try:
    from app.validators import ValidationSeverity, format_validation_report, validate_project
    VALIDATORS_AVAILABLE = True
except ImportError:
    VALIDATORS_AVAILABLE = False


def validate(
    project: str = typer.Option(..., "--project", "-p"),
    strict: bool = typer.Option(
        False, "--strict", help="Treat warnings as errors (non-zero exit)."
    ),
    compact: bool = typer.Option(
        False, "--compact", help="Use compact single-line output format."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output results in JSON format."
    ),
) -> None:
    """Run DAG / refs / frontmatter / paths / Q&A validators."""
    
    if not VALIDATORS_AVAILABLE:
        typer.echo("❌ Validation system not available. Ensure core package is installed.", err=True)
        raise typer.Exit(1)
    
    try:
        # Run validation
        typer.echo(f"🔍 Running validation on project '{project}'...")
        issues = validate_project(project, strict=strict)
        
        # Handle JSON output
        if json_output:
            import json
            json_data = {
                "project_slug": project,
                "strict_mode": strict,
                "issues": [issue.model_dump() for issue in issues],
                "summary": {
                    "error_count": sum(1 for i in issues if i.severity == ValidationSeverity.ERROR),
                    "warning_count": sum(1 for i in issues if i.severity == ValidationSeverity.WARNING),
                    "total_count": len(issues)
                }
            }
            typer.echo(json.dumps(json_data, indent=2))
        else:
            # Format and display report
            report = format_validation_report(issues, compact=compact)
            typer.echo(report)
        
        # Determine exit code
        error_count = sum(1 for issue in issues if issue.severity == ValidationSeverity.ERROR)
        warning_count = sum(1 for issue in issues if issue.severity == ValidationSeverity.WARNING)
        
        if error_count > 0:
            typer.echo(f"\n❌ Validation failed with {error_count} errors", err=True)
            raise typer.Exit(1)
        elif warning_count > 0:
            typer.echo(f"\n⚠️  Validation completed with {warning_count} warnings")
            if strict:
                typer.echo("(Treated as errors in strict mode)", err=True)
                raise typer.Exit(1)
        else:
            typer.echo("\n✅ Validation passed - no issues found!")
    
    except Exception as e:
        typer.echo(f"❌ Validation failed with error: {str(e)}", err=True)
        if "--debug" in sys.argv:
            import traceback
            typer.echo(traceback.format_exc(), err=True)
        raise typer.Exit(1)
