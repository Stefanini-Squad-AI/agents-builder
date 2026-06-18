# ETL Migration Workbench — Complete Flow

> End-to-end workflow for migrating ETL packages (SSIS → Databricks) using the Migration Workbench module.

---

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         ETL Migration Workbench — Pipeline Overview                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  📦 Phase 1         🔍 Phase 2         ⚙️ Phase 3          ✅ Phase 4               │
│  REGISTRATION       ANALYSIS           GENERATION          VALIDATION               │
│                                                                                      │
│  ┌──────────┐      ┌──────────┐       ┌──────────┐       ┌──────────┐              │
│  │ Upload   │      │ Parse    │       │ Generate │       │ Reconcile│              │
│  │ SSIS     │ ──►  │ DTSX     │  ──►  │ Databricks│ ──►  │ Data     │              │
│  │ Packages │      │ + LLM    │       │ Notebooks │       │ Rows     │              │
│  └──────────┘      └──────────┘       └──────────┘       └──────────┘              │
│       │                 │                   │                  │                    │
│       ▼                 ▼                   ▼                  ▼                    │
│  ┌──────────┐      ┌──────────┐       ┌──────────┐       ┌──────────┐              │
│  │ Context  │      │ Build    │       │ Create   │       │ Sign-off │              │
│  │ Extract  │      │ Migration│       │ Artifacts│       │ Approval │              │
│  │          │      │ Map      │       │          │       │          │              │
│  └──────────┘      └──────────┘       └──────────┘       └──────────┘              │
│                                                                                      │
│  Status: registered → analyzing → analyzed → generating → generated → validated     │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Package Lifecycle States

```
                                    ┌─────────────────┐
                                    │   registered    │ ◄── Upload artifact
                                    └────────┬────────┘
                                             │
                                    ┌────────▼────────┐
                                    │   analyzing     │ ◄── Queue analysis job
                                    └────────┬────────┘
                                             │
                          ┌──────────────────┼──────────────────┐
                          │                  │                  │
                 ┌────────▼────────┐ ┌───────▼────────┐ ┌──────▼───────┐
                 │ needs_feedback  │ │    analyzed    │ │ analysis_err │
                 │ (blockers > 0)  │ │ (no blockers)  │ │   (failed)   │
                 └────────┬────────┘ └───────┬────────┘ └──────────────┘
                          │                  │
                          │  Resolve all     │
                          │  blockers        │
                          └──────────┬───────┘
                                     │
                            ┌────────▼────────┐
                            │     ready       │ ◄── All blockers resolved
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │   generating    │ ◄── Trigger generation
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │   generated     │ ◄── Notebooks created
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │   validating    │ ◄── Run reconciliation
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │   validated     │ ◄── Data matches
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │    migrated     │ ◄── Sign-off approved
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │    verified     │ ◄── Production confirmed
                            └─────────────────┘
```

---

## Phase 1: Registration & Context Extraction

### 1.1 Package Upload

```
User                    Web UI                   API                      Service
 │                        │                       │                          │
 │  Upload SSIS package   │                       │                          │
 │  (TTR_001.dtsx)        │                       │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │                        │  POST /api/projects/{id}/artifacts               │
 │                        │  Content-Type: multipart/form-data               │
 │                        │  kind: "code"         │                          │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │                       │  1. Save file to disk    │
 │                        │                       │  2. Insert artifact row  │
 │                        │                       │  3. Queue extraction job │
 │                        │                       ├─────────────────────────►│
 │                        │                       │                          │
 │                        │  202 Accepted         │     Dramatiq:            │
 │                        │  artifact_id: uuid    │     extract_artifact     │
 │                        │◄──────────────────────┤                          │
 │                        │                       │                          │
 │  ┌──────────────────────────────────────────────────────────────────────┐ │
 │  │ Background: SSIS Extractor                                           │ │
 │  │                                                                      │ │
 │  │ 1. Parse XML namespace: www.microsoft.com/SqlServer/Dts              │ │
 │  │ 2. Extract ConnectionManagers → connections[]                        │ │
 │  │ 3. Extract ControlFlow → tasks[], containers[]                       │ │
 │  │ 4. Extract DataFlow → sources[], transforms[], destinations[]        │ │
 │  │ 5. Extract Variables → parameters[], variables[]                     │ │
 │  │ 6. Extract Annotations → developer notes                             │ │
 │  │ 7. Track UnparsedFeatures → what wasn't understood                   │ │
 │  │ 8. Generate content_md (structured markdown)                         │ │
 │  └──────────────────────────────────────────────────────────────────────┘ │
 │                        │                       │                          │
 │                        │  Poll: GET /api/artifacts/{id}                   │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │  status: "extracted"  │                          │
 │                        │  content_md: "..."    │                          │
 │                        │◄──────────────────────┤                          │
```

