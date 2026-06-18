"""`workshop llm-runs ...` — LLM audit log."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import typer
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")
console = Console()


def show_error(message: str, details: str | None = None) -> None:
    """Display error message."""
    console.print(f"❌ {message}", style="bold red")
    if details:
        console.print(f"   {details}", style="dim red")


@app.callback(invoke_without_command=True)
def list_runs(
    ctx: typer.Context,
    project: str = typer.Option(..., "--project", "-p"),
    kind: str | None = typer.Option(
        None, "--kind", help="Filter by run kind (propose_skill_set, draft_card, ...)."
    ),
    last: int = typer.Option(20, "--last", "-n", help="Show last N runs."),
) -> None:
    """List recent LLM calls for a project."""
    if ctx.invoked_subcommand is None:
        
        # Import LLM audit functionality
        try:
            from sqlalchemy import select, desc
            from app.domain.llm import LlmRun
            from app.domain.projects import Project
            import app.db
        except ImportError:
            show_error("LLM audit system not available. Ensure core package is installed.")
            raise typer.Exit(1)
        
        console.print(f"🤖 [bold]LLM Runs for project '{project}'[/bold]")
        
        try:
            with app.db.session_scope() as session:
                # Get project
                project_record = session.execute(
                    select(Project).where(Project.slug == project)
                ).scalar_one_or_none()
                
                if not project_record:
                    show_error(f"Project '{project}' not found")
                    raise typer.Exit(1)
                
                # Build query
                query = (
                    select(LlmRun)
                    .where(LlmRun.project_id == project_record.id)
                    .order_by(desc(LlmRun.created_at))
                    .limit(last)
                )
                
                if kind:
                    query = query.where(LlmRun.kind == kind)
                
                runs = session.execute(query).scalars().all()
                
                if not runs:
                    console.print(f"📭 No LLM runs found for project '{project}'")
                    if kind:
                        console.print(f"   (filtered by kind: {kind})")
                    return
                
                # Display runs table
                table = Table(title=f"LLM Runs ({len(runs)} shown)")
                table.add_column("ID", style="dim")
                table.add_column("Kind", style="cyan")
                table.add_column("Provider", style="blue")
                table.add_column("Model", style="green")
                table.add_column("Status", style="white")
                table.add_column("Tokens", justify="right", style="yellow")
                table.add_column("Cost", justify="right", style="magenta")
                table.add_column("Duration", justify="right", style="dim")
                table.add_column("Created", style="dim")
                
                for run in runs:
                    # Format duration
                    duration = ""
                    if run.created_at and run.updated_at:
                        delta = run.updated_at - run.created_at
                        duration = f"{delta.total_seconds():.1f}s"
                    
                    # Format cost
                    cost_display = f"${run.cost:.4f}" if run.cost else "-"
                    
                    # Format tokens
                    tokens_display = str(run.total_tokens) if run.total_tokens else "-"
                    
                    # Status with emoji
                    status_display = {
                        "success": "✅ Success",
                        "parse_error": "⚠️ Parse Error", 
                        "provider_error": "❌ Provider Error",
                        "in_progress": "🔄 Running"
                    }.get(run.status, run.status)
                    
                    # Created time
                    created_display = run.created_at.strftime("%H:%M:%S") if run.created_at else ""
                    
                    table.add_row(
                        str(run.id)[:8] + "...",  # Short ID
                        run.kind or "",
                        run.provider or "",
                        run.model or "",
                        status_display,
                        tokens_display,
                        cost_display,
                        duration,
                        created_display
                    )
                
                console.print(table)
                
                # Summary statistics
                console.print()
                total_cost = sum(run.cost or 0 for run in runs)
                total_tokens = sum(run.total_tokens or 0 for run in runs)
                successful_runs = len([r for r in runs if r.status == "success"])
                
                console.print(f"📊 [bold]Summary:[/bold] {successful_runs}/{len(runs)} successful")
                console.print(f"💰 [bold]Total cost:[/bold] ${total_cost:.4f}")
                console.print(f"🔢 [bold]Total tokens:[/bold] {total_tokens:,}")
                
                console.print()
                console.print("💡 [dim]Use 'workshop llm-runs show <id>' for detailed view[/dim]")
        
        except Exception as e:
            show_error("Failed to list LLM runs", str(e))
            raise typer.Exit(1)


@app.command(name="show")
def show(
    run_id: str = typer.Argument(..., help="UUID of the LLM run."),
) -> None:
    """Show the full prompt, response, and reasoning (if any) for a run."""
    
    # Import LLM audit functionality
    try:
        from sqlalchemy import select
        from app.domain.llm import LlmRun
        import app.db
        import uuid
    except ImportError:
        show_error("LLM audit system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    console.print(f"🔍 [bold]LLM Run Details[/bold]")
    
    try:
        # Parse UUID
        try:
            run_uuid = uuid.UUID(run_id)
        except ValueError:
            show_error("Invalid run ID format. Must be a UUID.")
            raise typer.Exit(1)
        
        with app.db.session_scope() as session:
            # Get LLM run
            run = session.execute(
                select(LlmRun).where(LlmRun.id == run_uuid)
            ).scalar_one_or_none()
            
            if not run:
                show_error(f"LLM run '{run_id}' not found")
                raise typer.Exit(1)
            
            # Display run metadata
            console.print(f"🆔 [bold]ID:[/bold] {run.id}")
            console.print(f"🏷️  [bold]Kind:[/bold] {run.kind or 'Unknown'}")
            console.print(f"🤖 [bold]Provider:[/bold] {run.provider or 'Unknown'}")
            console.print(f"🧠 [bold]Model:[/bold] {run.model or 'Unknown'}")
            console.print(f"📊 [bold]Status:[/bold] {run.status}")
            
            if run.total_tokens:
                console.print(f"🔢 [bold]Tokens:[/bold] {run.total_tokens:,}")
            
            if run.cost:
                console.print(f"💰 [bold]Cost:[/bold] ${run.cost:.6f}")
            
            if run.created_at:
                created_str = run.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                console.print(f"🕐 [bold]Created:[/bold] {created_str}")
            
            if run.error_message:
                console.print(f"❌ [bold]Error:[/bold] {run.error_message}")
            
            console.print()
            
            # Display prompt if available
            if run.prompt_json:
                console.print("📝 [bold]Prompt:[/bold]")
                try:
                    prompt_data = json.loads(run.prompt_json) if isinstance(run.prompt_json, str) else run.prompt_json
                    
                    # Show system prompt
                    if "system" in prompt_data:
                        console.print("🔧 [bold]System Prompt:[/bold]")
                        console.print(Syntax(prompt_data["system"], "markdown", theme="monokai"))
                        console.print()
                    
                    # Show user messages
                    if "messages" in prompt_data:
                        console.print("💬 [bold]Messages:[/bold]")
                        for i, msg in enumerate(prompt_data["messages"]):
                            role = msg.get("role", "unknown")
                            content = msg.get("content", "")
                            
                            # Truncate very long content
                            if len(content) > 1000:
                                content = content[:1000] + "\n[... truncated ...]"
                            
                            console.print(f"[bold]{role.upper()}:[/bold]")
                            console.print(Syntax(content, "markdown", theme="monokai"))
                            console.print()
                    
                except (json.JSONDecodeError, TypeError) as e:
                    console.print(f"[dim red]Error parsing prompt JSON: {e}[/dim red]")
                    console.print(f"[dim]Raw prompt data: {str(run.prompt_json)[:200]}...[/dim]")
                
                console.print()
            
            # Display response if available
            if run.response_json:
                console.print("📤 [bold]Response:[/bold]")
                try:
                    response_data = json.loads(run.response_json) if isinstance(run.response_json, str) else run.response_json
                    
                    # Pretty print JSON response
                    response_str = json.dumps(response_data, indent=2)
                    
                    # Truncate if very long
                    if len(response_str) > 2000:
                        lines = response_str.split('\n')
                        truncated_lines = lines[:50]  # First 50 lines
                        truncated_str = '\n'.join(truncated_lines)
                        console.print(Syntax(truncated_str, "json", theme="monokai"))
                        console.print(f"[dim]... and {len(lines) - 50} more lines[/dim]")
                    else:
                        console.print(Syntax(response_str, "json", theme="monokai"))
                    
                except (json.JSONDecodeError, TypeError) as e:
                    console.print(f"[dim red]Error parsing response JSON: {e}[/dim red]")
                    console.print(f"[dim]Raw response data: {str(run.response_json)[:200]}...[/dim]")
            
            # Show reasoning if available (from thinking traces)
            if hasattr(run, 'reasoning_trace') and run.reasoning_trace:
                console.print()
                console.print("🧠 [bold]AI Reasoning:[/bold]")
                console.print(run.reasoning_trace)
    
    except Exception as e:
        show_error("Failed to show LLM run details", str(e))
        raise typer.Exit(1)
