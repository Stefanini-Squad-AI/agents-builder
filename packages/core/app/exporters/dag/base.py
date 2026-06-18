"""Base DAG renderer classes and utilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass
class DagNode:
    """Represents a node in the dependency graph."""
    
    id: str  # Card code (e.g., "CORP-101")
    title: str
    phase_code: str
    phase_name: str
    status: str  # draft, in_progress, done, etc.
    human_gate: bool
    metadata: dict[str, Any]  # Additional node metadata


@dataclass  
class DagEdge:
    """Represents an edge in the dependency graph."""
    
    from_node: str  # Source card code
    to_node: str    # Target card code  
    relation: str   # depends_on, parallel_with
    metadata: dict[str, Any]  # Additional edge metadata


class ProjectDag(BaseModel):
    """Complete project dependency graph."""
    
    project_slug: str
    project_name: str
    nodes: list[DagNode]
    edges: list[DagEdge]
    phases: list[dict[str, Any]]  # Phase metadata for grouping


class BaseDagRenderer(ABC):
    """Abstract base class for DAG renderers."""

    @abstractmethod
    def render_project_dag(self, project_slug: str) -> str:
        """Render the complete project DAG.
        
        Args:
            project_slug: Project to render
            
        Returns:
            Rendered DAG content in the target format
        """
        ...

    @abstractmethod
    def render_dag_from_data(self, dag_data: ProjectDag) -> str:
        """Render DAG from pre-loaded data.
        
        Args:
            dag_data: Complete DAG data structure
            
        Returns:
            Rendered DAG content
        """
        ...

    def load_project_dag(self, project_slug: str) -> ProjectDag | None:
        """Load project DAG data from database.
        
        Args:
            project_slug: Project to load
            
        Returns:
            Complete DAG data or None if project not found
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        import app.db
        from app.domain.backlog import Card, Phase
        from app.domain.projects import Project
        from app.enums import CardDepRelation
        
        with app.db.session_scope() as session:
            # Load project with full dependency structure
            project_query = select(Project).where(
                Project.slug == project_slug
            ).options(
                selectinload(Project.phases).selectinload(Phase.cards).selectinload(Card.deps_out),
                selectinload(Project.phases).selectinload(Phase.cards).selectinload(Card.skill_links)
            )
            
            result = session.execute(project_query)
            project = result.scalar_one_or_none()
            
            if not project:
                return None
            
            # Build nodes from cards
            nodes = []
            cards_by_id = {}
            
            for phase in project.phases:
                for card in phase.cards:
                    cards_by_id[card.id] = card
                    
                    node = DagNode(
                        id=card.code,
                        title=card.title,
                        phase_code=phase.code,
                        phase_name=phase.name,
                        status=card.status,
                        human_gate=card.human_gate or False,
                        metadata={
                            "type": card.type,
                            "priority": card.priority,
                            "story_points": card.story_points,
                            "order_no": card.order_no
                        }
                    )
                    nodes.append(node)
            
            # Build edges from dependencies
            edges = []
            for phase in project.phases:
                for card in phase.cards:
                    for dep in card.deps_out:
                        if dep.depends_on_card_id in cards_by_id:
                            target_card = cards_by_id[dep.depends_on_card_id]
                            
                            edge = DagEdge(
                                from_node=target_card.code,  # Dependency points FROM target TO card
                                to_node=card.code,
                                relation=dep.relation,
                                metadata={}
                            )
                            edges.append(edge)
            
            # Build phase metadata
            phases_metadata = []
            for phase in sorted(project.phases, key=lambda p: p.order_no):
                phases_metadata.append({
                    "code": phase.code,
                    "name": phase.name,
                    "order_no": phase.order_no,
                    "description": phase.description_md
                })
            
            return ProjectDag(
                project_slug=project.slug,
                project_name=project.name,
                nodes=nodes,
                edges=edges,
                phases=phases_metadata
            )

    def get_phase_groups(self, dag_data: ProjectDag) -> dict[str, list[DagNode]]:
        """Group nodes by phase for visualization.
        
        Args:
            dag_data: DAG data structure
            
        Returns:
            Dictionary mapping phase codes to lists of nodes
        """
        groups = {}
        for node in dag_data.nodes:
            if node.phase_code not in groups:
                groups[node.phase_code] = []
            groups[node.phase_code].append(node)
        
        return groups

    def get_critical_path(self, dag_data: ProjectDag) -> list[str]:
        """Calculate the critical path through the DAG.
        
        Args:
            dag_data: DAG data structure
            
        Returns:
            List of card codes on the critical path
        """
        # Implementation of critical path algorithm would go here
        # For now, return empty list as placeholder
        return []

    def find_bottlenecks(self, dag_data: ProjectDag) -> list[DagNode]:
        """Find potential bottleneck nodes (high in-degree).
        
        Args:
            dag_data: DAG data structure
            
        Returns:
            List of nodes that are potential bottlenecks
        """
        # Count incoming edges for each node
        in_degree = {node.id: 0 for node in dag_data.nodes}
        
        for edge in dag_data.edges:
            if edge.relation == CardDepRelation.DEPENDS_ON.value:
                in_degree[edge.to_node] += 1
        
        # Find nodes with high in-degree (threshold: 3+ dependencies)
        bottlenecks = []
        for node in dag_data.nodes:
            if in_degree[node.id] >= 3:
                bottlenecks.append(node)
        
        return bottlenecks