# Implementation Plan: Migration Workbench Module

**Status:** Planning  
**Created:** 2026-05-15  
**Scope:** Migration Workbench module for ETL migrations (SSIS → Databricks, etc.)

---

## Architecture Decision

**Migration Workbench** is implemented as a **module** within Agents Workshop, not a separate tool.

```
Agents Workshop
├── Core (projects, cards, skills, export)
├── Template Families
│   ├── phase_vli (generic)
│   └── migration (ETL migrations)
│
└── Modules
    └── migration_workbench/     ← THIS MODULE
        ├── registry/            # Package tracking
        ├── context/             # Shared connections, rules, decisions
        ├── analysis/            # SSIS/Airflow parsers + enrichment
        ├── map/                 # Migration Map (flow graph)
        ├── generation/          # Target code generation
        ├── reconciliation/      # Data comparison
        └── parallel_run/        # Production validation
```

**Why module, not separate tool:**
- Reuses Agents Workshop infra (DB, jobs, export)
- Migrations need cards/skills generation (core feature)
- Non-migration users don't see migration complexity
- Future: add other modules (testing workbench, etc.)

---

## Key Concepts

### 1. Context Accumulation (Per Project)

Every package uploaded adds to project knowledge:
- New connections discovered → added to connection registry
- New tables discovered → added to table catalog
- New business rules found → added to rule catalog
- Relationships detected → migration map updated

**No package is analyzed in isolation** — all analysis happens with full project context.

### 2. Migration Map (Flow Graph)

As packages are uploaded, the system builds a **flow graph**:
- **Nodes** = packages
- **Edges** = data flows (PKG_A writes TABLE_X → PKG_B reads TABLE_X)
- **Flows** = connected components (groups of related packages)

Relationships detected automatically by matching:
- Source tables ↔ Target tables (data flow)
- Shared connections (same domain)
- Declared predecessors (control tables)

### 3. All Features Available

No scale tiers — everyone gets enterprise features:
- 1 package uses what it needs
- 2000 packages use clustering, batching, propagation
- UI shows what's relevant (empty sections hidden)

---

## Document Map

| Document | Purpose | When to Reference |
|---|---|---|
| `SPEC.md` | Core Agents Workshop specification | Base schema, existing tables |
| `MIGRATION_BACKLOG_COMPARISON.md` | Gap analysis vs VLI project | Phase structure, skills, `business-rules-compliance-analyzer` |
| `MIGRATION_KNOWLEDGE_STRATEGY.md` | Knowledge preservation approach | Technology profiles, RAG, why no fine-tuning |
| `LARGE_SCALE_MIGRATION_SHARED_CONTEXT.md` | Shared context architecture | Connection registry, rule catalog, decisions |
| `IMPLEMENTATION_ANALYSIS_ENRICHMENT.md` | Artifact enrichment system | Analysis schema, feedback workflow |
| `project-analysis.html` | Visual documentation | All tabs, diagrams, UI mockups |

---

## Module File Structure

```
packages/core/app/modules/migration_workbench/
├── __init__.py
├── router.py                    # Mount all sub-routers at /migrations/*
├── config.py                    # Module configuration
│
├── registry/                    # Package Registry
│   ├── __init__.py
│   ├── models.py               # etl_packages, package_clusters
│   ├── schemas.py              # Pydantic schemas
│   ├── service.py              # Package CRUD, bulk operations
│   └── router.py               # /migrations/packages/*
│
├── context/                     # Shared Context
│   ├── __init__.py
│   ├── models.py               # connections, rules, decisions
│   ├── schemas.py
│   ├── service.py              # Context management, propagation
│   └── router.py               # /migrations/context/*
│
├── analysis/                    # Package Analysis
│   ├── __init__.py
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base.py            # Parser interface
│   │   ├── ssis.py            # SSIS .dtsx parser
│   │   └── airflow.py         # Airflow DAG parser
│   ├── connection_points.py    # Extract sources/targets
│   ├── enrichment.py          # LLM analysis with profiles
│   ├── service.py             # Analysis orchestration
│   ├── jobs.py                # Dramatiq jobs
│   └── router.py              # /migrations/analysis/*
│
├── map/                         # Migration Map (Flow Graph)
│   ├── __init__.py
│   ├── models.py              # relationships, flows
│   ├── graph.py               # NetworkX graph operations
│   ├── detector.py            # Relationship detection
│   ├── service.py             # Map management
│   └── router.py              # /migrations/map/*
│
├── generation/                  # Target Code Generation
│   ├── __init__.py
│   ├── databricks/
│   │   ├── __init__.py
│   │   ├── notebook.py        # Generate .py notebooks
│   │   ├── workflow.py        # Generate workflow YAML
│   │   └── ddl.py             # Generate DDL
│   ├── templates/             # Jinja2 templates
│   │   ├── notebook_bronze.py.j2
│   │   ├── notebook_silver.py.j2
│   │   ├── notebook_gold.py.j2
│   │   └── workflow.yml.j2
│   ├── service.py
│   └── router.py              # /migrations/generate/*
│
├── reconciliation/              # Data Comparison
│   ├── __init__.py
│   ├── engine.py              # Comparison logic
│   ├── tolerance.py           # Threshold management
│   ├── report.py              # Generate reports
│   ├── service.py
│   └── router.py              # /migrations/reconciliation/*
│
├── parallel_run/                # Production Validation
│   ├── __init__.py
│   ├── orchestrator.py        # Run source + target
│   ├── comparison.py          # Compare outputs
│   ├── signoff.py             # Sign-off workflow
│   ├── service.py
│   └── router.py              # /migrations/parallel-run/*
│
├── profiles/                    # Technology Profiles
│   ├── __init__.py
│   ├── loader.py              # Load and parse YAML
│   ├── schema.py              # Profile Pydantic models
│   ├── ssis.yaml              # SSIS patterns
│   ├── airflow.yaml           # Airflow patterns
│   └── common_etl.yaml        # Cross-technology patterns
│
└── skills/                      # Pre-built Migration Skills
    ├── business-rules-compliance-analyzer/
    │   ├── SKILL.md
    │   └── resources/
    ├── disabled-task-auditor/
    │   ├── SKILL.md
    │   └── resources/
    └── etl-migration-reconciler/
        ├── SKILL.md
        └── resources/
```

