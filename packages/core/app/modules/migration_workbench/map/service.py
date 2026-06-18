"""Migration Map service - orchestration layer.

Coordinates object registry, relationship detection, and flow detection
to provide a unified API for the Migration Map.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.migration_workbench.map.detector import RelationshipDetector
from app.modules.migration_workbench.map.graph import FlowDetector
from app.modules.migration_workbench.map.object_registry import ObjectRegistry
from app.modules.migration_workbench.map.schemas import (
    ClusterView,
    ClusterWithMembers,
    FlowDepView,
    MapEdge,
    MapNode,
    MapRefreshResult,
    MapStats,
    MapVisualization,
    ObjectDirection,
    ObjectType,
    ObjectView,
    PackageObjectRefCreate,
    WaveSuggestionsResult,
)
from app.modules.migration_workbench.models import (
    ETLPackage,
    MigrationObject,
    PackageCluster,
    PackageFlowDep,
)


class MigrationMapService:
    """Service for managing the Migration Map.
    
    Provides high-level operations for:
    - Registering package objects when analyzed
    - Getting the full map visualization
    - Managing clusters and waves
    - Refreshing the map
    """
    
    def __init__(self, session: Session):
        """Initialize service.
        
        Args:
            session: Database session
        """
        self.session = session
        self.object_registry = ObjectRegistry(session)
        self.relationship_detector = RelationshipDetector(session)
        self.flow_detector = FlowDetector(session)
    
    def add_package(
        self,
        project_id: uuid.UUID,
        package_id: uuid.UUID,
        sources: list[dict],
        targets: list[dict],
    ) -> MapRefreshResult:
        """Add a package to the map after analysis.
        
        Registers objects, detects relationships, and updates clusters.
        
        Args:
            project_id: Project ID
            package_id: Package ID
            sources: List of source objects (tables read)
            targets: List of target objects (tables written)
            
        Returns:
            MapRefreshResult with statistics
        """
        start_time = time.time()
        
        objects_created = 0
        objects_updated = 0
        
        # Register source objects (read)
        for source in sources:
            ref = PackageObjectRefCreate(
                object_type=ObjectType(source.get("type", "table")),
                object_name=source["name"],
                direction=ObjectDirection.READ,
                connection_ref=source.get("connection"),
                schema_name=source.get("schema"),
                database_name=source.get("database"),
                access_type=source.get("access_type"),
                task_name=source.get("task_name"),
            )
            obj, pkg_ref = self.object_registry.register_package_ref(
                package_id, ref, project_id
            )
            if pkg_ref.id:  # New reference
                objects_created += 1
        
        # Register target objects (write)
        for target in targets:
            ref = PackageObjectRefCreate(
                object_type=ObjectType(target.get("type", "table")),
                object_name=target["name"],
                direction=ObjectDirection.WRITE,
                connection_ref=target.get("connection"),
                schema_name=target.get("schema"),
                database_name=target.get("database"),
                access_type=target.get("access_type"),
                task_name=target.get("task_name"),
            )
            obj, pkg_ref = self.object_registry.register_package_ref(
                package_id, ref, project_id
            )
            if pkg_ref.id:  # New reference
                objects_created += 1
        
        # Detect relationships
        deps = self.relationship_detector.detect_relationships(project_id, package_id)
        dependencies_created = len(deps)
        
        # Update clusters
        clusters = self.flow_detector.detect_clusters(project_id)
        cycles = sum(1 for c in clusters if c.has_cycles)
        
        duration_ms = (time.time() - start_time) * 1000
        
        return MapRefreshResult(
            objects_created=objects_created,
            objects_updated=objects_updated,
            dependencies_created=dependencies_created,
            dependencies_removed=0,
            clusters_created=len(clusters),
            clusters_merged=0,
            cycles_detected=cycles,
            duration_ms=duration_ms,
        )
    
    def get_map_visualization(
        self,
        project_id: uuid.UUID,
        include_objects: bool = False,
    ) -> MapVisualization:
        """Get the full map visualization data.
        
        Args:
            project_id: Project ID
            include_objects: Whether to include object nodes
            
        Returns:
            MapVisualization for React Flow
        """
        # Get all packages
        packages = self.session.execute(
            select(ETLPackage).where(ETLPackage.project_id == project_id)
        ).scalars().all()
        
        # Build nodes
        nodes = []
        for pkg in packages:
            nodes.append(MapNode(
                id=str(pkg.id),
                type="package",
                data={
                    "name": pkg.package_name,
                    "status": pkg.status,
                    "analysis_status": pkg.analysis_status,
                    "domain": pkg.domain,
                    "complexity": pkg.complexity,
                    "blockers_count": pkg.blockers_count or 0,
                    "pending_feedback_count": pkg.pending_feedback_count,
                },
                position=None,
            ))
        
        # Get dependencies for edges
        deps = self.relationship_detector.list_all_dependencies(project_id)
        
        edges = []
        for dep in deps:
            edges.append(MapEdge(
                id=str(dep.id),
                source=str(dep.upstream_package_id),
                target=str(dep.downstream_package_id),
                label=dep.via_object_name,
                animated=not dep.is_confirmed,
                style={"stroke": "#888" if dep.is_confirmed else "#ccc"},
            ))
        
        # Get clusters
        clusters = self.flow_detector.list_clusters(project_id)
        
        # Find orphans
        orphans = self.flow_detector.get_orphan_packages(project_id)
        orphan_names = [name for _, name in orphans]
        
        # Calculate stats
        stats = self._calculate_stats(project_id, packages, deps, clusters, orphans)
        
        return MapVisualization(
            nodes=nodes,
            edges=edges,
            clusters=clusters,
            orphan_packages=orphan_names,
            stats=stats,
        )
    
    def _calculate_stats(
        self,
        project_id: uuid.UUID,
        packages: list,
        deps: list,
        clusters: list,
        orphans: list,
    ) -> MapStats:
        """Calculate map statistics.
        
        Args:
            project_id: Project ID
            packages: List of packages
            deps: List of dependencies
            clusters: List of clusters
            orphans: List of orphan packages
            
        Returns:
            MapStats
        """
        analyzed = sum(1 for p in packages if p.analysis_status == "analyzed")
        object_count = self.object_registry.count_objects(project_id)
        cycles = sum(1 for c in clusters if c.has_cycles)
        
        # Calculate suggested waves
        if clusters:
            max_wave = max(c.suggested_wave or 0 for c in clusters)
        else:
            max_wave = 0
        
        return MapStats(
            total_packages=len(packages),
            analyzed_packages=analyzed,
            total_objects=object_count,
            total_dependencies=len(deps),
            cluster_count=len(clusters),
            orphan_count=len(orphans),
            cycles_detected=cycles,
            suggested_waves=max_wave,
        )
    
    def refresh_map(self, project_id: uuid.UUID) -> MapRefreshResult:
        """Refresh the entire map by recomputing all relationships.
        
        Use this when relationships may be stale or after
        manual changes.
        
        Args:
            project_id: Project ID
            
        Returns:
            MapRefreshResult with statistics
        """
        start_time = time.time()
        
        # Get all analyzed packages
        packages = self.session.execute(
            select(ETLPackage).where(
                ETLPackage.project_id == project_id,
                ETLPackage.analysis_status == "analyzed",
            )
        ).scalars().all()
        
        total_deps = 0
        for pkg in packages:
            deps = self.relationship_detector.detect_relationships(project_id, pkg.id)
            total_deps += len(deps)
        
        # Recompute clusters
        clusters = self.flow_detector.detect_clusters(project_id)
        cycles = sum(1 for c in clusters if c.has_cycles)
        
        duration_ms = (time.time() - start_time) * 1000
        
        return MapRefreshResult(
            objects_created=0,
            objects_updated=0,
            dependencies_created=total_deps,
            dependencies_removed=0,
            clusters_created=len(clusters),
            clusters_merged=0,
            cycles_detected=cycles,
            duration_ms=duration_ms,
        )
    
    def get_objects(
        self,
        project_id: uuid.UUID,
        object_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ObjectView]:
        """Get objects in a project.
        
        Args:
            project_id: Project ID
            object_type: Optional filter
            limit: Max results
            offset: Pagination offset
            
        Returns:
            List of ObjectView
        """
        return self.object_registry.list_objects(
            project_id, object_type, limit, offset
        )
    
    def get_dependencies(
        self,
        project_id: uuid.UUID,
    ) -> list[FlowDepView]:
        """Get all dependencies in a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            List of FlowDepView
        """
        return self.relationship_detector.list_all_dependencies(project_id)
    
    def get_clusters(self, project_id: uuid.UUID) -> list[ClusterView]:
        """Get all clusters in a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            List of ClusterView
        """
        return self.flow_detector.list_clusters(project_id)
    
    def get_cluster(self, cluster_id: uuid.UUID) -> ClusterWithMembers | None:
        """Get a cluster with members.
        
        Args:
            cluster_id: Cluster ID
            
        Returns:
            ClusterWithMembers or None
        """
        return self.flow_detector.get_cluster(cluster_id)
    
    def suggest_waves(self, project_id: uuid.UUID) -> WaveSuggestionsResult:
        """Suggest wave assignments.
        
        Args:
            project_id: Project ID
            
        Returns:
            WaveSuggestionsResult
        """
        return self.flow_detector.suggest_waves(project_id)
    
    def assign_wave(self, package_id: uuid.UUID, wave: int) -> bool:
        """Assign a wave to a package.
        
        Args:
            package_id: Package ID
            wave: Wave number
            
        Returns:
            True if assigned
        """
        return self.flow_detector.assign_wave(package_id, wave)
    
    def confirm_dependency(
        self,
        dep_id: uuid.UUID,
        is_confirmed: bool,
    ) -> bool:
        """Confirm or reject a dependency.
        
        Args:
            dep_id: Dependency ID
            is_confirmed: Whether to confirm
            
        Returns:
            True if updated
        """
        dep = self.relationship_detector.confirm_dependency(dep_id, is_confirmed)
        return dep is not None
    
    def create_manual_dependency(
        self,
        project_id: uuid.UUID,
        upstream_id: uuid.UUID,
        downstream_id: uuid.UUID,
    ) -> FlowDepView:
        """Create a manual dependency.
        
        Args:
            project_id: Project ID
            upstream_id: Upstream package ID
            downstream_id: Downstream package ID
            
        Returns:
            Created dependency view
        """
        dep = self.relationship_detector.create_manual_dependency(
            project_id, upstream_id, downstream_id
        )
        
        # Recompute clusters
        self.flow_detector.detect_clusters(project_id)
        
        return FlowDepView(
            id=dep.id,
            project_id=dep.project_id,
            upstream_package_id=dep.upstream_package_id,
            downstream_package_id=dep.downstream_package_id,
            via_object_id=dep.via_object_id,
            relationship_type=dep.relationship_type,
            is_confirmed=dep.is_confirmed,
            auto_detected=dep.auto_detected,
        )
    
    def delete_dependency(self, dep_id: uuid.UUID) -> bool:
        """Delete a dependency.
        
        Args:
            dep_id: Dependency ID
            
        Returns:
            True if deleted
        """
        return self.relationship_detector.delete_dependency(dep_id)
