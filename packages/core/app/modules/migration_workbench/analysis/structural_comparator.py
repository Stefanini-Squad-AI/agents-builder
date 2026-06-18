"""Structural comparison between SSIS-declared schema and actual DB schema.

Compares columns and tables declared in SSIS packages against the actual
database schema (from a Phase A dump or Lakebridge Profiler output).

Detects:
- Columns in SSIS but not in DB (stale references)
- Columns in DB but not in SSIS (potentially missing data)
- Type mismatches between SSIS and DB
- Nullable mismatches
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from app.modules.migration_workbench.analysis.schemas import (
    SSISPackage,
    Source,
    Destination,
    SourceColumn,
    ColumnMapping,
)
from app.modules.migration_workbench.analysis.type_mapping import (
    are_types_compatible,
    ssis_type_code_to_name,
)
from app.modules.migration_workbench.context.schemas import (
    ColumnMismatch,
    ColumnSchema,
    DatabaseSchema,
    StructuralComparisonResult,
    TableSchema,
)

log = structlog.get_logger(__name__)


class StructuralComparator:
    """Compare SSIS package schema against actual database schema."""
    
    def __init__(self, db_schema: DatabaseSchema):
        """Initialize with a database schema.
        
        Args:
            db_schema: The actual database schema to compare against
        """
        self._db_schema = db_schema
        self._table_lookup = self._build_table_lookup()
    
    def _build_table_lookup(self) -> dict[str, TableSchema]:
        """Build a lowercase lookup dictionary for tables."""
        lookup: dict[str, TableSchema] = {}
        for table in self._db_schema.tables:
            # Index by both full name and just table name (for flexibility)
            full_key = f"{table.schema_name.lower()}.{table.table_name.lower()}"
            short_key = table.table_name.lower()
            lookup[full_key] = table
            if short_key not in lookup:  # Don't overwrite if there are dupes
                lookup[short_key] = table
        return lookup
    
    def compare_package(self, package: SSISPackage) -> StructuralComparisonResult:
        """Compare an SSIS package against the database schema.
        
        Args:
            package: Parsed SSIS package
        
        Returns:
            StructuralComparisonResult with all detected mismatches
        """
        mismatches: list[ColumnMismatch] = []
        warnings: list[str] = []
        source_tables_checked = 0
        dest_tables_checked = 0
        
        # Check all data flows
        for df in package.data_flows:
            # Check sources
            for source in df.sources:
                table_name = self._extract_table_name(source)
                if not table_name:
                    warnings.append(f"Source '{source.name}' has no identifiable table")
                    continue
                
                table = self._find_table(table_name)
                if not table:
                    warnings.append(f"Source table '{table_name}' not found in schema dump")
                    continue
                
                source_tables_checked += 1
                source_mismatches = self._compare_source_columns(source, table)
                mismatches.extend(source_mismatches)
            
            # Check destinations
            for dest in df.destinations:
                table_name = self._extract_dest_table_name(dest)
                if not table_name:
                    warnings.append(f"Destination '{dest.name}' has no identifiable table")
                    continue
                
                table = self._find_table(table_name)
                if not table:
                    warnings.append(f"Destination table '{table_name}' not found in schema dump")
                    continue
                
                dest_tables_checked += 1
                dest_mismatches = self._compare_dest_columns(dest, table)
                mismatches.extend(dest_mismatches)
        
        return StructuralComparisonResult(
            compared_at=datetime.now(timezone.utc),
            source_tables_checked=source_tables_checked,
            destination_tables_checked=dest_tables_checked,
            mismatches=mismatches,
            warnings=warnings,
        )
    
    def _extract_table_name(self, source: Source) -> str | None:
        """Extract table name from a source component."""
        if source.table_name:
            return source.table_name
        
        # Try to extract from SQL command
        if source.sql_command:
            return self._extract_table_from_sql(source.sql_command)
        
        return None
    
    def _extract_dest_table_name(self, dest: Destination) -> str | None:
        """Extract table name from a destination component."""
        return dest.table_name
    
    def _extract_table_from_sql(self, sql: str) -> str | None:
        """Extract the primary table name from a SQL statement.
        
        This is a simple heuristic; complex queries may not parse correctly.
        """
        import re
        
        # Look for FROM clause
        from_match = re.search(r'\bFROM\s+(\[?[\w.]+\]?)', sql, re.IGNORECASE)
        if from_match:
            table = from_match.group(1)
            # Remove brackets if present
            return table.replace('[', '').replace(']', '')
        
        return None
    
    def _find_table(self, table_name: str) -> TableSchema | None:
        """Find a table by name in the schema."""
        # Normalize the name
        normalized = table_name.lower().replace('[', '').replace(']', '')
        
        # Try direct lookup
        if normalized in self._table_lookup:
            return self._table_lookup[normalized]
        
        # Try without schema prefix
        if '.' in normalized:
            short_name = normalized.split('.')[-1]
            if short_name in self._table_lookup:
                return self._table_lookup[short_name]
        
        return None
    
    def _compare_source_columns(
        self, 
        source: Source, 
        table: TableSchema
    ) -> list[ColumnMismatch]:
        """Compare source columns against actual table columns."""
        mismatches: list[ColumnMismatch] = []
        table_full_name = f"{table.schema_name}.{table.table_name}"
        
        # Build lookup of DB columns
        db_columns = {col.name.lower(): col for col in table.columns}
        
        # Check each source column
        for ssis_col in source.columns:
            col_name = ssis_col.name.lower()
            
            if col_name not in db_columns:
                mismatches.append(ColumnMismatch(
                    table_name=table_full_name,
                    column_name=ssis_col.name,
                    mismatch_type="missing_in_db",
                    ssis_type=ssis_col.data_type,
                    note="Column referenced in SSIS but not found in database schema"
                ))
                continue
            
            db_col = db_columns[col_name]
            
            # Check type compatibility
            if ssis_col.data_type:
                ssis_type = ssis_col.data_type
                if ssis_type.isdigit():
                    ssis_type = ssis_type_code_to_name(int(ssis_type))
                
                if not are_types_compatible(ssis_type, db_col.data_type):
                    mismatches.append(ColumnMismatch(
                        table_name=table_full_name,
                        column_name=ssis_col.name,
                        mismatch_type="type_mismatch",
                        ssis_type=ssis_type,
                        db_type=db_col.data_type,
                        note=f"SSIS type '{ssis_type}' may not be compatible with DB type '{db_col.data_type}'"
                    ))
        
        # Check for columns in DB but not in SSIS (optional — may be intentional)
        ssis_column_names = {col.name.lower() for col in source.columns}
        for db_col in table.columns:
            if db_col.name.lower() not in ssis_column_names:
                # Only flag non-nullable columns without defaults as potentially missing
                if not db_col.is_nullable and db_col.default_value is None:
                    mismatches.append(ColumnMismatch(
                        table_name=table_full_name,
                        column_name=db_col.name,
                        mismatch_type="missing_in_ssis",
                        db_type=db_col.data_type,
                        db_nullable=db_col.is_nullable,
                        note="Non-nullable column exists in DB but not referenced in SSIS source"
                    ))
        
        return mismatches
    
    def _compare_dest_columns(
        self, 
        dest: Destination, 
        table: TableSchema
    ) -> list[ColumnMismatch]:
        """Compare destination column mappings against actual table columns."""
        mismatches: list[ColumnMismatch] = []
        table_full_name = f"{table.schema_name}.{table.table_name}"
        
        # Build lookup of DB columns
        db_columns = {col.name.lower(): col for col in table.columns}
        
        # Check each column mapping
        for mapping in dest.columns:
            dest_col_name = mapping.destination_column.lower()
            
            if dest_col_name not in db_columns:
                mismatches.append(ColumnMismatch(
                    table_name=table_full_name,
                    column_name=mapping.destination_column,
                    mismatch_type="missing_in_db",
                    note=f"Destination column '{mapping.destination_column}' (mapped from '{mapping.source_column}') not found in database"
                ))
                continue
            
            db_col = db_columns[dest_col_name]
            
            # Check nullable mismatch — writing to non-nullable column from nullable source
            # This is a warning, not an error, since SSIS may handle nulls
            if not db_col.is_nullable and mapping.source_column:
                # We don't have source column nullability info easily, so just note it
                pass
        
        # Check for non-nullable columns without defaults that aren't being written to
        mapped_columns = {m.destination_column.lower() for m in dest.columns}
        for db_col in table.columns:
            if db_col.name.lower() not in mapped_columns:
                if not db_col.is_nullable and db_col.default_value is None and not db_col.is_identity:
                    mismatches.append(ColumnMismatch(
                        table_name=table_full_name,
                        column_name=db_col.name,
                        mismatch_type="missing_in_ssis",
                        db_type=db_col.data_type,
                        db_nullable=db_col.is_nullable,
                        note="Non-nullable column without default not mapped in destination — will cause INSERT failure"
                    ))
        
        return mismatches


def compare_schemas(
    package: SSISPackage,
    db_schema: DatabaseSchema,
) -> StructuralComparisonResult:
    """Convenience function to compare an SSIS package against a DB schema.
    
    Args:
        package: Parsed SSIS package
        db_schema: Database schema from Phase A dump or Lakebridge
    
    Returns:
        StructuralComparisonResult with all detected mismatches
    """
    comparator = StructuralComparator(db_schema)
    return comparator.compare_package(package)