---

## Implementation Phases

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: Module Foundation (Week 1-2)                                       │
│  ├── 1.1: Module scaffold & router setup                                    │
│  ├── 1.2: Technology Profiles (YAML + loader)                               │
│  ├── 1.3: MigrationFamily template (7 phases)                               │
│  └── 1.4: Project type extension                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  PHASE 2: Package Registry & Context (Week 3-4)                              │
│  ├── 2.1: Package registry tables & API                                     │
│  ├── 2.2: Connection registry (shared connections)                          │
│  ├── 2.3: Business rules catalog                                            │
│  ├── 2.4: Resolved decisions store                                          │
│  └── 2.5: Context accumulation service                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  PHASE 3: Analysis & Connection Points (Week 5-6)                            │
│  ├── 3.1: SSIS parser (extract connection points)                           │
│  ├── 3.2: Connection points extraction                                      │
│  ├── 3.3: Analysis with context (LLM enrichment)                            │
│  ├── 3.4: Feedback item extraction                                          │
│  └── 3.5: Analysis Dramatiq job                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  PHASE 4: Migration Map (Week 7-8)                                           │
│  ├── 4.1: Relationship detection (table matching)                           │
│  ├── 4.2: Flow discovery (connected components)                             │
│  ├── 4.3: Map persistence (relationships, flows tables)                     │
│  ├── 4.4: Map update on package upload                                      │
│  └── 4.5: Map visualization API                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  PHASE 5: Knowledge Propagation (Week 9-10)                                  │
│  ├── 5.1: Pattern library (Vector DB)                                       │
│  ├── 5.2: Few-shot selection service                                        │
│  ├── 5.3: Decision propagation ("resolve once, apply everywhere")           │
│  └── 5.4: Batch operations API                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  PHASE 6: Generation & Validation (Week 11-12)                               │
│  ├── 6.1: Target code generation (notebooks, workflows)                     │
│  ├── 6.2: Reconciliation engine                                             │
│  ├── 6.3: Parallel run orchestration                                        │
│  └── 6.4: Sign-off workflow                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  PHASE 7: Pre-Built Skills & Polish (Week 13-14)                             │
│  ├── 7.1: business-rules-compliance-analyzer skill                          │
│  ├── 7.2: disabled-task-auditor skill                                       │
│  ├── 7.3: etl-migration-reconciler skill                                    │
│  └── 7.4: Documentation & testing                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Module Foundation (Week 1-2)

### 1.1: Module Scaffold & Router Setup

**Goal:** Create the module structure and mount routes.

**Files:**
```
packages/core/app/modules/__init__.py
packages/core/app/modules/migration_workbench/__init__.py
packages/core/app/modules/migration_workbench/router.py
packages/core/app/modules/migration_workbench/config.py
```

**Code (router.py):**
```python
from fastapi import APIRouter

from .registry.router import router as registry_router
from .context.router import router as context_router
from .analysis.router import router as analysis_router
from .map.router import router as map_router
from .generation.router import router as generation_router
from .reconciliation.router import router as reconciliation_router
from .parallel_run.router import router as parallel_run_router

router = APIRouter(prefix="/migrations", tags=["Migration Workbench"])

router.include_router(registry_router, prefix="/packages")
router.include_router(context_router, prefix="/context")
router.include_router(analysis_router, prefix="/analysis")
router.include_router(map_router, prefix="/map")
router.include_router(generation_router, prefix="/generate")
router.include_router(reconciliation_router, prefix="/reconciliation")
router.include_router(parallel_run_router, prefix="/parallel-run")
```

**Integration (main.py):**
```python
from app.modules.migration_workbench.router import router as migration_router

app.include_router(migration_router)
```

**Effort:** 1 day

---

### 1.2: Technology Profiles

**Goal:** YAML-based technology profiles for pattern-aware generation.

**Reference:** [MIGRATION_KNOWLEDGE_STRATEGY.md](MIGRATION_KNOWLEDGE_STRATEGY.md) § Part 1-2

**Schema (schema.py):**
```python
from pydantic import BaseModel

class StructuralPattern(BaseModel):
    id: str
    name: str
    description: str
    detection_hint: str | None = None
    migration_implication: str
    skill_suggestion: str | None = None
    equivalent_in: dict[str, str] = {}

class TechnologyProfile(BaseModel):
    name: str
    slug: str
    file_extension: str
    format: str
    structural_patterns: list[StructuralPattern] = []
    execution_patterns: list[StructuralPattern] = []
    validation_requirements: list[StructuralPattern] = []
```

