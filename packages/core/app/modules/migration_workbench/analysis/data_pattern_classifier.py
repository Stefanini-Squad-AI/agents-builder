"""Data pattern classification for ETL tasks.

Analyzes SQL statements to detect data patterns (MERGE, SCD, CDC, etc.)
and assign Medallion layer (Bronze/Silver/Gold).
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field

from app.modules.migration_workbench.analysis.schemas import Task, TaskType


class DataPatternCategory(str, Enum):
    """Category of data pattern."""
    
    LOAD = "load"
    SCD = "scd"
    DELETE = "delete"
    INCREMENTAL = "incremental"
    TRANSFORM = "transform"
    UNKNOWN = "unknown"


class DataPattern(str, Enum):
    """All 15 data patterns for ETL tasks."""
    
    # Load Patterns
    MERGE = "merge"
    DELETE_INSERT = "delete_insert"
    APPEND_ONLY = "append_only"
    UPDATE_IN_PLACE = "update_in_place"
    
    # SCD Patterns
    SCD_TYPE_1 = "scd_type_1"
    SCD_TYPE_2 = "scd_type_2"
    SCD_TYPE_3 = "scd_type_3"
    
    # Delete Patterns
    SOFT_DELETE = "soft_delete"
    HARD_DELETE = "hard_delete"
    
    # Incremental Patterns
    WATERMARK = "watermark"
    CDC = "cdc"
    DELTA_DIFF = "delta_diff"
    
    # Transform Patterns
    LOOKUP_ENRICH = "lookup_enrich"
    AGGREGATE = "aggregate"
    PIVOT_UNPIVOT = "pivot_unpivot"
    
    # Unknown
    UNKNOWN = "unknown"


class MedallionLayer(str, Enum):
    """Medallion architecture layer."""
    
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    NOT_APPLICABLE = "n/a"


# Pattern metadata
PATTERN_INFO: dict[DataPattern, dict] = {
    DataPattern.MERGE: {
        "name": "MERGE (Upsert)",
        "category": DataPatternCategory.LOAD,
        "description": "Update existing rows and insert new rows",
    },
    DataPattern.DELETE_INSERT: {
        "name": "DELETE + INSERT (Full Reload)",
        "category": DataPatternCategory.LOAD,
        "description": "Truncate then insert fresh copy",
    },
    DataPattern.APPEND_ONLY: {
        "name": "APPEND Only",
        "category": DataPatternCategory.LOAD,
        "description": "Insert only, no updates or deletes",
    },
    DataPattern.UPDATE_IN_PLACE: {
        "name": "UPDATE In-Place",
        "category": DataPatternCategory.LOAD,
        "description": "Update existing rows only",
    },
    DataPattern.SCD_TYPE_1: {
        "name": "SCD Type 1 (Overwrite)",
        "category": DataPatternCategory.SCD,
        "description": "Overwrite old values, no history",
    },
    DataPattern.SCD_TYPE_2: {
        "name": "SCD Type 2 (History)",
        "category": DataPatternCategory.SCD,
        "description": "Track history with effective dates",
    },
    DataPattern.SCD_TYPE_3: {
        "name": "SCD Type 3 (Previous Value)",
        "category": DataPatternCategory.SCD,
        "description": "Track current and previous value only",
    },
    DataPattern.SOFT_DELETE: {
        "name": "Soft Delete",
        "category": DataPatternCategory.DELETE,
        "description": "Mark as deleted, preserve record",
    },
    DataPattern.HARD_DELETE: {
        "name": "Hard Delete",
        "category": DataPatternCategory.DELETE,
        "description": "Physically remove rows",
    },
    DataPattern.WATERMARK: {
        "name": "Watermark (Incremental)",
        "category": DataPatternCategory.INCREMENTAL,
        "description": "Load records newer than last run",
    },
    DataPattern.CDC: {
        "name": "CDC (Change Data Capture)",
        "category": DataPatternCategory.INCREMENTAL,
        "description": "Process I/U/D change events",
    },
    DataPattern.DELTA_DIFF: {
        "name": "Delta Diff (Compare)",
        "category": DataPatternCategory.INCREMENTAL,
        "description": "Compare and sync differences",
    },
    DataPattern.LOOKUP_ENRICH: {
        "name": "Lookup Enrichment",
        "category": DataPatternCategory.TRANSFORM,
        "description": "Join with reference tables",
    },
    DataPattern.AGGREGATE: {
        "name": "Aggregation",
        "category": DataPatternCategory.TRANSFORM,
        "description": "Group and summarize data",
    },
    DataPattern.PIVOT_UNPIVOT: {
        "name": "Pivot / Unpivot",
        "category": DataPatternCategory.TRANSFORM,
        "description": "Reshape between row/column formats",
    },
    DataPattern.UNKNOWN: {
        "name": "Unknown",
        "category": DataPatternCategory.UNKNOWN,
        "description": "Pattern could not be determined",
    },
}


class TaskPatternResult(BaseModel):
    """Pattern classification result for a single task."""
    
    task_name: str
    pattern: DataPattern
    pattern_name: str = ""
    category: DataPatternCategory = DataPatternCategory.UNKNOWN
    layer: MedallionLayer = MedallionLayer.NOT_APPLICABLE
    target_table: str | None = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    detection_evidence: list[str] = Field(default_factory=list)
    
    def model_post_init(self, _ctx: object) -> None:
        info = PATTERN_INFO.get(self.pattern, {})
        if not self.pattern_name:
            self.pattern_name = info.get("name", self.pattern.value)
        if self.category == DataPatternCategory.UNKNOWN:
            self.category = info.get("category", DataPatternCategory.UNKNOWN)


class PackageDesignAnalysis(BaseModel):
    """Complete design analysis for a package."""
    
    package_name: str
    task_patterns: list[TaskPatternResult] = Field(default_factory=list)
    
    # Summary counts
    pattern_summary: dict[str, int] = Field(default_factory=dict)
    layer_summary: dict[str, int] = Field(default_factory=dict)
    
    # Performance hints
    photon_eligible: bool = True
    performance_notes: list[str] = Field(default_factory=list)
    
    def model_post_init(self, _ctx: object) -> None:
        if not self.pattern_summary:
            self.pattern_summary = {}
            for tp in self.task_patterns:
                key = tp.pattern.value
                self.pattern_summary[key] = self.pattern_summary.get(key, 0) + 1
        
        if not self.layer_summary:
            self.layer_summary = {}
            for tp in self.task_patterns:
                key = tp.layer.value
                self.layer_summary[key] = self.layer_summary.get(key, 0) + 1


class DataPatternClassifier:
    """Classifies SQL tasks into data patterns and Medallion layers.
    
    Uses SQL keyword detection and task name heuristics.
    """
    
    def classify_task(self, task: Task) -> TaskPatternResult:
        """Classify a single task into a data pattern."""
        sql_upper = (task.sql_statement or "").upper()
        sql_orig = task.sql_statement or ""
        name = task.name.lower()
        evidence: list[str] = []
        
        # Skip non-SQL tasks
        if task.task_type != TaskType.EXECUTE_SQL or not sql_upper:
            return TaskPatternResult(
                task_name=task.name,
                pattern=DataPattern.UNKNOWN,
                layer=MedallionLayer.NOT_APPLICABLE,
                confidence=0.0,
                detection_evidence=["Not an Execute SQL task or no SQL"],
            )
        
        # Detect pattern
        pattern = self._detect_pattern(sql_upper, name, evidence)
        
        # Detect target table (preserve original case)
        target_table = self._extract_target_table(sql_orig)
        
        # Detect layer
        layer = self._detect_layer(sql_upper, name, pattern)
        
        # Calculate confidence
        confidence = min(0.9, 0.3 + 0.15 * len(evidence))
        
        return TaskPatternResult(
            task_name=task.name,
            pattern=pattern,
            layer=layer,
            target_table=target_table,
            confidence=confidence,
            detection_evidence=evidence,
        )
    
    def classify_tasks(self, tasks: list[Task]) -> list[TaskPatternResult]:
        """Classify multiple tasks."""
        results = []
        for task in self._flatten_tasks(tasks):
            if task.task_type == TaskType.EXECUTE_SQL:
                results.append(self.classify_task(task))
        return results
    
    def analyze_package(self, package_name: str, tasks: list[Task]) -> PackageDesignAnalysis:
        """Analyze all tasks in a package."""
        task_patterns = self.classify_tasks(tasks)
        
        # Determine Photon eligibility (no script tasks)
        has_scripts = any(
            t.task_type == TaskType.SCRIPT
            for t in self._flatten_tasks(tasks)
        )
        
        notes = []
        if has_scripts:
            notes.append("Contains Script Tasks - may not be fully Photon eligible")
        
        # Check for patterns that benefit from specific optimizations
        patterns = {tp.pattern for tp in task_patterns}
        
        if DataPattern.LOOKUP_ENRICH in patterns:
            notes.append("Contains lookups - consider BROADCAST hints for small dimensions")
        
        if DataPattern.AGGREGATE in patterns:
            notes.append("Contains aggregations - consider Z-ORDER on group-by columns")
        
        # Check for DATEDIFF patterns (range join hint)
        for t in self._flatten_tasks(tasks):
            if t.sql_statement and "DATEDIFF" in t.sql_statement.upper():
                notes.append("DATEDIFF detected - consider range join optimization")
                break
        
        return PackageDesignAnalysis(
            package_name=package_name,
            task_patterns=task_patterns,
            photon_eligible=not has_scripts,
            performance_notes=notes,
        )
    
    # -------------------------------------------------------------------------
    # Pattern Detection
    # -------------------------------------------------------------------------
    
    def _detect_pattern(
        self, sql: str, name: str, evidence: list[str]
    ) -> DataPattern:
        """Detect the data pattern from SQL and task name."""
        
        # CDC (check first - specific markers)
        if self._is_cdc(sql, name):
            evidence.append("CDC markers detected")
            return DataPattern.CDC
        
        # SCD Type 2 (check before MERGE - has specific markers)
        if self._is_scd_type_2(sql, name):
            evidence.append("SCD Type 2 columns detected")
            return DataPattern.SCD_TYPE_2
        
        # SCD Type 3
        if self._is_scd_type_3(sql, name):
            evidence.append("SCD Type 3 pattern detected")
            return DataPattern.SCD_TYPE_3
        
        # Soft Delete
        if self._is_soft_delete(sql, name):
            evidence.append("Soft delete pattern detected")
            return DataPattern.SOFT_DELETE
        
        # MERGE
        if "MERGE INTO" in sql or "MERGE " in sql:
            evidence.append("MERGE keyword found")
            return DataPattern.MERGE
        
        # Hard Delete
        if self._is_hard_delete(sql, name):
            evidence.append("Hard delete pattern detected")
            return DataPattern.HARD_DELETE
        
        # DELETE + INSERT (Full Reload)
        if self._is_delete_insert(sql, name):
            evidence.append("DELETE/TRUNCATE + INSERT pattern")
            return DataPattern.DELETE_INSERT
        
        # Watermark (Incremental)
        if self._is_watermark(sql, name):
            evidence.append("Watermark/incremental pattern")
            return DataPattern.WATERMARK
        
        # Delta Diff
        if self._is_delta_diff(sql, name):
            evidence.append("Delta diff comparison pattern")
            return DataPattern.DELTA_DIFF
        
        # Pivot/Unpivot
        if self._is_pivot_unpivot(sql, name):
            evidence.append("Pivot/Unpivot transformation")
            return DataPattern.PIVOT_UNPIVOT
        
        # Aggregate
        if self._is_aggregate(sql, name):
            evidence.append("Aggregation pattern")
            return DataPattern.AGGREGATE
        
        # Lookup Enrichment
        if self._is_lookup_enrich(sql, name):
            evidence.append("Lookup/join enrichment")
            return DataPattern.LOOKUP_ENRICH
        
        # Update In Place
        if "UPDATE " in sql and "INSERT" not in sql:
            evidence.append("UPDATE without INSERT")
            return DataPattern.UPDATE_IN_PLACE
        
        # SCD Type 1 (MERGE without SCD2 markers)
        if "UPDATE " in sql and "INSERT" in sql:
            evidence.append("Update + Insert without history columns")
            return DataPattern.SCD_TYPE_1
        
        # Append Only (INSERT only, no other DML)
        if "INSERT " in sql:
            if not any(k in sql for k in ["UPDATE", "DELETE", "MERGE", "TRUNCATE"]):
                evidence.append("INSERT only, no UPDATE/DELETE")
                return DataPattern.APPEND_ONLY
        
        return DataPattern.UNKNOWN
    
    def _is_cdc(self, sql: str, name: str) -> bool:
        cdc_markers = ["__$OPERATION", "__$START_LSN", "OP_TYPE", "CDC_"]
        return any(m in sql for m in cdc_markers) or "cdc" in name
    
    def _is_scd_type_2(self, sql: str, name: str) -> bool:
        scd2_cols = [
            "EFFECTIVE_DATE", "END_DATE", "VALID_FROM", "VALID_TO",
            "IS_CURRENT", "IS_ACTIVE", "DW_VALID",
        ]
        return (
            any(c in sql for c in scd2_cols)
            or "scd2" in name
            or "history" in name
        )
    
    def _is_scd_type_3(self, sql: str, name: str) -> bool:
        # Look for previous_*, prior_*, old_* patterns
        scd3_pattern = r"(PREVIOUS_|PRIOR_|OLD_)\w+"
        return bool(re.search(scd3_pattern, sql)) or "scd3" in name
    
    def _is_soft_delete(self, sql: str, name: str) -> bool:
        soft_delete_patterns = [
            "SET IS_DELETED", "SET DELETED_AT", "SET IS_ACTIVE.*=.*0",
            "SET ACTIVE.*=.*FALSE", "SET STATUS.*=.*DELETED",
        ]
        return (
            any(re.search(p, sql) for p in soft_delete_patterns)
            or "soft_delete" in name
            or "deactivate" in name
        )
    
    def _is_hard_delete(self, sql: str, name: str) -> bool:
        return (
            "DELETE FROM" in sql
            and ("NOT IN" in sql or "NOT EXISTS" in sql)
        ) or "hard_delete" in name or "purge" in name
    
    def _is_delete_insert(self, sql: str, name: str) -> bool:
        return (
            ("TRUNCATE" in sql or "DELETE FROM" in sql)
            and "INSERT" in sql
        ) or "reload" in name or "refresh" in name
    
    def _is_watermark(self, sql: str, name: str) -> bool:
        watermark_patterns = [
            r"WHERE.*>.*@LAST",
            r"WHERE.*MODIFIED_DATE.*>",
            r"WHERE.*UPDATED_AT.*>",
            r"WHERE.*>.*\(SELECT\s+MAX",
        ]
        return (
            any(re.search(p, sql) for p in watermark_patterns)
            or "incremental" in name
            or "watermark" in name
        )
    
    def _is_delta_diff(self, sql: str, name: str) -> bool:
        return (
            "EXCEPT" in sql
            or "HASHBYTES" in sql
            or "CHECKSUM" in sql
            or "diff" in name
            or "compare" in name
        )
    
    def _is_pivot_unpivot(self, sql: str, name: str) -> bool:
        return (
            "PIVOT" in sql
            or "UNPIVOT" in sql
            or "pivot" in name
            or "transpose" in name
        )
    
    def _is_aggregate(self, sql: str, name: str) -> bool:
        agg_funcs = ["SUM(", "COUNT(", "AVG(", "MAX(", "MIN("]
        return (
            any(f in sql for f in agg_funcs)
            and "GROUP BY" in sql
        ) or "aggregate" in name or "summary" in name
    
    def _is_lookup_enrich(self, sql: str, name: str) -> bool:
        return (
            ("JOIN" in sql and any(t in sql for t in ["DIM_", "REF_", "LKP_"]))
            or "lookup" in name
            or "enrich" in name
        )
    
    # -------------------------------------------------------------------------
    # Layer Detection
    # -------------------------------------------------------------------------
    
    def _detect_layer(
        self, sql: str, name: str, pattern: DataPattern
    ) -> MedallionLayer:
        """Detect the Medallion layer based on task characteristics."""
        
        # Name-based hints (strongest signal)
        if any(h in name for h in ["bronze", "raw", "landing", "ingest"]):
            return MedallionLayer.BRONZE
        if any(h in name for h in ["silver", "clean", "conform", "dedupe"]):
            return MedallionLayer.SILVER
        if any(h in name for h in ["gold", "dim_", "fact_", "final", "agg"]):
            return MedallionLayer.GOLD
        
        # Pattern-based defaults
        if pattern == DataPattern.APPEND_ONLY:
            # Raw event ingestion is typically Bronze
            if any(h in name for h in ["extract", "load", "copy"]):
                return MedallionLayer.BRONZE
        
        if pattern in (DataPattern.LOOKUP_ENRICH, DataPattern.DELTA_DIFF):
            return MedallionLayer.SILVER
        
        if pattern in (
            DataPattern.MERGE,
            DataPattern.SCD_TYPE_2,
            DataPattern.AGGREGATE,
        ):
            return MedallionLayer.GOLD
        
        # SQL-based hints
        if "DIM_" in sql or "FACT_" in sql:
            return MedallionLayer.GOLD
        if "STG_" in sql or "STAGING" in sql:
            return MedallionLayer.BRONZE
        
        return MedallionLayer.NOT_APPLICABLE
    
    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    
    def _extract_target_table(self, sql: str) -> str | None:
        """Extract the target table name from SQL."""
        # MERGE INTO table
        match = re.search(r"MERGE\s+INTO\s+(\[?\w+\]?\.?\[?\w+\]?)", sql)
        if match:
            return match.group(1).replace("[", "").replace("]", "")
        
        # INSERT INTO table
        match = re.search(r"INSERT\s+INTO\s+(\[?\w+\]?\.?\[?\w+\]?)", sql)
        if match:
            return match.group(1).replace("[", "").replace("]", "")
        
        # UPDATE table
        match = re.search(r"UPDATE\s+(\[?\w+\]?\.?\[?\w+\]?)", sql)
        if match:
            return match.group(1).replace("[", "").replace("]", "")
        
        # DELETE FROM table
        match = re.search(r"DELETE\s+FROM\s+(\[?\w+\]?\.?\[?\w+\]?)", sql)
        if match:
            return match.group(1).replace("[", "").replace("]", "")
        
        return None
    
    def _flatten_tasks(self, tasks: list[Task]) -> list[Task]:
        """Recursively flatten task tree."""
        result = []
        for task in tasks:
            result.append(task)
            if task.child_tasks:
                result.extend(self._flatten_tasks(task.child_tasks))
        return result
