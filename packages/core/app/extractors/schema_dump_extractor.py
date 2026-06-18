"""Extractor for database schema dump JSON files.

Parses uploaded schema dump files (JSON) into DatabaseSchema objects.
These dumps are produced by:
- `workshop schema-dump` CLI command (Phase A)
- Lakebridge Profiler (Phase B)
- Manual JSON construction

The extractor validates the JSON against the DatabaseSchema Pydantic model
and produces a markdown summary for the artifact's content_md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog
from pydantic import ValidationError

from app.extractors.base import Extractor, ExtractionResult, truncate_markdown
from app.modules.migration_workbench.context.schemas import (
    ColumnSchema,
    DatabaseSchema,
    TableSchema,
)

log = structlog.get_logger(__name__)


class SchemaDumpExtractor(Extractor):
    """Extracts database schema information from JSON dump files."""
    
    name = "schema_dump"
    
    def can_handle(self, mime_type: str | None, ext: str) -> bool:
        """Handle .json files that contain schema dumps.
        
        We're liberal with mime_type since JSON is often served as
        application/json, text/json, or even text/plain.
        """
        return ext == "json"
    
    def extract(self, path: Path) -> ExtractionResult:
        """Extract schema from JSON dump file.
        
        Args:
            path: Path to the JSON schema dump file
        
        Returns:
            ExtractionResult with markdown summary and validated schema
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            log.warning("schema_dump_invalid_json", path=str(path), error=str(e))
            return ExtractionResult(
                content_md=f"# Schema Dump Error\n\nInvalid JSON: {e}",
                content_md_truncated=False,
                extractor_used=self.name,
                error=f"Invalid JSON: {e}",
            )
        except Exception as e:
            log.warning("schema_dump_read_error", path=str(path), error=str(e))
            return ExtractionResult(
                content_md=f"# Schema Dump Error\n\nFailed to read file: {e}",
                content_md_truncated=False,
                extractor_used=self.name,
                error=f"Read error: {e}",
            )
        
        # Check if this looks like a schema dump
        if not self._looks_like_schema_dump(data):
            # Return generic JSON extraction (fall through to json extractor)
            return ExtractionResult(
                content_md=f"# JSON File\n\n```json\n{json.dumps(data, indent=2)[:10000]}\n```",
                content_md_truncated=False,
                extractor_used="json",
                error=None,
            )
        
        # Validate against DatabaseSchema model
        try:
            schema = DatabaseSchema.model_validate(data)
        except ValidationError as e:
            log.warning("schema_dump_validation_error", path=str(path), error=str(e))
            return ExtractionResult(
                content_md=self._format_validation_error(data, e),
                content_md_truncated=False,
                extractor_used=self.name,
                error=f"Schema validation failed: {e.error_count()} errors",
            )
        
        # Generate markdown summary
        md_content = self._format_schema_markdown(schema)
        truncated_content, was_truncated = truncate_markdown(md_content)
        
        return ExtractionResult(
            content_md=truncated_content,
            content_md_truncated=was_truncated,
            extractor_used=self.name,
            error=None,
        )
    
    def _looks_like_schema_dump(self, data: Any) -> bool:
        """Check if JSON data looks like a database schema dump."""
        if not isinstance(data, dict):
            return False
        
        # Must have at least dialect and tables
        has_dialect = "dialect" in data
        has_tables = "tables" in data and isinstance(data.get("tables"), list)
        has_database = "database_name" in data
        
        return has_dialect or (has_tables and has_database)
    
    def _format_validation_error(self, data: dict, error: ValidationError) -> str:
        """Format a validation error as readable markdown."""
        lines = [
            "# Schema Dump Validation Error",
            "",
            "The uploaded JSON file appears to be a schema dump but doesn't match the expected format.",
            "",
            "## Errors",
            "",
        ]
        
        for err in error.errors()[:10]:  # Limit to 10 errors
            loc = " → ".join(str(x) for x in err["loc"])
            lines.append(f"- **{loc}**: {err['msg']}")
        
        if error.error_count() > 10:
            lines.append(f"\n... and {error.error_count() - 10} more errors")
        
        lines.extend([
            "",
            "## Expected Format",
            "",
            "The schema dump should follow this structure:",
            "",
            "```json",
            "{",
            '  "dialect": "mssql",',
            '  "database_name": "MyDB",',
            '  "extracted_at": "2026-01-01T00:00:00Z",',
            '  "tables": [',
            '    {',
            '      "schema_name": "dbo",',
            '      "table_name": "Customers",',
            '      "columns": [',
            '        {"name": "ID", "ordinal_position": 1, "data_type": "int", ...}',
            "      ]",
            "    }",
            "  ]",
            "}",
            "```",
        ])
        
        return "\n".join(lines)
    
    def _format_schema_markdown(self, schema: DatabaseSchema) -> str:
        """Format a validated schema as detailed markdown."""
        lines = [
            f"# Database Schema: {schema.database_name}",
            "",
            f"**Dialect:** {schema.dialect.value}",
            f"**Extracted At:** {schema.extracted_at.isoformat()}",
            f"**Extraction Method:** {schema.extraction_method}",
            "",
        ]
        
        # Summary statistics
        total_columns = sum(len(t.columns) for t in schema.tables)
        total_fks = sum(len(t.foreign_keys) for t in schema.tables)
        total_indexes = sum(len(t.indexes) for t in schema.tables)
        
        lines.extend([
            "## Summary",
            "",
            f"- **Tables:** {len(schema.tables)}",
            f"- **Views:** {len(schema.views)}",
            f"- **Total Columns:** {total_columns}",
            f"- **Foreign Keys:** {total_fks}",
            f"- **Indexes:** {total_indexes}",
            f"- **Stored Procedures:** {len(schema.stored_procedures)}",
            f"- **Functions:** {len(schema.functions)}",
            "",
        ])
        
        # Tables section
        if schema.tables:
            lines.append("## Tables\n")
            
            for table in schema.tables:
                row_info = f" (~{table.row_count:,} rows)" if table.row_count else ""
                lines.append(f"### {table.schema_name}.{table.table_name}{row_info}\n")
                
                # Columns table
                lines.append("| Column | Type | Nullable | PK | FK | Default |")
                lines.append("|--------|------|----------|----|----|---------|")
                
                for col in table.columns:
                    type_str = self._format_column_type(col)
                    nullable = "✓" if col.is_nullable else "✗"
                    pk = "✓" if col.is_primary_key else ""
                    fk = "✓" if col.is_foreign_key else ""
                    default = col.default_value[:30] + "..." if col.default_value and len(col.default_value) > 30 else (col.default_value or "")
                    lines.append(f"| {col.name} | {type_str} | {nullable} | {pk} | {fk} | {default} |")
                
                lines.append("")
                
                # Primary key
                if table.primary_key:
                    pk_cols = ", ".join(table.primary_key.columns)
                    lines.append(f"**Primary Key:** `{table.primary_key.name}` ({pk_cols})\n")
                
                # Foreign keys
                if table.foreign_keys:
                    lines.append("**Foreign Keys:**")
                    for fk in table.foreign_keys:
                        fk_cols = ", ".join(fk.columns)
                        ref_cols = ", ".join(fk.referenced_columns)
                        ref_schema = f"{fk.referenced_schema}." if fk.referenced_schema else ""
                        lines.append(f"- `{fk.name}`: ({fk_cols}) → {ref_schema}{fk.referenced_table}({ref_cols})")
                    lines.append("")
                
                # Indexes
                if table.indexes:
                    lines.append("**Indexes:**")
                    for idx in table.indexes:
                        idx_cols = ", ".join(idx.columns)
                        unique_tag = " UNIQUE" if idx.is_unique else ""
                        clustered_tag = " CLUSTERED" if idx.is_clustered else ""
                        lines.append(f"- `{idx.name}`{unique_tag}{clustered_tag}: ({idx_cols})")
                    lines.append("")
        
        # Views section
        if schema.views:
            lines.append("## Views\n")
            for view in schema.views:
                lines.append(f"### {view.schema_name}.{view.view_name}\n")
                if view.definition:
                    # Truncate long definitions
                    definition = view.definition[:2000]
                    if len(view.definition) > 2000:
                        definition += "\n-- ... (definition truncated)"
                    lines.append(f"```sql\n{definition}\n```\n")
        
        # Stored procedures section
        if schema.stored_procedures:
            lines.append("## Stored Procedures\n")
            for sp in schema.stored_procedures:
                lines.append(f"- `{sp.schema_name}.{sp.procedure_name}`")
            lines.append("")
        
        # Functions section
        if schema.functions:
            lines.append("## Functions\n")
            for fn in schema.functions:
                ret_type = f" → {fn.return_type}" if fn.return_type else ""
                lines.append(f"- `{fn.schema_name}.{fn.function_name}`{ret_type}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_column_type(self, col: ColumnSchema) -> str:
        """Format column type with precision/scale/length."""
        base = col.data_type
        
        # Handle types with precision/scale
        if col.precision and col.scale:
            return f"{base}({col.precision},{col.scale})"
        elif col.precision:
            return f"{base}({col.precision})"
        elif col.max_length and col.max_length > 0:
            # -1 often means MAX in SQL Server
            if col.max_length == -1:
                return f"{base}(MAX)"
            return f"{base}({col.max_length})"
        
        return base


def parse_schema_dump(path: Path) -> DatabaseSchema | None:
    """Parse a schema dump file and return the DatabaseSchema object.
    
    This is a convenience function for code that needs the parsed schema
    object directly, rather than the markdown extraction result.
    
    Args:
        path: Path to the JSON schema dump file
    
    Returns:
        DatabaseSchema object if valid, None otherwise
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return DatabaseSchema.model_validate(data)
    except (json.JSONDecodeError, ValidationError, FileNotFoundError) as e:
        log.warning("schema_dump_parse_error", path=str(path), error=str(e))
        return None


def parse_schema_dump_from_json(data: dict) -> DatabaseSchema | None:
    """Parse a schema dump from a dictionary.
    
    Useful when the JSON has already been loaded (e.g., from an API request).
    
    Args:
        data: Dictionary containing schema dump data
    
    Returns:
        DatabaseSchema object if valid, None otherwise
    """
    try:
        return DatabaseSchema.model_validate(data)
    except ValidationError as e:
        log.warning("schema_dump_parse_error", error=str(e))
        return None