### 1.2 Package Registration

```
User                    Web UI                   API                      Service
 │                        │                       │                          │
 │  Clicks "Register as   │                       │                          │
 │  ETL Package"          │                       │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │                        │  POST /api/migrations/{project}/packages         │
 │                        │  {                    │                          │
 │                        │    "artifact_id": "...",                         │
 │                        │    "package_name": "TTR_001",                    │
 │                        │    "domain": "Finance",                          │
 │                        │    "card_prefix": "TTR"                          │
 │                        │  }                    │                          │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │                       │  Creates ETLPackage:     │
 │                        │                       │  ├─ status: registered   │
 │                        │                       │  ├─ complexity: medium   │
 │                        │                       │  └─ artifact linked      │
 │                        │                       ├─────────────────────────►│
 │                        │                       │                          │
 │                        │  201 Created          │                          │
 │                        │  ETLPackageView       │                          │
 │                        │◄──────────────────────┤                          │
```

### 1.3 Context Accumulation

As packages are uploaded, the system accumulates shared context:

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           Shared Context (Per Project)                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  📊 MigrationConnections                  📋 MigrationBusinessRules                  │
│  ─────────────────────                    ─────────────────────────                  │
│  ┌────────────────────────────────┐       ┌────────────────────────────────┐        │
│  │ connection_name: OLEDB_CRM_DB  │       │ rule_id: BR_001_SOFT_DELETE    │        │
│  │ connection_type: oledb         │       │ rule_name: Soft Delete Pattern │        │
│  │ source_server: sql01.corp.com  │       │ description: Use IsActive flag │        │
│  │ source_database: CRM           │       │ source: UPDATE...SET IsActive=0│        │
│  │ target_catalog: prod_catalog   │       │ target: MERGE with soft delete │        │
│  │ target_schema: bronze          │       │ used_by_packages: [TTR_001,    │        │
│  │ used_by_packages: [TTR_001,    │       │                    PCT_003]    │        │
│  │                    TTR_002]    │       │ status: confirmed              │        │
│  │ resolved_by: Ana Silva         │       └────────────────────────────────┘        │
│  └────────────────────────────────┘                                                 │
│                                                                                      │
│  🎯 MigrationResolvedDecisions            🗺️ MigrationObjects                       │
│  ─────────────────────────────            ───────────────────                       │
│  ┌────────────────────────────────┐       ┌────────────────────────────────┐        │
│  │ decision_type: incremental_    │       │ object_type: table             │        │
│  │                strategy        │       │ object_name: dbo.Customer      │        │
│  │ question: How to handle incr?  │       │ database_name: CRM             │        │
│  │ resolution: Use MERGE with CDC │       │ discovered_columns: [...]      │        │
│  │ scope: project                 │       │ read_by_count: 5               │        │
│  │ applied_to_packages: [TTR_001, │       │ written_by_count: 1            │        │
│  │   TTR_002, PCT_003, ...]       │       └────────────────────────────────┘        │
│  │ resolved_by: Tech Lead         │                                                 │
│  └────────────────────────────────┘                                                 │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 2: Analysis

### 2.1 Queue Analysis Job

```
User                    Web UI                   API                      Worker
 │                        │                       │                          │
 │  Clicks "Analyze"      │                       │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │                        │  POST /api/migrations/analysis/                  │
 │                        │       packages/{project}/analyze                 │
 │                        │  { "package_id": "..." }                         │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │                       │  1. Update status →      │
 │                        │                       │     "analyzing"          │
 │                        │                       │  2. Queue Dramatiq job   │
 │                        │                       ├─────────────────────────►│
 │                        │                       │                          │
 │                        │  { "status": "queued" }                          │
 │                        │◄──────────────────────┤                          │
```

