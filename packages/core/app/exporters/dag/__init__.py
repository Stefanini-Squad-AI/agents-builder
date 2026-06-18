"""DAG visualization and export utilities.

This module provides renderers for generating dependency graph visualizations:
- MermaidRenderer: Generate Mermaid flowchart syntax
- (Future) GraphvizRenderer: Generate Graphviz DOT format

Usage:
    from app.exporters.dag import create_dag_renderer, render_project_dag
    
    # Generate Mermaid DAG
    renderer = create_dag_renderer("mermaid")
    mermaid_content = renderer.render_project_dag("my-project-slug")
    
    # High-level function
    dag_content = render_project_dag("my-project-slug", "mermaid")
"""

from __future__ import annotations

from typing import Literal

from app.exporters.dag.base import BaseDagRenderer
from app.exporters.dag.mermaid import MermaidRenderer


def create_dag_renderer(format: Literal["mermaid"] = "mermaid") -> BaseDagRenderer:
    """Factory function to create the appropriate DAG renderer.
    
    Args:
        format: DAG output format ("mermaid")
        
    Returns:
        Configured DAG renderer instance
        
    Raises:
        ValueError: If format is not supported
    """
    if format == "mermaid":
        return MermaidRenderer()
    else:
        raise ValueError(f"Unsupported DAG format: {format}")


def render_project_dag(
    project_slug: str, 
    format: Literal["mermaid"] = "mermaid"
) -> str:
    """High-level function to render a project's dependency DAG.
    
    Args:
        project_slug: Project to render DAG for
        format: Output format
        
    Returns:
        Rendered DAG content
    """
    renderer = create_dag_renderer(format)
    return renderer.render_project_dag(project_slug)


__all__ = [
    "BaseDagRenderer",
    "MermaidRenderer", 
    "create_dag_renderer",
    "render_project_dag",
]