"""DAG service for dependency analysis and visualization."""

from __future__ import annotations

from typing import Any, Literal

from app.exporters.dag import create_dag_renderer, render_project_dag
from app.exporters.dag.base import DagNode, ProjectDag
from app.validators.dag_validator import DagValidator


class DagService:
    """Service for dependency graph analysis and visualization."""

    def __init__(self) -> None:
        """Initialize the DAG service."""
        self.dag_validator = DagValidator()

    def render_dag(
        self,
        project_slug: str,
        format: Literal["mermaid"] = "mermaid",
        *,
        highlight_critical_path: bool = False,
        highlight_bottlenecks: bool = False
    ) -> str:
        """Render project dependency DAG in the specified format.
        
        Args:
            project_slug: Project to render
            format: Output format (currently only "mermaid")
            highlight_critical_path: Whether to highlight critical path
            highlight_bottlenecks: Whether to highlight bottleneck nodes
            
        Returns:
            Rendered DAG content
        """
        if format == "mermaid":
            renderer = create_dag_renderer("mermaid")
            
            if highlight_critical_path or highlight_bottlenecks:
                # Use enhanced rendering
                return renderer.render_enhanced_dag(
                    project_slug,
                    highlight_critical_path=highlight_critical_path,
                    highlight_bottlenecks=highlight_bottlenecks
                )
            else:
                # Use basic rendering
                return render_project_dag(project_slug, "mermaid")
        else:
            raise ValueError(f"Unsupported DAG format: {format}")

    def analyze_dependencies(self, project_slug: str) -> dict[str, Any]:
        """Analyze project dependencies and provide insights.
        
        Args:
            project_slug: Project to analyze
            
        Returns:
            Dictionary with dependency analysis results
        """
        # Load DAG data
        renderer = create_dag_renderer("mermaid")
        dag_data = renderer.load_project_dag(project_slug)
        
        if not dag_data:
            return {"error": f"Project '{project_slug}' not found"}
        
        # Run validation
        validation_issues = self.dag_validator.validate(project_slug)
        
        # Calculate metrics
        analysis = {
            "project_slug": project_slug,
            "project_name": dag_data.project_name,
            "summary": {
                "total_cards": len(dag_data.nodes),
                "total_dependencies": len([
                    e for e in dag_data.edges if e.relation == "depends_on"
                ]),
                "parallel_relationships": len([
                    e for e in dag_data.edges if e.relation == "parallel_with"
                ]),
                "phases": len(dag_data.phases),
                "human_gates": len([n for n in dag_data.nodes if n.human_gate])
            },
            "validation": {
                "issues_found": len(validation_issues),
                "errors": [
                    issue for issue in validation_issues 
                    if issue.severity.value == "error"
                ],
                "warnings": [
                    issue for issue in validation_issues 
                    if issue.severity.value == "warning"
                ]
            },
            "phases": self._analyze_phases(dag_data),
            "critical_path": self._get_critical_path_analysis(dag_data),
            "bottlenecks": self._get_bottleneck_analysis(dag_data),
            "parallelization_opportunities": self._find_parallelization_opportunities(dag_data)
        }
        
        return analysis

    def get_topological_order(self, project_slug: str) -> list[str] | None:
        """Get topological ordering of cards for execution planning.
        
        Args:
            project_slug: Project to analyze
            
        Returns:
            List of card codes in topological order, or None if cycles exist
        """
        return self.dag_validator.calculate_topological_order(project_slug)

    def validate_dependencies(self, project_slug: str) -> dict[str, Any]:
        """Validate project dependencies and return detailed results.
        
        Args:
            project_slug: Project to validate
            
        Returns:
            Validation results with categorized issues
        """
        issues = self.dag_validator.validate(project_slug)
        
        # Categorize issues
        categorized = {
            "cycles": [],
            "cross_phase_issues": [],
            "orphaned_cards": [],
            "other_issues": []
        }
        
        for issue in issues:
            if "cycle" in issue.code:
                categorized["cycles"].append(issue)
            elif "phase" in issue.code:
                categorized["cross_phase_issues"].append(issue)
            elif "orphaned" in issue.code:
                categorized["orphaned_cards"].append(issue)
            else:
                categorized["other_issues"].append(issue)
        
        return {
            "project_slug": project_slug,
            "is_valid": len(issues) == 0,
            "total_issues": len(issues),
            "issues_by_category": categorized,
            "topological_order_possible": self.get_topological_order(project_slug) is not None
        }

    def get_dag_statistics(self, project_slug: str) -> dict[str, Any]:
        """Get detailed DAG statistics for reporting.
        
        Args:
            project_slug: Project to analyze
            
        Returns:
            Dictionary with DAG statistics
        """
        renderer = create_dag_renderer("mermaid")
        dag_data = renderer.load_project_dag(project_slug)
        
        if not dag_data:
            return {"error": f"Project '{project_slug}' not found"}
        
        # Calculate detailed statistics
        stats = {
            "project_slug": project_slug,
            "node_statistics": self._calculate_node_statistics(dag_data),
            "edge_statistics": self._calculate_edge_statistics(dag_data),
            "phase_statistics": self._calculate_phase_statistics(dag_data),
            "complexity_metrics": self._calculate_complexity_metrics(dag_data),
            "execution_estimates": self._calculate_execution_estimates(dag_data)
        }
        
        return stats

    def _analyze_phases(self, dag_data: ProjectDag) -> list[dict[str, Any]]:
        """Analyze individual phases."""
        phase_groups = {}
        renderer = create_dag_renderer("mermaid")
        groups = renderer.get_phase_groups(dag_data)
        
        analysis = []
        for phase_meta in sorted(dag_data.phases, key=lambda p: p["order_no"]):
            phase_code = phase_meta["code"]
            cards = groups.get(phase_code, [])
            
            analysis.append({
                "code": phase_code,
                "name": phase_meta["name"],
                "order": phase_meta["order_no"],
                "card_count": len(cards),
                "human_gates": len([c for c in cards if c.human_gate]),
                "completion_status": self._calculate_phase_completion(cards)
            })
        
        return analysis

    def _get_critical_path_analysis(self, dag_data: ProjectDag) -> dict[str, Any]:
        """Analyze critical path through the project."""
        renderer = create_dag_renderer("mermaid")
        critical_path = renderer.get_critical_path(dag_data)
        
        return {
            "exists": len(critical_path) > 0,
            "length": len(critical_path),
            "cards": critical_path,
            "estimated_duration": None  # TODO: Calculate based on story points
        }

    def _get_bottleneck_analysis(self, dag_data: ProjectDag) -> dict[str, Any]:
        """Analyze potential bottlenecks."""
        renderer = create_dag_renderer("mermaid")
        bottlenecks = renderer.find_bottlenecks(dag_data)
        
        return {
            "count": len(bottlenecks),
            "cards": [
                {"id": node.id, "title": node.title, "phase": node.phase_code} 
                for node in bottlenecks
            ],
            "risk_level": (
                "high" if len(bottlenecks) > 3 
                else "medium" if len(bottlenecks) > 0 
                else "low"
            )
        }

    def _find_parallelization_opportunities(self, dag_data: ProjectDag) -> list[dict[str, Any]]:
        """Find opportunities for parallel execution."""
        # Simple heuristic: cards with no dependencies that aren't already parallel
        opportunities = []
        
        # Build dependency map
        has_dependencies = set()
        for edge in dag_data.edges:
            if edge.relation == "depends_on":
                has_dependencies.add(edge.to_node)
        
        # Group independent cards by phase
        phase_groups = {}
        renderer = create_dag_renderer("mermaid")
        groups = renderer.get_phase_groups(dag_data)
        
        for phase_code, nodes in groups.items():
            independent_cards = [node for node in nodes if node.id not in has_dependencies]
            
            if len(independent_cards) > 1:
                opportunities.append({
                    "phase": phase_code,
                    "cards": [{"id": node.id, "title": node.title} for node in independent_cards],
                    "potential_parallel_cards": len(independent_cards)
                })
        
        return opportunities

    def _calculate_node_statistics(self, dag_data: ProjectDag) -> dict[str, Any]:
        """Calculate statistics about nodes."""
        nodes = dag_data.nodes
        
        return {
            "total_nodes": len(nodes),
            "nodes_by_status": self._count_by_field(nodes, "status"),
            "nodes_with_human_gates": len([n for n in nodes if n.human_gate]),
            "nodes_by_phase": len(set(n.phase_code for n in nodes))
        }

    def _calculate_edge_statistics(self, dag_data: ProjectDag) -> dict[str, Any]:
        """Calculate statistics about edges."""
        edges = dag_data.edges
        
        return {
            "total_edges": len(edges),
            "edges_by_type": self._count_by_field(edges, "relation"),
            "average_dependencies_per_card": (
                len(edges) / len(dag_data.nodes) if dag_data.nodes else 0
            )
        }

    def _calculate_phase_statistics(self, dag_data: ProjectDag) -> dict[str, Any]:
        """Calculate statistics about phases."""
        renderer = create_dag_renderer("mermaid")
        phase_groups = renderer.get_phase_groups(dag_data)
        
        return {
            "total_phases": len(dag_data.phases),
            "cards_per_phase": {code: len(nodes) for code, nodes in phase_groups.items()},
            "average_cards_per_phase": (
                sum(len(nodes) for nodes in phase_groups.values()) / len(dag_data.phases) 
                if dag_data.phases else 0
            )
        }

    def _calculate_complexity_metrics(self, dag_data: ProjectDag) -> dict[str, Any]:
        """Calculate project complexity metrics."""
        nodes = dag_data.nodes
        edges = dag_data.edges
        
        # Calculate in-degree and out-degree for each node
        in_degree = {node.id: 0 for node in nodes}
        out_degree = {node.id: 0 for node in nodes}
        
        for edge in edges:
            if edge.relation == "depends_on":
                in_degree[edge.to_node] += 1
                out_degree[edge.from_node] += 1
        
        return {
            "cyclomatic_complexity": len(edges) - len(nodes) + 2,  # Simplified metric
            "max_in_degree": max(in_degree.values()) if in_degree else 0,
            "max_out_degree": max(out_degree.values()) if out_degree else 0,
            "dependency_density": (
                len(edges) / (len(nodes) * (len(nodes) - 1)) if len(nodes) > 1 else 0
            )
        }

    def _calculate_execution_estimates(self, dag_data: ProjectDag) -> dict[str, Any]:
        """Calculate execution time estimates if story points are available."""
        # Placeholder for execution estimation logic
        return {
            "total_story_points": None,  # TODO: Sum story points if available
            "estimated_duration_days": None,  # TODO: Calculate based on story points
            "critical_path_duration": None  # TODO: Calculate critical path duration
        }

    def _calculate_phase_completion(self, cards: list[DagNode]) -> dict[str, Any]:
        """Calculate completion status for a phase."""
        if not cards:
            return {"percentage": 0, "done_count": 0, "total_count": 0}
        
        done_count = len([c for c in cards if c.status == "done"])
        
        return {
            "percentage": (done_count / len(cards)) * 100,
            "done_count": done_count,
            "total_count": len(cards)
        }

    def _count_by_field(self, items: list, field: str) -> dict[str, int]:
        """Count items by a specific field value."""
        counts = {}
        for item in items:
            value = getattr(item, field)
            counts[value] = counts.get(value, 0) + 1
        return counts