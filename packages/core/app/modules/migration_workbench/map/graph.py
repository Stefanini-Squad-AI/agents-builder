"""Flow detection using NetworkX.

Provides graph algorithms for:
- Connected component detection (clusters)
- Topological sorting (migration order)
- Cycle detection
- Wave assignment
"""

from __future__ import annotations

import uuid
from typing import Any

import networkx as nx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.migration_workbench.map.schemas import (
    ClusterView,
    ClusterWithMembers,
    ClusterMemberView,
    WaveSuggestion,
    WaveSuggestionsResult,
)
from app.modules.migration_workbench.models import (
    ETLPackage,
    PackageCluster,
    PackageClusterMember,
    PackageFlowDep,
)


class FlowDetector:
    """Detects flow patterns using graph algorithms.
    
    Uses NetworkX to:
    - Find connected components (clusters)
    - Compute topological order (migration sequence)
    - Detect cycles (problematic dependencies)
    - Suggest wave assignments
    """
    
    def __init__(self, session: Session):
        """Initialize detector.
        
        Args:
            session: Database session
        """
        self.session = session
    
    def build_graph(self, project_id: uuid.UUID) -> nx.DiGraph:
        """Build a directed graph from flow dependencies.
        
        Args:
            project_id: Project ID
            
        Returns:
            NetworkX DiGraph with packages as nodes
        """
        G = nx.DiGraph()
        
        # Add all packages as nodes
        packages = self.session.execute(
            select(ETLPackage.id, ETLPackage.package_name).where(
                ETLPackage.project_id == project_id
            )
        ).all()
        
        for pkg_id, pkg_name in packages:
            G.add_node(pkg_id, name=pkg_name)
        
        # Add edges from dependencies
        deps = self.session.execute(
            select(PackageFlowDep).where(
                PackageFlowDep.project_id == project_id
            )
        ).scalars().all()
        
        for dep in deps:
            G.add_edge(
                dep.upstream_package_id,
                dep.downstream_package_id,
                via_object=dep.via_object_id,
                relationship_type=dep.relationship_type,
            )
        
        return G
    
    def detect_clusters(self, project_id: uuid.UUID) -> list[PackageCluster]:
        """Detect connected components and compute migration order.
        
        Creates or updates PackageCluster records for each
        connected component in the dependency graph.
        
        Args:
            project_id: Project ID
            
        Returns:
            List of created/updated PackageCluster records
        """
        G = self.build_graph(project_id)
        
        if len(G.nodes) == 0:
            return []
        
        # Delete existing clusters for this project
        self.session.execute(
            select(PackageCluster).where(
                PackageCluster.project_id == project_id
            )
        )
        existing_clusters = self.session.execute(
            select(PackageCluster).where(
                PackageCluster.project_id == project_id
            )
        ).scalars().all()
        
        for cluster in existing_clusters:
            self.session.delete(cluster)
        self.session.flush()
        
        # Find weakly connected components
        components = list(nx.weakly_connected_components(G))
        
        # Get package names for naming clusters
        pkg_names = {
            node: G.nodes[node].get("name", str(node))
            for node in G.nodes
        }
        
        clusters = []
        for i, component in enumerate(components, 1):
            subgraph = G.subgraph(component)
            
            # Find roots (no incoming edges within component)
            roots = [n for n in component if subgraph.in_degree(n) == 0]
            
            # Find leaves (no outgoing edges within component)
            leaves = [n for n in component if subgraph.out_degree(n) == 0]
            
            # Check for cycles
            try:
                order = list(nx.topological_sort(subgraph))
                has_cycles = False
                cycle_packages = None
            except nx.NetworkXUnfeasible:
                # Cycle detected
                has_cycles = True
                cycles = list(nx.simple_cycles(subgraph))
                cycle_packages = list({node for cycle in cycles for node in cycle})
                order = list(component)  # Arbitrary order
            
            # Generate cluster name from root packages
            if roots:
                root_names = [pkg_names.get(r, "Unknown") for r in roots[:2]]
                name = f"Flow {i}: {', '.join(root_names)}"
            else:
                name = f"Flow {i} (cyclic)"
            
            cluster = PackageCluster(
                id=uuid.uuid4(),
                project_id=project_id,
                name=name,
                description=None,
                package_count=len(component),
                root_packages=roots if roots else None,
                leaf_packages=leaves if leaves else None,
                suggested_wave=i,
                migration_order=[
                    {"package_id": str(p), "position": j}
                    for j, p in enumerate(order)
                ],
                has_cycles=has_cycles,
                cycle_packages=cycle_packages,
            )
            self.session.add(cluster)
            clusters.append(cluster)
            
            # Add cluster members
            for j, pkg_id in enumerate(order):
                member = PackageClusterMember(
                    cluster_id=cluster.id,
                    package_id=pkg_id,
                    position_in_cluster=j,
                    assigned_wave=None,
                )
                self.session.add(member)
        
        self.session.flush()
        return clusters
    
    def get_cluster(self, cluster_id: uuid.UUID) -> ClusterWithMembers | None:
        """Get a cluster with its members.
        
        Args:
            cluster_id: Cluster ID
            
        Returns:
            ClusterWithMembers or None
        """
        cluster = self.session.execute(
            select(PackageCluster).where(PackageCluster.id == cluster_id)
        ).scalar_one_or_none()
        
        if not cluster:
            return None
        
        # Get members with package names
        members = self.session.execute(
            select(PackageClusterMember, ETLPackage.package_name)
            .join(ETLPackage, PackageClusterMember.package_id == ETLPackage.id)
            .where(PackageClusterMember.cluster_id == cluster_id)
            .order_by(PackageClusterMember.position_in_cluster)
        ).all()
        
        member_views = [
            ClusterMemberView(
                cluster_id=member.cluster_id,
                package_id=member.package_id,
                package_name=pkg_name,
                position_in_cluster=member.position_in_cluster,
                assigned_wave=member.assigned_wave,
            )
            for member, pkg_name in members
        ]
        
        return ClusterWithMembers(
            **ClusterView.model_validate(cluster).model_dump(),
            members=member_views,
        )
    
    def list_clusters(self, project_id: uuid.UUID) -> list[ClusterView]:
        """List all clusters in a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            List of ClusterView
        """
        clusters = self.session.execute(
            select(PackageCluster)
            .where(PackageCluster.project_id == project_id)
            .order_by(PackageCluster.suggested_wave)
        ).scalars().all()
        
        return [ClusterView.model_validate(c) for c in clusters]
    
    def detect_cycles(self, project_id: uuid.UUID) -> list[list[uuid.UUID]]:
        """Detect all cycles in the dependency graph.
        
        Args:
            project_id: Project ID
            
        Returns:
            List of cycles (each cycle is a list of package IDs)
        """
        G = self.build_graph(project_id)
        
        try:
            cycles = list(nx.simple_cycles(G))
            return cycles
        except Exception:
            return []
    
    def suggest_waves(self, project_id: uuid.UUID) -> WaveSuggestionsResult:
        """Suggest wave assignments based on topological order.
        
        Packages with no dependencies go in Wave 1.
        Packages depending only on Wave N packages go in Wave N+1.
        
        Args:
            project_id: Project ID
            
        Returns:
            WaveSuggestionsResult with suggestions and unassignable packages
        """
        G = self.build_graph(project_id)
        
        if len(G.nodes) == 0:
            return WaveSuggestionsResult(
                suggestions=[],
                total_waves=0,
                unassignable=[],
            )
        
        # Get package names
        pkg_names = {
            node: G.nodes[node].get("name", str(node))
            for node in G.nodes
        }
        
        # Get current wave assignments
        current_waves = {}
        members = self.session.execute(
            select(PackageClusterMember.package_id, PackageClusterMember.assigned_wave)
        ).all()
        for pkg_id, wave in members:
            current_waves[pkg_id] = wave
        
        suggestions = []
        unassignable = []
        wave_assignments: dict[uuid.UUID, int] = {}
        
        # Process each weakly connected component separately
        for component in nx.weakly_connected_components(G):
            subgraph = G.subgraph(component)
            
            try:
                # Topological sort gives us valid ordering
                order = list(nx.topological_sort(subgraph))
                
                # Assign waves based on longest path to each node
                for node in order:
                    predecessors = list(subgraph.predecessors(node))
                    if not predecessors:
                        wave = 1
                    else:
                        wave = max(wave_assignments.get(p, 0) for p in predecessors) + 1
                    wave_assignments[node] = wave
                    
                    suggestions.append(WaveSuggestion(
                        package_id=node,
                        package_name=pkg_names.get(node, str(node)),
                        current_wave=current_waves.get(node),
                        suggested_wave=wave,
                        reason="Topological order" if predecessors else "No dependencies",
                    ))
                    
            except nx.NetworkXUnfeasible:
                # Cycle detected - these packages can't be wave-assigned
                for node in component:
                    unassignable.append(pkg_names.get(node, str(node)))
        
        # Calculate total waves
        total_waves = max(wave_assignments.values()) if wave_assignments else 0
        
        return WaveSuggestionsResult(
            suggestions=sorted(suggestions, key=lambda s: (s.suggested_wave, s.package_name)),
            total_waves=total_waves,
            unassignable=unassignable,
        )
    
    def assign_wave(
        self,
        package_id: uuid.UUID,
        wave: int,
    ) -> bool:
        """Manually assign a wave to a package.
        
        Args:
            package_id: Package ID
            wave: Wave number
            
        Returns:
            True if assigned
        """
        member = self.session.execute(
            select(PackageClusterMember).where(
                PackageClusterMember.package_id == package_id
            )
        ).scalar_one_or_none()
        
        if member:
            member.assigned_wave = wave
            self.session.flush()
            return True
        
        return False
    
    def get_orphan_packages(self, project_id: uuid.UUID) -> list[tuple[uuid.UUID, str]]:
        """Get packages with no dependencies (isolated nodes).
        
        Args:
            project_id: Project ID
            
        Returns:
            List of (package_id, package_name) tuples
        """
        G = self.build_graph(project_id)
        
        orphans = []
        for node in G.nodes:
            if G.in_degree(node) == 0 and G.out_degree(node) == 0:
                orphans.append((node, G.nodes[node].get("name", str(node))))
        
        return orphans
    
    def get_migration_order(
        self,
        project_id: uuid.UUID,
    ) -> list[tuple[uuid.UUID, str, int]]:
        """Get the recommended migration order for all packages.
        
        Args:
            project_id: Project ID
            
        Returns:
            List of (package_id, package_name, wave) tuples
        """
        result = self.suggest_waves(project_id)
        
        return [
            (s.package_id, s.package_name, s.suggested_wave)
            for s in result.suggestions
        ]
