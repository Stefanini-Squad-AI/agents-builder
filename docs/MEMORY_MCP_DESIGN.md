# Memory MCP — Knowledge Graph for Migration

> Full design for using `@modelcontextprotocol/server-memory` as the LLM's
> navigable working memory across the migration lifecycle.
> Covers: three maps (source/migration/target), entity/relation/observation
> schemas, lifecycle-stage observation examples, cross-map queries,
> decision verification pattern, and target map population.

---

## 1. What the Memory MCP Is

**Package**: `@modelcontextprotocol/server-memory` — a Knowledge Graph Memory Server providing persistent, cross-session memory for LLM agents.

### Core Concepts

| Concept | What | Example |
|---------|------|---------|
| **Entity** | A node with a unique name, type, and observations | `{name: "John_Smith", entityType: "person", observations: ["Speaks Spanish"]}` |
| **Relation** | A directed edge between two entities | `{from: "John_Smith", to: "Anthropic", relationType: "works_at"}` |
| **Observation** | An atomic fact attached to an entity | `"Graduated in 2019"` |

### Tools (9 total)

| Tool | Risk Level | What it does |
|------|-----------|--------------|
| `create_entities` | N2 (write) | Create multiple entities (name + type + observations). Ignores duplicates. |
| `create_relations` | N2 (write) | Create directed relations between entities. Skips duplicates. |
| `add_observations` | N2 (write) | Add new facts to existing entities. Fails if entity doesn't exist. |
| `delete_entities` | N2 (write) | Remove entities + cascade-delete their relations. |
| `delete_observations` | N2 (write) | Remove specific observations from entities. |
| `delete_relations` | N2 (write) | Remove specific relations. |
| `read_graph` | N1 (read) | Return the entire knowledge graph. |
| `search_nodes` | N1 (read) | Search entity names, types, and observations by query string. |
| `open_nodes` | N1 (read) | Retrieve specific nodes by name + their inter-relations. |

### In the Workshop spec

- **Config**: `entries/memory.yaml` — no env vars, no config fields, no credentials required
- **Test connection**: No-op (always available)
- **Context rendering**: "Read stored keys, render as markdown" — injected into LLM prompts via `render_project_context()`
- **Storage**: JSONL file on disk (`memory.jsonl`), path configurable via `MEMORY_FILE_PATH` env var

---

## 2. The Three Maps: Source, Migration, Target

```
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│  SOURCE MAP      │         │  MIGRATION MAP   │         │  TARGET MAP      │
│  (what exists)   │────────►│  (what we're     │────────►│  (where it goes) │
│                  │         │   doing about it) │         │                  │
│  SSIS packages   │         │  Decisions       │         │  Databricks      │
│  SQL Server DBs  │         │  Wave assignments│         │  Unity Catalog   │
│  Tables/Columns  │         │  Status tracking │         │  Schemas/Tables  │
│  Connections     │         │  Reconciliation  │         │  Notebooks/Jobs  │
│  Transforms      │         │  Blockers        │         │  Clusters        │
└──────────────────┘         └──────────────────┘         └──────────────────┘
         │                            │                            │
         └────────────────────────────┼────────────────────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │    Memory MCP             │
                        │    (single knowledge      │
                        │     graph, 3 namespaces)  │
                        └───────────────────────────┘
```

### Namespace strategy

Avoids name collisions between source and target entities:

```
source:table:dbo.Customer
source:package:TTR_001
source:column:dbo.Customer.CustomerID

target:catalog:prod_catalog
target:schema:bronze
target:table:bronze.crm_customer
target:column:bronze.crm_customer.customer_name
target:notebook:finance_ttr_001_load

migration:decision:incremental_load_TTR_001
migration:wave:Wave_1
migration:blocker:script_task_csharp_TTR_001
```

This way `search_nodes("Customer")` returns both `source:table:dbo.Customer` and `target:table:bronze.crm_customer` — and the cross-map relation `migrates_to` connects them.

---

## 3. Source Map Entities & Relations

### Entities

| Entity Type | Examples | Where Discovered |
|-------------|----------|------------------|
| `package` | TTR_001, PCT_003, CORP_Load_All | SSIS parse |
| `table` | dbo.Customer, dbo.Orders, stg.Staging_Payments | SSIS parse + schema dump |
| `column` | dbo.Customer.CustomerID, dbo.Orders.OrderDate | SSIS parse + schema dump |
| `connection` | CRM_DB, DW_PROD, FlatFile_Inbound | SSIS parse |
| `transform` | LKP_Customer, DER_CalcRate, MJN_OrderLines | SSIS parse |
| `decision` | "incremental_load_strategy", "null_handling" | Analysis (LLM + human) |
| `domain` | Finance, HR, SupplyChain | Analysis (LLM) |
| `wave` | Wave_1, Wave_2, Wave_3 | Migration planning |
| `blocker` | "Script_Task_C#_in_TTR_001", "Dynamic_SQL_in_PCT_003" | Analysis (LLM) |