### 2.2 Analysis Pipeline (Background)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         analyze_package Dramatiq Actor                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │ Step 1: Load Technology Profile (ssis.yaml)                                 │    │
│  │                                                                             │    │
│  │ structural_patterns:                                                        │    │
│  │   - disabled_tasks: "DTS:Disabled='True'"                                   │    │
│  │   - change_annotations: "AnnotationLayout elements"                         │    │
│  │   - connection_managers: "DTS:ConnectionManager"                            │    │
│  │                                                                             │    │
│  │ execution_patterns:                                                         │    │
│  │   - incremental_vs_full: "processamento_full parameter"                     │    │
│  │   - soft_deletes: "UPDATE...SET exclusao_logica"                            │    │
│  │                                                                             │    │
│  │ validation_requirements:                                                    │    │
│  │   - parallel_run: "Side-by-side validation before cutover"                  │    │
│  │   - static_code_comparison: "Rule-by-rule comparison"                       │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                           │                                          │
│                                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │ Step 2: Load Project Context                                                │    │
│  │                                                                             │    │
│  │ ContextService.get_project_context(project_id) →                            │    │
│  │   ├─ connections: [{OLEDB_CRM_DB, OLEDB_DW_PROD, ...}]                      │    │
│  │   ├─ business_rules: [{BR_001_SOFT_DELETE, BR_002_CDC, ...}]                │    │
│  │   ├─ resolved_decisions: [{incremental_strategy → MERGE, ...}]             │    │
│  │   ├─ packages: [{TTR_001, TTR_002, ...}] (already analyzed)                 │    │
│  │   └─ objects: [{dbo.Customer, dbo.Orders, ...}]                             │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                           │                                          │
│                                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │ Step 3: Parse Package (SSIS Parser)                                         │    │
│  │                                                                             │    │
│  │ SSISParser.parse(content) →                                                 │    │
│  │   ├─ connection_managers: [{name, type, connection_string, ...}]            │    │
│  │   ├─ control_flow: [{task_name, task_type, disabled, ...}]                  │    │
│  │   ├─ data_flow: [{sources, transforms, destinations}]                       │    │
│  │   ├─ variables: [{name, data_type, value, evaluates_as_expression}]         │    │
│  │   ├─ parameters: [{name, data_type, required}]                              │    │
│  │   └─ unparsed_features: [{location, description, xml_snippet}]              │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                           │                                          │
│                                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │ Step 4: Extract Connection Points                                           │    │
│  │                                                                             │    │
│  │ ConnectionPointsExtractor.extract(parsed) →                                 │    │
│  │   ├─ source_tables: [dbo.Customer, dbo.Orders, ...]                         │    │
│  │   ├─ target_tables: [stg.Staging_Orders, ...]                               │    │
│  │   ├─ source_connections: [OLEDB_CRM_DB]                                     │    │
│  │   └─ target_connections: [OLEDB_DW_PROD]                                    │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                           │                                          │
│                                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │ Step 5: LLM Analysis (with full context)                                    │    │
│  │                                                                             │    │
│  │ LLMService.run(analyze_package_prompt) →                                    │    │
│  │   Input:                                                                    │    │
│  │   ├─ Package structure (parsed)                                             │    │
│  │   ├─ Technology profile (SSIS patterns)                                     │    │
│  │   ├─ Project context (prior decisions, connections, rules)                  │    │
│  │   └─ Target profile (Databricks patterns)                                   │    │
│  │                                                                             │    │
│  │   Output (structured JSON):                                                 │    │
│  │   ├─ complexity: "high"                                                     │    │
│  │   ├─ estimated_effort: "5d"                                                 │    │
│  │   ├─ domain: "Finance"                                                      │    │
│  │   ├─ patterns_detected: [CDC, SCD_Type_2, MERGE]                            │    │
│  │   ├─ blockers: [{type, description, resolution_options}]                    │    │
│  │   ├─ business_rules: [{id, name, source_impl, target_impl}]                 │    │
│  │   └─ medallion_layer: "silver"                                              │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                           │                                          │
│                                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │ Step 6: Auto-Resolve Known Blockers                                         │    │
│  │                                                                             │    │
│  │ For each blocker:                                                           │    │
│  │   existing = ContextService.find_resolved_decision(decision_type)           │    │
│  │   if existing:                                                              │    │
│  │     blocker.status = "auto_resolved"                                        │    │
│  │     blocker.resolution = existing.resolution                                │    │
│  │     blocker.resolved_by = f"Propagated from {existing.package_id}"          │    │
│  │                                                                             │    │
│  │ Example:                                                                    │    │
│  │   Blocker: "How to handle incremental load?"                                │    │
│  │   → Found decision: "Use MERGE with CDC" (resolved in TTR_001)              │    │
│  │   → Auto-resolve: Apply same decision                                       │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                           │                                          │
│                                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │ Step 7: Update Migration Map                                                │    │
│  │                                                                             │    │
│  │ RelationshipDetector.detect_relationships(project_id, package_id) →         │    │
│  │   ├─ New writes: TTR_001 → writes → stg.Staging_Orders                      │    │
│  │   ├─ Match: TTR_002 reads stg.Staging_Orders                                │    │
│  │   └─ Edge: TTR_001 → data_flow → TTR_002                                    │    │
│  │                                                                             │    │
│  │ FlowDetector.detect_clusters(project_id) →                                  │    │
│  │   ├─ Cluster 1: [TTR_001 → TTR_002 → TTR_003]                               │    │
│  │   └─ Cluster 2: [PCT_001 → PCT_002] (isolated)                              │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                           │                                          │
│                                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │ Step 8: Save Results                                                        │    │
│  │                                                                             │    │
│  │ package.analysis_json = analysis_results                                    │    │
│  │ package.complexity = "high"                                                 │    │
│  │ package.domain = "Finance"                                                  │    │
│  │ package.estimated_effort = "5d"                                             │    │
│  │ package.blockers_count = 3                                                  │    │
│  │ package.auto_resolved_count = 2                                             │    │
│  │ package.status = "analyzed" if no_open_blockers else "needs_feedback"       │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Blocker Resolution (Human-in-the-Loop)

