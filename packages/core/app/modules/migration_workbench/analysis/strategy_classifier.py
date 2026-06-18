"""Generation strategy classification (backward analysis).

Analyzes parsed SSIS packages to determine the optimal target architecture:
- SQL_NOTEBOOK: Pure SQL, Photon optimized
- PYSPARK: Complex logic, custom Python
- HYBRID_SINGLE: Mixed SQL/Python in one notebook
- MODULAR: Orchestrator + multiple SQL modules
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.modules.migration_workbench.analysis.schemas import (
    DataFlow,
    SSISPackage,
    Task,
    TaskType,
)


class GenerationStrategy(str, Enum):
    """Target notebook generation strategy."""
    
    SQL_NOTEBOOK = "sql"           # Single SQL notebook (Photon optimized)
    PYSPARK = "pyspark"            # Single PySpark notebook (full Python)
    HYBRID_SINGLE = "hybrid"       # One notebook with mixed SQL/Python cells
    MODULAR = "modular"            # Orchestrator (Python) + SQL module notebooks


class NotebookModule(BaseModel):
    """A planned notebook module in the generation output."""
    
    name: str = Field(..., description="Notebook filename without extension")
    notebook_type: str = Field(..., description="orchestrator | sql_module | pyspark_module")
    purpose: str = Field(..., description="What this module does")
    depends_on: list[str] = Field(default_factory=list, description="Other modules this calls")
    estimated_cells: int = 1


class GenerationPlan(BaseModel):
    """Backward analysis result: planned target structure."""
    
    strategy: GenerationStrategy
    rationale: str = Field(..., description="Why this strategy was chosen")
    
    # Planned modules (1+ for MODULAR, exactly 1 for others)
    modules: list[NotebookModule] = Field(default_factory=list)
    
    # Detected indicators
    has_script_components: bool = False
    has_foreach_loops: bool = False
    has_complex_dataflow: bool = False
    has_dynamic_sql: bool = False
    sql_task_count: int = 0
    dataflow_task_count: int = 0
    total_task_count: int = 0
    sql_task_ratio: float = 0.0
    
    # Performance hints
    photon_eligible: bool = False
    requires_broadcast_hints: bool = False
    requires_range_joins: bool = False
    
    # Notes
    notes: list[str] = Field(default_factory=list)


class StrategyClassifier:
    """Classifies a parsed SSIS package into a generation strategy.
    
    This is the backward analysis step: we look at SSIS structure
    and decide the optimal Databricks notebook architecture.
    """
    
    # Thresholds
    SQL_RATIO_THRESHOLD = 0.8  # Above this, prefer SQL-only
    MODULAR_MIN_SQL_TASKS = 3  # Below this, use single notebook
    COMPLEX_DATAFLOW_THRESHOLD = 3  # Components per data flow
    
    def classify(self, package: SSISPackage) -> GenerationPlan:
        """Classify a parsed SSIS package.
        
        Args:
            package: Parsed SSIS package
            
        Returns:
            GenerationPlan with chosen strategy and rationale
        """
        # Flatten tasks (including container children)
        all_tasks = self._flatten_tasks(package.tasks)
        
        # Compute indicators
        sql_count = sum(1 for t in all_tasks if t.task_type == TaskType.EXECUTE_SQL)
        dataflow_count = sum(1 for t in all_tasks if t.task_type == TaskType.DATA_FLOW)
        total_count = len([t for t in all_tasks if t.task_type != TaskType.SEQUENCE])
        
        has_script = any(t.task_type == TaskType.SCRIPT for t in all_tasks)
        has_foreach = any(t.task_type == TaskType.FOREACH_LOOP for t in all_tasks)
        has_complex_df = self._has_complex_dataflow(package.data_flows)
        has_dynamic_sql = self._has_dynamic_sql(package, all_tasks)
        
        sql_ratio = sql_count / total_count if total_count > 0 else 0.0
        
        # Build plan
        plan = GenerationPlan(
            strategy=GenerationStrategy.PYSPARK,  # Default, will be updated
            rationale="",
            has_script_components=has_script,
            has_foreach_loops=has_foreach,
            has_complex_dataflow=has_complex_df,
            has_dynamic_sql=has_dynamic_sql,
            sql_task_count=sql_count,
            dataflow_task_count=dataflow_count,
            total_task_count=total_count,
            sql_task_ratio=sql_ratio,
        )
        
        # Decision tree
        if has_script:
            plan.strategy = GenerationStrategy.PYSPARK
            plan.rationale = (
                f"Package contains Script Task(s) requiring custom Python/C# logic. "
                f"PySpark provides full programming capabilities."
            )
            plan.notes.append("Script Components require manual translation to PySpark UDFs")
        
        elif has_complex_df and dataflow_count >= 2:
            plan.strategy = GenerationStrategy.PYSPARK
            plan.rationale = (
                f"Package has {dataflow_count} complex Data Flow Tasks with multiple "
                f"transformations. PySpark allows explicit DataFrame caching and broadcast control."
            )
            plan.requires_broadcast_hints = True
        
        elif has_foreach and sql_count >= self.MODULAR_MIN_SQL_TASKS:
            plan.strategy = GenerationStrategy.MODULAR
            plan.rationale = (
                f"Package uses Foreach Loop with {sql_count} SQL operations. "
                f"Modular structure: PySpark orchestrator + reusable SQL modules."
            )
            plan.modules = self._plan_modular(package, all_tasks)
        
        elif sql_ratio >= self.SQL_RATIO_THRESHOLD and sql_count >= self.MODULAR_MIN_SQL_TASKS:
            plan.strategy = GenerationStrategy.MODULAR
            plan.rationale = (
                f"Package is {sql_ratio:.0%} SQL with {sql_count} distinct SQL operations. "
                f"Modular SQL notebooks maximize Photon optimization and analyst maintainability."
            )
            plan.photon_eligible = True
            plan.modules = self._plan_modular(package, all_tasks)
        
        elif sql_ratio >= self.SQL_RATIO_THRESHOLD:
            plan.strategy = GenerationStrategy.SQL_NOTEBOOK
            plan.rationale = (
                f"Package is {sql_ratio:.0%} SQL with {sql_count} operations. "
                f"Single SQL notebook is simplest and Photon-optimized."
            )
            plan.photon_eligible = True
            plan.modules = [
                NotebookModule(
                    name=self._notebook_name(package.name),
                    notebook_type="sql_module",
                    purpose="Full migration in single SQL notebook",
                    estimated_cells=sql_count + 2,
                )
            ]
        
        elif has_foreach or has_dynamic_sql:
            plan.strategy = GenerationStrategy.HYBRID_SINGLE
            plan.rationale = (
                f"Package has dynamic behavior (loops/dynamic SQL) requiring Python control flow, "
                f"but most operations are SQL-friendly. Hybrid notebook combines both."
            )
            plan.modules = [
                NotebookModule(
                    name=self._notebook_name(package.name),
                    notebook_type="hybrid_module",
                    purpose="Mixed SQL/Python cells in single notebook",
                    estimated_cells=total_count + 2,
                )
            ]
        
        else:
            plan.strategy = GenerationStrategy.PYSPARK
            plan.rationale = (
                f"Mixed workload ({sql_count} SQL, {dataflow_count} data flows). "
                f"PySpark provides unified API for both."
            )
            plan.modules = [
                NotebookModule(
                    name=self._notebook_name(package.name),
                    notebook_type="pyspark_module",
                    purpose="Full migration in PySpark",
                    estimated_cells=total_count + 3,
                )
            ]
        
        # Performance hints
        if any(
            t.sql_statement and "MERGE" in t.sql_statement.upper()
            for t in all_tasks
            if t.sql_statement
        ):
            plan.notes.append("MERGE statements detected - use Delta Lake MERGE INTO")
        
        if any(
            t.sql_statement and "DATEDIFF" in t.sql_statement.upper()
            for t in all_tasks
            if t.sql_statement
        ):
            plan.notes.append(
                "DATEDIFF-based joins detected - consider range joins with binSize"
            )
            plan.requires_range_joins = True
        
        return plan
    
    def _flatten_tasks(self, tasks: list[Task]) -> list[Task]:
        """Recursively flatten task tree including container children."""
        result = []
        for task in tasks:
            result.append(task)
            if task.child_tasks:
                result.extend(self._flatten_tasks(task.child_tasks))
        return result
    
    def _has_complex_dataflow(self, data_flows: list[DataFlow]) -> bool:
        """Check if any data flow has many components."""
        for df in data_flows:
            total_components = (
                len(df.sources)
                + len(df.destinations)
                + len(df.transformations)
            )
            if total_components >= self.COMPLEX_DATAFLOW_THRESHOLD:
                return True
            
            # Lookups are particularly complex
            if any(
                "lookup" in t.component_type.lower()
                for t in df.transformations
            ):
                return True
        
        return False
    
    def _has_dynamic_sql(self, package: SSISPackage, tasks: list[Task]) -> bool:
        """Check for dynamic SQL patterns."""
        # Variables with expressions
        if any(v.is_expression for v in package.variables):
            return True
        
        # SQL statements with variable references
        for task in tasks:
            if task.sql_statement and ("?" in task.sql_statement or "@" in task.sql_statement):
                return True
        
        return False
    
    def _plan_modular(
        self,
        package: SSISPackage,
        tasks: list[Task],
    ) -> list[NotebookModule]:
        """Plan modular notebook structure.
        
        Creates one orchestrator + one SQL module per logical SQL operation.
        """
        base_name = self._notebook_name(package.name)
        modules: list[NotebookModule] = []
        
        # Orchestrator (always first)
        orchestrator = NotebookModule(
            name=f"00_{base_name}_orchestrator",
            notebook_type="orchestrator",
            purpose="Coordinates execution of SQL modules with error handling",
            estimated_cells=4,
        )
        modules.append(orchestrator)
        
        # SQL modules - group SQL tasks by purpose
        sql_tasks = [t for t in tasks if t.task_type == TaskType.EXECUTE_SQL]
        
        module_groups = self._group_sql_tasks(sql_tasks)
        
        for idx, (purpose, group_tasks) in enumerate(module_groups, start=1):
            module = NotebookModule(
                name=f"{idx:02d}_{base_name}_{purpose}",
                notebook_type="sql_module",
                purpose=f"SQL operations: {purpose}",
                estimated_cells=len(group_tasks) + 1,
            )
            modules.append(module)
            orchestrator.depends_on.append(module.name)
        
        return modules
    
    def _group_sql_tasks(
        self,
        sql_tasks: list[Task],
    ) -> list[tuple[str, list[Task]]]:
        """Group SQL tasks by inferred purpose (extract/transform/merge/etc)."""
        groups: dict[str, list[Task]] = {
            "extract": [],
            "transform": [],
            "merge": [],
            "cleanup": [],
            "other": [],
        }
        
        for task in sql_tasks:
            sql = (task.sql_statement or "").upper()
            name = task.name.lower()
            
            if "MERGE" in sql or "merge" in name or "upsert" in name:
                groups["merge"].append(task)
            elif "TRUNCATE" in sql or "DELETE" in sql or "cleanup" in name:
                groups["cleanup"].append(task)
            elif "INSERT" in sql and "SELECT" in sql:
                groups["transform"].append(task)
            elif "SELECT" in sql and "INTO" in sql:
                groups["extract"].append(task)
            elif "INSERT" in sql:
                groups["extract"].append(task)
            else:
                groups["other"].append(task)
        
        # Return only non-empty groups in logical order
        ordered = []
        for key in ["extract", "transform", "merge", "cleanup", "other"]:
            if groups[key]:
                ordered.append((key, groups[key]))
        
        return ordered
    
    def _notebook_name(self, package_name: str) -> str:
        """Generate notebook base name from package name."""
        # Clean up package name for use as filename
        name = package_name.lower()
        name = name.replace(".dtsx", "")
        # Replace non-alphanumeric with underscore
        cleaned = "".join(c if c.isalnum() else "_" for c in name)
        # Collapse repeated underscores
        while "__" in cleaned:
            cleaned = cleaned.replace("__", "_")
        return cleaned.strip("_")