**SSIS Profile (ssis.yaml):**
```yaml
name: SQL Server Integration Services (SSIS)
slug: ssis
file_extension: .dtsx
format: xml

structural_patterns:
  - id: disabled_tasks
    name: Disabled Tasks
    description: SSIS packages often contain disabled tasks
    detection_hint: "DTS:Disabled='True'"
    migration_implication: Must audit before migration
    skill_suggestion: Include task audit in discovery
    
  - id: change_annotations
    name: Change Annotations
    description: Developer notes in AnnotationLayout blocks
    detection_hint: "AnnotationLayout elements"
    migration_implication: Risk information hidden here
    skill_suggestion: Parse for risk register
    
  - id: connection_managers
    name: Connection Managers
    description: External connectivity definitions
    detection_hint: "DTS:ConnectionManager elements"
    migration_implication: Map to target platform
    
  - id: execution_modes
    name: Multiple Execution Modes
    description: Packages support incremental/full modes
    detection_hint: "EvaluateAsExpression=True variables"
    migration_implication: All modes must be replicated

execution_patterns:
  - id: incremental_vs_full
    name: Incremental vs Full Reload
    description: Control flags determine execution mode
    detection_hint: "processamento_full parameter"
    migration_implication: Target must support MERGE and OVERWRITE
    
  - id: soft_deletes
    name: Soft Deletes
    description: Logical deletion via flag columns
    detection_hint: "UPDATE...SET exclusao_logica"
    migration_implication: Preserve exact business rule

validation_requirements:
  - id: parallel_run
    name: Parallel Run
    description: Side-by-side validation before cutover
    rationale: Cannot rely on unit tests alone
    skill_suggestion: Include parallel run phase
    
  - id: static_code_comparison
    name: Static Code Comparison
    description: Rule-by-rule source vs target comparison
    rationale: Ensures no business logic drift
    skill_suggestion: Include static analysis step
```

**Effort:** 2 days

---

### 1.3: MigrationFamily Template

**Goal:** 7-phase migration template family.

**Reference:** [MIGRATION_BACKLOG_COMPARISON.md](MIGRATION_BACKLOG_COMPARISON.md)

```python
MIGRATION_PHASES = [
    {"code": "phase-1-discovery", "name": "Discovery & Assessment", "order_no": 1},
    {"code": "phase-2-foundation", "name": "Infrastructure Foundation", "order_no": 2},
    {"code": "phase-3-transformation", "name": "Data Transformation (Silver)", "order_no": 3},
    {"code": "phase-4-aggregation", "name": "Data Aggregation (Gold)", "order_no": 4},
    {"code": "phase-5-business-rules", "name": "Business Rules Implementation", "order_no": 5},
    {"code": "phase-6-cutover", "name": "Cutover Preparation", "order_no": 6},
    {"code": "phase-7-parallel-run", "name": "Parallel Run & Validation", "order_no": 7},
]

class MigrationFamily(TemplateFamily):
    slug = "migration"
    name = "Migration Workbench"
    
    def on_project_create(self, project: Project, db):
        for phase_def in MIGRATION_PHASES:
            phase = Phase(project_id=project.id, **phase_def)
            db.add(phase)
```

**Effort:** 2 days

---

### 1.4: Project Type Extension

**SQL:**
```sql
ALTER TABLE projects ADD COLUMN project_type TEXT 
    DEFAULT 'application'
    CHECK (project_type IN ('application', 'migration'));

ALTER TABLE projects ADD COLUMN source_technology TEXT;
ALTER TABLE projects ADD COLUMN target_technology TEXT;
```

**Effort:** 0.5 days

---

## Phase 2: Package Registry & Context (Week 3-4)

### 2.1: Package Registry Tables

```sql
CREATE TABLE etl_packages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    
    package_name TEXT NOT NULL,
    package_path TEXT,
    artifact_id UUID REFERENCES project_artifacts(id),
    
    domain TEXT,
    complexity TEXT DEFAULT 'medium',
    
    status TEXT DEFAULT 'registered'
        CHECK (status IN (
            'registered', 'analyzing', 'analyzed', 
            'needs_feedback', 'ready', 
            'generating', 'generated',
            'validating', 'validated', 
            'migrated', 'verified'
        )),
    
    pending_feedback_count INTEGER DEFAULT 0,
    blocking_feedback_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    analyzed_at TIMESTAMPTZ,
    migrated_at TIMESTAMPTZ,
    
    UNIQUE (project_id, package_name)
);
```

**Effort:** 1 day

---

### 2.2-2.4: Connection Registry, Rules Catalog, Decisions Store

**Reference:** [LARGE_SCALE_MIGRATION_SHARED_CONTEXT.md](LARGE_SCALE_MIGRATION_SHARED_CONTEXT.md)

