"""Object Registry for tracking tables/files/APIs across packages."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.migration_workbench.map.schemas import (
    ObjectCreate,
    ObjectDirection,
    ObjectView,
    ObjectWithPackages,
    PackageObjectRefCreate,
    PackageObjectRefView,
)
from app.modules.migration_workbench.models import (
    ETLPackage,
    MigrationObject,
    PackageObjectRef,
)


class ObjectRegistry:
    """Registry for tracking data objects across packages.
    
    When packages are analyzed, their source and target objects
    (tables, files, APIs) are registered here. This enables:
    - Relationship detection (Package A writes → Package B reads)
    - Lineage tracking
    - Impact analysis
    """
    
    def __init__(self, session: Session):
        """Initialize registry.
        
        Args:
            session: Database session
        """
        self.session = session
    
    def register_object(
        self,
        project_id: uuid.UUID,
        obj: ObjectCreate,
    ) -> MigrationObject:
        """Register or update a data object.
        
        If object already exists, merges discovered columns.
        
        Args:
            project_id: Project ID
            obj: Object to register
            
        Returns:
            The created or updated MigrationObject
        """
        # Check if object exists
        existing = self.session.execute(
            select(MigrationObject).where(
                MigrationObject.project_id == project_id,
                MigrationObject.object_type == obj.object_type.value,
                MigrationObject.object_name == obj.object_name,
            )
        ).scalar_one_or_none()
        
        if existing:
            # Merge columns if provided
            if obj.discovered_columns:
                existing_cols = existing.discovered_columns or []
                existing_names = {c.get("name") for c in existing_cols}
                for col in obj.discovered_columns:
                    if col.get("name") not in existing_names:
                        existing_cols.append(col)
                existing.discovered_columns = existing_cols
            
            # Update connection ref if not set
            if obj.connection_ref and not existing.connection_ref:
                existing.connection_ref = obj.connection_ref
            
            return existing
        
        # Create new object
        migration_obj = MigrationObject(
            id=uuid.uuid4(),
            project_id=project_id,
            object_type=obj.object_type.value,
            object_name=obj.object_name,
            connection_ref=obj.connection_ref,
            schema_name=obj.schema_name,
            database_name=obj.database_name,
            discovered_columns=obj.discovered_columns,
        )
        self.session.add(migration_obj)
        self.session.flush()
        
        return migration_obj
    
    def register_package_ref(
        self,
        package_id: uuid.UUID,
        ref: PackageObjectRefCreate,
        project_id: uuid.UUID,
    ) -> tuple[MigrationObject, PackageObjectRef]:
        """Register a package's reference to an object.
        
        Creates the object if it doesn't exist, then creates
        the reference from the package.
        
        Args:
            package_id: Package ID
            ref: Reference details
            project_id: Project ID
            
        Returns:
            Tuple of (object, reference)
        """
        # Register or get the object
        obj_create = ObjectCreate(
            object_type=ref.object_type,
            object_name=ref.object_name,
            connection_ref=ref.connection_ref,
            schema_name=ref.schema_name,
            database_name=ref.database_name,
            discovered_columns=None,
        )
        migration_obj = self.register_object(project_id, obj_create)
        
        # Check if reference already exists
        existing_ref = self.session.execute(
            select(PackageObjectRef).where(
                PackageObjectRef.package_id == package_id,
                PackageObjectRef.object_id == migration_obj.id,
                PackageObjectRef.direction == ref.direction.value,
            )
        ).scalar_one_or_none()
        
        if existing_ref:
            # Update existing reference
            if ref.columns_accessed:
                existing_cols = existing_ref.columns_accessed or []
                existing_ref.columns_accessed = list(set(existing_cols + ref.columns_accessed))
            return migration_obj, existing_ref
        
        # Create new reference
        pkg_ref = PackageObjectRef(
            id=uuid.uuid4(),
            package_id=package_id,
            object_id=migration_obj.id,
            direction=ref.direction.value,
            access_type=ref.access_type.value if ref.access_type else None,
            sql_fragment=ref.sql_fragment,
            columns_accessed=ref.columns_accessed,
            task_name=ref.task_name,
            extraction_confidence=ref.extraction_confidence,
        )
        self.session.add(pkg_ref)
        
        # Update object counts
        if ref.direction == ObjectDirection.WRITE:
            migration_obj.written_by_count += 1
        else:
            migration_obj.read_by_count += 1
        
        self.session.flush()
        return migration_obj, pkg_ref
    
    def register_package_objects(
        self,
        package_id: uuid.UUID,
        project_id: uuid.UUID,
        refs: list[PackageObjectRefCreate],
    ) -> list[tuple[MigrationObject, PackageObjectRef]]:
        """Register multiple object references for a package.
        
        Args:
            package_id: Package ID
            project_id: Project ID
            refs: List of references to register
            
        Returns:
            List of (object, reference) tuples
        """
        results = []
        for ref in refs:
            result = self.register_package_ref(package_id, ref, project_id)
            results.append(result)
        return results
    
    def get_object(
        self,
        project_id: uuid.UUID,
        object_type: str,
        object_name: str,
    ) -> MigrationObject | None:
        """Get an object by identity.
        
        Args:
            project_id: Project ID
            object_type: Type of object
            object_name: Name of object
            
        Returns:
            MigrationObject or None
        """
        return self.session.execute(
            select(MigrationObject).where(
                MigrationObject.project_id == project_id,
                MigrationObject.object_type == object_type,
                MigrationObject.object_name == object_name,
            )
        ).scalar_one_or_none()
    
    def get_object_by_id(self, object_id: uuid.UUID) -> MigrationObject | None:
        """Get an object by ID.
        
        Args:
            object_id: Object ID
            
        Returns:
            MigrationObject or None
        """
        return self.session.execute(
            select(MigrationObject).where(MigrationObject.id == object_id)
        ).scalar_one_or_none()
    
    def list_objects(
        self,
        project_id: uuid.UUID,
        object_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ObjectView]:
        """List objects in a project.
        
        Args:
            project_id: Project ID
            object_type: Optional filter by type
            limit: Max results
            offset: Pagination offset
            
        Returns:
            List of ObjectView
        """
        query = select(MigrationObject).where(
            MigrationObject.project_id == project_id
        )
        
        if object_type:
            query = query.where(MigrationObject.object_type == object_type)
        
        query = query.order_by(MigrationObject.object_name).limit(limit).offset(offset)
        
        objects = self.session.execute(query).scalars().all()
        return [ObjectView.model_validate(obj) for obj in objects]
    
    def get_object_with_packages(
        self,
        object_id: uuid.UUID,
    ) -> ObjectWithPackages | None:
        """Get object with list of packages that reference it.
        
        Args:
            object_id: Object ID
            
        Returns:
            ObjectWithPackages or None
        """
        obj = self.get_object_by_id(object_id)
        if not obj:
            return None
        
        # Get reading packages
        reading = self.session.execute(
            select(ETLPackage.package_name)
            .join(PackageObjectRef, PackageObjectRef.package_id == ETLPackage.id)
            .where(
                PackageObjectRef.object_id == object_id,
                PackageObjectRef.direction.in_(["read", "lookup"]),
            )
        ).scalars().all()
        
        # Get writing packages
        writing = self.session.execute(
            select(ETLPackage.package_name)
            .join(PackageObjectRef, PackageObjectRef.package_id == ETLPackage.id)
            .where(
                PackageObjectRef.object_id == object_id,
                PackageObjectRef.direction == "write",
            )
        ).scalars().all()
        
        return ObjectWithPackages(
            **ObjectView.model_validate(obj).model_dump(),
            reading_packages=list(reading),
            writing_packages=list(writing),
        )
    
    def get_package_refs(
        self,
        package_id: uuid.UUID,
        direction: str | None = None,
    ) -> list[PackageObjectRefView]:
        """Get all object references for a package.
        
        Args:
            package_id: Package ID
            direction: Optional filter by direction
            
        Returns:
            List of PackageObjectRefView
        """
        query = (
            select(PackageObjectRef, MigrationObject)
            .join(MigrationObject, PackageObjectRef.object_id == MigrationObject.id)
            .where(PackageObjectRef.package_id == package_id)
        )
        
        if direction:
            query = query.where(PackageObjectRef.direction == direction)
        
        results = self.session.execute(query).all()
        
        views = []
        for ref, obj in results:
            view = PackageObjectRefView(
                id=ref.id,
                package_id=ref.package_id,
                object_id=ref.object_id,
                direction=ref.direction,
                access_type=ref.access_type,
                sql_fragment=ref.sql_fragment,
                columns_accessed=ref.columns_accessed,
                task_name=ref.task_name,
                extraction_confidence=ref.extraction_confidence,
                object_name=obj.object_name,
                object_type=obj.object_type,
            )
            views.append(view)
        
        return views
    
    def count_objects(self, project_id: uuid.UUID) -> int:
        """Count objects in a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            Object count
        """
        return self.session.execute(
            select(func.count(MigrationObject.id)).where(
                MigrationObject.project_id == project_id
            )
        ).scalar_one()
    
    def get_objects_written_by(
        self,
        package_id: uuid.UUID,
    ) -> list[MigrationObject]:
        """Get all objects written by a package.
        
        Args:
            package_id: Package ID
            
        Returns:
            List of MigrationObject
        """
        return self.session.execute(
            select(MigrationObject)
            .join(PackageObjectRef, PackageObjectRef.object_id == MigrationObject.id)
            .where(
                PackageObjectRef.package_id == package_id,
                PackageObjectRef.direction == "write",
            )
        ).scalars().all()
    
    def get_objects_read_by(
        self,
        package_id: uuid.UUID,
    ) -> list[MigrationObject]:
        """Get all objects read by a package.
        
        Args:
            package_id: Package ID
            
        Returns:
            List of MigrationObject
        """
        return self.session.execute(
            select(MigrationObject)
            .join(PackageObjectRef, PackageObjectRef.object_id == MigrationObject.id)
            .where(
                PackageObjectRef.package_id == package_id,
                PackageObjectRef.direction.in_(["read", "lookup"]),
            )
        ).scalars().all()
    
    def get_packages_reading_object(
        self,
        object_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        """Get package IDs that read an object.
        
        Args:
            object_id: Object ID
            
        Returns:
            List of package IDs
        """
        return list(self.session.execute(
            select(PackageObjectRef.package_id).where(
                PackageObjectRef.object_id == object_id,
                PackageObjectRef.direction.in_(["read", "lookup"]),
            )
        ).scalars().all())
    
    def get_packages_writing_object(
        self,
        object_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        """Get package IDs that write to an object.
        
        Args:
            object_id: Object ID
            
        Returns:
            List of package IDs
        """
        return list(self.session.execute(
            select(PackageObjectRef.package_id).where(
                PackageObjectRef.object_id == object_id,
                PackageObjectRef.direction == "write",
            )
        ).scalars().all())
