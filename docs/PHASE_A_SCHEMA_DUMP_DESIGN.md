# Phase A: Schema Dump & Structural Comparison — Full Design Document

> Captures the complete analysis from sessions on 2026-05-29.
> Covers: SSIS parser gaps, context management design, Lakebridge credentials,
> phased plan (A→B), and codebase patterns study.

---

## Table of Contents

1. [SSIS Parser Gaps — Prioritized](#1-ssis-parser-gaps--prioritized)
2. [Context Management — MigrationAnalysisContext](#2-context-management--migrationanalysiscontext)
3. [Lakebridge Credential Architecture](#3-lakebridge-credential-architecture)
4. [Phased Plan: A (Schema Dump) → B (Lakebridge)](#4-phased-plan-a-schema-dump--b-lakebridge)
5. [Codebase Patterns & Conventions](#5-codebase-patterns--conventions)
6. [Key Gaps Confirmed in Code](#6-key-gaps-confirmed-in-code)

---

## 1. SSIS Parser Gaps — Prioritized

### 1.1 Critical gaps (directly affect migration correctness)

| Gap | What's Missing | Why It Matters |
|-----|---------------|----------------|
| **Transform internals** | Derived column expressions, lookup mappings, merge join keys, conditional split conditions, aggregate functions, SCD configuration | These are the **core transformation logic** being migrated. Currently the LLM sees "Lookup (name only)" — it can't reason about what the lookup does |
| **Data flow path topology** | Which source output connects to which transform input, which transform output connects to which destination input | Without this, the data flow is a **flat list** of components with no wiring — the LLM can't understand the pipeline structure |
| **Execute SQL parameter bindings** | Parameter names, types, directions, result set bindings | Parameterized SQL is captured as raw text with `?` placeholders but the bindings are lost |
| **Script Task content** | C#/VB.NET code in `ScriptProject` element | Script tasks contain arbitrary logic — currently invisible |
| **Event handlers** | OnError, OnWarning executables with their own tasks | Error handling is part of operational correctness — the profile YAML lists `event_handlers` as a pattern but the parser never reads them |
| **Variable/Parameter data types** | `DTS:DataType` attribute exists but is never read | Variables drive dynamic SQL and expressions — their type matters for type mapping |

### 1.2 Moderate gaps (affect completeness but not core logic)

| Gap | What's Missing |
|-----|---------------|
| **Package configurations** | XML config, SQL Server config, env var config — runtime overrides of design-time values |
| **For/Foreach loop logic** | InitExpression, EvalExpression, AssignExpression, enumerator type, variable mappings |
| **Execute Package references** | Child package name, ID, parameter passing |
| **Precedence constraint LogicalAnd** | When multiple constraints converge: AND or OR? |
| **Full SQL statements** | Currently truncated at 200 chars in the LLM prompt |
| **Connection manager GUID** | Components reference connections by GUID but the parser doesn't capture it — matching is fragile |

### 1.3 Low gaps (nice to have)

| Gap | What's Missing |
|-----|---------------|
| Log providers | Log provider type and configuration |
| Protection level | EncryptSensitiveWithUserKey, DontSaveSensitive, etc. |
| Transaction isolation | Required/Supported/NotSupported per container |
| Checkpoint/restart | CheckpointUsage, ForceExecutionResult, DelayValidation |
| LocaleID | Locale-specific string comparisons |
| Task properties dict | Generic properties bag per task |
| Annotation positions | X/Y coordinates for visual layout |

---

## 2. Context Management — MigrationAnalysisContext

### 2.1 Current state: massive unused budget

The analysis LLM call uses ~5,650 tokens out of 200K (Claude) or 128K (GPT-4o). **95%+ of the context window is empty.** You could add 100KB+ of additional context without concern.

### 2.2 The problem isn't budget — it's **structure**

Currently, context is assembled ad-hoc in multiple places:

| Where | What it builds | Limitation |
|-------|---------------|------------|
| `analyzer.py._format_package_summary()` | Package structure for LLM | Truncates SQL at 200 chars, omits transform properties, omits columns |
| `analyzer.py._format_context()` | Resolved decisions + business rules | Only 10 of each, no schema info |
| `project_context_service.py` | ProjectContext for general prompts | Doesn't include migration-specific context |
| `context/service.py.get_context_summary_for_prompt()` | Migration context summary | Only connections, rules, decisions — no schema, no lineage |

### 2.3 Proposed: Unified `MigrationAnalysisContext`

```python
class MigrationAnalysisContext(BaseModel):
    """Complete context for any migration-related LLM call.

    Assembled ONCE per analysis run, then passed to whichever
    prompt needs it. No more ad-hoc formatting.
    """

    # --- Existing (from ProjectContext) ---
    objective: str
    qa: dict[str, str]
    tech_choices_by_dimension: dict[str, list[TechChoiceView]]
    context_notes_md: str

    # --- Existing (from migration context) ---
    resolved_decisions: list[ResolvedDecisionView]
    business_rules: list[BusinessRuleView]
    connections: list[ConnectionView]

    # --- NEW: Structural (from SSIS parse) ---
    package_structure: PackageStructureContext

    # --- NEW: Schema (from DB introspection or uploaded dump) ---
    source_schema: DatabaseSchema | None          # from Option A or B
    target_schema: DatabaseSchema | None          # from Databricks query

    # --- NEW: Lineage (from connection points + object registry) ---
    column_lineage: list[ColumnLineage]
    object_refs: list[PackageObjectRefView]       # which tasks touch which tables/columns

    # --- NEW: Cross-package (from migration map) ---
    related_packages: list[RelatedPackageView]     # packages sharing objects
    shared_decisions: list[ResolvedDecisionView]   # decisions from related packages

    # --- NEW: Structural comparison (if generated) ---
    structural_comparison: StructuralComparisonResult | None
```

And the key sub-model:

```python
class PackageStructureContext(BaseModel):
    """Rich structural context from SSIS parse.

    This is what _format_package_summary() SHOULD produce —
    full structure, not truncated summaries.
    """
    # Control flow
    tasks: list[TaskView]                        # full detail, not truncated
    precedence_constraints: list[PrecedenceConstraintView]
    event_handlers: list[EventHandlerView]       # NEW — currently unparsed

    # Data flows (FULL detail)
    data_flows: list[DataFlowDetailView]
    # Each with: sources (with columns), transforms (with properties/expressions),
    #            destinations (with column mappings), paths (wiring topology)

    # Variables/Parameters (FULL detail)
    variables: list[VariableView]                # including data_type, value, expression
    parameters: list[ParameterView]              # including data_type

    # Connections (FULL detail)
    connection_managers: list[ConnectionManagerDetailView]

    # Disabled tasks (with reasons if determinable)
    disabled_tasks: list[DisabledTaskView]

    # Parse warnings
    parse_warnings: list[str]

    # What COULDN'T be parsed (explicit gaps)
    unparsed_features: list[UnparsedFeature]     # NEW — tells the LLM what it doesn't know
```

The critical addition is `unparsed_features`:

```python
class UnparsedFeature(BaseModel):
    feature: str          # e.g. "event_handlers", "script_tasks", "transform_expressions"
    count: int            # how many instances exist
    location: str         # where in the package
    note: str             # e.g. "3 Script Tasks contain C# logic not parseable from XML"
```

This tells the LLM **what it doesn't know** — so it can flag those as risks instead of silently ignoring them.

### 2.4 How context flows through the pipeline

```
                    ┌──────────────────┐
                    │  SSIS Parse      │ ← ENHANCE: parse transforms, event handlers,
                    │  (enriched)      │   variable types, data flow paths
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Schema Dump     │ ← NEW: Option A (uploaded) or B (Lakebridge Profiler)
                    │  (source DB)     │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Databricks      │ ← NEW: query Unity Catalog for target schema
                    │  Target Schema   │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Migration       │ ← EXISTING: decisions, rules, connections
                    │  Context         │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Migration       │ ← ALL context assembled here
                    │  AnalysisContext │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────▼──┐  ┌───────▼──────┐  ┌───▼──────────┐
    │ Analysis   │  │ Generation   │  │ Reconciliation│
    │ LLM prompt │  │ LLM/template │  │ Agent prompt  │
    └────────────┘  └──────────────┘  └───────────────┘
```

Every downstream consumer gets the **same** `MigrationAnalysisContext` — no more ad-hoc formatting, no more truncated SQL, no more missing transform details.

---

## 3. Lakebridge Credential Architecture

### 3.1 Key insight: Lakebridge does NOT need source DB credentials from Workshop

| Component | Source DB Access? | How |
|-----------|-------------------|-----|
| **Analyzer** | No | Scans local files only |
| **Profiler** | Yes | Connects from **within Databricks** via Unity Catalog Connections |
| **Transpiler** | No | Operates on local files only |
| **Reconciler** | Yes | Connects from **within Databricks** via Unity Catalog Connections |

The Workshop only stores:
- **Databricks PAT** (Fernet-encrypted in `databricks_configs.pat_enc`)
- **Workspace URL** + **Catalog/Schema**

Source DB credentials live **in the Databricks workspace** as Unity Catalog Connections (JDBC URLs, usernames, passwords). The Workshop never sees them.

### 3.2 But yes, credentials ARE needed — just not by Workshop directly

The user must:
1. Have a **Databricks workspace** (even a free trial works)
2. Configure a **Unity Catalog Connection** to the source SQL Server (within Databricks)
3. Provide a **Databricks PAT** to Workshop

This means Lakebridge can connect to any database that Databricks supports via Unity Catalog Connections — which is extensive (SQL Server, Oracle, PostgreSQL, MySQL, Snowflake, Redshift, etc.).

### 3.3 Credential storage pattern (from SPEC_MCP_CONFIG.md)

- Databricks PAT: Fernet-encrypted in `databricks_configs` table (`pat_enc` column)
- Source DB JDBC credentials: Stored in Databricks Unity Catalog, NOT in Workshop
- Encryption key: Server-side secret, loaded from environment variable
- All encrypted fields use `Fernet.encrypt()` / `Fernet.decrypt()` at read/write boundary

---

## 4. Phased Plan: A (Schema Dump) → B (Lakebridge)

### 4.1 Design Principle

Phase A and B share the same schema infrastructure:

```
Phase A: schema.json (uploaded)  ──┐
                                    ├──► DatabaseSchema ──► MigrationAnalysisContext
Phase B: Profiler output (auto)  ──┘
```

Whether the schema comes from a manual upload or an automated Lakebridge Profiler call, the downstream consumers (structural comparison, LLM context, reconciliation) don't care. This means Phase A works standalone, and Phase B is a **drop-in upgrade** that automates what Phase A does manually.

### 4.2 Phase A: Schema Dump Upload (zero new dependencies)

**Goal**: Users provide source DB schema as a structured file. Workshop uses it for structural comparison and LLM context enrichment.

| Step | What | Detail |
|------|------|--------|
| A1 | Define `DatabaseSchema` schema | Dialect-agnostic: `tables: list[TableSchema]`, each with `name`, `schema_name`, `columns: list[ColumnSchema]` (name, data_type, nullable, is_pk, is_fk, default, length/precision/scale), `foreign_keys`, `indexes`, `row_count` (optional), `constraints`. |
| A2 | Build `workshop schema-dump` CLI command | Emits SQL queries for the target dialect. For SQL Server: queries `INFORMATION_SCHEMA.*` + `sys.*` views. For PostgreSQL: queries `information_schema.*` + `pg_catalog.*`. Outputs JSON. **The user runs this against their DB** — Workshop never connects directly. |
| A3 | Build `SchemaDumpExtractor` | Reads uploaded JSON artifact, validates against `DatabaseSchema` schema, returns structured object. |
| A4 | Wire into `MigrationAnalysisContext` | Add `source_schema: DatabaseSchema | None` field. When a schema dump artifact exists, parse it and include in context. |
| A5 | Enhance analysis LLM prompt | Add `_format_schema_context()` method that renders: table DDL summaries, column type mappings (SSIS type → DB type → Databricks type), row counts, constraint info. |
| A6 | Build `StructuralComparator` | Compare SSIS-declared columns (from parse) against actual DB columns (from schema dump). Flag: columns in SSIS not in DB (stale), columns in DB not in SSIS (missing), type mismatches. |
| A7 | Build SSIS→Databricks type mapping | `dt_str`→`STRING`, `dt_i4`→`INT`, `dt_numeric`→`DECIMAL(p,s)`, `dt_dbtimestamp`→`TIMESTAMP`, etc. Used by structural comparison and LLM context. |

**What the user experience looks like:**
```bash
# Step 1: User runs against their SQL Server (one-time)
workshop schema-dump --dialect mssql --connection "Server=prod-sql;Database=ETL_DB;" --output schema.json

# Step 2: User uploads the dump
workshop artifact upload schema.json --kind spec --group architectural_standards

# Step 3: Workshop uses it automatically in analysis and comparison
workshop skill propose   # LLM now sees actual DB schema, not just SSIS design-time metadata
```

### 4.3 Phase B: Lakebridge Integration (requires Databricks workspace)

**Goal**: Use Lakebridge Profiler for schema extraction and Reconciler for data comparison — both connecting to source DB from within Databricks.

| Step | What | Detail |
|------|------|--------|
| B1 | Add `databricks_configs` table + ORM | Per-project Databricks workspace connection (workspace_url, cli_profile, pat_enc, catalog_name, schema_name). Fernet-encrypted PAT. |
| B2 | Build `LakebridgeClient` | Async subprocess wrapper: `databricks labs lakebridge <command>`. Decrypts PAT, sets `DATABRICKS_TOKEN` + `DATABRICKS_HOST` env vars, runs subprocess, captures stdout/stderr, handles timeouts. |
| B3 | Build `LakebridgeAnalyzerService` | Orchestrates `analyze` command. Ingests JSON output as artifact. This is Phase 1 of the Lakebridge spec — already fully designed. |
| B4 | Build `LakebridgeProfilerService` | Orchestrates `execute-database-profiler`. Requires Unity Catalog Connection to source DB (configured in Databricks, not Workshop). Ingests profiler output as `DatabaseSchema` artifact — **reuses Phase A's schema infrastructure**. |
| B5 | Build `LakebridgeReconcilerService` | Orchestrates `reconcile` (CLI + programmatic). Uses `uc_connection_name` for source DB access. Ingests results into `ReconciliationRun` table — **reuses Phase A's reconciliation infrastructure** but with real data instead of stubs. |
| B6 | Wire Profiler output → `MigrationAnalysisContext` | Profiler output IS a `DatabaseSchema` — same as Option A's uploaded dump. The context assembly doesn't care where the schema came from. |
| B7 | Wire Reconciler results → signoff | Auto-populate checklist items from reconciliation results. |
| B8 | UI: Databricks config page | Settings page for workspace URL, PAT, catalog/schema. Connection test button. |

**What the user experience looks like:**
```bash
# Step 1: User configures Databricks workspace (one-time per project)
workshop project config-databricks --workspace-url https://myorg.cloud.databricks.com --pat ...

# Step 2: User configures Unity Catalog Connection in Databricks (one-time, in Databricks UI)
# (Workshop never sees source DB credentials)

# Step 3: Profiler extracts schema automatically
workshop migration profile --package my-package --uc-connection sqlserver-prod
# → Lakebridge connects to SQL Server FROM Databricks, extracts schema + metrics
# → Stored as DatabaseSchema artifact (same format as Phase A)

# Step 4: Reconciler compares data automatically
workshop migration reconcile --package my-package --uc-connection sqlserver-prod
# → Lakebridge compares source vs Databricks: schema, row counts, data values
# → Results stored in reconciliation_runs table
# → Evidence report generated
# → Signoff checklist auto-populated
```

### 4.4 DatabaseSchema Format (shared by Phase A and B)

```json
{
  "dialect": "mssql",
  "database_name": "ETL_DB",
  "schema_name": "dbo",
  "extracted_at": "2026-05-29T10:00:00Z",
  "extraction_method": "schema_dump_cli",
  "tables": [
    {
      "schema_name": "dbo",
      "table_name": "Customer",
      "table_type": "BASE TABLE",
      "row_count": 1500000,
      "columns": [
        {
          "name": "CustomerID",
          "ordinal_position": 1,
          "data_type": "int",
          "max_length": 4,
          "precision": 10,
          "scale": 0,
          "is_nullable": false,
          "is_identity": true,
          "is_primary_key": true,
          "is_foreign_key": false,
          "default_value": "NEXT VALUE FOR CustomerSeq"
        },
        {
          "name": "CustomerName",
          "ordinal_position": 2,
          "data_type": "nvarchar",
          "max_length": 200,
          "precision": 0,
          "scale": 0,
          "is_nullable": false,
          "is_identity": false,
          "is_primary_key": false,
          "is_foreign_key": false,
          "default_value": null
        }
      ],
      "primary_key": {
        "name": "PK_Customer",
        "columns": ["CustomerID"]
      },
      "foreign_keys": [
        {
          "name": "FK_Customer_Region",
          "columns": ["RegionID"],
          "referenced_table": "Region",
          "referenced_columns": ["RegionID"]
        }
      ],
      "indexes": [
        {
          "name": "IX_Customer_Name",
          "columns": ["CustomerName"],
          "is_unique": false,
          "type": "NONCLUSTERED"
        }
      ],
      "constraints": []
    }
  ],
  "views": [],
  "stored_procedures": [],
  "functions": []
}
```

### 4.5 SSIS → Databricks Type Mapping (Phase A7)

| SSIS DataType | SQL Server Type | Databricks Type |
|--------------|----------------|-----------------|
| `dt_str` / `dt_wstr` | varchar / nvarchar | `STRING` |
| `dt_i1` | tinyint | `TINYINT` |
| `dt_i2` | smallint | `SMALLINT` |
| `dt_i4` | int | `INT` |
| `dt_i8` | bigint | `BIGINT` |
| `dt_r4` | real / float(24) | `FLOAT` |
| `dt_r8` | float / float(53) | `DOUBLE` |
| `dt_numeric` | decimal(p,s) | `DECIMAL(p,s)` |
| `dt_bool` | bit | `BOOLEAN` |
| `dt_date` | date | `DATE` |
| `dt_dbtimestamp` | datetime / datetime2 | `TIMESTAMP` |
| `dt_dbtime` | time | `STRING` (no TIME type in Delta) |
| `dt_bytes` | varbinary | `BINARY` |
| `dt_guid` | uniqueidentifier | `STRING` |
| `dt_dbtimestampoffset` | datetimeoffset | `TIMESTAMP` (loses offset) |

---

## 5. Codebase Patterns & Conventions

### 5.1 ORM Models (`models.py`)

- **Base classes**: `UuidPkMixin`, `TimestampsMixin`, `Base` (from `app.domain.base`)
- **PK**: `id: Mapped[uuid.UUID]` with `server_default=func.gen_random_uuid()`
- **Enums**: Stored as `String(20)` with CHECK constraints via `_values_csv()` (tuple of string values, NOT `StrEnum`)
- **JSON**: `JSONB` for flexible dicts, `ARRAY(Text)` for string lists, `ARRAY(UUID)` for UUID lists
- **Relationships**: `relationship()` with `back_populates`, `foreign_keys`, `uselist`, `cascade`
- **Constraints**: `UniqueConstraint`, `CheckConstraint`, `Index` in `__table_args__` tuple
- **Naming**: snake_case table names, `uq_` prefix for uniques, `ix_` for indexes, `ck_` for checks

### 5.2 Pydantic Schemas

- **Base class**: `BaseModel` from pydantic v2
- **Enums**: `class Foo(str, Enum)` — NOT `StrEnum` from stdlib
- **Naming**: `FooBase` → `FooCreate` → `FooUpdate` → `FooView` (with `model_config = {"from_attributes": True}`)
- **Fields**: `Field(...)` for required, `Field(default_factory=list)` for lists, `| None` for optional
- **Post-init**: `model_post_init()` for computed fields
- **Forward refs**: `model_rebuild()` at bottom of file

### 5.3 Services

- **DI**: `__init__(self, session: Session)` — synchronous, receives SQLAlchemy Session
- **DB access**: `self.session.get()`, `self.session.execute(select(...))`, `self.session.scalars()`
- **LLM access**: `PackageAnalyzer` receives `LLMService` separately, not through Session
- **Return types**: Pydantic models (Views), ORM models, or primitive dicts
- **Naming**: `get_X_or_raise()`, `list_X()`, `register_X()`, `find_X()`

### 5.4 SSIS Parser

- **XML parsing**: `xml.etree.ElementTree`, DTS namespace `"{www.microsoft.com/SqlServer/Dts}"`
- **Component classification**: by `componentClassID` attribute — "Source"/"Destination" in name
- **Properties**: iterates `<property name="...">` elements
- **Columns**: parses `<outputColumn>` with `dataType`, `length`, `precision`, `scale` attributes
- **Column mappings**: parses `<inputColumn>` + `<externalMetadataColumn>` for destination mappings
- **Gaps confirmed in parser code**:
  - Variable `data_type` never read (line 289: `Variable()` created without `data_type`)
  - Parameter `data_type` never read (line 319: `Parameter()` created without `data_type`)
  - Transform `_parse_transform_component()` only reads `properties` dict — no expressions, no input/output columns
  - No data flow paths (which output connects to which input)
  - No event handlers parsed
  - SQL truncated at 200 chars in `_format_package_summary()` (analyzer.py:247)

### 5.5 Context Service

- **Assembly**: `get_project_context()` builds `ProjectContext` from DB queries (packages, connections, rules, decisions)
- **LLM formatting**: `get_context_summary_for_prompt()` renders Markdown — connections, rules, decisions (10 max)
- **Missing**: No schema info, no column lineage, no structural comparison, no source/target DB metadata

### 5.6 CLI

- **Framework**: `typer` with `rich` for output
- **Pattern**: `app = typer.Typer(no_args_is_help=True)`, commands as `@app.command()`
- **API calls**: `api_get()`, `api_post()` from `workshop._common` — CLI talks to REST API, not DB directly
- **Options**: `typer.Option(...)` with `--long`, `-s` short flags

### 5.7 LLM

- **Prompt**: `ChatPrompt[T]` with `system`, `messages: list[ChatMessage]`, `response_schema: type[BaseModel]`, `temperature`
- **Result**: `ChatResult` with `.parsed` (typed), `.raw_text`, token counts
- **Service**: `LLMService.run(prompt)` → `ChatResult`

### 5.8 Cross-cutting Enums (`app/enums.py`)

- All enums are `StrEnum` (Python 3.11+)
- Stored in Postgres as plain `TEXT` with CHECK constraint via `values_csv(enum_cls)`
- Key enums: `ProjectStatus`, `ProjectType`, `ArtifactKind`, `ExtractionStatus`, `SkillKind`, `GapStatus`, `CardType`, `Priority`, `TechChoiceRole`, `LlmRunKind`, `UserRole`

---

## 6. Key Gaps Confirmed in Code

These are the specific, line-level gaps found by reading the actual source files:

| # | Gap | Location | Detail |
|---|-----|----------|--------|
| 1 | Reconciliation stubs | `reconciliation/service.py:210-280` | All 5 check types in `_run_check()` return hardcoded values (ROW_COUNT=10000, CHECKSUM="abc123", KEY_MATCH=0 missing, AGGREGATE=1M, SAMPLE_DATA="5 rows") |
| 2 | No run persistence | `reconciliation/service.py:293-302` | `list_runs()` returns `[]`, `get_run()` returns `None` — both have TODO comments |
| 3 | No ReconciliationRun ORM model | `models.py` (missing) | No table to persist reconciliation results |
| 4 | `discovered_columns` never populated | `models.py:654` | `MigrationObject.discovered_columns: Mapped[dict | None] = mapped_column(JSONB, nullable=True)` — field exists but never written |
| 5 | `columns_accessed` never populated | `models.py:719` | `PackageObjectRef.columns_accessed: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)` — field exists but never written |
| 6 | Signoff not wired to reconciliation | `signoff/service.py:70-83` | `pr_02` ("Row counts match") and `pr_03` ("Checksums match") are checklist items but never auto-populated from reconciliation results |
| 7 | `validating` status never set | `models.py:49` | `PACKAGE_STATUS_VALUES` includes `"validating"` but no code path ever sets it |
| 8 | Variable data_type not parsed | `analysis/parsers/ssis.py:289` | `Variable()` created without `data_type` — the `DTS:DataType` XML attribute exists but is never read |
| 9 | Parameter data_type not parsed | `analysis/parsers/ssis.py:319` | `Parameter()` created without `data_type` — same issue as variables |
| 10 | Transform internals missing | `analysis/parsers/ssis.py:611-634` | `_parse_transform_component()` only reads flat `properties` dict — no expressions, no input/output columns, no structured transform-specific data |
| 11 | No data flow path topology | `analysis/parsers/ssis.py:445-490` | `_parse_data_flow_task()` extracts sources/transforms/destinations as flat lists — no `<path>` elements parsed to wire outputs to inputs |
| 12 | SQL truncated in LLM prompt | `analysis/analyzer.py:247-249` | `task.sql_statement[:200]` with "..." — full SQL is available but truncated for prompt |
| 13 | Transform properties omitted from LLM | `analysis/analyzer.py:274` | `_format_package_summary()` renders transforms as `name (component_type)` only — no properties, no expressions |
| 14 | Source columns omitted from LLM | `analysis/analyzer.py:269` | Sources rendered as `name (type): table_name` — no column detail |
| 15 | Destination column mappings omitted from LLM | `analysis/analyzer.py:280` | Destinations rendered as `name (type): table_name` — no column mapping detail |
| 16 | Context limited to 10 items | `context/service.py:401,403` | Both decisions and rules limited to 10 most recent |
| 17 | No schema info in context | `context/service.py:362-405` | `get_context_summary_for_prompt()` has no source/target schema, no column types, no row counts |
| 18 | No column lineage in context | `context/service.py:362-405` | No column-level lineage passed to LLM |
| 19 | Signoff in-memory only | `signoff/service.py:175` | `self._requests: dict[uuid.UUID, SignoffRequest] = {}` — no DB persistence |
| 20 | AnalysisService references non-existent attrs | `analysis/service.py:92-99` | References `cp.entity_type`, `cp.entity_name`, `cp.schema_name`, `cp.connection_ref`, `cp.direction` on `PackageConnectionPoints` — but the model doesn't have these attributes (it has `source_tables`, `target_tables`, etc.) |

---

## Appendix A: Relevant File Paths

| File | Purpose |
|------|---------|
| `docs/SPEC.md` | Master spec v2 (approved), defines full architecture |
| `docs/SPEC_LAKEBRIDGE_INTEGRATION.md` | Lakebridge integration spec (1,496 lines, planned, not implemented) |
| `docs/SPEC_MCP_CONFIG.md` | MCP server config spec, defines credential/secret patterns (Fernet) |
| `packages/core/app/enums.py` | All shared enums (183 lines) |
| `packages/core/app/domain/base.py` | ORM base classes (UuidPkMixin, TimestampsMixin, Base) |
| `packages/core/app/modules/migration_workbench/models.py` | All ORM models (883 lines) |
| `packages/core/app/modules/migration_workbench/analysis/schemas.py` | SSIS + analysis Pydantic schemas (433 lines) |
| `packages/core/app/modules/migration_workbench/analysis/parsers/ssis.py` | SSIS XML parser (764 lines) |
| `packages/core/app/modules/migration_workbench/analysis/analyzer.py` | LLM-powered analyzer (443 lines) |
| `packages/core/app/modules/migration_workbench/analysis/service.py` | Analysis coordination service (309 lines) |
| `packages/core/app/modules/migration_workbench/context/service.py` | Context assembly service (405 lines) |
| `packages/core/app/modules/migration_workbench/context/schemas.py` | Context Pydantic schemas (206 lines) |
| `packages/core/app/modules/migration_workbench/reconciliation/schemas.py` | Reconciliation Pydantic schemas (168 lines) |
| `packages/core/app/modules/migration_workbench/reconciliation/service.py` | Reconciliation service (302 lines, stubbed) |
| `packages/core/app/modules/migration_workbench/signoff/service.py` | Signoff workflow service (372 lines, in-memory) |
| `packages/core/app/modules/migration_workbench/generation/databricks_generator.py` | Databricks code generator |
| `packages/core/app/seed/reference/ref-corp-vli/skills/corp-reconciler.yaml` | Authoritative skill definition for 4-section reconciliation report + traceability chains |
| `packages/cli/workshop/commands/artifact.py` | CLI artifact upload command (typer pattern) |

## Appendix B: Existing Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Schema acquisition | Option A (upload) then Option B (Lakebridge) | Avoids driver/network/credential complexity initially |
| Architecture style | Hybrid: deterministic classes + LLM agents | Classes for computation (SQL, diff, render), agents for interpretation (hypotheses, risk) |
| Column metadata source | SSIS parse for source-side + Databricks query for target | Avoids multi-dialect source DB problem |
| Context management | Unified `MigrationAnalysisContext` | Single model assembled once, consumed by all prompts |
| Lakebridge credentials | Databricks PAT in Workshop, source DB creds in Unity Catalog | Workshop never sees source DB credentials |
| Enum storage | TEXT + CHECK constraint (not native Postgres ENUM) | Avoids ALTER TYPE pain on migrations |
| Signoff-reconciliation wiring | Phase B (after reconciliation is real) | Can't wire stubs to signoff |

> **See also**: [`MEMORY_MCP_DESIGN.md`](./MEMORY_MCP_DESIGN.md) — Full design for the Memory MCP knowledge graph (three maps, entity/relation/observation schemas, lifecycle observations, cross-map queries, decision verification, target map population).
