"""Mermaid flowchart renderer for project DAGs."""

from __future__ import annotations

from app.enums import CardDepRelation, CardStatus
from app.exporters.dag.base import BaseDagRenderer, DagNode, ProjectDag


class MermaidRenderer(BaseDagRenderer):
    """Renders project DAGs as Mermaid flowcharts."""

    def render_project_dag(self, project_slug: str) -> str:
        """Render the complete project DAG as Mermaid flowchart.
        
        Args:
            project_slug: Project to render
            
        Returns:
            Mermaid flowchart syntax
        """
        dag_data = self.load_project_dag(project_slug)
        if not dag_data:
            return f"graph TD\n    Empty[\"Project '{project_slug}' not found\"]"
        
        return self.render_dag_from_data(dag_data)

    def render_dag_from_data(self, dag_data: ProjectDag) -> str:
        """Render DAG from pre-loaded data as Mermaid flowchart.
        
        Args:
            dag_data: Complete DAG data structure
            
        Returns:
            Mermaid flowchart content
        """
        lines = []
        
        # Header
        lines.append("graph TD")
        lines.append(f"    %% {dag_data.project_name} - Dependency DAG")
        lines.append("")
        
        # Define nodes with styling
        for node in dag_data.nodes:
            node_def = self._format_node_definition(node)
            lines.append(f"    {node_def}")
        
        lines.append("")
        
        # Define edges
        dependency_edges = []
        parallel_edges = []
        
        for edge in dag_data.edges:
            if edge.relation == CardDepRelation.DEPENDS_ON.value:
                dependency_edges.append(edge)
            elif edge.relation == CardDepRelation.PARALLEL_WITH.value:
                parallel_edges.append(edge)
        
        # Add dependency edges (solid arrows)
        if dependency_edges:
            lines.append("    %% Dependencies")
            for edge in dependency_edges:
                lines.append(f"    {edge.from_node} --> {edge.to_node}")
        
        # Add parallel edges (dashed arrows)
        if parallel_edges:
            lines.append("")
            lines.append("    %% Parallel relationships")
            for edge in parallel_edges:
                lines.append(f"    {edge.from_node} -.-> {edge.to_node}")
        
        lines.append("")
        
        # Group nodes by phases using subgraphs
        phase_groups = self.get_phase_groups(dag_data)
        sorted_phases = sorted(dag_data.phases, key=lambda p: p["order_no"])
        
        for phase_meta in sorted_phases:
            phase_code = phase_meta["code"]
            if phase_code in phase_groups:
                lines.append(f"    subgraph {phase_code}[\"{phase_meta['name']}\"]")
                
                # List nodes in this phase
                for node in phase_groups[phase_code]:
                    lines.append(f"        {node.id}")
                
                lines.append("    end")
                lines.append("")
        
        # Add styling
        lines.extend(self._get_styling_rules())
        
        return "\n".join(lines)

    def _format_node_definition(self, node: DagNode) -> str:
        """Format a single node definition with appropriate styling.
        
        Args:
            node: Node to format
            
        Returns:
            Mermaid node definition
        """
        # Sanitize title for Mermaid
        safe_title = self._sanitize_mermaid_text(node.title)
        
        # Choose node shape based on characteristics
        if node.human_gate:
            # Diamond shape for human gates
            node_shape = f"{node.id}{{\"🚪 {node.id}: {safe_title}\"}}"
        elif node.status == CardStatus.DONE.value:
            # Square brackets for completed cards
            node_shape = f"{node.id}[\"✅ {node.id}: {safe_title}\"]"
        elif node.status == CardStatus.IN_PROGRESS.value:
            # Round brackets for in-progress cards
            node_shape = f"{node.id}(\"🔄 {node.id}: {safe_title}\")"
        else:
            # Default rectangle for other cards
            node_shape = f"{node.id}[\"📋 {node.id}: {safe_title}\"]"
        
        return node_shape

    def _sanitize_mermaid_text(self, text: str) -> str:
        """Sanitize text for safe use in Mermaid syntax.
        
        Args:
            text: Raw text
            
        Returns:
            Mermaid-safe text
        """
        # Replace problematic characters
        sanitized = text.replace('"', "'")
        sanitized = sanitized.replace('\n', ' ')
        sanitized = sanitized.replace('\r', ' ')
        
        # Limit length to avoid layout issues
        if len(sanitized) > 50:
            sanitized = sanitized[:47] + "..."
        
        return sanitized

    def _get_styling_rules(self) -> list[str]:
        """Get Mermaid CSS styling rules for the DAG.
        
        Returns:
            List of styling rule lines
        """
        return [
            "    %% Styling",
            "    classDef draftCard fill:#f9f9f9,stroke:#666,color:#000",
            "    classDef inProgressCard fill:#fff3cd,stroke:#856404,color:#856404", 
            "    classDef doneCard fill:#d4edda,stroke:#155724,color:#155724",
            "    classDef humanGate fill:#f8d7da,stroke:#721c24,color:#721c24",
            "    classDef phase fill:#e3f2fd,stroke:#1976d2,color:#1976d2",
            "",
        ]

    def render_critical_path_overlay(self, dag_data: ProjectDag) -> str:
        """Render additional Mermaid syntax to highlight critical path.
        
        Args:
            dag_data: DAG data structure
            
        Returns:
            Additional Mermaid lines for critical path highlighting
        """
        critical_path = self.get_critical_path(dag_data)
        
        if not critical_path:
            return ""
        
        lines = [
            "    %% Critical Path Highlighting",
            "    classDef criticalPath fill:#ffebee,stroke:#d32f2f,stroke-width:3px,color:#d32f2f",
        ]
        
        # Apply critical path styling
        for card_code in critical_path:
            lines.append(f"    class {card_code} criticalPath")
        
        return "\n".join(lines)

    def render_bottleneck_overlay(self, dag_data: ProjectDag) -> str:
        """Render additional Mermaid syntax to highlight bottlenecks.
        
        Args:
            dag_data: DAG data structure
            
        Returns:
            Additional Mermaid lines for bottleneck highlighting  
        """
        bottlenecks = self.find_bottlenecks(dag_data)
        
        if not bottlenecks:
            return ""
        
        lines = [
            "    %% Bottleneck Highlighting",
            "    classDef bottleneck fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#f57c00",
        ]
        
        # Apply bottleneck styling
        for node in bottlenecks:
            lines.append(f"    class {node.id} bottleneck")
        
        return "\n".join(lines)

    def render_enhanced_dag(self, project_slug: str, *, 
                          highlight_critical_path: bool = False,
                          highlight_bottlenecks: bool = False) -> str:
        """Render DAG with optional enhancements.
        
        Args:
            project_slug: Project to render
            highlight_critical_path: Whether to highlight critical path
            highlight_bottlenecks: Whether to highlight bottlenecks
            
        Returns:
            Enhanced Mermaid flowchart content
        """
        dag_data = self.load_project_dag(project_slug)
        if not dag_data:
            return f"graph TD\n    Empty[\"Project '{project_slug}' not found\"]"
        
        # Base DAG
        base_dag = self.render_dag_from_data(dag_data)
        
        # Add enhancements
        enhancements = []
        
        if highlight_critical_path:
            critical_path_overlay = self.render_critical_path_overlay(dag_data)
            if critical_path_overlay:
                enhancements.append(critical_path_overlay)
        
        if highlight_bottlenecks:
            bottleneck_overlay = self.render_bottleneck_overlay(dag_data)
            if bottleneck_overlay:
                enhancements.append(bottleneck_overlay)
        
        if enhancements:
            return base_dag + "\n\n" + "\n\n".join(enhancements)
        else:
            return base_dag