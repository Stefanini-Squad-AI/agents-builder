"""Relationship detection for Migration Map.

Detects data flow relationships between packages by analyzing
which packages read/write the same objects.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.modules.migration_workbench.map.object_registry import ObjectRegistry
from app.modules.migration_workbench.map.schemas import (
    FlowDepCreate,
    FlowDepView,
    FlowRelationshipType,
)
from app.modules.migration_workbench.models import (
    ETLPackage,
    MigrationObject,
    PackageFlowDep,
    PackageObjectRef,
)


class RelationshipDetector:
    """Detects data flow relationships between packages.
    
    When Package A writes an object that Package B reads,
    we create a data flow dependency: A → B.
    
    This enables:
    - Migration order computation (topological sort)
    - Impact analysis (what breaks if A fails?)
    - Cluster detection (which packages are related?)
    """
    
    def __init__(self, session: Session):
        """Initialize detector.
        
        Args:
            session: Database session
        """
        self.session = session
        self.object_registry = ObjectRegistry(session)
    
    def detect_relationships(
        self,
        project_id: uuid.UUID,
        package_id: uuid.UUID,
    ) -> list[PackageFlowDep]:
        """Detect all relationships for a newly analyzed package.
        
        When a package is analyzed:
        1. Find packages that READ what this package WRITES (this → others)
        2. Find packages that WRITE what this package READS (others → this)
        
        Args:
            project_id: Project ID
            package_id: Package ID that was just analyzed
            
        Returns:
            List of created PackageFlowDep records
        """
        created_deps = []
        
        # Get objects written by this package
        writes = self.object_registry.get_objects_written_by(package_id)
        
        # Get objects read by this package
        reads = self.object_registry.get_objects_read_by(package_id)
        
        # Find downstream dependencies (this package → others)
        for obj in writes:
            readers = self.object_registry.get_packages_reading_object(obj.id)
            for reader_id in readers:
                if reader_id != package_id:
                    dep = self._create_or_get_dependency(
                        project_id=project_id,
                        upstream_id=package_id,
                        downstream_id=reader_id,
                        via_object_id=obj.id,
                    )
                    if dep:
                        created_deps.append(dep)
        
        # Find upstream dependencies (others → this package)
        for obj in reads:
            writers = self.object_registry.get_packages_writing_object(obj.id)
            for writer_id in writers:
                if writer_id != package_id:
                    dep = self._create_or_get_dependency(
                        project_id=project_id,
                        upstream_id=writer_id,
                        downstream_id=package_id,
                        via_object_id=obj.id,
                    )
                    if dep:
                        created_deps.append(dep)
        
        self.session.flush()
        return created_deps
    
    def _create_or_get_dependency(
        self,
        project_id: uuid.UUID,
        upstream_id: uuid.UUID,
        downstream_id: uuid.UUID,
        via_object_id: uuid.UUID,
    ) -> PackageFlowDep | None:
        """Create a dependency if it doesn't exist.
        
        Args:
            project_id: Project ID
            upstream_id: Package that writes
            downstream_id: Package that reads
            via_object_id: Object connecting them
            
        Returns:
            Created PackageFlowDep or None if already exists
        """
        # Check if dependency already exists
        existing = self.session.execute(
            select(PackageFlowDep).where(
                PackageFlowDep.upstream_package_id == upstream_id,
                PackageFlowDep.downstream_package_id == downstream_id,
                PackageFlowDep.via_object_id == via_object_id,
            )
        ).scalar_one_or_none()
        
        if existing:
            return None
        
        dep = PackageFlowDep(
            id=uuid.uuid4(),
            project_id=project_id,
            upstream_package_id=upstream_id,
            downstream_package_id=downstream_id,
            via_object_id=via_object_id,
            relationship_type="data_flow",
            auto_detected=True,
            is_confirmed=False,
        )
        self.session.add(dep)
        return dep
    
    def find_upstream(
        self,
        package_id: uuid.UUID,
    ) -> list[FlowDepView]:
        """Find all packages that this package depends on.
        
        Args:
            package_id: Package ID
            
        Returns:
            List of upstream dependencies
        """
        deps = self.session.execute(
            select(PackageFlowDep, ETLPackage, MigrationObject)
            .join(
                ETLPackage, 
                PackageFlowDep.upstream_package_id == ETLPackage.id
            )
            .outerjoin(
                MigrationObject,
                PackageFlowDep.via_object_id == MigrationObject.id
            )
            .where(PackageFlowDep.downstream_package_id == package_id)
        ).all()
        
        return [
            FlowDepView(
                id=dep.id,
                project_id=dep.project_id,
                upstream_package_id=dep.upstream_package_id,
                downstream_package_id=dep.downstream_package_id,
                via_object_id=dep.via_object_id,
                relationship_type=dep.relationship_type,
                is_confirmed=dep.is_confirmed,
                auto_detected=dep.auto_detected,
                upstream_package_name=pkg.package_name,
                downstream_package_name=None,
                via_object_name=obj.object_name if obj else None,
            )
            for dep, pkg, obj in deps
        ]
    
    def find_downstream(
        self,
        package_id: uuid.UUID,
    ) -> list[FlowDepView]:
        """Find all packages that depend on this package.
        
        Args:
            package_id: Package ID
            
        Returns:
            List of downstream dependencies
        """
        deps = self.session.execute(
            select(PackageFlowDep, ETLPackage, MigrationObject)
            .join(
                ETLPackage,
                PackageFlowDep.downstream_package_id == ETLPackage.id
            )
            .outerjoin(
                MigrationObject,
                PackageFlowDep.via_object_id == MigrationObject.id
            )
            .where(PackageFlowDep.upstream_package_id == package_id)
        ).all()
        
        return [
            FlowDepView(
                id=dep.id,
                project_id=dep.project_id,
                upstream_package_id=dep.upstream_package_id,
                downstream_package_id=dep.downstream_package_id,
                via_object_id=dep.via_object_id,
                relationship_type=dep.relationship_type,
                is_confirmed=dep.is_confirmed,
                auto_detected=dep.auto_detected,
                upstream_package_name=None,
                downstream_package_name=pkg.package_name,
                via_object_name=obj.object_name if obj else None,
            )
            for dep, pkg, obj in deps
        ]
    
    def list_all_dependencies(
        self,
        project_id: uuid.UUID,
    ) -> list[FlowDepView]:
        """List all dependencies in a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            List of all dependencies
        """
        # Aliases for the two package joins
        UpstreamPkg = ETLPackage.__table__.alias("upstream_pkg")
        DownstreamPkg = ETLPackage.__table__.alias("downstream_pkg")
        
        deps = self.session.execute(
            select(PackageFlowDep).where(
                PackageFlowDep.project_id == project_id
            )
        ).scalars().all()
        
        # Fetch package names in bulk
        pkg_ids = set()
        for dep in deps:
            pkg_ids.add(dep.upstream_package_id)
            pkg_ids.add(dep.downstream_package_id)
        
        pkg_names = {}
        if pkg_ids:
            pkgs = self.session.execute(
                select(ETLPackage.id, ETLPackage.package_name).where(
                    ETLPackage.id.in_(pkg_ids)
                )
            ).all()
            pkg_names = {p.id: p.package_name for p in pkgs}
        
        # Fetch object names
        obj_ids = {dep.via_object_id for dep in deps if dep.via_object_id}
        obj_names = {}
        if obj_ids:
            objs = self.session.execute(
                select(MigrationObject.id, MigrationObject.object_name).where(
                    MigrationObject.id.in_(obj_ids)
                )
            ).all()
            obj_names = {o.id: o.object_name for o in objs}
        
        return [
            FlowDepView(
                id=dep.id,
                project_id=dep.project_id,
                upstream_package_id=dep.upstream_package_id,
                downstream_package_id=dep.downstream_package_id,
                via_object_id=dep.via_object_id,
                relationship_type=dep.relationship_type,
                is_confirmed=dep.is_confirmed,
                auto_detected=dep.auto_detected,
                upstream_package_name=pkg_names.get(dep.upstream_package_id),
                downstream_package_name=pkg_names.get(dep.downstream_package_id),
                via_object_name=obj_names.get(dep.via_object_id) if dep.via_object_id else None,
            )
            for dep in deps
        ]
    
    def confirm_dependency(
        self,
        dep_id: uuid.UUID,
        is_confirmed: bool,
    ) -> PackageFlowDep | None:
        """Confirm or reject a dependency.
        
        Args:
            dep_id: Dependency ID
            is_confirmed: Whether to confirm
            
        Returns:
            Updated dependency or None
        """
        dep = self.session.execute(
            select(PackageFlowDep).where(PackageFlowDep.id == dep_id)
        ).scalar_one_or_none()
        
        if dep:
            dep.is_confirmed = is_confirmed
            self.session.flush()
        
        return dep
    
    def create_manual_dependency(
        self,
        project_id: uuid.UUID,
        upstream_id: uuid.UUID,
        downstream_id: uuid.UUID,
        relationship_type: str = "inferred",
    ) -> PackageFlowDep:
        """Create a manual dependency (human-specified).
        
        Args:
            project_id: Project ID
            upstream_id: Upstream package ID
            downstream_id: Downstream package ID
            relationship_type: Type of relationship
            
        Returns:
            Created dependency
        """
        dep = PackageFlowDep(
            id=uuid.uuid4(),
            project_id=project_id,
            upstream_package_id=upstream_id,
            downstream_package_id=downstream_id,
            via_object_id=None,
            relationship_type=relationship_type,
            auto_detected=False,
            is_confirmed=True,
        )
        self.session.add(dep)
        self.session.flush()
        return dep
    
    def delete_dependency(self, dep_id: uuid.UUID) -> bool:
        """Delete a dependency.
        
        Args:
            dep_id: Dependency ID
            
        Returns:
            True if deleted
        """
        dep = self.session.execute(
            select(PackageFlowDep).where(PackageFlowDep.id == dep_id)
        ).scalar_one_or_none()
        
        if dep:
            self.session.delete(dep)
            self.session.flush()
            return True
        
        return False