### Relations

| Relation | Meaning | Example |
|----------|---------|---------|
| `package → reads_from → table` | Source dependency | TTR_001 → reads_from → dbo.Customer |
| `package → writes_to → table` | Target dependency | TTR_001 → writes_to → stg.Staging_Orders |
| `package → lookup_on → table` | Lookup reference | TTR_001 → lookup_on → dbo.Region |
| `package → uses_connection → connection` | Connection usage | TTR_001 → uses_connection → CRM_DB |
| `package → contains_transform → transform` | Transform ownership | TTR_001 → contains_transform → LKP_Customer |
| `package → belongs_to_domain → domain` | Domain classification | TTR_001 → belongs_to_domain → Finance |
| `package → assigned_to_wave → wave` | Migration wave | TTR_001 → assigned_to_wave → Wave_1 |
| `package → depends_on → package` | Execution order | PCT_003 → depends_on → TTR_001 |
| `table → has_column → column` | Schema structure | dbo.Customer → has_column → CustomerID |
| `table → lives_in → connection` | Physical location | dbo.Customer → lives_in → CRM_DB |
| `transform → references_table → table` | Lookup/reference target | LKP_Customer → references_table → dbo.Customer |
| `decision → applies_to → package` | Decision scope | "incremental_load_strategy" → applies_to → TTR_001 |
| `decision → verified_by → human` | Human signoff | "incremental_load_strategy" → verified_by → "Ana Silva" |
| `blocker → blocks → package` | Blocking relationship | "Script_Task_C#" → blocks → TTR_001 |

---

## 4. Target Map Entities & Relations

### Why it matters

Without it, the LLM generates code into a **void**. It doesn't know:
- Does `bronze.staging_orders` already exist? (collision risk)
- Is there a shared `utils` notebook with helper functions? (reuse opportunity)
- What naming convention does the team use? (consistency)
- Which cluster/warehouse is available? (resource constraint)
- Are there existing jobs that the new notebook should be added to? (orchestration)
- What schemas already exist in Unity Catalog? (placement decision)

### Entities

| Entity Type | Examples | How Discovered |
|-------------|----------|----------------|
| `catalog` | prod_catalog, staging_catalog | Unity Catalog API / `SHOW CATALOGS` |
| `schema` | bronze, silver, gold, finance_bronze | Unity Catalog API / `SHOW SCHEMAS` |
| `delta_table` | bronze.staging_orders, gold.dim_customer | `SHOW TABLES` + `DESCRIBE EXTENDED` |
| `delta_column` | bronze.staging_orders.order_id | `DESCRIBE TABLE` |
| `view` | gold.v_customer_orders | `SHOW VIEWS` |
| `volume` | landing_volume, archive_volume | Unity Catalog API |
| `notebook` | finance_ttr_001_load, shared_utils | Workspace API / `ls /Workspace/` |
| `job` | daily_finance_etl, hourly_incremental | Jobs API |
| `cluster` | shared_autoscale, adhoc_warehouse | Clusters API |
| `alert` | pipeline_failure_alert, dq_check | Alerts API |
| `workflow` | finance_wave1_orchestration | Databricks Workflows API |

### Relations

| Relation | Meaning | Example |
|----------|---------|---------|
| `catalog → contains_schema → schema` | Catalog hierarchy | prod_catalog → contains_schema → bronze |
| `schema → contains_table → delta_table` | Schema hierarchy | bronze → contains_table → staging_orders |
| `delta_table → has_column → delta_column` | Table structure | staging_orders → has_column → order_id |
| `delta_table → partitioned_by → delta_column` | Partition strategy | staging_orders → partitioned_by → order_date |
| `delta_table → zordered_by → delta_column` | Z-order strategy | dim_customer → zordered_by → customer_id |
| `delta_table → has_cdf_enabled → true` | Change data feed | staging_orders → has_cdf_enabled → true |
| `notebook → reads_from → delta_table` | Read dependency | finance_ttr_001 → reads_from → bronze.staging_orders |
| `notebook → writes_to → delta_table` | Write dependency | finance_ttr_001 → writes_to → silver.orders |
| `notebook → calls_notebook → notebook` | Notebook chaining | wave1_orchestrator → calls_notebook → finance_ttr_001 |
| `job → runs_notebook → notebook` | Job composition | daily_finance → runs_notebook → finance_ttr_001 |
| `job → uses_cluster → cluster` | Resource binding | daily_finance → uses_cluster → shared_autoscale |
| `job → triggered_by → schedule` | Scheduling | daily_finance → triggered_by → cron_0600_utc |
| `alert → monitors → job` | Monitoring | failure_alert → monitors → daily_finance |
| `workflow → contains_job → job` | Orchestration | wave1 → contains_job → daily_finance |