```sql
CREATE TABLE migration_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    
    connection_name TEXT NOT NULL,
    connection_type TEXT,
    source_server TEXT,
    source_database TEXT,
    auth_method TEXT,
    
    target_catalog TEXT,
    target_schema TEXT,
    
    used_by_packages UUID[] DEFAULT '{}',
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    
    UNIQUE (project_id, connection_name)
);

CREATE TABLE migration_business_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    
    rule_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    description TEXT,
    source_implementation TEXT,
    target_implementation TEXT,
    
    category TEXT,
    applies_to_domains TEXT[] DEFAULT '{}',
    used_by_packages UUID[] DEFAULT '{}',
    
    status TEXT DEFAULT 'discovered',
    
    UNIQUE (project_id, rule_id)
);

CREATE TABLE migration_resolved_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    
    decision_type TEXT NOT NULL,
    question TEXT NOT NULL,
    resolution TEXT NOT NULL,
    resolution_rationale TEXT,
    
    scope TEXT DEFAULT 'project',
    flow_id UUID,
    package_id UUID REFERENCES etl_packages(id),
    
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ DEFAULT NOW(),
    applied_to_packages UUID[] DEFAULT '{}'
);
```

**Effort:** 3 days

---

### 2.5: Context Accumulation Service

```python
class ContextService:
    def get_project_context(self, project_id: UUID) -> ProjectContext:
        return ProjectContext(
            connections=self._get_connections(project_id),
            business_rules=self._get_business_rules(project_id),
            resolved_decisions=self._get_decisions(project_id),
            packages=self._get_packages(project_id),
            flows=self._get_flows(project_id),
        )
    
    def register_connection(self, project_id: UUID, connection: ConnectionCreate):
        existing = self.db.query(MigrationConnection).filter_by(
            project_id=project_id,
            connection_name=connection.connection_name
        ).first()
        
        if existing:
            existing.used_by_packages = list(set(
                existing.used_by_packages + [connection.discovered_in_package]
            ))
            return existing
        
        conn = MigrationConnection(project_id=project_id, **connection.dict())
        self.db.add(conn)
        return conn
    
    def find_resolved_decision(self, project_id: UUID, decision_type: str) -> ResolvedDecision | None:
        return self.db.query(MigrationResolvedDecision).filter(
            MigrationResolvedDecision.project_id == project_id,
            MigrationResolvedDecision.decision_type == decision_type,
            MigrationResolvedDecision.scope == 'project',
        ).first()
```

**Effort:** 2 days

---

## Phase 3: Analysis & Connection Points (Week 5-6)

### 3.1: SSIS Parser

```python
class SSISParser:
    NS = {'DTS': 'www.microsoft.com/SqlServer/Dts'}
    
    def parse(self, content: str) -> SSISPackage:
        root = ET.fromstring(content)
        return SSISPackage(
            name=root.get('{www.microsoft.com/SqlServer/Dts}ObjectName'),
            connection_managers=self._parse_connections(root),
            tasks=self._parse_tasks(root),
            variables=self._parse_variables(root),
            annotations=self._parse_annotations(root),
        )
```

**Effort:** 2 days

---

### 3.2: Connection Points Extraction

```python
@dataclass
class PackageConnectionPoints:
    package_id: UUID
    source_tables: list[TableRef]
    target_tables: list[TableRef]
    source_connections: list[str]
    target_connections: list[str]
    declared_predecessors: list[str]
```

```sql
CREATE TABLE package_connection_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    package_id UUID NOT NULL REFERENCES etl_packages(id),
    
    source_tables JSONB DEFAULT '[]',
    source_connections TEXT[] DEFAULT '{}',
    target_tables JSONB DEFAULT '[]',
    target_connections TEXT[] DEFAULT '{}',
    declared_predecessors TEXT[] DEFAULT '{}',
    
    extracted_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (package_id)
);
```

**Effort:** 2 days

---

### 3.3-3.5: Analysis with Context & Dramatiq Job

```python
@dramatiq.actor
def analyze_package(project_id: str, package_id: str):
    with get_db() as db:
        package = db.query(ETLPackage).get(UUID(package_id))
        
        # Load technology profile
        profile = load_profile(package.project.source_technology)
        
        # Load accumulated project context
        context_service = ContextService(db)
        project_context = context_service.get_project_context(UUID(project_id))
        
        # Parse the package
        parser = get_parser(package.project.source_technology)
        parsed = parser.parse(package.artifact.content_md)
        
        # Extract connection points
        connection_points = ConnectionPointsExtractor().extract(parsed)
        
        # Register new connections
        for conn in parsed.connection_managers:
            context_service.register_connection(UUID(project_id), conn)
        
        # Analyze with LLM
        analysis = analyze_with_llm(parsed, profile, project_context)
        
        # Extract feedback items (check if already resolved)
        feedback_items = extract_feedback_items(analysis)
        for item in feedback_items:
            existing = context_service.find_resolved_decision(
                UUID(project_id), item.decision_type
            )
            if existing:
                item.status = 'auto_resolved'
                item.resolution = existing.resolution
        
        # Update migration map
        map_service = MigrationMapService(db)
        map_service.add_package(UUID(project_id), UUID(package_id), connection_points)
        
        # Save and update status
        save_all(db, package_id, analysis, connection_points, feedback_items)
        package.status = 'needs_feedback' if any_open(feedback_items) else 'analyzed'
```

**Effort:** 4 days

---

## Phase 4: Migration Map (Week 7-8)

The Migration Map is a **living flow graph** that grows as packages are uploaded. It shows:
- Data dependencies between packages (who produces data that others consume)
- Connected components (flows that should migrate together)
- Migration waves (topologically sorted execution order)
- Column-level lineage (optional, for detailed traceability)