```
User                    Web UI                   API                      Service
 │                        │                       │                          │
 │  Views pending blockers│                       │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │                        │  GET /api/migrations/analysis/                   │
 │                        │      projects/{slug}/blockers                    │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │  ┌────────────────────────────────────────────────────────────────────┐   │
 │  │ Pending Blockers (2)                                               │   │
 │  │                                                                    │   │
 │  │ ┌────────────────────────────────────────────────────────────────┐ │   │
 │  │ │ 🔴 Script Task C# Code                                         │ │   │
 │  │ │ Package: TTR_001                                               │ │   │
 │  │ │ Location: Control Flow > SCR_Transform_Address                 │ │   │
 │  │ │                                                                │ │   │
 │  │ │ Options:                                                       │ │   │
 │  │ │ ○ Convert to PySpark UDF                                       │ │   │
 │  │ │ ○ Rewrite in SQL                                               │ │   │
 │  │ │ ○ Mark as manual implementation                                │ │   │
 │  │ │                                                                │ │   │
 │  │ │ [Apply to all similar] [Resolve]                               │ │   │
 │  │ └────────────────────────────────────────────────────────────────┘ │   │
 │  │                                                                    │   │
 │  │ ┌────────────────────────────────────────────────────────────────┐ │   │
 │  │ │ 🟡 Dynamic SQL in Execute SQL Task                             │ │   │
 │  │ │ Package: TTR_001                                               │ │   │
 │  │ │ Location: Control Flow > SQL_Build_Query                       │ │   │
 │  │ │                                                                │ │   │
 │  │ │ Options:                                                       │ │   │
 │  │ │ ○ Convert to parameterized query                               │ │   │
 │  │ │ ○ Use Spark SQL with string interpolation                      │ │   │
 │  │ │                                                                │ │   │
 │  │ │ [Apply to all similar] [Resolve]                               │ │   │
 │  │ └────────────────────────────────────────────────────────────────┘ │   │
 │  └────────────────────────────────────────────────────────────────────┘   │
 │                        │                       │                          │
 │  Selects resolution +  │                       │                          │
 │  "Apply to all similar"│                       │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │                        │  POST /api/migrations/context/                   │
 │                        │       {project}/decisions                        │
 │                        │  {                    │                          │
 │                        │    "decision_type": "script_task_csharp",        │
 │                        │    "resolution": "convert_to_pyspark_udf",       │
 │                        │    "scope": "project",                           │
 │                        │    "resolved_by": "Tech Lead"                    │
 │                        │  }                    │                          │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │                       │  PropagationService      │
 │                        │                       │  .propagate_decision()   │
 │                        │                       │  → Applied to 15 packages│
 │                        │                       ├─────────────────────────►│
 │                        │                       │                          │
 │                        │  { "applied_to": 15 } │                          │
 │                        │◄──────────────────────┤                          │
```

---

## Phase 3: Generation

### 3.1 Design Guidance (Pre-Generation)