### Target Map Observations

```
"Table bronze.staging_orders has 1.5M rows, 23 columns, partitioned by order_date"
"Table gold.dim_customer uses SCD Type 2 pattern — columns valid_from, valid_to, is_current"
"Notebook shared_utils contains reusable functions: log_metrics(), handle_errors(), apply_scd2()"
"Notebook shared_utils is imported by 12 other notebooks — do not modify signature without review"
"Job daily_finance_etl runs at 06:00 UTC, average duration 12 min, max concurrent 3"
"Cluster shared_autoscale: min=2, max=8 workers, i3.xlarge, spot enabled 70%"
"Schema bronze follows naming convention: {source_system}_{source_table} — e.g., crm_customer"
"Schema gold follows naming convention: dim_{entity} for dimensions, fact_{event} for facts"
"Table silver.orders has changeDataFeed enabled — can be used for incremental downstream"
"View gold.v_customer_orders joins dim_customer + fact_orders — used by BI team"
"Volume landing_volume receives files via Azure Data Factory from on-prem SFTP"
"No notebook in workspace uses PySpark DataFrame API — team prefers SQL cells exclusively"
"Job hourly_incremental has failed 3 times in last 7 days — investigate before adding dependencies"
"Alert pipeline_failure_alert sends to Slack channel #data-alerts and email DL data-eng@corp.com"
"Cluster adhoc_warehouse is SQL Warehouse type — cannot run PySpark, only SQL"
"Table bronze.staging_payments has OPTIMIZE auto-compaction enabled"
```

---

## 5. Cross-Map Relations (The Bridge)

These connect source entities to target entities — the actual migration mapping:

| Cross-Map Relation | Meaning | Example |
|-------------------|---------|---------|
| `source:table → migrates_to → target:delta_table` | Table mapping | dbo.Customer → migrates_to → bronze.crm_customer |
| `source:column → maps_to → target:delta_column` | Column mapping | dbo.Customer.Name → maps_to → bronze.crm_customer.customer_name |
| `source:package → implemented_by → target:notebook` | Code mapping | TTR_001 → implemented_by → finance_ttr_001_load |
| `source:connection → targets → target:catalog` | Connection mapping | CRM_DB → targets → prod_catalog |
| `source:package → scheduled_by → target:job` | Orchestration mapping | TTR_001 → scheduled_by → daily_finance_etl |
| `source:table → validated_by → target:delta_table` | Reconciliation pair | dbo.Orders → validated_by → silver.orders |

### Cross-Map Observations

```
"dbo.Customer migrates to bronze.crm_customer — column names snake_cased per team convention"
"dbo.Customer.Name (nvarchar(200)) maps to bronze.crm_customer.customer_name (STRING) — no data loss"
"dbo.Customer.TaxRate (decimal(5,2)) maps to bronze.crm_customer.tax_rate (DECIMAL(5,2)) — exact match"
"TTR_001 implemented by notebook finance_ttr_001_load — 3 SQL cells, 1 Python cell for logging"
"Connection CRM_DB targets catalog prod_catalog, schema bronze — all CRM tables land here"
"TTR_001 was daily at 06:00 in SSIS → now scheduled_by job daily_finance_etl at 06:00 UTC"
"dbo.Orders → silver.orders: row count MATCH (1.5M), checksum MATCH as of 2026-05-29"
"dbo.Payment → silver.payments: row count MISMATCH (source=800K, target=799K) — under investigation"
```

---

## 6. Observations by Lifecycle Stage

### 6.1 During SSIS Parse (auto-generated, no human check)