### 4.1: Migration Objects Registry

Track all tables/files/APIs discovered across packages:

```sql
-- Tables/Objects discovered across all packages
CREATE TABLE migration_objects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    
    -- Identity
    object_type TEXT NOT NULL,        -- 'table' | 'file' | 'api' | 'queue'
    object_name TEXT NOT NULL,        -- 'dbo.FactSales' | '/data/input.csv'
    connection_ref TEXT,              -- Which connection accesses this
    
    -- Metadata (accumulated from multiple packages)
    schema_name TEXT,
    database_name TEXT,
    discovered_columns JSONB,         -- Columns seen across packages [{name, type}]
    
    -- Statistics
    read_by_count INTEGER DEFAULT 0,
    written_by_count INTEGER DEFAULT 0,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE (project_id, object_type, object_name)
);

-- Package ↔ Object relationships (who reads/writes what)
CREATE TABLE package_object_refs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    package_id UUID NOT NULL REFERENCES etl_packages(id),
    object_id UUID NOT NULL REFERENCES migration_objects(id),
    
    -- Relationship type
    direction TEXT NOT NULL,           -- 'read' | 'write' | 'lookup'
    access_type TEXT,                  -- 'full_load' | 'incremental' | 'merge' | 'delete_insert'
    
    -- Extracted details
    sql_fragment TEXT,                 -- The actual SQL if available
    columns_accessed TEXT[],           -- Which columns
    
    -- Source in DTSX
    task_name TEXT,                    -- Which task in the package
    extraction_confidence FLOAT DEFAULT 1.0,
    
    UNIQUE (package_id, object_id, direction)
);
```

**Effort:** 1 day

---

### 4.2: Column-Level Lineage (Optional)

For detailed traceability, track column transformations:

```sql
-- Column-level lineage within packages
CREATE TABLE column_lineage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    package_id UUID NOT NULL REFERENCES etl_packages(id),
    
    -- Source
    source_object_id UUID NOT NULL REFERENCES migration_objects(id),
    source_column TEXT NOT NULL,
    
    -- Target
    target_object_id UUID NOT NULL REFERENCES migration_objects(id),
    target_column TEXT NOT NULL,
    
    -- Transformation
    transformation_type TEXT,        -- 'direct' | 'derived' | 'aggregated' | 'filtered' | 'cast'
    transformation_expr TEXT,        -- e.g., "CAST(amount AS DECIMAL(18,2))"
    
    -- Extraction metadata
    confidence FLOAT DEFAULT 1.0,
    task_name TEXT
);

CREATE INDEX idx_column_lineage_source ON column_lineage(source_object_id, source_column);
CREATE INDEX idx_column_lineage_target ON column_lineage(target_object_id, target_column);
```

**Extraction complexity:**
| Type | Difficulty | Source in SSIS |
|------|------------|----------------|
| Direct mappings | Easy | inputColumns/outputColumns metadata |
| SQL expressions | Medium | Derived Column transform |
| CASE expressions | Medium | Parse SqlStatementSource |
| Aggregations | Hard | Aggregate transform |

**Start with**: Table-level + direct column mappings. Add expression parsing later.

**Effort:** 2 days

---

### 4.3: Package Flow Dependencies

Computed edges between packages based on shared objects:

```sql
-- Computed flow dependencies (Package A → Package B)
CREATE TABLE package_flow_deps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    
    upstream_package_id UUID NOT NULL REFERENCES etl_packages(id),
    downstream_package_id UUID NOT NULL REFERENCES etl_packages(id),
    
    -- Why connected
    via_object_id UUID REFERENCES migration_objects(id),
    relationship_type TEXT NOT NULL,   -- 'data_flow' | 'control' | 'inferred'
    
    -- Confidence
    is_confirmed BOOLEAN DEFAULT false,  -- Human verified
    auto_detected BOOLEAN DEFAULT true,
    
    UNIQUE (upstream_package_id, downstream_package_id, via_object_id)
);

-- Package clusters (connected components in the graph)
CREATE TABLE package_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    
    name TEXT,
    description TEXT,
    
    -- Computed
    package_count INTEGER DEFAULT 0,
    root_packages UUID[],              -- Entry points (no upstream)
    leaf_packages UUID[],              -- Exit points (no downstream)
    
    -- Migration planning
    suggested_wave INTEGER,
    migration_order JSONB              -- Topological sort [{package_id, position}]
);

CREATE TABLE package_cluster_members (
    cluster_id UUID NOT NULL REFERENCES package_clusters(id) ON DELETE CASCADE,
    package_id UUID NOT NULL REFERENCES etl_packages(id),
    position_in_cluster INTEGER,
    PRIMARY KEY (cluster_id, package_id)
);
```

**Effort:** 1 day

---

### 4.4: Relationship & Flow Detection