```
User                    Web UI                   API                      Service
 │                        │                       │                          │
 │  Clicks "Generate"     │                       │                          │
 │  on package            │                       │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │                        │  GET /api/migrations/{project}/generation/       │
 │                        │      packages/{id}/design                        │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │                       │  DataPatternClassifier   │
 │                        │                       │  .analyze_package()      │
 │                        │                       ├─────────────────────────►│
 │                        │                       │                          │
 │  ┌────────────────────────────────────────────────────────────────────┐   │
 │  │ Design Guidance                                                    │   │
 │  │                                                                    │   │
 │  │ Package: TTR_001 — Daily Sales Load                                │   │
 │  │                                                                    │   │
 │  │ ┌─────────────────────────────────────────────────────────────────┐│   │
 │  │ │ Data Patterns Detected                                          ││   │
 │  │ │                                                                 ││   │
 │  │ │ Task                    Pattern         Layer       Confidence  ││   │
 │  │ │ ─────────────────────────────────────────────────────────────── ││   │
 │  │ │ DFT_Load_Sales          MERGE           Silver      95%         ││   │
 │  │ │ DFT_Lookup_Customer     BROADCAST_JOIN  Silver      90%         ││   │
 │  │ │ SQL_Update_Audit        DIRECT_INSERT   Bronze      85%         ││   │
 │  │ │ DFT_Calc_Metrics        AGGREGATE       Gold        80%         ││   │
 │  │ └─────────────────────────────────────────────────────────────────┘│   │
 │  │                                                                    │   │
 │  │ ┌─────────────────────────────────────────────────────────────────┐│   │
 │  │ │ Performance Recommendations                                     ││   │
 │  │ │                                                                 ││   │
 │  │ │ ✓ Photon eligible (all patterns supported)                      ││   │
 │  │ │ ✓ Use Z-ORDER on customer_id for MERGE                          ││   │
 │  │ │ ⚠ Consider partitioning by order_date for large tables          ││   │
 │  │ └─────────────────────────────────────────────────────────────────┘│   │
 │  │                                                                    │   │
 │  │                    [Cancel]  [Generate Notebooks]                  │   │
 │  └────────────────────────────────────────────────────────────────────┘   │
 │◄───────────────────────┤                       │                          │
```

### 3.2 Notebook Generation

```
User                    Web UI                   API                      Service
 │                        │                       │                          │
 │  Clicks "Generate      │                       │                          │
 │  Notebooks"            │                       │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │                        │  POST /api/migrations/{project}/generation/      │
 │                        │       packages/{id}/generate                     │
 │                        │  {                    │                          │
 │                        │    "options": {       │                          │
 │                        │      "target": "databricks",                     │
 │                        │      "include_tests": true,                      │
 │                        │      "use_photon": true                          │
 │                        │    }                  │                          │
 │                        │  }                    │                          │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │                       │  GenerationService       │
 │                        │                       │  .generate()             │
 │                        │                       ├─────────────────────────►│
 │                        │                       │                          │
 │  ┌────────────────────────────────────────────────────────────────────┐   │
 │  │ Generation Pipeline                                                │   │
 │  │                                                                    │   │
 │  │ 1. Load Jinja2 templates:                                          │   │
 │  │    ├─ pyspark_module.py.j2                                         │   │
 │  │    ├─ sql_notebook.sql.j2                                          │   │
 │  │    ├─ orchestrator.py.j2                                           │   │
 │  │    └─ README.md.j2                                                 │   │
 │  │                                                                    │   │
 │  │ 2. Build generation context:                                       │   │
 │  │    ├─ package: TTR_001                                             │   │
 │  │    ├─ sources: [dbo.Customer, dbo.Orders]                          │   │
 │  │    ├─ targets: [bronze.crm_customer, bronze.orders]                │   │
 │  │    ├─ transforms: [LKP_Customer → broadcast join]                  │   │
 │  │    └─ patterns: [MERGE, BROADCAST_JOIN, SCD_TYPE_2]                │   │
 │  │                                                                    │   │
 │  │ 3. Render artifacts:                                               │   │
 │  │    ├─ TTR_001/bronze_load.py (42 lines)                            │   │
 │  │    ├─ TTR_001/silver_transform.py (87 lines)                       │   │
 │  │    ├─ TTR_001/orchestrator.py (35 lines)                           │   │
 │  │    └─ TTR_001/README.md (documentation)                            │   │
 │  └────────────────────────────────────────────────────────────────────┘   │
 │                        │                       │                          │
 │                        │  GenerationResult     │                          │
 │                        │  {                    │                          │
 │                        │    "artifacts": [...],│                          │
 │                        │    "total_lines": 164,│                          │
 │                        │    "warnings": []     │                          │
 │                        │  }                    │                          │
 │                        │◄──────────────────────┤                          │
 │                        │                       │                          │
 │  Shows preview with    │                       │                          │
 │  syntax highlighting   │                       │                          │
 │◄───────────────────────┤                       │                          │
```

### 3.3 Lakebridge Transpiler (Alternative)