```
"Uses dynamic SQL via variable User::vSQL in Execute SQL Task 'Load_Data'"
"Derived Column 'Calc_Rate' applies expression: [Rate] * 1.15"
"Lookup 'LKP_Customer' matches on column CustomerID, caches full table"
"Data flow has fan-in pattern: 3 sources → 1 destination"
"Package has 2 event handlers: OnError sends email, OnFailure logs to table"
"Connection string for CRM_DB is expression-based: depends on variable User::EnvFlag"
"Foreach Loop iterates over files matching pattern *.csv in \\share\\inbound\\"
"OLE DB Destination uses fast-load mode with table lock hint"
"Merge Join is LEFT join on OrderID between OrderHeader and OrderLines"
"Conditional Split routes rows: [Amount] > 10000 → 'HighValue', else → 'Standard'"
```

### 6.2 During Analysis (LLM — needs human review)

```
"Pattern incremental_load detected with 95% confidence — uses CDC via Execute SQL Task"
"Pattern SCD_Type_2 detected on dimension Customer — requires history table pattern in Databricks"
"Pattern truncate_and_reload detected — full load every run, no incremental logic"
"Business rule: Row count validation must match within 0.01% variance"
"Business rule: Customer status changes require audit trail (SCD Type 2)"
"Estimated complexity: HIGH — 12 transforms, 3 script tasks, dynamic SQL"
"Domain classification: Finance — processes payment and invoice data"
"Package TTR_001 is likely deprecated — last modified 2019-03-15, no recent executions"
"Risk: Derived Column expressions use locale-specific date parsing (DD/MM/YYYY)"
```

### 6.3 During Generation (auto + human review of output)

```
"Generated notebook uses MERGE INTO pattern for incremental load on dbo.Orders"
"Lookup LKP_Customer translated to Spark broadcast join with dim_customer"
"Target table bronze_staging_orders uses Delta Lake OPTIMIZE + ZORDER after write"
"Script Task 'Transform_Address' replaced with UDF stub — requires manual implementation"
"Conditional Split translated to Spark WHEN/OTHERWISE CASE expression"
"Execute SQL Task 'Update_Audit' translated to post-write logging cell"
```

### 6.4 During Reconciliation (auto-generated from data comparison)

```
"Row count for dbo.Orders: source=1,500,000 target=1,500,000 — MATCH"
"Row count for dbo.Customer: source=250,000 target=249,997 — MISMATCH (variance=0.001%)"
"Checksum mismatch on dbo.Payment: source=abc123 target=def456 — INVESTIGATE"
"Schema drift detected: column 'Tax_Rate' added to source after initial analysis"
"Primary key coverage: 100% of source PKs exist in target for dbo.Orders"
"Sample data comparison: 50 rows sampled, 49 exact matches, 1 timestamp difference <1s"
```

### 6.5 During Structural Comparison (Phase A6)

```
"Column dbo.Customer.TaxRate exists in DB but not referenced in any SSIS package"
"Column dbo.Customer.LegacyCode referenced in TTR_001 but NULL for 99.7% of rows"
"Type mismatch: SSIS declares dt_str(50) but DB has nvarchar(200) for Customer.Notes"
"Table dbo.AuditLog exists in DB but has no SSIS package reading/writing it"
"Foreign key FK_Orders_Customer is NOT enforced in source DB (WITH NOCHECK)"
"Index IX_Customer_Name is heavily used (99% seek ratio) — preserve in Databricks"
```

### 6.6 Cross-Session / Human Observations (most valuable — persists across sessions)

```
"Team prefers bronze/silver/gold medallion architecture"
"Source DB ETL_DB has nightly maintenance window 2-5 AM UTC — schedule around it"
"Package TTR_001 is confirmed deprecated by business owner Maria Santos — skip migration"
"Connection CRM_DB requires VPN access — coordinate with infra team before profiling"
"Domain Finance has 23 packages, domain HR has 5 — prioritize Finance first"
"Wave 1 should include all independent packages (no cross-domain dependencies)"
"dbo.Customer uses soft-delete pattern (IsActive flag) — do not hard-delete in target"
"All datetime columns in source are in UTC — no timezone conversion needed"
"Package PCT_003 has a race condition with TTR_001 — must enforce execution order"
"Business rule: payments over $10K require dual approval — must preserve in target"
"Connection DW_PROD is being decommissioned Q3 2026 — migrate off it first"
"Test environment Databricks workspace has limited cluster size — keep notebooks small"
"Team has no Spark experience — prefer SQL-based notebook cells over PySpark DF API"
```

---

