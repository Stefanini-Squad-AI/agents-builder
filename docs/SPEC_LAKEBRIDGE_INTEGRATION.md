# SPEC: Databricks Lakebridge Integration

**Feature ID:** W-LB-INT
**Status:** Planned
**Depends on:** Project, ProjectArtifact, ArtifactGroup, Card, CardStatus, ExportService, Fernet encryption (from MCP config spec), artifact groups (from artifact groups spec)

---

## 1. Objective

Integrate [Databricks Labs Lakebridge](https://github.com/databrickslabs/lakebridge) (free, open-source) into the Agents Workshop so that:

1. **Assessment** — Lakebridge Analyzer scans uploaded SQL/ETL artifacts and produces complexity reports ingested as Workshop artifacts, feeding gap analysis and migration planning.
2. **Transpilation** — Workshop cards representing migration tasks can trigger Lakebridge transpilation (BladeBridge, Morpheus, or Switch), with job status tracked in the Workshop backlog.
3. **Reconciliation** — After migration, Lakebridge Reconcile validates data fidelity between source and Databricks, with results surfaced on cards as acceptance criteria evidence.

Implementation is **phased**:
- **Phase 1** — Databricks workspace connection config, Analyzer orchestration, artifact ingestion.
- **Phase 2** — Transpiler orchestration (BladeBridge/Morpheus/Switch), job tracking, output ingestion.
- **Phase 3** — Reconciler orchestration (CLI + programmatic API), result ingestion, card acceptance criteria validation.

---

## 2. Phased Delivery

| Phase | Scope | Value |
|-------|-------|-------|
| Phase 1 | Databricks config, Analyzer CLI orchestration, JSON report ingestion | Migration complexity scores visible in Workshop; artifacts auto-categorized; feeds gap analysis |
| Phase 2 | Transpiler CLI orchestration, job tracking, output capture | Migration tasks executable from Workshop; transpiled code captured as artifacts; status tracked on cards |
| Phase 3 | Reconciler CLI + programmatic API, result ingestion, card validation | Post-migration data fidelity checks visible in Workshop; acceptance criteria auto-validated |

---

## 3. Lakebridge Overview

### 3.1 What Lakebridge Is

Databricks Labs Lakebridge is a free, open-source Python toolkit (databricks-labs-lakebridge on PyPI) that automates SQL migration to Databricks across three phases:

| Phase | Component | CLI Command | Description |
|-------|-----------|-------------|-------------|
| Pre-migration | Analyzer | databricks labs lakebridge analyze | Scans SQL/ETL files, produces complexity report (Excel + optional JSON) |
| Pre-migration | Profiler | databricks labs lakebridge execute-database-profiler | Connects to source DB, extracts metadata/metrics, generates dashboard |
| Conversion | Transpiler (BladeBridge) | databricks labs lakebridge transpile | Deterministic, mature, wide dialect support |
| Conversion | Transpiler (Morpheus) | databricks labs lakebridge transpile | Deterministic, next-gen, strong correctness guarantees |
| Conversion | Transpiler (Switch) | databricks labs lakebridge llm-transpile | LLM-powered (experimental), uses Mosaic AI Model Serving |
| Post-migration | Reconciler | databricks labs lakebridge reconcile | Compares source vs Databricks: schema, row counts, data values |

### 3.2 Installation & Prerequisites

| Requirement | Details |
|-------------|---------|
| Databricks workspace | Any workspace (production, development, or free trial) |
| Databricks CLI | Installed and configured with PAT or Service Principal |
| Python | 3.10.1 - 3.13.x |
| Java | 11+ (required for Morpheus transpiler) |
| Network | GitHub, Maven Central, PyPI access |

Install command: databricks labs install lakebridge

### 3.3 Supported Source Dialects

**Analyzer** (30+ dialects): Oracle, SQL Server, Snowflake, Redshift, Synapse, Teradata, PostgreSQL, MySQL, Netezza, DB2, Greenplum, Hive, Presto, Athena, BigQuery, Vertica, SAP HANA, DataStage, SSIS, AbInitio, Alteryx, PentahoDI, Pig, PySpark, SAS, Sqoop, Talend, Airflow, ADF, Oozie, Python, Scala, SPSS, SSRS, Cloudera/Impala.

**Transpiler - BladeBridge**: mssql, netezza, oracle, redshift (experimental), snowflake, synapse, teradata, datastage, ssis (experimental).

**Transpiler - Morpheus**: mssql, synapse.

**Transpiler - Switch**: mssql, mysql, netezza, oracle, postgresql, redshift, snowflake, synapse, teradata, python, scala, airflow, pyspark, unknown_etl.

**Reconciler**: Oracle, Snowflake, SQL Server, Redshift, Databricks.

### 3.4 API Surface

Lakebridge is primarily a **CLI tool** invoked via databricks labs lakebridge <command>. There is no REST API or MCP server.

**Programmatic access available for:**
- **Reconciler**: Python import databricks.labs.lakebridge.reconcile.trigger_recon_service.TriggerReconService - usable from notebooks or Python processes.
- **Analyzer JSON output**: --generate-json true flag produces machine-readable JSON alongside Excel.

**No programmatic access for:**
- Analyzer (CLI only, but JSON output is parseable)
- Transpiler (CLI only; Switch runs as Databricks Job asynchronously)

---

# Phase 1: Databricks Config & Analyzer Integration

---

## 4. Domain Model

### 4.1 New table: databricks_configs

Per-project Databricks workspace connection. One row per project (1:1).

``sql
CREATE TABLE databricks_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    workspace_url   TEXT NOT NULL,
    cli_profile     TEXT NOT NULL DEFAULT 'DEFAULT',
    pat_enc         TEXT NOT NULL,
    catalog_name    TEXT NOT NULL DEFAULT 'remorph',
    schema_name     TEXT NOT NULL DEFAULT 'transpiler',
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(project_id)
);

CREATE INDEX ix_databricks_configs__project_id ON databricks_configs(project_id);
``

**Field semantics:**

