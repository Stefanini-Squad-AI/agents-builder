"""Connection points extraction from parsed packages.

Extracts source/target tables, files, and connections from parsed ETL packages
to populate the PackageConnectionPoints model.
"""

from __future__ import annotations

import re
from typing import Any

from app.modules.migration_workbench.analysis.schemas import (
    ColumnLineage,
    ExtractedConnectionPoints,
    FileRef,
    SSISPackage,
    TableRef,
)


class ConnectionPointsExtractor:
    """Extracts connection points from parsed ETL packages.
    
    Connection points include:
    - Source tables/views
    - Destination tables
    - Source/destination files
    - Declared package dependencies (Execute Package Tasks)
    """
    
    def extract(self, package: SSISPackage) -> ExtractedConnectionPoints:
        """Extract all connection points from a parsed package.
        
        Args:
            package: Parsed SSIS package
            
        Returns:
            ExtractedConnectionPoints with sources, targets, and dependencies
        """
        source_tables: list[TableRef] = []
        target_tables: list[TableRef] = []
        source_files: list[FileRef] = []
        target_files: list[FileRef] = []
        source_connections: list[str] = []
        target_connections: list[str] = []
        predecessors: list[str] = []
        column_lineage: list[ColumnLineage] = []
        
        has_dynamic_sources = False
        has_dynamic_destinations = False
        warnings: list[str] = []
        
        # Build connection manager lookup for server/database info
        conn_lookup = {cm.name: cm for cm in package.connection_managers}
        
        # Process data flows
        for data_flow in package.data_flows:
            # Sources
            for source in data_flow.sources:
                if self._is_file_component(source.component_type):
                    source_files.append(FileRef(
                        connection_ref=source.connection_ref,
                        file_type=self._infer_file_type(source.component_type),
                    ))
                else:
                    # Database source
                    table = self._extract_table_from_source(source, conn_lookup)
                    if table:
                        source_tables.append(table)
                    
                    if source.connection_ref:
                        source_connections.append(source.connection_ref)
                
                # Check for dynamic sources
                if source.sql_command and self._is_dynamic(source.sql_command):
                    has_dynamic_sources = True
            
            # Destinations
            for dest in data_flow.destinations:
                if self._is_file_component(dest.component_type):
                    target_files.append(FileRef(
                        connection_ref=dest.connection_ref,
                        file_type=self._infer_file_type(dest.component_type),
                    ))
                else:
                    # Database destination
                    table = self._extract_table_from_destination(dest, conn_lookup)
                    if table:
                        target_tables.append(table)
                    
                    if dest.connection_ref:
                        target_connections.append(dest.connection_ref)
            
            # Column lineage
            for dest in data_flow.destinations:
                if dest.table_name:
                    for mapping in dest.columns:
                        # Try to find source table
                        source_table = self._find_source_table(data_flow, mapping.source_column)
                        if source_table:
                            column_lineage.append(ColumnLineage(
                                source_table=source_table,
                                source_column=mapping.source_column,
                                target_table=dest.table_name,
                                target_column=mapping.destination_column,
                            ))
        
        # Process Execute SQL Tasks for additional table references
        for task in package.tasks:
            if task.sql_statement:
                tables = self._extract_tables_from_sql(task.sql_statement)
                # Add to sources (we can't always determine if it's source or target)
                for table in tables.get("tables", []):
                    # Avoid duplicates
                    if not any(t.table_name == table for t in source_tables):
                        # Full SQL — no truncation for richer LLM context
                        source_tables.append(TableRef(
                            table_name=table,
                            connection_ref=task.connection_ref,
                            access_type="sql",
                            sql_query=task.sql_statement,
                        ))
                
                if task.connection_ref:
                    source_connections.append(task.connection_ref)
                
                if self._is_dynamic(task.sql_statement):
                    has_dynamic_sources = True
            
            # Check for Execute Package Task (dependencies)
            if task.task_type.value == "Execute Package Task":
                child_pkg = self._extract_child_package_name(task)
                if child_pkg:
                    predecessors.append(child_pkg)
            
            # Recurse into containers
            for child in task.child_tasks:
                if child.sql_statement and child.connection_ref:
                    source_connections.append(child.connection_ref)
        
        # Deduplicate
        source_connections = list(set(source_connections))
        target_connections = list(set(target_connections))
        predecessors = list(set(predecessors))
        
        return ExtractedConnectionPoints(
            source_tables=source_tables,
            source_files=source_files,
            source_connections=source_connections,
            target_tables=target_tables,
            target_files=target_files,
            target_connections=target_connections,
            declared_predecessors=predecessors,
            column_lineage=column_lineage,
            has_dynamic_sources=has_dynamic_sources,
            has_dynamic_destinations=has_dynamic_destinations,
            extraction_warnings=warnings,
        )
    
    def _is_file_component(self, component_type: str) -> bool:
        """Check if component type is file-based."""
        file_types = ["flat file", "excel", "raw file"]
        return any(ft in component_type.lower() for ft in file_types)
    
    def _infer_file_type(self, component_type: str) -> str:
        """Infer file type from component type."""
        comp_lower = component_type.lower()
        if "excel" in comp_lower:
            return "excel"
        elif "flat file" in comp_lower:
            return "csv"
        elif "raw file" in comp_lower:
            return "raw"
        return "unknown"
    
    def _extract_table_from_source(
        self, source: Any, conn_lookup: dict
    ) -> TableRef | None:
        """Extract table reference from a source component."""
        if source.table_name:
            schema, table = self._parse_table_name(source.table_name)
            return TableRef(
                schema_name=schema,
                table_name=table,
                connection_ref=source.connection_ref,
                access_type="table",
            )
        elif source.sql_command:
            # Try to extract main table from SQL
            tables = self._extract_tables_from_sql(source.sql_command)
            if tables.get("from"):
                schema, table = self._parse_table_name(tables["from"][0])
                # Full SQL — no truncation for richer LLM context
                return TableRef(
                    schema_name=schema,
                    table_name=table,
                    connection_ref=source.connection_ref,
                    access_type="query",
                    sql_query=source.sql_command,
                )
        return None
    
    def _extract_table_from_destination(
        self, dest: Any, conn_lookup: dict
    ) -> TableRef | None:
        """Extract table reference from a destination component."""
        if dest.table_name:
            schema, table = self._parse_table_name(dest.table_name)
            return TableRef(
                schema_name=schema,
                table_name=table,
                connection_ref=dest.connection_ref,
                access_type="table",
            )
        return None
    
    def _parse_table_name(self, full_name: str) -> tuple[str | None, str]:
        """Parse table name into schema and table.
        
        Handles formats like:
        - TableName
        - [TableName]
        - schema.TableName
        - [schema].[TableName]
        - database.schema.TableName
        """
        # Remove brackets
        name = full_name.replace("[", "").replace("]", "").strip()
        
        parts = name.split(".")
        if len(parts) >= 2:
            # Take last two parts as schema.table
            return parts[-2], parts[-1]
        return None, parts[-1]
    
    def _extract_tables_from_sql(self, sql: str) -> dict[str, list[str]]:
        """Extract table names from SQL statement.
        
        Returns dict with 'from' (source tables) and 'into' (target tables).
        """
        result: dict[str, list[str]] = {"from": [], "into": [], "tables": []}
        
        # Normalize whitespace
        sql = " ".join(sql.split())
        
        # FROM clause tables
        from_pattern = r"\bFROM\s+(\[?\w+\]?(?:\.\[?\w+\]?)*)"
        for match in re.finditer(from_pattern, sql, re.IGNORECASE):
            table = match.group(1).replace("[", "").replace("]", "")
            result["from"].append(table)
            result["tables"].append(table)
        
        # JOIN tables
        join_pattern = r"\bJOIN\s+(\[?\w+\]?(?:\.\[?\w+\]?)*)"
        for match in re.finditer(join_pattern, sql, re.IGNORECASE):
            table = match.group(1).replace("[", "").replace("]", "")
            result["from"].append(table)
            result["tables"].append(table)
        
        # INSERT INTO tables
        insert_pattern = r"\bINSERT\s+INTO\s+(\[?\w+\]?(?:\.\[?\w+\]?)*)"
        for match in re.finditer(insert_pattern, sql, re.IGNORECASE):
            table = match.group(1).replace("[", "").replace("]", "")
            result["into"].append(table)
            result["tables"].append(table)
        
        # UPDATE tables
        update_pattern = r"\bUPDATE\s+(\[?\w+\]?(?:\.\[?\w+\]?)*)"
        for match in re.finditer(update_pattern, sql, re.IGNORECASE):
            table = match.group(1).replace("[", "").replace("]", "")
            result["into"].append(table)
            result["tables"].append(table)
        
        # DELETE FROM tables
        delete_pattern = r"\bDELETE\s+FROM\s+(\[?\w+\]?(?:\.\[?\w+\]?)*)"
        for match in re.finditer(delete_pattern, sql, re.IGNORECASE):
            table = match.group(1).replace("[", "").replace("]", "")
            result["into"].append(table)
            result["tables"].append(table)
        
        # TRUNCATE tables
        truncate_pattern = r"\bTRUNCATE\s+TABLE\s+(\[?\w+\]?(?:\.\[?\w+\]?)*)"
        for match in re.finditer(truncate_pattern, sql, re.IGNORECASE):
            table = match.group(1).replace("[", "").replace("]", "")
            result["into"].append(table)
            result["tables"].append(table)
        
        return result
    
    def _is_dynamic(self, text: str) -> bool:
        """Check if text contains dynamic/expression elements."""
        dynamic_indicators = [
            "@[",  # SSIS variable reference
            "?",   # Parameter marker
            "GETDATE()",
            "CONCAT(",
        ]
        return any(ind in text for ind in dynamic_indicators)
    
    def _find_source_table(self, data_flow: Any, column_name: str) -> str | None:
        """Try to find which source table a column came from."""
        for source in data_flow.sources:
            for col in source.columns:
                if col.name == column_name:
                    return source.table_name
        return None
    
    def _extract_child_package_name(self, task: Any) -> str | None:
        """Extract child package name from Execute Package Task."""
        # This would be in task.properties
        props = task.properties or {}
        
        # Common property names
        for key in ["PackageName", "PackageID", "PackagePath"]:
            if key in props:
                value = props[key]
                # Extract just the package name
                if "\\" in value:
                    return value.split("\\")[-1].replace(".dtsx", "")
                return value.replace(".dtsx", "")
        
        return None


def extract_connection_points(package: SSISPackage) -> ExtractedConnectionPoints:
    """Convenience function to extract connection points.
    
    Args:
        package: Parsed SSIS package
        
    Returns:
        Extracted connection points
    """
    extractor = ConnectionPointsExtractor()
    return extractor.extract(package)