```
User                    Web UI                   API                      Worker
 │                        │                       │                          │
 │  Clicks "Transpile     │                       │                          │
 │  with Lakebridge"      │                       │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │                        │  POST /api/lakebridge/{project}/transpile        │
 │                        │  {                    │                          │
 │                        │    "artifact_ids": ["..."],                      │
 │                        │    "source_dialect": "tsql",                     │
 │                        │    "target_dialect": "databricks"                │
 │                        │  }                    │                          │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │                       │  1. Create LakebridgeJob │
 │                        │                       │  2. Queue Dramatiq actor │
 │                        │                       ├─────────────────────────►│
 │                        │                       │                          │
 │  ┌────────────────────────────────────────────────────────────────────┐   │
 │  │ run_lakebridge_transpiler (Background)                             │   │
 │  │                                                                    │   │
 │  │ CLI: databricks labs lakebridge transpile                          │   │
 │  │      --source tsql                                                 │   │
 │  │      --input-path /tmp/input/                                      │   │
 │  │      --output-path /tmp/output/                                    │   │
 │  │                                                                    │   │
 │  │ Output:                                                            │   │
 │  │   /tmp/output/TTR_001.sql → Databricks SQL                         │   │
 │  │   /tmp/output/TTR_001.py  → PySpark notebook                       │   │
 │  └────────────────────────────────────────────────────────────────────┘   │
 │                        │                       │                          │
 │  Poll job status       │  GET /api/lakebridge/{project}/jobs/{id}         │
 │  ─────────────────────►├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │  { "status": "completed", "artifacts": [...] }   │
 │◄───────────────────────┤◄──────────────────────┤                          │
```

---

## Phase 4: Validation

### 4.1 Reconciliation

```
User                    Web UI                   API                      Service
 │                        │                       │                          │
 │  Clicks "Run           │                       │                          │
 │  Reconciliation"       │                       │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │                        │  POST /api/migrations/{project}/reconciliation/  │
 │                        │       packages/{id}/run                          │
 │                        │  {                    │                          │
 │                        │    "config": {        │                          │
 │                        │      "checks": ["row_count", "checksum"],        │
 │                        │      "sample_size": 1000,                        │
 │                        │      "tolerance": 0.001                          │
 │                        │    }                  │                          │
 │                        │  }                    │                          │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │                       │  ReconciliationService   │
 │                        │                       │  .run_reconciliation()   │
 │                        │                       ├─────────────────────────►│
 │                        │                       │                          │
 │  ┌────────────────────────────────────────────────────────────────────┐   │
 │  │ Reconciliation Checks                                              │   │
 │  │                                                                    │   │
 │  │ For each table mapping (source → target):                          │   │
 │  │                                                                    │   │
 │  │ 1. Row Count Check:                                                │   │
 │  │    SELECT COUNT(*) FROM source.dbo.Orders      → 1,500,000         │   │
 │  │    SELECT COUNT(*) FROM target.bronze.orders   → 1,500,000         │   │
 │  │    Result: MATCH ✓                                                 │   │
 │  │                                                                    │   │
 │  │ 2. Checksum Check:                                                 │   │
 │  │    SELECT MD5(CONCAT(*)) FROM source           → abc123...         │   │
 │  │    SELECT MD5(CONCAT(*)) FROM target           → abc123...         │   │
 │  │    Result: MATCH ✓                                                 │   │
 │  │                                                                    │   │
 │  │ 3. Sample Data Check:                                              │   │
 │  │    Compare 1000 random rows                                        │   │
 │  │    Mismatches: 0                                                   │   │
 │  │    Result: MATCH ✓                                                 │   │
 │  └────────────────────────────────────────────────────────────────────┘   │
 │                        │                       │                          │
 │                        │  ReconciliationRunResult                         │
 │                        │  {                    │                          │
 │                        │    "status": "passed",│                          │
 │                        │    "source_row_count": 1500000,                  │
 │                        │    "target_row_count": 1500000,                  │
 │                        │    "check_results": [...]                        │
 │                        │  }                    │                          │
 │                        │◄──────────────────────┤                          │
```

### 4.2 Sign-off Workflow