| Field | Purpose |
|-------|---------|
| workspace_url | Databricks workspace URL (e.g. https://myorg.cloud.databricks.com) |
| cli_profile | Databricks CLI profile name in ~/.databrickscfg |
| pat_enc | Fernet-encrypted Personal Access Token. Never returned in API responses. |
| catalog_name | Default Unity Catalog for Lakebridge operations |
| schema_name | Default schema within the catalog |
| enabled | Toggle Lakebridge integration on/off without deleting config |

### 4.2 ORM: DatabricksConfig

Add to packages/core/app/domain/lakebridge.py:

`python
class DatabricksConfig(UuidPkMixin, TimestampsMixin, Base):
    __tablename__ = "databricks_configs"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_databricks_configs__project_id"),
        Index("ix_databricks_configs__project_id", "project_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
    )
    workspace_url: Mapped[str] = mapped_column(Text, nullable=False)
    cli_profile: Mapped[str] = mapped_column(String(64), nullable=False, server_default="DEFAULT")
    pat_enc: Mapped[str] = mapped_column(Text, nullable=False)
    catalog_name: Mapped[str] = mapped_column(String(128), nullable=False, server_default="remorph")
    schema_name: Mapped[str] = mapped_column(String(128), nullable=False, server_default="transpiler")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    project: Mapped["Project"] = relationship(back_populates="databricks_config")
`

Add to Project ORM:

`python
databricks_config: Mapped["DatabricksConfig | None"] = relationship(
    back_populates="project", uselist=False, cascade="all, delete-orphan",
)
`

### 4.3 New table: lakebridge_jobs

Tracks all Lakebridge CLI executions (analyze, transpile, reconcile) per project.

``sql
CREATE TABLE lakebridge_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_type        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    source_dialect  TEXT NOT NULL,
    transpiler      TEXT,
    input_artifact_ids JSONB NOT NULL DEFAULT '[]',
    result_artifact_id UUID REFERENCES project_artifacts(id) ON DELETE SET NULL,
    cli_command     TEXT NOT NULL,
    cli_stdout      TEXT,
    cli_stderr      TEXT,
    exit_code       INTEGER,
    duration_ms     INTEGER,
    error_message   TEXT,
    metadata_json   JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_lakebridge_jobs__project_status ON lakebridge_jobs(project_id, status);
CREATE INDEX ix_lakebridge_jobs__project_type ON lakebridge_jobs(project_id, job_type);
``

**Field semantics:**

| Field | Purpose |
|-------|---------|
| job_type | LakebridgeJobType enum value: nalyze, 	ranspile_bladebridge, 	ranspile_morpheus, 	ranspile_switch, econcile |
| status | LakebridgeJobStatus enum value: pending, unning, completed, ailed, cancelled |
| source_dialect | Source dialect used (e.g. oracle, snowflake, mssql) |
| 	ranspiler | Transpiler used (nullable for analyze/reconcile): ladebridge, morpheus, switch |
| input_artifact_ids | JSONB array of UUIDs - which Workshop artifacts were used as input |
| esult_artifact_id | FK to the project_artifacts row created from the job output (e.g. Analyzer JSON report) |
| cli_command | Full CLI command string that was executed |
| cli_stdout | Captured stdout (truncated to 64KB) |
| cli_stderr | Captured stderr (truncated to 64KB) |
| exit_code | Process exit code |
| duration_ms | Wall-clock duration of the CLI execution |
| error_message | Human-readable error if job failed |
| metadata_json | Job-type-specific metadata (e.g. Switch job URL, Reconcile recon_id, Analyzer report path) |

### 4.4 ORM: LakebridgeJob

`python
class LakebridgeJob(UuidPkMixin, TimestampsMixin, Base):
    __tablename__ = "lakebridge_jobs"
    __table_args__ = (
        CheckConstraint(
            f"job_type IN ({values_csv(LakebridgeJobType)})",
            name="ck_lakebridge_jobs__job_type",
        ),
        CheckConstraint(
            f"status IN ({values_csv(LakebridgeJobStatus)})",
            name="ck_lakebridge_jobs__status",
        ),
        Index("ix_lakebridge_jobs__project_status", "project_id", "status"),
        Index("ix_lakebridge_jobs__project_type", "project_id", "job_type"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
    )
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    source_dialect: Mapped[str] = mapped_column(String(32), nullable=False)
    transpiler: Mapped[str | None] = mapped_column(String(32))
    input_artifact_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    result_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_artifacts.id", ondelete="SET NULL"),
    )
    cli_command: Mapped[str] = mapped_column(Text, nullable=False)
    cli_stdout: Mapped[str | None] = mapped_column(Text)
    cli_stderr: Mapped[str | None] = mapped_column(Text)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    project: Mapped["Project"] = relationship(back_populates="lakebridge_jobs")
    result_artifact: Mapped["ProjectArtifact | None"] = relationship(back_populates="lakebridge_jobs")
`

Add to Project ORM:

`python
lakebridge_jobs: Mapped[list["LakebridgeJob"]] = relationship(
    back_populates="project", cascade="all, delete-orphan", order_by="LakebridgeJob.created_at.desc()",
)
`

Add to ProjectArtifact ORM:

`python
lakebridge_jobs: Mapped[list["LakebridgeJob"]] = relationship(back_populates="result_artifact")
`

---

## 5. Enums

Add to packages/core/app/enums.py:

`python
class LakebridgeJobType(StrEnum):
    ANALYZE = "analyze"
    TRANSPILE_BLADEBRIDGE = "transpile_bladebridge"
    TRANSPILE_MORPHEUS = "transpile_morpheus"
    TRANSPILE_SWITCH = "transpile_switch"
    RECONCILE = "reconcile"


class LakebridgeJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
`

---

## 6. Pydantic Schemas

### 6.1 Views (packages/core/app/schemas/views.py)

`python
class DatabricksConfigView(BaseModel):
    model_config = _VIEW_CONFIG
    id: uuid.UUID
    project_id: uuid.UUID
    workspace_url: str
    cli_profile: str
    catalog_name: str
    schema_name: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class LakebridgeJobView(BaseModel):
    model_config = _VIEW_CONFIG
    id: uuid.UUID
    project_id: uuid.UUID
    job_type: LakebridgeJobType
    status: LakebridgeJobStatus
    source_dialect: str
    transpiler: str | None = None
    input_artifact_ids: list[str] = []
    result_artifact_id: str | None = None
    cli_command: str
    cli_stdout: str | None = None
    cli_stderr: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    error_message: str | None = None
    metadata_json: dict = {}
    created_at: datetime
    updated_at: datetime


class AnalyzerSummaryView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_files: int
    analyzed_files: int
    skipped_files: int
    high_complexity_count: int
    very_high_complexity_count: int
    source_dialect: str
    complexity_distribution: dict[str, int]
`

**Security note:** DatabricksConfigView deliberately omits pat_enc. The PAT is never included in any API response.


---

## 7. Services

### 7.1 DatabricksConfigService

File: `packages/core/app/services/databricks_config_service.py`

```python
class DatabricksConfigService:
    def __init__(self) -> None: ...

    def get_config(self, project_id: uuid.UUID) -> DatabricksConfig | None:
        """Return config for project, or None if not configured."""

    def save_config(
        self,
        project_id: uuid.UUID,
        workspace_url: str,
        cli_profile: str,
        pat_plain: str,
        catalog_name: str,
        schema_name: str,
    ) -> DatabricksConfig:
        """Create or update config. Encrypts PAT with Fernet before storage.
        If config already exists for project, updates in-place."""

    def delete_config(self, project_id: uuid.UUID) -> None:
        """Delete config (cascades to jobs)."""

    def toggle_enabled(self, project_id: uuid.UUID, enabled: bool) -> DatabricksConfig:
        """Toggle integration on/off."""

    def decrypt_pat(self, config: DatabricksConfig) -> str:
        """Decrypt PAT for CLI invocation. Internal use only - never exposed via API."""
```

**Encryption:** Uses the same Fernet key and pattern as MCP secrets (from `SPEC_MCP_CONFIG.md` section 8). The `pat_plain` parameter is encrypted immediately in `save_config()` and stored as `pat_enc`. `decrypt_pat()` is called only by `LakebridgeClient` before CLI invocation.

### 7.2 LakebridgeClient

File: `packages/core/app/services/lakebridge_client.py`

Async subprocess wrapper around `databricks labs lakebridge` CLI commands.

```python
@dataclass
class LakebridgeCliResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class LakebridgeClient:
    def __init__(self, config: DatabricksConfig) -> None:
        """Store config. Decrypt PAT for subprocess env."""

    async def _run_cli(self, args: list[str], timeout: int = 600) -> LakebridgeCliResult:
        """Core subprocess runner. Sets DATABRICKS_TOKEN env var from decrypted PAT.
        Runs: databricks labs lakebridge <args>
        Captures stdout/stderr. Enforces timeout.
        Truncates output to 64KB."""

    async def run_analyze(
        self,
        input_dir: Path,
        source_dialect: str,
        report_file: Path,
        generate_json: bool = True,
    ) -> LakebridgeCliResult:
        """
        Run: databricks labs lakebridge analyze
             --source-directory <input_dir>
             --source-tech <source_dialect>
             --report-file <report_file>
             --generate-json true
        """

    async def run_transpile(
        self,
        input_dir: Path,
        output_dir: Path,
        source_dialect: str,
        transpiler: str = "morpheus",
        skip_validation: bool = False,
        catalog_name: str | None = None,
        schema_name: str | None = None,
        error_file_path: Path | None = None,
    ) -> LakebridgeCliResult:
        """
        Run: databricks labs lakebridge transpile
             --source-dialect <source_dialect>
             --input-source <input_dir>
             --output-folder <output_dir>
             [--skip-validation true]
             [--catalog-name <catalog>]
             [--schema-name <schema>]
             [--error-file-path <error_file>]
        """

    async def run_llm_transpile(
        self,
        input_dir: Path,
        output_ws_folder: str,
        source_dialect: str,
        catalog_name: str | None = None,
        schema_name: str | None = None,
        volume: str | None = None,
        foundation_model: str | None = None,
    ) -> LakebridgeCliResult:
        """
        Run: databricks labs lakebridge llm-transpile
             --input-source <input_dir>
             --output-ws-folder <output_ws_folder>
             --source-dialect <source_dialect>
             --accept-terms true
             [--catalog-name <catalog>]
             [--schema-name <schema>]
             [--volume <volume>]
             [--foundation-model <model>]

        Note: Switch runs as a Databricks Job asynchronously.
        The CLI returns immediately with a job URL.
        Polling for completion is handled by the service layer.
        """

    async def run_reconcile(self) -> LakebridgeCliResult:
        """
        Run: databricks labs lakebridge reconcile

        Uses the reconcile config previously set up via
        `databricks labs lakebridge configure-reconcile`.
        """

    async def check_prerequisites(self) -> dict[str, bool]:
        """Verify Databricks CLI is installed and lakebridge is available.
        Returns: {"cli_installed": bool, "lakebridge_installed": bool, "workspace_reachable": bool}"""
```

**Subprocess environment:** The client sets `DATABRICKS_TOKEN` and `DATABRICKS_HOST` environment variables for the subprocess (from decrypted PAT and workspace_url). It does NOT write to `~/.databrickscfg`.

**Timeout defaults:** Analyzer: 600s, Transpile: 1800s (30 min), Switch: 300s (returns immediately), Reconcile: 3600s (1 hour).

### 7.3 LakebridgeAnalyzerService

File: `packages/core/app/services/lakebridge_analyzer_service.py`

Orchestrates the full analyze workflow: prepare input dir from artifacts, run CLI, parse JSON, ingest result.

```python
class LakebridgeAnalyzerService:
    def __init__(self) -> None:
        self._config_svc = DatabricksConfigService()
        self._client: LakebridgeClient | None = None

    async def run_analyze(
        self,
        project_id: uuid.UUID,
        source_dialect: str,
        artifact_ids: list[uuid.UUID] | None = None,
    ) -> LakebridgeJob:
        """
        Full analyze workflow:
        1. Load DatabricksConfig (raise if missing/disabled)
        2. Create LakebridgeJob row (status=pending)
        3. Prepare temp input dir: copy artifact files from "code to be migrated" group
           (or specific artifact_ids if provided)
        4. Create LakebridgeClient
        5. Update job status to "running"
        6. Call client.run_analyze()
        7. Parse JSON report if exit_code == 0
        8. Ingest report as new ProjectArtifact (kind=ANALYZER_REPORT, group=ARCHITECTURAL_STANDARDS)
        9. Link result_artifact_id on job
        10. Update job status to "completed" (or "failed")
        11. Return job
        """

    def _prepare_input_dir(
        self,
        project_id: uuid.UUID,
        artifact_ids: list[uuid.UUID] | None,
    ) -> Path:
        """Create temp directory, copy artifact files into it.
        If artifact_ids is None, uses all artifacts in "code_to_be_migrated" group.
        Returns path to temp dir (caller responsible for cleanup)."""

    def _parse_json_report(self, json_path: Path) -> AnalyzerReport:
        """Parse Lakebridge Analyzer JSON output into structured AnalyzerReport."""

    def _ingest_report(
        self,
        project_id: uuid.UUID,
        report: AnalyzerReport,
        json_path: Path,
    ) -> ProjectArtifact:
        """Create ProjectArtifact from analyzer report.
        - kind = ArtifactKind.ANALYZER_REPORT
        - artifact_group = ArtifactGroup.ARCHITECTURAL_STANDARDS
        - content = JSON string of the report
        - filename = "analyzer_report_<diaect>_<timestamp>.json"
        """

    def get_analyzer_summary(self, project_id: uuid.UUID) -> AnalyzerSummaryView | None:
        """Extract summary from most recent completed analyze job result artifact."""

    def get_job(self, job_id: uuid.UUID) -> LakebridgeJob | None: ...

    def list_jobs(
        self,
        project_id: uuid.UUID,
        job_type: LakebridgeJobType | None = None,
    ) -> list[LakebridgeJob]: ...
```

### 7.4 AnalyzerReport dataclass

```python
@dataclass
class AnalyzerReport:
    source_dialect: str
    total_files: int
    files: list[AnalyzerFileReport]

@dataclass
class AnalyzerFileReport:
    file_path: str
    object_type: str          # PROCEDURE, FUNCTION, TABLE, VIEW, etc.
    complexity_score: str     # LOW, MEDIUM, HIGH, VERY HIGH
    line_count: int
    issue_count: int
    issues: list[str]         # FIXME markers, unsupported syntax, etc.
```


---

## 8. API Endpoints

### 8.1 Databricks Config

File: `packages/core/app/api/lakebridge.py`

```python
router = APIRouter(tags=["lakebridge"])
```

| Method | Path | Request | Response | Description |
|--------|------|---------|----------|-------------|
| GET | `/api/projects/{slug}/lakebridge/config` | - | `DatabricksConfigView` | Get Databricks config (PAT omitted) |
| POST | `/api/projects/{slug}/lakebridge/config` | `DatabricksConfigCreate` | `DatabricksConfigView` (201) | Create/update config |
| DELETE | `/api/projects/{slug}/lakebridge/config` | - | 204 | Delete config |
| PATCH | `/api/projects/{slug}/lakebridge/config/toggle` | `{enabled: bool}` | `DatabricksConfigView` | Toggle enabled |

**Request schemas:**

```python
class DatabricksConfigCreate(BaseModel):
    workspace_url: str = Field(..., min_length=1)
    cli_profile: str = Field(default="DEFAULT", max_length=64)
    pat: str = Field(..., min_length=1, description="Databricks PAT (encrypted before storage)")
    catalog_name: str = Field(default="remorph", max_length=128)
    schema_name: str = Field(default="transpiler", max_length=128)
```

### 8.2 Analyzer

| Method | Path | Request | Response | Description |
|--------|------|---------|----------|-------------|
| POST | `/api/projects/{slug}/lakebridge/analyze` | `AnalyzeRequest` | `LakebridgeJobView` (202) | Start analyzer job |
| GET | `/api/projects/{slug}/lakebridge/analyze/summary` | - | `AnalyzerSummaryView` | Get latest analysis summary |
| GET | `/api/projects/{slug}/lakebridge/jobs` | - | `list[LakebridgeJobView]` | List all Lakebridge jobs |
| GET | `/api/projects/{slug}/lakebridge/jobs/{job_id}` | - | `LakebridgeJobView` | Get job detail |
| POST | `/api/projects/{slug}/lakebridge/jobs/{job_id}/cancel` | - | `LakebridgeJobView` | Cancel a running job |

**Request schemas:**

```python
class AnalyzeRequest(BaseModel):
    source_dialect: str = Field(..., description="Source dialect (e.g. oracle, snowflake, mssql)")
    artifact_ids: list[uuid.UUID] | None = Field(default=None, description="Specific artifacts to analyze; None = all in code_to_be_migrated group")
```

### 8.3 Prerequisites Check

| Method | Path | Request | Response | Description |
|--------|------|---------|----------|-------------|
| GET | `/api/projects/{slug}/lakebridge/prerequisites` | - | `PrerequisitesView` | Check if Lakebridge CLI is installed and workspace is reachable |

```python
class PrerequisitesView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cli_installed: bool
    lakebridge_installed: bool
    workspace_reachable: bool
    all_ok: bool  # True iff all three are True
```

---

## 9. Alembic Migration

File: `packages/core/alembic/versions/<timestamp>_lakebridge_tables.py`

```python
revision = "20260529_1200"
down_revision = "<previous_revision>"

_JOB_TYPE_VALUES = "'analyze', 'transpile_bladebridge', 'transpile_morpheus', 'transpile_switch', 'reconcile'"
_JOB_STATUS_VALUES = "'pending', 'running', 'completed', 'failed', 'cancelled'"


def upgrade() -> None:
    op.create_table(
        "databricks_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_url", sa.Text, nullable=False),
        sa.Column("cli_profile", sa.String(64), nullable=False, server_default="DEFAULT"),
        sa.Column("pat_enc", sa.Text, nullable=False),
        sa.Column("catalog_name", sa.String(128), nullable=False, server_default="remorph"),
        sa.Column("schema_name", sa.String(128), nullable=False, server_default="transpiler"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", name="uq_databricks_configs__project_id"),
    )
    op.create_index("ix_databricks_configs__project_id", "databricks_configs", ["project_id"])

    op.create_table(
        "lakebridge_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("source_dialect", sa.String(32), nullable=False),
        sa.Column("transpiler", sa.String(32)),
        sa.Column("input_artifact_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("result_artifact_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("project_artifacts.id", ondelete="SET NULL")),
        sa.Column("cli_command", sa.Text, nullable=False),
        sa.Column("cli_stdout", sa.Text),
        sa.Column("cli_stderr", sa.Text),
        sa.Column("exit_code", sa.Integer),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("error_message", sa.Text),
        sa.Column("metadata_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"job_type IN ({_JOB_TYPE_VALUES})", name="ck_lakebridge_jobs__job_type"),
        sa.CheckConstraint(f"status IN ({_JOB_STATUS_VALUES})", name="ck_lakebridge_jobs__status"),
    )
    op.create_index("ix_lakebridge_jobs__project_status", "lakebridge_jobs", ["project_id", "status"])
    op.create_index("ix_lakebridge_jobs__project_type", "lakebridge_jobs", ["project_id", "job_type"])


def downgrade() -> None:
    op.drop_index("ix_lakebridge_jobs__project_type", table_name="lakebridge_jobs")
    op.drop_index("ix_lakebridge_jobs__project_status", table_name="lakebridge_jobs")
    op.drop_table("lakebridge_jobs")
    op.drop_index("ix_databricks_configs__project_id", table_name="databricks_configs")
    op.drop_table("databricks_configs")
```

---

## 10. Artifact Integration

### 10.1 New ArtifactKind

Add to `ArtifactKind` enum:

```python
class ArtifactKind(StrEnum):
    # ... existing values ...
    ANALYZER_REPORT = "analyzer_report"
    TRANSPILED_CODE = "transpiled_code"
    RECONCILE_RESULT = "reconcile_result"
```

### 10.2 Artifact Group Placement

| Lakebridge Output | ArtifactKind | ArtifactGroup | Rationale |
|-------------------|-------------|---------------|-----------|
| Analyzer JSON report | `ANALYZER_REPORT` | `ARCHITECTURAL_STANDARDS` | Complexity scores are architectural guidance |
| Transpiled code files | `TRANSPILED_CODE` | `CODE_TO_BE_MIGRATED` | Transpiled output IS the migrated code |
| Reconcile results | `RECONCILE_RESULT` | `ARCHITECTURAL_STANDARDS` | Validation results are quality standards evidence |

### 10.3 Analyzer Report Content

When ingested, the analyzer report artifact stores:
- `filename`: `analyzer_report_<dialect>_<timestamp>.json`
- `content`: Full JSON string from `--generate-json true`
- `artifact_group`: `architectural_standards`
- `kind`: `analyzer_report`

The `AnalyzerSummaryView` is derived by parsing this artifact, not stored separately.

---

## 11. Context Integration

### 11.1 Analyzer Report in ProjectContext

When `render_project_context()` builds context for LLM prompts, analyzer report data is included in the `ARCHITECTURAL_STANDARDS` group section:

```markdown
## Architectural Standards

### Artifacts
... existing artifacts ...

### Lakebridge Analysis (oracle, 2026-05-29)
- Total files: 247
- High complexity: 18 files
- Very high complexity: 5 files
- Key issues: 3 files with unsupported PIVOT syntax, 2 files with recursive CTEs
```

This feeds into all 5 LLM prompts (ProposeSkillSet, DraftSkillBody, ProposeBacklog, DraftCard, SuggestTechStack) automatically via `ProjectContext.artifact_groups["architectural_standards"]`.

### 11.2 No Structural Prompt Changes

Following the same pattern as MCP context (SPEC_MCP_CONFIG.md section 14), analyzer data flows through the existing `ProjectContext` -> `render_project_context()` pipeline with zero structural changes to prompt classes.


---

# Phase 2: Transpiler Integration

---

## 12. Transpiler Services

### 12.1 LakebridgeTranspileService

File: `packages/core/app/services/lakebridge_transpile_service.py`

```python
class LakebridgeTranspileService:
    def __init__(self) -> None:
        self._config_svc = DatabricksConfigService()

    async def run_transpile(
        self,
        project_id: uuid.UUID,
        source_dialect: str,
        transpiler: str = "morpheus",
        artifact_ids: list[uuid.UUID] | None = None,
        skip_validation: bool = False,
    ) -> LakebridgeJob:
        '''
        Full transpile workflow:
        1. Load DatabricksConfig (raise if missing/disabled)
        2. Validate transpiler supports source_dialect
        3. Create LakebridgeJob row (status=pending, job_type=transpile_<transpiler>)
        4. Prepare temp input dir from artifacts
        5. Create temp output dir
        6. Create LakebridgeClient
        7. Update job status to "running"
        8. Call client.run_transpile() or client.run_llm_transpile()
        9. If exit_code == 0:
           a. Ingest transpiled files as ProjectArtifact (kind=TRANSPILED_CODE, group=CODE_TO_BE_MIGRATED)
           b. Link result_artifact_id on job
        10. Update job status to "completed" (or "failed")
        11. Return job
        '''

    def _validate_dialect_support(self, transpiler: str, source_dialect: str) -> None:
        '''Raise ValueError if transpiler does not support the dialect.
        Uses DIALECT_SUPPORT_MAP constant.'''

    def _ingest_transpiled_output(
        self, project_id: uuid.UUID, output_dir: Path, source_dialect: str, transpiler: str,
    ) -> ProjectArtifact:
        '''Create ProjectArtifact from transpiled output directory.
        - kind = ArtifactKind.TRANSPILED_CODE
        - artifact_group = ArtifactGroup.CODE_TO_BE_MIGRATED
        - content = ZIP of output dir (or single file if only one)
        - filename = "transpiled_<dialect>_<transpiler>_<timestamp>.zip"
        '''

    async def poll_switch_job(self, job: LakebridgeJob) -> LakebridgeJob:
        '''Poll Switch (LLM transpiler) Databricks Job for completion.
        Reads job URL from job.metadata_json["switch_job_url"].
        Updates job.status when complete.
        Called by background task or manual refresh.'''
```

### 12.2 Dialect Support Map

```python
DIALECT_SUPPORT_MAP: dict[str, set[str]] = {
    "bladebridge": {"mssql", "netezza", "oracle", "redshift", "snowflake", "synapse", "teradata", "datastage", "ssis"},
    "morpheus": {"mssql", "synapse"},
    "switch": {"mssql", "mysql", "netezza", "oracle", "postgresql", "redshift", "snowflake", "synapse", "teradata", "python", "scala", "airflow", "pyspark", "unknown_etl"},
}
```

### 12.3 Switch Job Polling

Switch (LLM transpiler) runs asynchronously as a Databricks Job. After `run_llm_transpile()` returns, the service:

1. Extracts the Switch job URL from CLI stdout (pattern: `https://workspace.databricks.com/jobs/<job_id>/runs/<run_id>`)
2. Stores it in `job.metadata_json["switch_job_url"]`
3. A background task (or manual API call) polls the Databricks Jobs API for completion
4. On completion, the output is in the Databricks Workspace at the `--output-ws-folder` path
5. The service downloads the output and ingests as artifact

**Polling implementation options:**
- **Option A (recommended):** Background `asyncio.Task` with exponential backoff (5s, 10s, 20s, 60s, 120s) up to max 30 minutes
- **Option B:** Manual refresh via `POST /api/projects/{slug}/lakebridge/jobs/{job_id}/refresh`

---

## 13. Transpiler API Endpoints

| Method | Path | Request | Response | Description |
|--------|------|---------|----------|-------------|
| POST | `/api/projects/{slug}/lakebridge/transpile` | `TranspileRequest` | `LakebridgeJobView` (202) | Start transpiler job |
| GET | `/api/projects/{slug}/lakebridge/transpile/dialects` | - | `DialectSupportView` | List supported dialects per transpiler |
| POST | `/api/projects/{slug}/lakebridge/jobs/{job_id}/refresh` | - | `LakebridgeJobView` | Refresh job status (for Switch async jobs) |

**Request schemas:**

```python
class TranspileRequest(BaseModel):
    source_dialect: str = Field(..., description="Source dialect (e.g. oracle, snowflake)")
    transpiler: str = Field(default="morpheus", description="Transpiler: bladebridge, morpheus, or switch")
    artifact_ids: list[uuid.UUID] | None = Field(default=None, description="Specific artifacts; None = all in code_to_be_migrated group")
    skip_validation: bool = Field(default=False, description="Skip post-transpile SQL validation")

class DialectSupportView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bladebridge: list[str]
    morpheus: list[str]
    switch: list[str]
```


---

# Phase 3: Reconciler Integration

---

## 14. Reconciler Services

### 14.1 LakebridgeReconcileService

File: `packages/core/app/services/lakebridge_reconcile_service.py`

```python
class LakebridgeReconcileService:
    def __init__(self) -> None:
        self._config_svc = DatabricksConfigService()

    async def run_reconcile_cli(self, project_id: uuid.UUID) -> LakebridgeJob:
        '''
        Run reconcile via CLI.
        Prerequisite: configure-reconcile must have been run previously
        (sets up workspace resources, dashboards, config file).

        Workflow:
        1. Load DatabricksConfig (raise if missing/disabled)
        2. Create LakebridgeJob row (status=pending, job_type=reconcile)
        3. Create LakebridgeClient
        4. Update job status to "running"
        5. Call client.run_reconcile()
        6. On completion, store recon_id in metadata_json
        7. Update job status
        8. Return job
        '''

    async def run_reconcile_programmatic(
        self,
        project_id: uuid.UUID,
        source_dialect: str,
        source_catalog: str,
        source_schema: str,
        uc_connection_name: str,
        target_catalog: str,
        target_schema: str,
        tables: list[ReconcileTableConfig],
        report_type: str = "all",
    ) -> LakebridgeJob:
        '''
        Run reconcile via Python API (TriggerReconService).
        This gives fine-grained control over table-level configuration.

        Requires databricks-labs-lakebridge to be importable in the
        Workshop server environment.

        Workflow:
        1. Load DatabricksConfig
        2. Create LakebridgeJob row
        3. Build ReconcileConfig and TableRecon from parameters
        4. Call TriggerReconService.trigger_recon()
        5. Store recon_id in metadata_json
        6. Ingest results as ProjectArtifact (kind=RECONCILE_RESULT, group=ARCHITECTURAL_STANDARDS)
        7. Update job status
        8. Return job
        '''

    def _build_reconcile_config(self, source_dialect, source_catalog, source_schema,
                                 uc_connection_name, target_catalog, target_schema, report_type):
        '''Build Lakebridge ReconcileConfig from parameters.'''

    def _build_table_recon(self, tables: list[ReconcileTableConfig]):
        '''Build Lakebridge TableRecon from table configs.'''

    def _ingest_reconcile_results(self, project_id, recon_id, source_dialect):
        '''Create ProjectArtifact from reconcile results.
        - kind = ArtifactKind.RECONCILE_RESULT
        - artifact_group = ArtifactGroup.ARCHITECTURAL_STANDARDS
        - filename = "reconcile_<dialect>_<timestamp>.json"
        '''
```

### 14.2 ReconcileTableConfig

```python
class ReconcileTableConfig(BaseModel):
    source_name: str
    target_name: str
    join_columns: list[str] = []
    column_mapping: dict[str, str] = {}   # source_col -> target_col
    key_type: str = "data"                # schema, row, data, all
```

### 14.3 Reconcile Execution Modes

| Mode | When | How | Trade-off |
|------|------|-----|-----------|
| CLI | Quick check, all tables | `databricks labs lakebridge reconcile` | Simple but coarse; uses pre-configured config |
| Programmatic | Fine-grained, per-table | `TriggerReconService.trigger_recon()` | More setup but per-table control, custom column mappings/thresholds |

---

## 15. Reconciler API Endpoints

| Method | Path | Request | Response | Description |
|--------|------|---------|----------|-------------|
| POST | `/api/projects/{slug}/lakebridge/reconcile` | `ReconcileRequest` | `LakebridgeJobView` (202) | Start reconcile job |
| GET | `/api/projects/{slug}/lakebridge/reconcile/config` | - | `ReconcileConfigView | None` | Get current reconcile config |

**Request schemas:**

```python
class ReconcileRequest(BaseModel):
    mode: str = Field(default="cli", description="Execution mode: cli or programmatic")
    source_dialect: str | None = Field(default=None, description="Required for programmatic mode")
    source_catalog: str | None = None
    source_schema: str | None = None
    uc_connection_name: str | None = None
    target_catalog: str | None = None
    target_schema: str | None = None
    tables: list[ReconcileTableConfig] | None = None
    report_type: str = Field(default="all", description="Report type: schema, row, data, all")

class ReconcileConfigView(BaseModel):
    model_config = _VIEW_CONFIG
    source_dialect: str
    source_catalog: str
    source_schema: str
    uc_connection_name: str | None = None
    target_catalog: str
    target_schema: str
    report_type: str
```

---

## 16. Card Integration

### 16.1 Linking Cards to Lakebridge Jobs

Cards representing migration tasks can be linked to Lakebridge jobs via `metadata_json` on the job:

```python
job.metadata_json["card_id"] = str(card.id)
```

This is optional - not all Lakebridge jobs are card-specific. When a card is linked:

1. **Card status reflects job status:**
   - Job `running` -> Card `in_progress`
   - Job `completed` -> Card `done` (if reconcile also passes)
   - Job `failed` -> Card remains `in_progress` with error note

2. **Card acceptance criteria auto-validation:**
   - Reconcile results are checked against card acceptance_criteria_md
   - If all reconcile checks pass, criteria are marked as validated

### 16.2 Card Action Buttons

UI adds action buttons on cards when a Databricks config exists:

| Button | Condition | Action |
|--------|-----------|--------|
| Analyze | Card has artifacts in `code_to_be_migrated` | POST `/api/projects/{slug}/lakebridge/analyze` |
| Transpile | Card has artifacts in `code_to_be_migrated` | POST `/api/projects/{slug}/lakebridge/transpile` |
| Reconcile | Card has linked transpiled code artifact | POST `/api/projects/{slug}/lakebridge/reconcile` |


---

## 17. Frontend

### 17.1 TypeScript Types

Add to `packages/web/lib/api/types.ts`:

```typescript
export enum LakebridgeJobType {
  ANALYZE = "analyze",
  TRANSPILE_BLADEBRIDGE = "transpile_bladebridge",
  TRANSPILE_MORPHEUS = "transpile_morpheus",
  TRANSPILE_SWITCH = "transpile_switch",
  RECONCILE = "reconcile",
}

export enum LakebridgeJobStatus {
  PENDING = "pending",
  RUNNING = "running",
  COMPLETED = "completed",
  FAILED = "failed",
  CANCELLED = "cancelled",
}

export interface DatabricksConfigView {
  id: string;
  project_id: string;
  workspace_url: string;
  cli_profile: string;
  catalog_name: string;
  schema_name: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface LakebridgeJobView {
  id: string;
  project_id: string;
  job_type: LakebridgeJobType;
  status: LakebridgeJobStatus;
  source_dialect: string;
  transpiler: string | null;
  input_artifact_ids: string[];
  result_artifact_id: string | null;
  cli_command: string;
  cli_stdout: string | null;
  cli_stderr: string | null;
  exit_code: number | null;
  duration_ms: number | null;
  error_message: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AnalyzerSummaryView {
  total_files: number;
  analyzed_files: number;
  skipped_files: number;
  high_complexity_count: number;
  very_high_complexity_count: number;
  source_dialect: string;
  complexity_distribution: Record<string, number>;
}

export interface PrerequisitesView {
  cli_installed: boolean;
  lakebridge_installed: boolean;
  workspace_reachable: boolean;
  all_ok: boolean;
}
```

### 17.2 API Endpoints

Add `packages/web/lib/api/endpoints/lakebridge.ts`:

```typescript
export const lakebridgeApi = {
  async getConfig(slug: string): Promise<DatabricksConfigView> {
    return get<DatabricksConfigView>(`/api/projects/${slug}/lakebridge/config`);
  },
  async saveConfig(slug: string, data: DatabricksConfigCreate): Promise<DatabricksConfigView> {
    return post<DatabricksConfigView, DatabricksConfigCreate>(`/api/projects/${slug}/lakebridge/config`, data);
  },
  async deleteConfig(slug: string): Promise<void> {
    return del(`/api/projects/${slug}/lakebridge/config`);
  },
  async toggleConfig(slug: string, enabled: boolean): Promise<DatabricksConfigView> {
    return patch<DatabricksConfigView>(`/api/projects/${slug}/lakebridge/config/toggle`, { enabled });
  },
  async checkPrerequisites(slug: string): Promise<PrerequisitesView> {
    return get<PrerequisitesView>(`/api/projects/${slug}/lakebridge/prerequisites`);
  },
  async runAnalyze(slug: string, data: AnalyzeRequest): Promise<LakebridgeJobView> {
    return post<LakebridgeJobView, AnalyzeRequest>(`/api/projects/${slug}/lakebridge/analyze`, data);
  },
  async getAnalyzerSummary(slug: string): Promise<AnalyzerSummaryView> {
    return get<AnalyzerSummaryView>(`/api/projects/${slug}/lakebridge/analyze/summary`);
  },
  async runTranspile(slug: string, data: TranspileRequest): Promise<LakebridgeJobView> {
    return post<LakebridgeJobView, TranspileRequest>(`/api/projects/${slug}/lakebridge/transpile`, data);
  },
  async getDialectSupport(slug: string): Promise<DialectSupportView> {
    return get<DialectSupportView>(`/api/projects/${slug}/lakebridge/transpile/dialects`);
  },
  async runReconcile(slug: string, data: ReconcileRequest): Promise<LakebridgeJobView> {
    return post<LakebridgeJobView, ReconcileRequest>(`/api/projects/${slug}/lakebridge/reconcile`, data);
  },
  async listJobs(slug: string): Promise<LakebridgeJobView[]> {
    return get<LakebridgeJobView[]>(`/api/projects/${slug}/lakebridge/jobs`);
  },
  async getJob(slug: string, jobId: string): Promise<LakebridgeJobView> {
    return get<LakebridgeJobView>(`/api/projects/${slug}/lakebridge/jobs/${jobId}`);
  },
  async cancelJob(slug: string, jobId: string): Promise<LakebridgeJobView> {
    return post<LakebridgeJobView>(`/api/projects/${slug}/lakebridge/jobs/${jobId}/cancel`, {});
  },
  async refreshJob(slug: string, jobId: string): Promise<LakebridgeJobView> {
    return post<LakebridgeJobView>(`/api/projects/${slug}/lakebridge/jobs/${jobId}/refresh`, {});
  },
};
```

### 17.3 TanStack Query Hooks

Add `packages/web/lib/api/queries/use-lakebridge.ts`:

```typescript
export function useDatabricksConfig(projectSlug: string) {
  return useQuery({
    queryKey: queryKeys.lakebridgeConfig(projectSlug),
    queryFn: () => lakebridgeApi.getConfig(projectSlug),
    enabled: !!projectSlug,
    staleTime: 5 * 60 * 1000,
  });
}

export function useSaveDatabricksConfig(projectSlug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: DatabricksConfigCreate) => lakebridgeApi.saveConfig(projectSlug, data),
    onSuccess: () => invalidateLakebridge(projectSlug),
  });
}

export function useDeleteDatabricksConfig(projectSlug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => lakebridgeApi.deleteConfig(projectSlug),
    onSuccess: () => invalidateLakebridge(projectSlug),
  });
}

export function useLakebridgeJobs(projectSlug: string) {
  return useQuery({
    queryKey: queryKeys.lakebridgeJobs(projectSlug),
    queryFn: () => lakebridgeApi.listJobs(projectSlug),
    enabled: !!projectSlug,
    staleTime: 30 * 1000,
  });
}

export function useRunAnalyze(projectSlug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AnalyzeRequest) => lakebridgeApi.runAnalyze(projectSlug, data),
    onSuccess: () => invalidateLakebridge(projectSlug),
  });
}

export function useRunTranspile(projectSlug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TranspileRequest) => lakebridgeApi.runTranspile(projectSlug, data),
    onSuccess: () => invalidateLakebridge(projectSlug),
  });
}

export function useRunReconcile(projectSlug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ReconcileRequest) => lakebridgeApi.runReconcile(projectSlug, data),
    onSuccess: () => invalidateLakebridge(projectSlug),
  });
}

export function useAnalyzerSummary(projectSlug: string) {
  return useQuery({
    queryKey: queryKeys.lakebridgeAnalyzerSummary(projectSlug),
    queryFn: () => lakebridgeApi.getAnalyzerSummary(projectSlug),
    enabled: !!projectSlug,
    staleTime: 2 * 60 * 1000,
  });
}

export function usePrerequisites(projectSlug: string) {
  return useQuery({
    queryKey: queryKeys.lakebridgePrerequisites(projectSlug),
    queryFn: () => lakebridgeApi.checkPrerequisites(projectSlug),
    enabled: !!projectSlug,
    staleTime: 60 * 1000,
  });
}
```

### 17.4 Query Keys

Add to `packages/web/lib/query-client.ts`:

```typescript
lakebridgeConfig: (slug: string) => ['projects', slug, 'lakebridge', 'config'] as const,
lakebridgeJobs: (slug: string) => ['projects', slug, 'lakebridge', 'jobs'] as const,
lakebridgeAnalyzerSummary: (slug: string) => ['projects', slug, 'lakebridge', 'analyzer-summary'] as const,
lakebridgePrerequisites: (slug: string) => ['projects', slug, 'lakebridge', 'prerequisites'] as const,
```

Add invalidation helper:

```typescript
export function invalidateLakebridge(projectSlug: string) {
  queryClient.invalidateQueries({ queryKey: ['projects', projectSlug, 'lakebridge'] });
}
```


---

## 18. UI Components

### 18.1 DatabricksConfigForm

Location: `packages/web/components/lakebridge/DatabricksConfigForm.tsx`

Fields:
- Workspace URL (text input, required)
- CLI Profile (text input, default "DEFAULT")
- Personal Access Token (password input, required)
- Catalog Name (text input, default "remorph")
- Schema Name (text input, default "transpiler")

Actions:
- Save (calls `useSaveDatabricksConfig`)
- Delete (calls `useDeleteDatabricksConfig`, with confirmation)
- Toggle Enabled (switch toggle, calls `toggleConfig`)

Prerequisites banner: Shows `PrerequisitesView` status before allowing operations.

### 18.2 LakebridgeJobList

Location: `packages/web/components/lakebridge/LakebridgeJobList.tsx`

Table showing all Lakebridge jobs for the project:
- Columns: Type, Status (with badge), Source Dialect, Transpiler, Duration, Created, Actions
- Status badges: pending (gray), running (blue, animated), completed (green), failed (red), cancelled (gray)
- Actions: View Details, Cancel (if running), Refresh (if Switch type)

### 18.3 LakebridgeJobDetail

Location: `packages/web/components/lakebridge/LakebridgeJobDetail.tsx`

Panel/drawer showing:
- Full CLI command
- Stdout/stderr (collapsible, syntax-highlighted)
- Exit code
- Duration
- Error message (if failed)
- Metadata JSON (collapsible)
- Link to result artifact

### 18.4 AnalyzerSummaryCard

Location: `packages/web/components/lakebridge/AnalyzerSummaryCard.tsx`

Card showing latest analysis summary:
- Total files analyzed
- Complexity distribution (bar chart: LOW/MEDIUM/HIGH/VERY HIGH)
- Source dialect
- Timestamp

### 18.5 LakebridgePanel

Location: `packages/web/components/lakebridge/LakebridgePanel.tsx`

Project-level panel (tab or sidebar) containing:
- DatabricksConfigForm (if no config) or config summary + edit
- Prerequisites status
- AnalyzerSummaryCard (if analysis exists)
- Action buttons: Analyze, Transpile, Reconcile
- LakebridgeJobList

---

## 19. Export Integration

### 19.1 Lakebridge Data in Export

When exporting a project (FilesystemExporter/ZipExporter), Lakebridge data is included in the `.agents/` directory:

```
.agents/
  lakebridge/
    config.json              # DatabricksConfigView (PAT masked)
    analyzer-report.json     # Latest analyzer report artifact content
    transpiled-code/         # Latest transpiled output files
    reconcile-results.json   # Latest reconcile results
    jobs.json                # LakebridgeJobView[] summary
```

### 19.2 PAT Masking in Export

The exported `config.json` replaces `pat_enc` with `"***MASKED***"`. Consuming agents must configure their own Databricks credentials.

---

## 20. Security Considerations

### 20.1 PAT Encryption

- PAT is encrypted with Fernet at rest (same key as MCP secrets)
- PAT is never included in API responses (omitted from `DatabricksConfigView`)
- PAT is never included in exports (masked)
- PAT is decrypted only in `LakebridgeClient._run_cli()` and set as process environment variable
- PAT is never logged

### 20.2 Subprocess Security

- `LakebridgeClient` runs `databricks labs lakebridge` as a subprocess
- Environment variables (`DATABRICKS_TOKEN`, `DATABRICKS_HOST`) are set only for the subprocess, not globally
- Subprocess runs with the Workshop server's OS user (no privilege escalation)
- Timeout enforced to prevent hung processes
- Output truncated to 64KB to prevent memory exhaustion

### 20.3 Input Validation

- `source_dialect` validated against known dialects (from DIALECT_SUPPORT_MAP)
- `transpiler` validated against known transpiler names
- Artifact IDs validated to belong to the project
- File paths sanitized (no path traversal)

---

## 21. Error Handling

### 21.1 Error Scenarios

| Scenario | Handling |
|----------|----------|
| Databricks config not found | 404 with clear message: "Databricks config not found. Configure via POST /api/projects/{slug}/lakebridge/config" |
| Databricks config disabled | 400: "Lakebridge integration is disabled" |
| CLI not installed | PrerequisitesView shows `cli_installed: false`; analyze/transpile/reconcile return 503 |
| Lakebridge not installed | PrerequisitesView shows `lakebridge_installed: false`; operations return 503 |
| Workspace unreachable | PrerequisitesView shows `workspace_reachable: false`; operations return 503 |
| Unsupported dialect | 400: "Transpiler '<name>' does not support dialect '<dialect>'" |
| CLI timeout | Job status set to "failed" with `error_message: "CLI execution timed out after <N>s"` |
| CLI non-zero exit | Job status set to "failed" with `exit_code` and `cli_stderr` captured |
| Switch job failed | Polling detects failure; job status set to "failed" with Databricks job run error |
| No artifacts to analyze | 400: "No artifacts found in 'code_to_be_migrated' group" |
| Reconcile config missing | 400: "Run 'databricks labs lakebridge configure-reconcile' first" |

### 21.2 Retry Policy

- **CLI commands:** No automatic retry (idempotency not guaranteed)
- **Switch job polling:** Exponential backoff, max 30 minutes
- **Prerequisites check:** Cached for 5 minutes (staleTime in frontend)

---

## 22. Testing Strategy

### 22.1 Unit Tests

| Test | Target | What |
|------|--------|------|
| `test_databricks_config_service` | `DatabricksConfigService` | CRUD, encryption/decryption, toggle |
| `test_lakebridge_client` | `LakebridgeClient` | CLI argument construction, env vars, timeout, output truncation |
| `test_lakebridge_analyzer_service` | `LakebridgeAnalyzerService` | Workflow steps, JSON parsing, artifact ingestion |
| `test_lakebridge_transpile_service` | `LakebridgeTranspileService` | Dialect validation, workflow, output ingestion |
| `test_lakebridge_reconcile_service` | `LakebridgeReconcileService` | CLI mode, programmatic mode, config building |
| `test_dialect_support_map` | `DIALECT_SUPPORT_MAP` | Completeness, consistency |

### 22.2 Integration Tests

| Test | What |
|------|------|
| `test_lakebridge_cli_e2e` | Full analyze workflow with mock Databricks CLI (requires `databricks` on PATH) |
| `test_lakebridge_api_e2e` | Full API flow: config -> analyze -> jobs -> summary |

### 22.3 Mock Strategy

- `LakebridgeClient` is mockable: inject a mock that returns predetermined `LakebridgeCliResult`
- Databricks CLI can be mocked with a shell script that echoes expected output
- Reconciler programmatic API can be mocked by patching `TriggerReconService.trigger_recon`

---

## 23. Deployment Considerations

### 23.1 Prerequisites

The Workshop server host must have:
1. **Databricks CLI** installed and configured (`databricks` on PATH)
2. **Lakebridge** installed (`databricks labs install lakebridge`)
3. **Java 11+** (if using Morpheus transpiler)
4. **Network access** to the Databricks workspace

### 23.2 Optional: Lakebridge Python Package

For programmatic reconcile, `databricks-labs-lakebridge` must be importable:
```bash
pip install databricks-labs-lakebridge
```

This is optional - CLI-only mode works without it.

### 23.3 Configuration

No Workshop server configuration changes needed. All Lakebridge config is per-project via the API.

---

## 24. Summary of New Artifacts

| Artifact | Location | Description |
|----------|----------|-------------|
| `packages/core/app/domain/lakebridge.py` | ORM models | `DatabricksConfig`, `LakebridgeJob` |
| `packages/core/app/enums.py` | Additions | `LakebridgeJobType`, `LakebridgeJobStatus` |
| `packages/core/app/schemas/views.py` | Additions | `DatabricksConfigView`, `LakebridgeJobView`, `AnalyzerSummaryView` |
| `packages/core/app/services/databricks_config_service.py` | New | Config CRUD + encryption |
| `packages/core/app/services/lakebridge_client.py` | New | CLI subprocess wrapper |
| `packages/core/app/services/lakebridge_analyzer_service.py` | New | Analyzer orchestration |
| `packages/core/app/services/lakebridge_transpile_service.py` | New | Transpiler orchestration |
| `packages/core/app/services/lakebridge_reconcile_service.py` | New | Reconciler orchestration |
| `packages/core/app/api/lakebridge.py` | New | API router (20 endpoints) |
| `packages/core/alembic/versions/*_lakebridge_tables.py` | New | Migration |
| `packages/web/lib/api/types.ts` | Additions | TypeScript types + enums |
| `packages/web/lib/api/endpoints/lakebridge.ts` | New | API client |
| `packages/web/lib/api/queries/use-lakebridge.ts` | New | TanStack Query hooks |
| `packages/web/components/lakebridge/` | New | UI components (5 files) |

**Total new files:** 10 backend + 4 frontend = 14
**Total new endpoints:** 20
**Total new DB tables:** 2
**Total new enums:** 2 (+ 3 new ArtifactKind values)
