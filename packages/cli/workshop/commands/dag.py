"""`workshop dag` — print Mermaid DAG."""

from __future__ import annotations

import sys

import typer

# Import the DAG system
try:
    from app.services import DagService
    DAG_SERVICE_AVAILABLE = True
except ImportError:
    DAG_SERVICE_AVAILABLE = False


def dag(
    project: str = typer.Option(..., "--project", "-p"),
    format: str = typer.Option("mermaid", "--format", help="Output format (mermaid)"),
    critical_path: bool = typer.Option(False, "--critical-path", help="Highlight critical path"),
    bottlenecks: bool = typer.Option(False, "--bottlenecks", help="Highlight bottlenecks"),
    analyze: bool = typer.Option(False, "--analyze", help="Show dependency analysis instead of DAG"),
    stats: bool = typer.Option(False, "--stats", help="Show DAG statistics"),
    validate: bool = typer.Option(False, "--validate", help="Validate dependencies only"),
) -> None:
    """Print the project's card dependency DAG as Mermaid (top-down)."""
    
    if not DAG_SERVICE_AVAILABLE:
        typer.echo("❌ DAG system not available. Ensure core package is installed.", err=True)
        raise typer.Exit(1)
    
    try:
        dag_service = DagService()
        
        # Handle different output modes
        if validate:
            # Validation mode
            typer.echo(f"🔍 Validating dependencies for project '{project}'...")
            validation_results = dag_service.validate_dependencies(project)
            
            if validation_results.get("error"):
                typer.echo(f"❌ {validation_results['error']}", err=True)
                raise typer.Exit(1)
            
            if validation_results["is_valid"]:
                typer.echo("✅ All dependencies are valid!")
            else:
                typer.echo(f"❌ Found {validation_results['total_issues']} dependency issues:", err=True)
                
                # Show categorized issues
                for category, issues in validation_results["issues_by_category"].items():
                    if issues:
                        typer.echo(f"\n{category.replace('_', ' ').title()}:", err=True)
                        for issue in issues:
                            typer.echo(f"  • {issue.message}", err=True)
            
            # Show topological order status
            if validation_results["topological_order_possible"]:
                typer.echo("\n✅ Topological ordering is possible (no cycles)")
            else:
                typer.echo("\n❌ Topological ordering not possible (cycles detected)", err=True)
                raise typer.Exit(1)
        
        elif analyze:
            # Analysis mode
            typer.echo(f"📊 Analyzing dependencies for project '{project}'...")
            analysis = dag_service.analyze_dependencies(project)
            
            if analysis.get("error"):
                typer.echo(f"❌ {analysis['error']}", err=True)
                raise typer.Exit(1)
            
            # Display analysis results
            summary = analysis["summary"]
            typer.echo(f"\n📋 Project: {analysis['project_name']}")
            typer.echo(f"   Cards: {summary['total_cards']}")
            typer.echo(f"   Dependencies: {summary['total_dependencies']}")
            typer.echo(f"   Parallel relationships: {summary['parallel_relationships']}")
            typer.echo(f"   Phases: {summary['phases']}")
            typer.echo(f"   Human gates: {summary['human_gates']}")
            
            # Validation summary
            validation = analysis["validation"]
            if validation["issues_found"] == 0:
                typer.echo("✅ No validation issues found")
            else:
                typer.echo(f"⚠️  {validation['issues_found']} validation issues found")
            
            # Phase breakdown
            typer.echo("\n📈 Phases:")
            for phase in analysis["phases"]:
                completion = phase["completion_status"]
                typer.echo(f"   {phase['order']}. {phase['name']}: {phase['card_count']} cards ({completion['percentage']:.0f}% done)")
            
            # Critical path and bottlenecks
            critical_path = analysis["critical_path"]
            if critical_path["exists"]:
                typer.echo(f"\n🎯 Critical path: {critical_path['length']} cards")
            
            bottlenecks = analysis["bottlenecks"]
            if bottlenecks["count"] > 0:
                typer.echo(f"⚠️  Bottlenecks: {bottlenecks['count']} cards (risk: {bottlenecks['risk_level']})")
            
            # Parallelization opportunities
            opportunities = analysis["parallelization_opportunities"]
            if opportunities:
                typer.echo(f"\n🚀 Parallelization opportunities in {len(opportunities)} phases")
        
        elif stats:
            # Statistics mode
            typer.echo(f"📈 Gathering DAG statistics for project '{project}'...")
            statistics = dag_service.get_dag_statistics(project)
            
            if statistics.get("error"):
                typer.echo(f"❌ {statistics['error']}", err=True)
                raise typer.Exit(1)
            
            # Display detailed statistics
            node_stats = statistics["node_statistics"]
            edge_stats = statistics["edge_statistics"]
            complexity = statistics["complexity_metrics"]
            
            typer.echo(f"\n📊 DAG Statistics for '{project}'")
            typer.echo(f"   Total nodes: {node_stats['total_nodes']}")
            typer.echo(f"   Total edges: {edge_stats['total_edges']}")
            typer.echo(f"   Human gates: {node_stats['nodes_with_human_gates']}")
            typer.echo(f"   Avg dependencies/card: {edge_stats['average_dependencies_per_card']:.1f}")
            
            typer.echo(f"\n🧮 Complexity Metrics:")
            typer.echo(f"   Cyclomatic complexity: {complexity['cyclomatic_complexity']}")
            typer.echo(f"   Max in-degree: {complexity['max_in_degree']}")
            typer.echo(f"   Max out-degree: {complexity['max_out_degree']}")
            typer.echo(f"   Dependency density: {complexity['dependency_density']:.3f}")
        
        else:
            # Default DAG rendering mode
            if format != "mermaid":
                typer.echo(f"❌ Unsupported format: {format}. Only 'mermaid' is supported.", err=True)
                raise typer.Exit(1)
            
            typer.echo(f"🎨 Generating {format.title()} DAG for project '{project}'...")
            
            dag_content = dag_service.render_dag(
                project,
                format="mermaid",
                highlight_critical_path=critical_path,
                highlight_bottlenecks=bottlenecks
            )
            
            if not dag_content or "not found" in dag_content:
                typer.echo(f"❌ Project '{project}' not found or has no cards", err=True)
                raise typer.Exit(1)
            
            # Output the DAG
            typer.echo(dag_content)
            
            # Optional usage hint
            if not (critical_path or bottlenecks):
                typer.echo(f"\n💡 Tip: Use --critical-path and --bottlenecks for enhanced visualization", err=True)
    
    except Exception as e:
        typer.echo(f"❌ DAG operation failed: {str(e)}", err=True)
        if "--debug" in sys.argv:
            import traceback
            typer.echo(traceback.format_exc(), err=True)
        raise typer.Exit(1)