```
User                    Web UI                   API                      Service
 │                        │                       │                          │
 │  Creates sign-off      │                       │                          │
 │  request               │                       │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │                        │  POST /api/migrations/{project}/signoff/requests │
 │                        │  {                    │                          │
 │                        │    "signoff_type": "parallel_run",               │
 │                        │    "package_id": "...",                          │
 │                        │    "requested_by": "Data Engineer"               │
 │                        │  }                    │                          │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │                       │  SignoffService          │
 │                        │                       │  .create_signoff()       │
 │                        │                       │  → Creates checklist     │
 │                        │                       ├─────────────────────────►│
 │                        │                       │                          │
 │  ┌────────────────────────────────────────────────────────────────────┐   │
 │  │ Sign-off Checklist (Parallel Run)                                  │   │
 │  │                                                                    │   │
 │  │ Pre-Requisites:                                                    │   │
 │  │ ☑ pr_01: Analysis complete and approved                            │   │
 │  │ ☐ pr_02: Row counts match within tolerance                         │   │
 │  │ ☐ pr_03: Checksums match                                           │   │
 │  │ ☐ pr_04: Sample data validated                                     │   │
 │  │                                                                    │   │
 │  │ Technical Validation:                                              │   │
 │  │ ☐ pr_05: Performance acceptable (<2x source)                       │   │
 │  │ ☐ pr_06: Error handling tested                                     │   │
 │  │ ☐ pr_07: Logging and monitoring in place                           │   │
 │  │                                                                    │   │
 │  │ Business Sign-off:                                                 │   │
 │  │ ☐ pr_08: Business rules validated by SME                           │   │
 │  │ ☐ pr_09: Output matches business expectations                      │   │
 │  │                                                                    │   │
 │  │ Status: DRAFT                                                      │   │
 │  │                    [Auto-Populate from Reconciliation]             │   │
 │  └────────────────────────────────────────────────────────────────────┘   │
 │◄───────────────────────┤                       │                          │
 │                        │                       │                          │
 │  Clicks "Auto-Populate"│                       │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │                        │  POST /api/migrations/{project}/signoff/         │
 │                        │       requests/{id}/auto-populate                │
 │                        │  { "reconciliation_run_id": "..." }              │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │                       │  SignoffService          │
 │                        │                       │  .auto_populate_from_    │
 │                        │                       │   reconciliation()       │
 │                        │                       │  → pr_02, pr_03 auto-set │
 │                        │                       ├─────────────────────────►│
 │                        │                       │                          │
 │  ┌────────────────────────────────────────────────────────────────────┐   │
 │  │ Sign-off Checklist (Updated)                                       │   │
 │  │                                                                    │   │
 │  │ ☑ pr_02: Row counts match ✓                                        │   │
 │  │          Auto-populated from ReconciliationRun abc-123             │   │
 │  │          Source: 1,500,000 rows, Target: 1,500,000 rows            │   │
 │  │                                                                    │   │
 │  │ ☑ pr_03: Checksums match ✓                                         │   │
 │  │          Auto-populated from ReconciliationRun abc-123             │   │
 │  └────────────────────────────────────────────────────────────────────┘   │
 │◄───────────────────────┤                       │                          │
```

### 4.3 Approval Flow

```
Data Engineer           Web UI                   API                   Tech Lead
     │                     │                       │                       │
     │  Submits sign-off   │                       │                       │
     ├────────────────────►│                       │                       │
     │                     │                       │                       │
     │                     │  POST .../signoff/requests/{id}/submit         │
     │                     ├──────────────────────►│                       │
     │                     │                       │                       │
     │                     │  status: PENDING      │                       │
     │                     │◄──────────────────────┤                       │
     │                     │                       │                       │
     │                     │                       │  Notification sent     │
     │                     │                       ├──────────────────────►│
     │                     │                       │                       │
     │                     │                       │     Reviews checklist  │
     │                     │                       │◄──────────────────────┤
     │                     │                       │                       │
     │                     │  POST .../signoff/requests/{id}/approve        │
     │                     │  {                    │                       │
     │                     │    "approved_by": "Tech Lead",                │
     │                     │    "comments": "Validated against prod data"  │
     │                     │  }                    │                       │
     │                     │◄──────────────────────┼───────────────────────┤
     │                     │                       │                       │
     │                     │                       │  1. status → APPROVED │
     │                     │                       │  2. package.status →  │
     │                     │                       │     "migrated"        │
     │                     │                       │  3. Audit log entry   │
     │                     │                       │                       │
     │  Notification:      │                       │                       │
     │  "Sign-off approved"│                       │                       │
     │◄────────────────────┤                       │                       │
```

---

## Complete Migration Map Visualization

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              Migration Map — Project View                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  Filters: [All Waves ▼] [All Status ▼] [Show Tables ☑]        [Auto Layout] [Export]│
│                                                                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│                          WAVE 1                        WAVE 2                        │
│                                                                                      │
│   ┌─────────────────┐                        ┌─────────────────┐                    │
│   │ 📦 TTR_001      │                        │ 📦 TTR_003      │                    │
│   │ Daily Sales     │                        │ Monthly Agg     │                    │
│   │ ✅ migrated     │                        │ 🔵 generated    │                    │
│   └────────┬────────┘                        └────────▲────────┘                    │
│            │                                          │                             │
│            │ writes                                   │ reads                       │
│            ▼                                          │                             │
│   ┌─────────────────┐                        ┌───────┴─────────┐                    │
│   │ 📊 bronze.      │                        │ 📊 silver.      │                    │
│   │    orders       │────────────────────────│    orders       │                    │
│   └─────────────────┘         reads          └─────────────────┘                    │
│            │                                          ▲                             │
│            │ reads                                    │                             │
│            ▼                                          │                             │
│   ┌─────────────────┐                                 │                             │
│   │ 📦 TTR_002      │                                 │                             │
│   │ Transform       │─────────────────────────────────┘                             │
│   │ ✅ migrated     │              writes                                           │
│   └─────────────────┘                                                               │
│                                                                                      │
│   ┌─────────────────┐                                                               │
│   │ 📦 PCT_001      │ (isolated cluster)                                            │
│   │ Payments        │                                                               │
│   │ 🟡 analyzing    │                                                               │
│   └─────────────────┘                                                               │
│                                                                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  Summary: 4 packages | 2 clusters | Wave 1: 2 migrated | Wave 2: 1 pending          │
│  [Assign Waves Auto] [Manual Link Mode] [Export Mermaid]                            │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## API Reference Summary