```python
class RelationshipDetector:
    """Detect data flow relationships between packages via shared objects."""
    
    def detect_relationships(self, project_id: UUID, new_package_id: UUID) -> list[FlowDep]:
        """When a new package is added, find relationships with existing packages."""
        
        # Get objects written by new package
        new_writes = self.db.query(PackageObjectRef).filter(
            PackageObjectRef.package_id == new_package_id,
            PackageObjectRef.direction == 'write'
        ).all()
        
        # Get objects read by new package
        new_reads = self.db.query(PackageObjectRef).filter(
            PackageObjectRef.package_id == new_package_id,
            PackageObjectRef.direction.in_(['read', 'lookup'])
        ).all()
        
        relationships = []
        
        # Find packages that READ what new package WRITES (new → existing)
        for write_ref in new_writes:
            readers = self.db.query(PackageObjectRef).filter(
                PackageObjectRef.object_id == write_ref.object_id,
                PackageObjectRef.direction.in_(['read', 'lookup']),
                PackageObjectRef.package_id != new_package_id
            ).all()
            
            for reader in readers:
                relationships.append(FlowDep(
                    upstream_package_id=new_package_id,
                    downstream_package_id=reader.package_id,
                    via_object_id=write_ref.object_id,
                    relationship_type='data_flow'
                ))
        
        # Find packages that WRITE what new package READS (existing → new)
        for read_ref in new_reads:
            writers = self.db.query(PackageObjectRef).filter(
                PackageObjectRef.object_id == read_ref.object_id,
                PackageObjectRef.direction == 'write',
                PackageObjectRef.package_id != new_package_id
            ).all()
            
            for writer in writers:
                relationships.append(FlowDep(
                    upstream_package_id=writer.package_id,
                    downstream_package_id=new_package_id,
                    via_object_id=read_ref.object_id,
                    relationship_type='data_flow'
                ))
        
        return relationships


class FlowDetector:
    """Detect connected components and compute migration order."""
    
    def detect_clusters(self, project_id: UUID) -> list[PackageCluster]:
        """Find connected components and compute topological sort."""
        import networkx as nx
        
        # Build graph from flow deps
        deps = self.db.query(PackageFlowDep).filter_by(project_id=project_id).all()
        
        G = nx.DiGraph()
        for dep in deps:
            G.add_edge(dep.upstream_package_id, dep.downstream_package_id)
        
        # Add orphan packages (no dependencies)
        all_packages = self.db.query(ETLPackage.id).filter_by(project_id=project_id).all()
        for (pkg_id,) in all_packages:
            if pkg_id not in G:
                G.add_node(pkg_id)
        
        # Find weakly connected components
        components = list(nx.weakly_connected_components(G))
        
        clusters = []
        for i, component in enumerate(components):
            subgraph = G.subgraph(component)
            
            # Find roots (no incoming edges)
            roots = [n for n in component if subgraph.in_degree(n) == 0]
            
            # Find leaves (no outgoing edges)
            leaves = [n for n in component if subgraph.out_degree(n) == 0]
            
            # Topological sort for execution order
            try:
                order = list(nx.topological_sort(subgraph))
            except nx.NetworkXUnfeasible:
                # Cycle detected - mark for human review
                order = list(component)
            
            clusters.append(PackageCluster(
                project_id=project_id,
                name=f"Flow {i + 1}",
                package_count=len(component),
                root_packages=roots,
                leaf_packages=leaves,
                migration_order=[{"package_id": str(p), "position": j} for j, p in enumerate(order)]
            ))
        
        return clusters
```

**Effort:** 2 days

---

### 4.5: Migration Map UI (React Flow)

**Library Choice: React Flow**
- Native React integration (we use Next.js)
- Built-in drag-and-drop for manual linking
- Dagre plugin for automatic DAG layouts
- Custom node types for packages and tables

**Frontend Files:**
```
packages/web/src/app/migrations/[slug]/map/
├── page.tsx                    # Map page wrapper
├── components/
│   ├── migration-map.tsx      # React Flow canvas
│   ├── package-node.tsx       # Custom package node
│   ├── table-node.tsx         # Custom table/object node
│   ├── map-controls.tsx       # Filters, wave assignment
│   └── map-sidebar.tsx        # Details panel
```

**Package Node Component:**
```tsx
import { Handle, Position } from 'reactflow';
import { Badge } from '@/components/ui/badge';

interface PackageNodeProps {
  data: {
    name: string;
    status: 'registered' | 'analyzed' | 'ready' | 'migrated';
    wave?: number;
    feedbackCount: number;
  };
}

export function PackageNode({ data }: PackageNodeProps) {
  const statusColors = {
    registered: 'bg-gray-100',
    analyzed: 'bg-yellow-100',
    ready: 'bg-green-100',
    migrated: 'bg-blue-100',
  };

  return (
    <div className={`px-4 py-2 rounded-lg border-2 ${statusColors[data.status]}`}>
      <Handle type="target" position={Position.Top} />
      
      <div className="font-medium text-sm">{data.name}</div>
      <div className="flex gap-1 mt-1">
        {data.wave && <Badge variant="outline">Wave {data.wave}</Badge>}
        {data.feedbackCount > 0 && (
          <Badge variant="destructive">{data.feedbackCount} issues</Badge>
        )}
      </div>
      
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
```

**Map API Response:**
```python
class MapVisualization(BaseModel):
    nodes: list[MapNode]
    edges: list[MapEdge]
    clusters: list[ClusterInfo]
    orphan_packages: list[str]
    stats: MapStats

class MapNode(BaseModel):
    id: str
    type: str  # 'package' | 'table'
    data: dict
    position: dict | None  # Let React Flow auto-layout if None

class MapEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str | None  # Table name connecting them
    animated: bool = False  # True for in-progress flows
```

