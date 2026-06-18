"""`workshop card ...` — card CRUD."""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.table import Table

# Import the card system
try:
    from app.services.card_service import CardService
    CARD_SERVICE_AVAILABLE = True
except ImportError:
    CARD_SERVICE_AVAILABLE = False

from workshop._common import stub

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")
console = Console()


def show_error(message: str, details: str | None = None) -> None:
    """Display error message."""
    console.print(f"❌ {message}", style="bold red")
    if details:
        console.print(f"   {details}", style="dim red")


def show_success(message: str) -> None:
    """Display success message."""
    console.print(f"✅ {message}", style="bold green")


@app.command(name="list")
def list_cards(
    project: str = typer.Option(..., "--project", "-p"),
    phase: str | None = typer.Option(None, "--phase", help="Filter by phase code."),
) -> None:
    """List cards (optionally filtered by phase)."""
    
    if not CARD_SERVICE_AVAILABLE:
        show_error("Card system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        service = CardService()
        cards = service.list_project_cards(project)
        
        if not cards:
            console.print(f"📋 No cards found in project '{project}'")
            console.print("💡 Generate cards with: [bold]workshop card propose --project " + project + "[/bold]")
            return
        
        # Filter by phase if specified
        if phase:
            cards = [card for card in cards if card.phase_code.lower() == phase.lower()]
            if not cards:
                console.print(f"📋 No cards found in phase '{phase}' of project '{project}'")
                return
        
        # Group by phase for display
        phases = {}
        for card in cards:
            phase_key = f"{card.phase_code}"
            if phase_key not in phases:
                phases[phase_key] = {
                    "name": f"{card.phase_code}: {card.phase_name}",
                    "cards": []
                }
            phases[phase_key]["cards"].append(card)
        
        # Display cards by phase
        for phase_key, phase_data in phases.items():
            console.print(f"\n📊 [bold]{phase_data['name']}[/bold]")
            
            table = Table()
            table.add_column("Code", style="cyan")
            table.add_column("Name", style="white")
            table.add_column("Status", style="blue")
            table.add_column("Human Gate", justify="center")
            table.add_column("Hours", justify="right", style="green")
            
            for card in phase_data["cards"]:
                human_gate_indicator = "🚪" if card.has_human_gate else ""
                hours = str(card.estimated_hours) if card.estimated_hours else "-"
                
                table.add_row(
                    card.code,
                    card.name,
                    card.status,
                    human_gate_indicator,
                    hours
                )
            
            console.print(table)
        
        # Show statistics
        stats = service.get_cards_statistics(project)
        console.print()
        console.print(f"📊 [bold]Summary:[/bold] {stats['total_cards']} cards, {stats['completion_percentage']:.0f}% completed")
        
        if stats['estimated_total_hours'] > 0:
            console.print(f"⏱️  [bold]Estimated:[/bold] {stats['estimated_total_hours']} hours")
        
        if stats['with_human_gates'] > 0:
            console.print(f"🚪 [bold]Human gates:[/bold] {stats['with_human_gates']} cards")
        
    except Exception as e:
        show_error("Failed to list cards", str(e))
        raise typer.Exit(1)


@app.command(name="draft")
def draft(
    card_code: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Run the `DraftCard` LLM prompt for one card."""
    
    # Import LLM functionality
    try:
        from workshop._llm_utils import (
            create_llm_service_for_project,
            load_project_context,
            run_llm_prompt,
            show_llm_error,
            show_llm_success
        )
        from app.prompts import DraftCardPrompt
        from app.services import CardService
        import app.db
    except ImportError:
        show_error("LLM system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    console.print(f"📋 [bold]Drafting content for card '{card_code}' in project '{project}'[/bold]")
    
    # Get the card
    card_service = CardService()
    card = card_service.get_card(project, card_code)
    
    if not card:
        show_error(f"Card '{card_code}' not found in project '{project}'")
        console.print("💡 List available cards: [bold]workshop card list --project " + project + "[/bold]")
        raise typer.Exit(1)
    
    # Check if card already has content
    has_content = any([
        card.context_md and card.context_md.strip(),
        card.task_md and card.task_md.strip(),
        card.outputs_md and card.outputs_md.strip(),
        card.acceptance_criteria_md and card.acceptance_criteria_md.strip(),
        card.human_gate_checklist_md and card.human_gate_checklist_md.strip()
    ])
    
    if has_content and not force:
        console.print(f"⚠️  Card '{card_code}' already has content. Use --force to overwrite.")
        console.print("💡 Current sections with content:")
        if card.context_md and card.context_md.strip():
            console.print("   • Context")
        if card.task_md and card.task_md.strip():
            console.print("   • Tasks")
        if card.outputs_md and card.outputs_md.strip():
            console.print("   • Outputs")
        if card.acceptance_criteria_md and card.acceptance_criteria_md.strip():
            console.print("   • Acceptance Criteria")
        if card.human_gate_checklist_md and card.human_gate_checklist_md.strip():
            console.print("   • Human Gate")
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
        # Create prompt with card details
        prompt = DraftCardPrompt.create(context, card_code)
        
        # Run LLM
        result = run_llm_prompt(
            llm_service, 
            prompt, 
            f"Card Content Generation for '{card.name}'"
        )
        
        if not result or not result.parsed:
            show_llm_error("Failed to generate card content")
            raise typer.Exit(1)
        
        # Update card with generated content
        drafted_card = result.parsed
        
        updated_card = card_service.update_card_content(
            project, 
            card_code,
            context_md=drafted_card.context,
            task_md=drafted_card.task,
            outputs_md=drafted_card.outputs,
            acceptance_criteria_md=drafted_card.acceptance_criteria,
            human_gate_checklist_md=drafted_card.human_gate_checklist if drafted_card.human_gate_checklist else None
        )
        
        if not updated_card:
            show_llm_error("Failed to save card content")
            raise typer.Exit(1)
        
        # Show results
        show_llm_success(f"Generated content for card '{card.name}'")
        
        console.print("📋 [bold]Generated Sections:[/bold]")
        
        sections_generated = []
        if drafted_card.context and drafted_card.context.strip():
            sections_generated.append("Context")
        if drafted_card.task and drafted_card.task.strip():
            sections_generated.append("Tasks")
        if drafted_card.outputs and drafted_card.outputs.strip():
            sections_generated.append("Outputs")
        if drafted_card.acceptance_criteria and drafted_card.acceptance_criteria.strip():
            sections_generated.append("Acceptance Criteria")
        if drafted_card.human_gate_checklist and drafted_card.human_gate_checklist.strip():
            sections_generated.append("Human Gate Checklist")
        
        for section in sections_generated:
            console.print(f"   ✅ {section}")
        
        # Show inputs if suggested
        if hasattr(drafted_card, 'inputs') and drafted_card.inputs:
            console.print()
            console.print(f"📎 [bold]Suggested {len(drafted_card.inputs)} inputs:[/bold]")
            for inp in drafted_card.inputs:
                console.print(f"   • {inp.kind}: {inp.path}")
        
        console.print()
        console.print("💡 [dim]Use 'workshop card show " + card_code + "' to view the complete card[/dim]")
        
    except Exception as e:
        show_llm_error("Card drafting failed", str(e))
        if "--debug" in sys.argv:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


@app.command(name="show")
def show(
    card_code: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Render the full card markdown to stdout."""
    
    if not CARD_SERVICE_AVAILABLE:
        show_error("Card system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    try:
        service = CardService()
        card = service.get_card(project, card_code)
        
        if not card:
            show_error(f"Card '{card_code}' not found in project '{project}'")
            console.print("💡 List available cards: [bold]workshop card list --project " + project + "[/bold]")
            raise typer.Exit(1)
        
        # Render and display card markdown
        card_markdown = service.render_card_markdown(card)
        console.print(card_markdown)
        
    except Exception as e:
        show_error("Failed to show card", str(e))
        raise typer.Exit(1)


@app.command(name="edit")
def edit(
    card_code: str = typer.Argument(...),
    project: str = typer.Option(..., "--project", "-p"),
    section: str | None = typer.Option(
        None,
        "--section",
        help="Edit one section only: context, task, outputs, ac, gate.",
    ),
) -> None:
    """Open $EDITOR on a card (full body or one section)."""
    
    if not CARD_SERVICE_AVAILABLE:
        show_error("Card system not available. Ensure core package is installed.")
        raise typer.Exit(1)
    
    if section:
        valid_sections = ["context", "task", "outputs", "ac", "gate"]
        if section not in valid_sections:
            show_error(f"Invalid section '{section}'. Choose from: {', '.join(valid_sections)}")
            raise typer.Exit(1)
    
    try:
        from workshop._utils import open_editor
        
        service = CardService()
        card = service.get_card(project, card_code)
        
        if not card:
            show_error(f"Card '{card_code}' not found in project '{project}'")
            raise typer.Exit(1)
        
        if section:
            console.print(f"📝 Editing {section} section for: {card.name}")
            
            # Get current content based on section
            if section == "context":
                current_content = card.context_md or "## Context\n\nDescribe the background and rationale for this card.\n"
                field_name = "context_md"
            elif section == "task":
                current_content = card.task_md or "## Tasks\n\n1. [ ] Define specific tasks to complete this card\n2. [ ] Add implementation steps\n3. [ ] List any deliverables\n"
                field_name = "task_md"
            elif section == "outputs":
                current_content = card.outputs_md or "## Outputs\n\nDescribe what will be produced by this card:\n\n- Files created/modified\n- Documentation updated\n- Features implemented\n"
                field_name = "outputs_md"
            elif section == "ac":
                current_content = card.acceptance_criteria_md or "## Acceptance Criteria\n\n- [ ] Criteria 1: Describe what success looks like\n- [ ] Criteria 2: Define measurable outcomes\n- [ ] Criteria 3: Specify quality standards\n"
                field_name = "acceptance_criteria_md"
            else:  # gate
                current_content = card.human_gate_checklist_md or "## Human Gate Checklist\n\n- [ ] Review requirement 1\n- [ ] Validate approach 2\n- [ ] Approve final output\n"
                field_name = "human_gate_checklist_md"
            
            try:
                # Open editor
                new_content = open_editor(
                    content=current_content,
                    file_extension=".md"
                )
                
                # Update card section
                update_kwargs = {field_name: new_content}
                updated_card = service.update_card_content(project, card_code, **update_kwargs)
                
                if updated_card:
                    show_success(f"Card '{card_code}' {section} section updated successfully!")
                else:
                    show_error("Failed to update card")
                    raise typer.Exit(1)
                    
            except RuntimeError as e:
                console.print(f"⚠️  Card editing cancelled: {e}", style="yellow")
        else:
            # Edit full card as rendered markdown (read-only view)
            console.print(f"📝 Viewing full card: {card.name}")
            console.print("💡 Use --section to edit specific sections")
            
            card_markdown = service.render_card_markdown(card)
            console.print(card_markdown)
        
    except Exception as e:
        show_error("Failed to edit card", str(e))
        if "--debug" in sys.argv:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)