| Module | Endpoint | Method | Purpose |
|--------|----------|--------|---------|
| **Registry** | `/api/migrations/{project}/packages` | POST | Register new package |
| | `/api/migrations/{project}/packages` | GET | List packages |
| | `/api/migrations/{project}/packages/{id}` | GET | Get package details |
| **Analysis** | `/api/migrations/analysis/packages/{project}/analyze` | POST | Queue single package |
| | `/api/migrations/analysis/packages/{project}/analyze-bulk` | POST | Queue multiple packages |
| | `/api/migrations/analysis/packages/{project}/{id}/status` | GET | Get analysis status |
| | `/api/migrations/analysis/packages/{project}/{id}/results` | GET | Get full results |
| | `/api/migrations/analysis/projects/{project}/summary` | GET | Project summary |
| | `/api/migrations/analysis/projects/{project}/blockers` | GET | Pending blockers |
| **Context** | `/api/migrations/{project}/context/connections` | GET/POST | Manage connections |
| | `/api/migrations/{project}/context/rules` | GET/POST | Manage business rules |
| | `/api/migrations/{project}/context/decisions` | GET/POST | Manage decisions |
| **Map** | `/api/migrations/{project}/map` | GET | Get migration map |
| | `/api/migrations/{project}/map/clusters` | GET | Get clusters |
| | `/api/migrations/{project}/map/objects` | GET | Get all objects |
| **Generation** | `/api/migrations/{project}/generation/packages/{id}/design` | GET | Design guidance |
| | `/api/migrations/{project}/generation/packages/{id}/preview` | GET | Preview generation |
| | `/api/migrations/{project}/generation/packages/{id}/generate` | POST | Generate artifacts |
| | `/api/migrations/{project}/generation/packages/{id}/download` | POST | Download ZIP |
| **Reconciliation** | `/api/migrations/{project}/reconciliation/packages/{id}/run` | POST | Run checks |
| | `/api/migrations/{project}/reconciliation/runs` | GET | List runs |
| | `/api/migrations/{project}/reconciliation/runs/{id}` | GET | Get run details |
| **Sign-off** | `/api/migrations/{project}/signoff/requests` | POST | Create sign-off |
| | `/api/migrations/{project}/signoff/requests` | GET | List sign-offs |
| | `/api/migrations/{project}/signoff/requests/{id}/submit` | POST | Submit for approval |
| | `/api/migrations/{project}/signoff/requests/{id}/approve` | POST | Approve |
| | `/api/migrations/{project}/signoff/requests/{id}/reject` | POST | Reject |

---

## Database Tables

| Table | Purpose |
|-------|---------|
| `etl_packages` | Package registry with status tracking |
| `migration_connections` | Shared connection definitions |
| `migration_business_rules` | Discovered business rules |
| `migration_resolved_decisions` | Project-wide decisions |
| `migration_objects` | Tables/files/APIs discovered |
| `package_object_refs` | Package → Object relationships |
| `package_flow_deps` | Package → Package data flows |
| `package_clusters` | Connected components |
| `reconciliation_runs` | Reconciliation execution history |
| `reconciliation_check_results` | Per-check results |
| `signoff_requests` | Approval requests |
| `signoff_checklist_items` | Checklist items per request |

---

## Key Differentiators

| Feature | Traditional Migration | Migration Workbench |
|---------|----------------------|---------------------|
| **Context** | Each package analyzed in isolation | Full project context (connections, rules, decisions) |
| **Decisions** | Resolved per-package | "Resolve once, apply everywhere" via propagation |
| **Visualization** | Spreadsheet/docs | Interactive migration map (React Flow) |
| **Validation** | Manual SQL queries | Automated reconciliation with audit trail |
| **Sign-off** | Email/document-based | Structured workflow with auto-population |
| **Lakebridge** | Separate tool | Integrated CLI + artifact storage |