**UI Mockup:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Migration Map                                        [Auto Layout] [Export]│
├─────────────────────────────────────────────────────────────────────────────┤
│ Filters: [All Waves ▼] [All Status ▼] [Show Tables ☑] [Show Columns ☐]     │
├───────────────────────────────────────────────────┬─────────────────────────┤
│                                                   │ Selected: ETL_Sales     │
│   ┌───────────────┐                               │ ─────────────────────── │
│   │ staging.raw   │                               │ Status: Analyzed ✓      │
│   │   _sales      │                               │ Wave: 1                 │
│   │   (table)     │                               │ Domain: Sales           │
│   └───────┬───────┘                               │                         │
│           │                                       │ Sources:                │
│           ▼                                       │ • staging.raw_sales     │
│   ┌───────────────┐                               │                         │
│   │ ETL_Sales_    │──┐                            │ Targets:                │
│   │   Daily       │  │                            │ • bronze.fact_sales     │
│   │  ✓ Wave 1     │  │                            │                         │
│   └───────┬───────┘  │                            │ Connections:            │
│           │          │                            │ • OLEDB_DW_Corp ✓       │
│           ▼          │                            │ • OLEDB_STG ✓           │
│   ┌───────────────┐  │                            │                         │
│   │ bronze.fact   │  │                            │ Feedback:               │
│   │   _sales      │  │                            │ • 0 blocking            │
│   │   (table)     │  │                            │ • 2 resolved            │
│   └───────┬───────┘  │                            │                         │
│           │          │                            │ [View Analysis]         │
│           ▼          │                            │ [Generate Code]         │
│   ┌───────────────┐  │                            │                         │
│   │ ETL_Sales_    │◄─┘                            │                         │
│   │   Monthly     │                               │                         │
│   │  ⏳ Wave 2    │                               │                         │
│   └───────────────┘                               │                         │
├───────────────────────────────────────────────────┴─────────────────────────┤
│  Clusters: 3 | Packages: 2000 | Orphans: 45 | Suggested Waves: 8           │
│  [Assign Waves Automatically] [Manual Link Mode] [Resolve Orphans]          │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Effort:** 3 days

---

### 4.6: Progressive Discovery Flow

As packages are uploaded, the map updates automatically:

```
Upload Package 1 (ETL_Sales_Daily):
  → Extract: reads staging.raw_sales, writes bronze.fact_sales
  → Objects: Create staging.raw_sales, bronze.fact_sales
  → Refs: PKG1 reads raw_sales, PKG1 writes fact_sales
  → Graph: [PKG1] (isolated)
  → Cluster: Flow 1 = [PKG1]

Upload Package 2 (ETL_Sales_Monthly):
  → Extract: reads bronze.fact_sales, writes silver.sales_monthly
  → Objects: bronze.fact_sales exists! Create silver.sales_monthly
  → Refs: PKG2 reads fact_sales, PKG2 writes sales_monthly
  → Match: PKG1 WRITES fact_sales, PKG2 READS fact_sales → EDGE!
  → Graph: PKG1 → PKG2
  → Cluster: Flow 1 = [PKG1 → PKG2]

Upload Package 3 (ETL_Inventory):
  → Extract: reads staging.raw_inventory, writes bronze.fact_inventory
  → No matches with existing
  → Graph: PKG1 → PKG2, [PKG3]
  → Clusters: Flow 1 = [PKG1 → PKG2], Flow 2 = [PKG3]

Upload Package 4 (ETL_Combined_Report):
  → Reads: silver.sales_monthly, bronze.fact_inventory
  → Matches: PKG2 writes sales_monthly, PKG3 writes fact_inventory
  → Graph: PKG1 → PKG2 → PKG4 ← PKG3
  → Clusters MERGED: Flow 1 = [PKG1 → PKG2 → PKG4 ← PKG3]
```

**Effort:** Included in 4.4

---

## Phase 5: Knowledge Propagation (Week 9-10)

### 5.1: Pattern Library (Vector DB)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE migration_patterns (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    package_id UUID REFERENCES etl_packages(id),
    embedding VECTOR(1536),
    domain TEXT,
    summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON migration_patterns USING ivfflat (embedding vector_cosine_ops);
```

**Effort:** 2 days

---

### 5.2-5.4: Few-Shot, Propagation, Batch API

**Reference:** [MIGRATION_KNOWLEDGE_STRATEGY.md](MIGRATION_KNOWLEDGE_STRATEGY.md)

```python
class PropagationService:
    def propagate_decision(self, decision_id: UUID) -> int:
        decision = self.db.query(MigrationResolvedDecision).get(decision_id)
        
        affected = self._find_packages_with_question(
            decision.project_id, decision.decision_type
        )
        
        for package_id in affected:
            self._auto_resolve_feedback(package_id, decision)
        
        decision.applied_to_packages = affected
        return len(affected)
