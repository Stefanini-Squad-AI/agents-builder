"""`workshop backlog ...` — phase-organized backlog (Step 0.6: stubs)."""

from __future__ import annotations

import typer

from workshop._common import stub

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@app.command(name="propose")
def propose(project: str = typer.Option(..., "--project", "-p")) -> None:
    """Run the `ProposeBacklog` LLM prompt — proposes phases + cards + deps."""
    
    from rich.console import Console
    console = Console()
    
    # Import LLM functionality
    try:
        from workshop._llm_utils import (
            check_project_readiness, 
            create_llm_service_for_project,
            load_project_context,
            run_llm_prompt,
            show_llm_error,
            show_llm_success
        )
        from app.prompts import ProposeBacklogPrompt
        import app.db
    except ImportError:
        console.print("❌ LLM system not available. Ensure core package is installed.", style="bold red")
        raise typer.Exit(1)
    
    console.print(f"📊 [bold]Proposing backlog for project '{project}'[/bold]")
    
    # Check project readiness
    if not check_project_readiness(project):
        raise typer.Exit(1)
    
    # Load project context
    context = load_project_context(project)
    if not context:
        raise typer.Exit(1)
    
    # Create LLM service
    llm_service = create_llm_service_for_project(project)
    if not llm_service:
        raise typer.Exit(1)
    
    try:
        # Create prompt
        prompt = ProposeBacklogPrompt.create(context)
        
        # Run LLM
        result = run_llm_prompt(
            llm_service, 
            prompt, 
            "Backlog Generation"
        )
        
        if not result or not result.parsed:
            show_llm_error("Failed to generate backlog")
            raise typer.Exit(1)
        
        # Save phases and cards to database
        with app.db.session_scope() as session:
            # Get project for backlog creation
            from sqlalchemy import select
            from app.domain.projects import Project
            from app.domain.backlog import Phase, Card
            
            project_record = session.execute(
                select(Project).where(Project.slug == project)
            ).scalar_one_or_none()
            
            if not project_record:
                show_llm_error(f"Project '{project}' not found")
                raise typer.Exit(1)
            
            # Check if backlog already exists
            existing_phases = session.execute(
                select(Phase.id).where(Phase.project_id == project_record.id)
            ).scalars().all()
            
            if existing_phases:
                console.print(f"⚠️  Project '{project}' already has {len(existing_phases)} phases.")
                from rich.prompt import Confirm
                if not Confirm.ask("Replace existing backlog?"):
                    console.print("Backlog generation cancelled.")
                    raise typer.Exit(0)
                
                # Delete existing phases and cards (cascading)
                from app.domain.backlog import Phase
                phases_to_delete = session.execute(
                    select(Phase).where(Phase.project_id == project_record.id)
                ).scalars().all()
                
                for phase in phases_to_delete:
                    session.delete(phase)
            
            # Create phases and cards
            total_cards = 0
            phase_records = []
            
            for order_no, proposed_phase in enumerate(result.parsed.phases):
                # Create phase
                phase = Phase(
                    project_id=project_record.id,
                    code=proposed_phase.code,
                    name=proposed_phase.name,
                    description=proposed_phase.description,
                    order_no=order_no + 1
                )
                session.add(phase)
                session.flush()  # Get the ID
                
                phase_records.append((phase, proposed_phase))
                
                # Create cards for this phase
                for card_order, proposed_card in enumerate(proposed_phase.cards):
                    card = Card(
                        phase_id=phase.id,
                        code=proposed_card.code,
                        name=proposed_card.name,
                        description=proposed_card.description,
                        status="todo",
                        priority=proposed_card.priority or "medium",
                        estimated_hours=proposed_card.estimated_hours,
                        has_human_gate=bool(proposed_card.requires_human_gate),
                        order_no=card_order + 1
                    )
                    session.add(card)
                    total_cards += 1
            
            session.commit()
        
        # Show results
        show_llm_success(f"Generated backlog for project '{project}'")
        
        console.print("📊 [bold]Generated Backlog:[/bold]")
        
        from rich.table import Table
        
        # Summary table
        summary_table = Table(title="Backlog Summary")
        summary_table.add_column("Phase", style="cyan")
        summary_table.add_column("Name", style="white")  
        summary_table.add_column("Cards", justify="right", style="green")
        summary_table.add_column("Est. Hours", justify="right", style="blue")
        
        for phase_record, proposed_phase in phase_records:
            total_phase_hours = sum(
                card.estimated_hours or 0 
                for card in proposed_phase.cards
            )
            
            summary_table.add_row(
                proposed_phase.code,
                proposed_phase.name,
                str(len(proposed_phase.cards)),
                str(total_phase_hours) if total_phase_hours > 0 else "-"
            )
        
        console.print(summary_table)
        console.print()
        console.print(f"📋 [bold]Total: {len(result.parsed.phases)} phases, {total_cards} cards[/bold]")
        
        # Show phase details
        for proposed_phase in result.parsed.phases:
            console.print(f"\n🏷️  [bold]{proposed_phase.code}: {proposed_phase.name}[/bold]")
            console.print(f"   {proposed_phase.description}")
            
            for card in proposed_phase.cards[:3]:  # Show first 3 cards
                console.print(f"   • {card.code}: {card.name}")
            
            if len(proposed_phase.cards) > 3:
                console.print(f"   [dim]... and {len(proposed_phase.cards) - 3} more cards[/dim]")
        
        console.print()
        console.print("💡 [dim]Use 'workshop card list' to see all cards, or 'workshop card draft <code>' to generate content[/dim]")
        
    except Exception as e:
        show_llm_error("Backlog generation failed", str(e))
        if "--debug" in sys.argv:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)