## 7. Where Observations Enter the Application

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  SSIS Parse  │────►│  LLM Analysis │────►│  Generation  │────►│Reconciliation│
│  (auto)      │     │  (LLM+human) │     │  (auto+human)│     │  (auto)      │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                     │                     │                     │
       ▼                     ▼                     ▼                     ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                        Memory MCP (Knowledge Graph)                     │
  │                                                                         │
  │  Entities:  package, table, column, connection, transform, decision,    │
  │             domain, wave, blocker, catalog, schema, delta_table,        │
  │             notebook, job, cluster, alert, workflow                     │
  │                                                                         │
  │  Relations: reads_from, writes_to, depends_on, migrates_to, ...        │
  │                                                                         │
  │  Observations: (all the examples in section 6)                          │
  └────────────────────────────────┬────────────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Next LLM call retrieves     │
                    │  relevant context via        │
                    │  search_nodes / open_nodes   │
                    └─────────────────────────────┘
```

Each stage **writes** observations and **reads** prior ones:

| Stage | Writes | Reads |
|-------|--------|-------|
| **Parse** | Entities (package, table, column, connection, transform) + relations + auto-observations | Nothing (first stage) |
| **Analysis** | Decision entities + blocker entities + LLM-observations (pending human review) | Prior package/table/transform entities + any human-verified observations |
| **Human Review** | Verifies LLM observations, adds human observations, marks decisions as `verified_by` human | Unverified observations from analysis |
| **Generation** | Target-mapping observations | All verified decisions + domain knowledge + human preferences |
| **Reconciliation** | Match/mismatch observations | Expected schema from parse + actual schema from dump |

---

## 8. Decision Verification Pattern

Every decision has an audit trail: who proposed it (LLM or human), who verified it, when, and any additional context.

```python
# LLM proposes a decision
memory.create_entities([{
    "name": "decision:incremental_load_TTR_001",
    "entityType": "decision",
    "observations": [
        "Proposed: Use MERGE INTO with delta.changeDataFeed",
        "Rationale: Package uses CDC pattern via Execute SQL Task",
        "Status: pending_human_review",
        "Proposed by: LLM analysis run abc-123"
    ]
}])

# Human verifies (via Workshop UI or CLI)
memory.add_observations([{
    "entityName": "decision:incremental_load_TTR_001",
    "contents": [
        "Status: verified",
        "Verified by: Ana Silva on 2026-05-29",
        "Human note: Also enable changeDataFeed on target Delta table"
    ]
}])
memory.create_relations([{
    "from": "decision:incremental_load_TTR_001",
    "to": "Ana_Silva",
    "relationType": "verified_by"
}])
```

---

## 9. Example Cross-Map Queries

### "What does package TTR_001 touch and where does it go?"

```
search_nodes("TTR_001")
  → entity: package:TTR_001
  → relations:
      reads_from → table:dbo.Customer, table:dbo.Region
      writes_to → table:stg.Staging_Orders
      lookup_on → table:dbo.Customer
      contains_transform → LKP_Customer, DER_CalcRate
      implemented_by → notebook:finance_ttr_001_load
      scheduled_by → job:daily_finance_etl
      belongs_to_domain → Finance
      assigned_to_wave → Wave_1
  → observations:
      "Uses CDC pattern via Execute SQL Task"
      "Derived Column Calc_Rate applies expression: [Rate] * 1.15"
      "Decision: use MERGE INTO — verified by Ana Silva"
```

### "What depends on table dbo.Customer?"

```
search_nodes("Customer")
  → entity: table:dbo.Customer
  → relations:
      read_by → package:TTR_001, package:PCT_003
      written_by → package:CORP_Load_All
      migrates_to → delta_table:bronze.crm_customer
      has_column → CustomerID, Name, TaxRate, RegionID, ...
  → observations:
      "Has 250,000 rows, 23 columns"
      "Soft-delete pattern (IsActive flag)"
      "SCD Type 2 in target — columns valid_from, valid_to, is_current"
      "FK_Orders_Customer is NOT enforced in source (WITH NOCHECK)"
```

### "What's the status of Wave 1?"

```
open_nodes(["Wave_1"])
  → relations: contains → TTR_001, PCT_003, CORP_Load_All
  → for each package, check if implemented_by relation exists to a notebook
  → for each notebook, check if scheduled_by relation exists to a job
  → for each source→target table pair, check if validated_by observation exists
  → aggregate: 2/3 packages implemented, 1/3 reconciled, 0/3 signed off
