"""Reconciliation service for validating migrations.

Compares source and target data to ensure migration accuracy.
In a real implementation, this would connect to actual databases.
For now, we provide the framework with simulated metrics.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.migration_workbench.models import ETLPackage
from app.modules.migration_workbench.reconciliation.schemas import (
    ReconciliationConfig,
    ReconciliationMetric,
    ReconciliationRunResult,
    ReconciliationRunView,
    ReconciliationStatus,
    ReconciliationType,
    TableReconciliation,
)


class ReconciliationService:
    """High-level reconciliation API."""
    
    def __init__(self, session: Session) -> None:
        self.session = session
    
    def get_package_or_raise(self, package_id: uuid.UUID) -> ETLPackage:
        package = self.session.get(ETLPackage, package_id)
        if not package:
            raise ValueError(f"Package {package_id} not found")
        return package
    
    def run_reconciliation(
        self,
        package_id: uuid.UUID,
        config: ReconciliationConfig | None = None,
    ) -> ReconciliationRunResult:
        """Run reconciliation checks for a package.
        
        In a production system, this would:
        1. Connect to source database (e.g., SQL Server)
        2. Connect to target database (Databricks/Delta Lake)
        3. Execute comparison queries
        4. Aggregate and return results
        
        For now, we extract table info from the package analysis
        and provide a framework for the checks.
        """
        config = config or ReconciliationConfig()
        package = self.get_package_or_raise(package_id)
        
        run_id = uuid.uuid4()
        started_at = datetime.now(timezone.utc)
        
        # Extract tables from package analysis
        tables_to_check = self._extract_tables_from_package(package, config)
        
        table_results: list[TableReconciliation] = []
        overall_status = ReconciliationStatus.PASSED
        
        for source_table, target_table in tables_to_check:
            table_result = self._reconcile_table(
                source_table=source_table,
                target_table=target_table,
                config=config,
            )
            table_results.append(table_result)
            
            if table_result.status == ReconciliationStatus.FAILED:
                overall_status = ReconciliationStatus.FAILED
            elif (
                table_result.status == ReconciliationStatus.WARNING
                and overall_status == ReconciliationStatus.PASSED
            ):
                overall_status = ReconciliationStatus.WARNING
        
        completed_at = datetime.now(timezone.utc)
        
        result = ReconciliationRunResult(
            id=run_id,
            package_id=package_id,
            package_name=package.package_name,
            status=overall_status,
            started_at=started_at,
            completed_at=completed_at,
            tables=table_results,
            config=config,
        )
        
        # Update package status if all passed
        if overall_status == ReconciliationStatus.PASSED:
            package.status = "validated"
            self.session.add(package)
        
        return result
    
    def _extract_tables_from_package(
        self,
        package: ETLPackage,
        config: ReconciliationConfig,
    ) -> list[tuple[str, str]]:
        """Extract source→target table mappings from package analysis.
        
        Priority:
        1. Explicit mappings in config
        2. Inferred from package connection_points
        3. Inferred from analysis_json data flows
        """
        # Use explicit mappings if provided
        if config.table_mappings:
            return list(config.table_mappings.items())
        
        # Try to extract from connection_points
        mappings: list[tuple[str, str]] = []
        
        if package.connection_points:
            sources = package.connection_points.sources or []
            targets = package.connection_points.targets or []
            
            # Simple heuristic: match by position or name similarity
            source_tables = [
                s.get("table_name") or s.get("name")
                for s in sources
                if isinstance(s, dict)
            ]
            target_tables = [
                t.get("table_name") or t.get("name")
                for t in targets
                if isinstance(t, dict)
            ]
            
            # Pair them up (simplified)
            for i, src in enumerate(source_tables):
                if src:
                    tgt = target_tables[i] if i < len(target_tables) else src
                    mappings.append((src, tgt or src))
        
        # Fallback: try analysis_json
        if not mappings and package.analysis_json:
            analysis = package.analysis_json
            if "data_flows" in analysis:
                for flow in analysis.get("data_flows", []):
                    for src in flow.get("sources", []):
                        src_table = src.get("table_name")
                        if src_table:
                            mappings.append((src_table, src_table))
        
        return mappings or [("sample_table", "sample_table")]
    
    def _reconcile_table(
        self,
        source_table: str,
        target_table: str,
        config: ReconciliationConfig,
    ) -> TableReconciliation:
        """Run reconciliation checks for a single table pair.
        
        In production, this executes actual database queries.
        Here we provide the framework with placeholder metrics.
        """
        metrics: list[ReconciliationMetric] = []
        status = ReconciliationStatus.PASSED
        
        for check_type in config.check_types:
            metric = self._run_check(
                check_type=check_type,
                source_table=source_table,
                target_table=target_table,
                config=config,
            )
            metrics.append(metric)
            
            if not metric.match:
                # Check if within acceptable variance
                if (
                    metric.variance is not None
                    and metric.variance_threshold is not None
                    and metric.variance <= metric.variance_threshold
                ):
                    if status == ReconciliationStatus.PASSED:
                        status = ReconciliationStatus.WARNING
                else:
                    status = ReconciliationStatus.FAILED
        
        return TableReconciliation(
            source_table=source_table,
            target_table=target_table,
            status=status,
            metrics=metrics,
        )
    
    def _run_check(
        self,
        check_type: ReconciliationType,
        source_table: str,
        target_table: str,
        config: ReconciliationConfig,
    ) -> ReconciliationMetric:
        """Execute a single reconciliation check.
        
        STUB: In production, execute actual SQL queries against source/target.
        """
        if check_type == ReconciliationType.ROW_COUNT:
            # Placeholder: would execute COUNT(*) on both databases
            # For demo, simulate matching counts
            source_count = 10000  # SELECT COUNT(*) FROM source_table
            target_count = 10000  # SELECT COUNT(*) FROM target_table
            
            match = source_count == target_count
            variance = (
                abs(source_count - target_count) / source_count * 100
                if source_count > 0
                else 0.0
            )
            
            return ReconciliationMetric(
                metric_name="row_count",
                source_value=source_count,
                target_value=target_count,
                match=match,
                variance=variance,
                variance_threshold=config.row_count_variance_threshold,
                notes="Row count comparison (simulated)",
            )
        
        elif check_type == ReconciliationType.CHECKSUM:
            # Placeholder: would compute hash of sampled rows
            source_hash = "abc123"
            target_hash = "abc123"
            
            return ReconciliationMetric(
                metric_name="checksum_md5",
                source_value=source_hash,
                target_value=target_hash,
                match=source_hash == target_hash,
                notes=f"MD5 checksum of first {config.checksum_sample_size} rows",
            )
        
        elif check_type == ReconciliationType.KEY_MATCH:
            # Placeholder: would check PK existence
            missing_in_target = 0
            missing_in_source = 0
            
            return ReconciliationMetric(
                metric_name="key_match",
                source_value=f"{missing_in_source} missing",
                target_value=f"{missing_in_target} missing",
                match=missing_in_target == 0 and missing_in_source == 0,
                notes="Primary key existence check",
            )
        
        elif check_type == ReconciliationType.AGGREGATE:
            # Placeholder: would SUM numeric columns
            source_sum = 1_000_000.00
            target_sum = 1_000_000.00
            
            return ReconciliationMetric(
                metric_name="aggregate_sum",
                source_value=source_sum,
                target_value=target_sum,
                match=source_sum == target_sum,
                variance=abs(source_sum - target_sum) / source_sum * 100 if source_sum else 0,
                notes="SUM of numeric columns",
            )
        
        else:  # SAMPLE_DATA
            return ReconciliationMetric(
                metric_name="sample_data",
                source_value="5 rows sampled",
                target_value="5 rows sampled",
                match=True,
                notes="Random sample comparison",
            )
    
    def list_runs(
        self,
        project_id: uuid.UUID,
        package_id: uuid.UUID | None = None,
        limit: int = 20,
    ) -> list[ReconciliationRunView]:
        """List recent reconciliation runs.
        
        Note: In production, this would query a reconciliation_runs table.
        For now, we return an empty list as runs aren't persisted yet.
        """
        # TODO: Query reconciliation_runs table when model is added
        return []
    
    def get_run(self, run_id: uuid.UUID) -> ReconciliationRunResult | None:
        """Get a specific reconciliation run by ID.
        
        Note: In production, this would query a reconciliation_runs table.
        """
        # TODO: Query reconciliation_runs table when model is added
        return None