```

**Effort:** 4 days

---

## Phase 6: Generation & Validation (Week 11-12)

- Target code generation (notebooks, workflows, DDL)
- Reconciliation engine
- Parallel run orchestration
- Sign-off workflow

**Reference:** VLI CORP-601, CORP-605, CORP-606

**Effort:** 8 days

---

## Phase 7: Pre-Built Skills (Week 13-14)

**Status:** ✅ COMPLETED

### Skills Created

1. **business-rules-compliance-analyzer** — Static code analysis for business rule extraction
2. **disabled-task-auditor** — Classify disabled tasks for migration decisions
3. **etl-migration-reconciler** — Reconciliation and data validation patterns
4. **change-history-risk-analyzer** — Assess migration risk based on package history

### Additional Deliverables

1. **Databricks Target Profile** (`profiles/databricks.yaml`)
   - Medallion architecture (Bronze/Silver/Gold) with patterns and anti-patterns
   - 15 data patterns (MERGE, SCD Types 1-3, CDC, Watermark, etc.)
   - Performance hints (Photon, broadcast, Z-ORDER, range joins)

2. **Data Pattern Classifier** (`analysis/data_pattern_classifier.py`)
   - `DataPattern` enum with all 15 patterns
   - `DataPatternClassifier` for per-task pattern detection
   - `MedallionLayer` assignment based on task analysis
   - Performance recommendations and Photon eligibility

3. **Design Guidance API** (`GET /generation/packages/{id}/design`)
   - Pre-generation analysis showing per-table patterns
   - Layer assignments and confidence scores
   - Performance notes and optimization hints

4. **Design Guidance UI** (`DesignGuidancePanel`)
   - New "Design" tab in Generation Dialog (before Preview)
   - Pattern table with icons and tooltips
   - Photon eligibility indicator
   - Layer distribution summary

5. **Skill Loader Service** (`skills/skill_loader.py`)
   - `SkillLoader` class for discovering SKILL.md files
   - `SkillSummary` and `SkillDetail` schemas
   - API endpoint `GET /skills` and `GET /skills/{id}`
   - React `SkillsPanel` component

**Reference:** [MIGRATION_BACKLOG_COMPARISON.md](MIGRATION_BACKLOG_COMPARISON.md) § Skill Definition

**Effort:** 5 days (actual: 1 session)

**Tests:** 16 new tests added (DataPatternClassifier: 11, SkillLoader: 5)

---

## Summary

| Phase | Weeks | Key Deliverables | Status |
|---|---|---|---|
| 1: Foundation | 1-2 | Module scaffold, profiles, MigrationFamily | ✅ |
| 2: Registry & Context | 3-4 | Package registry, connections, rules, decisions | ✅ |
| 3: Analysis | 5-6 | SSIS parser, connection points, context-aware analysis | ✅ |
| 4: Migration Map | 7-8 | Object registry, flow detection, column lineage, React Flow UI | ✅ |
| 5: Knowledge | 9-10 | Vector DB, few-shot, decision propagation, batch ops | ✅ |
| 6: Generation | 11-12 | Notebooks, reconciliation, parallel run | ✅ |
| 7: Skills | 13-14 | Pre-built skills, design guidance, skill loader | ✅ |

**Total: 14 weeks** (All phases complete)

---

## Validation Project

**Use VLI reference project** (`packages/core/app/seed/reference/ref-corp-vli/`) as validation:
- 7 phases, 25 cards, 6 skills
- Real SSIS → Databricks migration
- Full example of what Migration Workbench should generate

**Validation Checkpoints:**
| Phase | Validate Against |
|---|---|
| Phase 1 | MigrationFamily creates same 7 phases as VLI |
| Phase 3 | SSIS parser extracts expected connection points |
| Phase 4 | Migration Map matches VLI package dependencies |
| Phase 6 | Generated notebooks match VLI structure |
| Phase 7 | Skills match VLI skill definitions |

---

## Dependencies

```
Phase 1 (Foundation)
    │
    ▼
Phase 2 (Registry & Context)
    │
    ▼
Phase 3 (Analysis) ──────────────────────┐
    │                                     │
    ▼                                     │
Phase 4 (Migration Map)                   │
    │                                     │
    ▼                                     │
Phase 5 (Knowledge) ◄────────────────────┘
    │                   uses context & map
    ▼
Phase 6 (Generation & Validation)
    │
    ▼
Phase 7 (Skills) ──── can start after Phase 1
```

---

## Quick Start (Week 1)

1. Create module directory structure
2. Create `ssis.yaml` technology profile
3. Create `MigrationFamily` with 7 phases
4. Add `project_type` column to projects table
5. Wire up module router in `main.py`

---

## Frontend Dependencies (Phase 4)

Install React Flow for Migration Map visualization:

```bash
cd packages/web
npm install reactflow @dagrejs/dagre
```

**React Flow** was chosen over D3.js and Cytoscape.js because:
- Native React integration (we use Next.js)
- Built-in drag-and-drop for manual linking
- Dagre plugin for automatic DAG layouts
- Custom node components for packages and tables

---

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Graph visualization | React Flow | Native React, DAG layout, custom nodes |
| Column lineage | Start table-level | Direct mappings first, expressions later |
| Vector DB | pgvector | Same DB, enough for 2000 patterns |
| Validation project | VLI | Real migration, full coverage |

---

## ROI Target

With shared context and knowledge propagation:

| Metric | Without | With | Reduction |
|---|---|---|---|
| Feedback items | 2000 × 30 = 60,000 | ~7,000 | 88% |
| Human time | 60,000 × 5 min = 5,000 hrs | ~570 hrs | 89% |
| Migration duration | 18 months | 6 months | 67% |