```

### "Can I add a new notebook to the daily_finance_etl job?"

```
open_nodes(["job:daily_finance_etl"])
  → uses_cluster → shared_autoscale (min=2, max=8)
  → runs_notebook → finance_ttr_001, finance_pct_003
  → observations: "average duration 12 min", "max concurrent 3"
  → check cluster capacity: 2 notebooks already, max concurrent 3 → yes, 1 slot available
```

---

## 10. Target Map Population

### Option 1: Databricks REST API (always available, no Lakebridge needed)

```python
def extract_target_map(databricks_client):
    for catalog in client.list_catalogs():
        memory.create_entities([{
            "name": f"catalog:{catalog.name}",
            "entityType": "catalog",
            "observations": [f"Owner: {catalog.owner}", f"Comment: {catalog.comment}"]
        }])

        for schema in client.list_schemas(catalog.name):
            memory.create_entities([{
                "name": f"schema:{catalog.name}.{schema.name}",
                "entityType": "schema",
                "observations": [f"Catalog: {catalog.name}"]
            }])
            memory.create_relations([{
                "from": f"catalog:{catalog.name}",
                "to": f"schema:{catalog.name}.{schema.name}",
                "relationType": "contains_schema"
            }])

            for table in client.list_tables(catalog.name, schema.name):
                columns = client.describe_table(catalog.name, schema.name, table.name)
                memory.create_entities([{
                    "name": f"table:{catalog.name}.{schema.name}.{table.name}",
                    "entityType": "delta_table",
                    "observations": [
                        f"Table type: {table.table_type}",
                        f"Storage location: {table.storage_location}",
                        f"Created at: {table.created_at}",
                        f"Partition columns: {table.partition_columns}",
                    ]
                }])
                # ... columns, partitions, properties, CDF status

    for notebook in client.list_notebooks():
        deps = analyze_notebook_dependencies(notebook)
        memory.create_entities([{
            "name": f"notebook:{notebook.path}",
            "entityType": "notebook",
            "observations": [f"Language: {notebook.language}", f"Cells: {len(notebook.cells)}"]
        }])
        for dep in deps.reads:
            memory.create_relations([{
                "from": f"notebook:{notebook.path}",
                "to": f"table:{dep}",
                "relationType": "reads_from"
            }])
        for dep in deps.writes:
            memory.create_relations([{
                "from": f"notebook:{notebook.path}",
                "to": f"table:{dep}",
                "relationType": "writes_to"
            }])

    for job in client.list_jobs():
        # Job → notebook mappings, schedules, clusters
        ...
```

### Option 2: Lakebridge Profiler (Phase B — deeper metadata)

Lakebridge's `execute-database-profiler` can extract schema + statistics from the Databricks side too (it's just another JDBC source from its perspective). This gives row counts, column statistics, partition info that the REST API doesn't provide.

### Option 3: SQL introspection (lightweight, always works)

```sql
-- Run in Databricks SQL
SHOW CATALOGS;
SHOW SCHEMAS IN prod_catalog;
SHOW TABLES IN prod_catalog.bronze;
DESCRIBE EXTENDED prod_catalog.bronze.staging_orders;
DESCRIBE HISTORY prod_catalog.bronze.staging_orders;  -- Delta Lake history
```

---

## 11. When to Populate Each Map

| Map | When | Trigger |
|-----|------|---------|
| **Source** | On SSIS parse + schema dump upload | `workshop migration analyze` / artifact upload |
| **Target** | On Databricks connection config + periodically | `workshop project config-databricks` / nightly refresh / on-demand |
| **Migration (bridge)** | On analysis + human decisions + generation + reconciliation | Each lifecycle stage writes its piece |

The **Target Map should be refreshable** — Databricks structure evolves (new tables, modified notebooks, job changes). A nightly refresh or on-demand `workshop target refresh` keeps it current.

---

## 12. Key Insight: Memory MCP as the LLM's Navigable Working Memory

The DB models (`ETLPackage`, `MigrationObject`, `PackageObjectRef`, etc.) are the **source of truth** — structured, typed, queryable by the application. But they're not naturally navigable by the LLM.

The Memory MCP is the **LLM's view** of that truth:

- `search_nodes("Customer")` → returns the Customer entity + all packages that read/write it + all observations about it
- `open_nodes(["TTR_001", "dbo.Orders"])` → returns both entities + the relations between them + all observations
- `read_graph()` → full map (for small projects) or filtered subgraph

This means the LLM can **reason about the migration map** without the application having to format it into a prompt. Instead of `_format_package_summary()` truncating everything to 200 chars, the LLM can pull exactly what it needs from the knowledge graph.
