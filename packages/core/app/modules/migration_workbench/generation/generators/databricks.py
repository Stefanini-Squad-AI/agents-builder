"""Databricks notebook generator (modular and single-file)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.modules.migration_workbench.analysis.schemas import (
    SSISPackage,
    Task,
    TaskType,
)
from app.modules.migration_workbench.analysis.strategy_classifier import (
    GenerationPlan,
    GenerationStrategy,
    StrategyClassifier,
)
from app.modules.migration_workbench.generation.schemas import (
    ArtifactTier,
    GeneratedArtifact,
    GenerationOptions,
    GenerationResult,
)


_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _make_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )


class DatabricksGenerator:
    """Generates Databricks notebook artifacts from a parsed SSIS package.
    
    Behavior:
    - Runs StrategyClassifier (or uses force_strategy from options) to decide layout
    - Renders Jinja2 templates per the strategy
    - Returns a GenerationResult with one or more GeneratedArtifacts
    """
    
    def __init__(self) -> None:
        self.env = _make_env()
    
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    
    def generate(
        self,
        package: SSISPackage,
        package_id,
        options: GenerationOptions | None = None,
    ) -> GenerationResult:
        """Generate all artifacts for a package."""
        options = options or GenerationOptions()
        
        # Backward analysis (or override)
        plan = StrategyClassifier().classify(package)
        strategy_source = "classifier"
        if options.force_strategy:
            plan.strategy = options.force_strategy
            strategy_source = "user_override"
        
        # Dispatch by strategy
        if plan.strategy == GenerationStrategy.MODULAR:
            artifacts = self._render_modular(package, plan, options)
        elif plan.strategy == GenerationStrategy.SQL_NOTEBOOK:
            artifacts = self._render_sql_notebook(package, plan, options)
        elif plan.strategy == GenerationStrategy.HYBRID_SINGLE:
            artifacts = self._render_pyspark(package, plan, options)  # treat as pyspark
        else:  # PYSPARK
            artifacts = self._render_pyspark(package, plan, options)
        
        # Always add README
        readme = self._render_readme(package, plan, options, artifacts)
        artifacts.append(readme)
        
        return GenerationResult(
            package_id=package_id,
            package_name=package.name,
            strategy=plan.strategy,
            strategy_source=strategy_source,
            artifacts=artifacts,
            warnings=list(plan.notes),
            generated_at=datetime.utcnow(),
        )
    
    # ------------------------------------------------------------------
    # Renderers
    # ------------------------------------------------------------------
    
    def _render_modular(
        self,
        package: SSISPackage,
        plan: GenerationPlan,
        options: GenerationOptions,
    ) -> list[GeneratedArtifact]:
        """Render orchestrator + SQL modules."""
        artifacts: list[GeneratedArtifact] = []
        
        sql_modules_meta = [m for m in plan.modules if m.notebook_type == "sql_module"]
        orchestrator_meta = next(
            (m for m in plan.modules if m.notebook_type == "orchestrator"),
            None,
        )
        
        # Flatten and group SQL tasks by phase (same logic as classifier)
        all_tasks = self._flatten_tasks(package.tasks)
        sql_tasks = [t for t in all_tasks if t.task_type == TaskType.EXECUTE_SQL]
        grouped = StrategyClassifier()._group_sql_tasks(sql_tasks)
        
        # Render orchestrator
        if orchestrator_meta:
            tmpl = self.env.get_template("orchestrator.py.j2")
            content = tmpl.render(
                package_name=package.name,
                target_catalog=options.target_catalog,
                target_schema=options.target_schema,
                include_docstring_header=options.include_docstring_header,
                generated_at=datetime.utcnow().isoformat(timespec="seconds"),
                sql_modules=sql_modules_meta,
            )
            artifacts.append(
                GeneratedArtifact(
                    name=f"{orchestrator_meta.name}.py",
                    relative_path=f"{orchestrator_meta.name}.py",
                    tier=ArtifactTier.ORCHESTRATOR,
                    language="python",
                    content=content,
                    depends_on=[m.name for m in sql_modules_meta],
                    notes=["PySpark orchestrator coordinating SQL modules"],
                )
            )
        
        # Render one SQL module per group
        tmpl = self.env.get_template("sql_module.sql.j2")
        for module_meta, (phase, tasks) in zip(sql_modules_meta, grouped):
            statements = [
                {
                    "task_name": t.name,
                    "description": t.description,
                    "sql": t.sql_statement or "-- (empty)",
                }
                for t in tasks
            ]
            content = tmpl.render(
                module_name=module_meta.name,
                purpose=module_meta.purpose,
                phase=phase,
                source_task_count=len(tasks),
                target_catalog=options.target_catalog,
                target_schema=options.target_schema,
                include_docstring_header=options.include_docstring_header,
                include_comments=options.include_comments,
                include_validation_cells=options.include_validation_cells,
                enable_photon_hints=options.enable_photon_hints,
                statements=statements,
            )
            artifacts.append(
                GeneratedArtifact(
                    name=f"{module_meta.name}.sql",
                    relative_path=f"{module_meta.name}.sql",
                    tier=ArtifactTier.SQL_MODULE,
                    language="sql",
                    content=content,
                    notes=[f"SQL module: {phase} ({len(tasks)} statements)"],
                )
            )
        
        return artifacts
    
    def _render_sql_notebook(
        self,
        package: SSISPackage,
        plan: GenerationPlan,
        options: GenerationOptions,
    ) -> list[GeneratedArtifact]:
        """Render single SQL notebook."""
        all_tasks = self._flatten_tasks(package.tasks)
        sql_tasks = [
            t for t in all_tasks
            if t.task_type == TaskType.EXECUTE_SQL and t.sql_statement
        ]
        
        tmpl = self.env.get_template("sql_notebook.sql.j2")
        content = tmpl.render(
            package_name=package.name,
            target_catalog=options.target_catalog,
            target_schema=options.target_schema,
            include_docstring_header=options.include_docstring_header,
            include_validation_cells=options.include_validation_cells,
            generated_at=datetime.utcnow().isoformat(timespec="seconds"),
            sql_tasks=sql_tasks,
        )
        
        name = plan.modules[0].name if plan.modules else self._fallback_name(package)
        return [
            GeneratedArtifact(
                name=f"{name}.sql",
                relative_path=f"{name}.sql",
                tier=ArtifactTier.SQL_MODULE,
                language="sql",
                content=content,
                notes=["Single SQL notebook (Photon optimized)"],
            )
        ]
    
    def _render_pyspark(
        self,
        package: SSISPackage,
        plan: GenerationPlan,
        options: GenerationOptions,
    ) -> list[GeneratedArtifact]:
        """Render single PySpark notebook."""
        all_tasks = self._flatten_tasks(package.tasks)
        # Skip pure containers (no own logic)
        renderable_tasks = [
            t for t in all_tasks
            if t.task_type not in (TaskType.SEQUENCE, TaskType.FOR_LOOP, TaskType.FOREACH_LOOP)
        ]
        
        tmpl = self.env.get_template("pyspark_module.py.j2")
        content = tmpl.render(
            package_name=package.name,
            target_catalog=options.target_catalog,
            target_schema=options.target_schema,
            include_docstring_header=options.include_docstring_header,
            include_comments=options.include_comments,
            include_validation_cells=options.include_validation_cells,
            generated_at=datetime.utcnow().isoformat(timespec="seconds"),
            tasks=renderable_tasks,
            connections=package.connection_managers,
        )
        
        name = plan.modules[0].name if plan.modules else self._fallback_name(package)
        return [
            GeneratedArtifact(
                name=f"{name}.py",
                relative_path=f"{name}.py",
                tier=ArtifactTier.PYSPARK_MODULE,
                language="python",
                content=content,
                notes=["PySpark notebook"],
            )
        ]
    
    def _render_readme(
        self,
        package: SSISPackage,
        plan: GenerationPlan,
        options: GenerationOptions,
        artifacts: list[GeneratedArtifact],
    ) -> GeneratedArtifact:
        tmpl = self.env.get_template("README.md.j2")
        content = tmpl.render(
            package_name=package.name,
            target_catalog=options.target_catalog,
            target_schema=options.target_schema,
            strategy=plan.strategy.value,
            rationale=plan.rationale,
            generated_at=datetime.utcnow().isoformat(timespec="seconds"),
            artifacts=artifacts,
            warnings=plan.notes,
            notes=plan.notes,
        )
        return GeneratedArtifact(
            name="README.md",
            relative_path="README.md",
            tier=ArtifactTier.DOCUMENTATION,
            language="markdown",
            content=content,
            notes=["Bundle README"],
        )
    
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    
    def _flatten_tasks(self, tasks: list[Task]) -> list[Task]:
        result: list[Task] = []
        for t in tasks:
            result.append(t)
            if t.child_tasks:
                result.extend(self._flatten_tasks(t.child_tasks))
        return result
    
    def _fallback_name(self, package: SSISPackage) -> str:
        name = package.name.lower().replace(".dtsx", "")
        cleaned = "".join(c if c.isalnum() else "_" for c in name)
        while "__" in cleaned:
            cleaned = cleaned.replace("__", "_")
        return cleaned.strip("_") or "notebook"
