# Large-Scale SSIS Migration: Shared Context Architecture

**Date**: 2026-05-15  
**Use Case**: Migrating ~2,000 SSIS packages for a client  
**Problem**: Knowledge discovered in Package N should automatically apply to Packages N+1 through 2000

---

## 1. The Challenge

When migrating 2,000 packages one-by-one:

| Issue | Impact |
|-------|--------|
| Same connection asked 500 times | "What's the auth for OLEDB_DW_Corporativo?" |
| Same business rule rediscovered | "Why does MRS win tie-breaks?" answered per package |
| Same pattern reimplemented | DELETE+INSERT → MERGE converted individually |
| No learning curve | Package 2000 takes as long as Package 1 |
| No batch operations | Can't say "these 50 packages are identical patterns" |

---

## 2. Solution: Shared Migration Context

### 2.1 Project-Level vs Package-Level

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PROJECT: "Client XYZ SSIS Migration"                                       │
│  └── 2,000 packages                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PROJECT-LEVEL CONTEXT (shared across all packages)                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ • Connection Registry (20 unique connections used by many packages)     ││
│  │ • Business Rule Catalog (50 rules shared across packages)               ││
│  │ • Pattern Library (15 common transformation patterns)                   ││
│  │ • Resolved Decisions (100 decisions that apply to multiple packages)   ││
│  │ • Naming Conventions (how legacy names map to modern names)             ││
│  │ • SME Contact List (who to ask for which type of question)              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│  PACKAGE-LEVEL CONTEXT (specific to one package)                            │
│  ┌───────┐ ┌───────┐ ┌───────┐                                             │
│  │PKG 1  │ │PKG 2  │ │PKG 3  │ ...                                         │
│  │       │ │       │ │       │                                             │
│  │• Uses │ │• Uses │ │• Uses │                                             │
│  │  shared│ │  shared│ │  shared│                                         │
│  │  conn  │ │  conn  │ │  conn  │                                          │
│  │• Local│ │• Local│ │• Local│                                             │
│  │  vars  │ │  vars  │ │  vars  │                                          │
│  └───────┘ └───────┘ └───────┘                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 How Knowledge Propagates

```
Package 1 (first to use Connection X):
  ┌────────────────────────────────────────────────┐
  │ Analysis finds: OLEDB_DW_Corporativo           │
  │ Feedback Item: "Auth method? Server? Database?"│
  │ Human resolves: Windows Auth, SRVDW01, DW_Corp │
  └───────────────────────┬────────────────────────┘
                          │
                          ▼ SAVED TO PROJECT CONTEXT
  ┌────────────────────────────────────────────────┐
  │ Connection Registry Entry:                      │
  │   name: OLEDB_DW_Corporativo                   │
  │   server: SRVDW01                              │
  │   database: DW_Corp                            │
  │   auth: windows_auth                           │
  │   databricks_target: catalog.bronze.dw_corp   │
  │   used_by_packages: [PKG_001, ...]             │
  └────────────────────────────────────────────────┘

Package 2-500 (also use Connection X):
  ┌────────────────────────────────────────────────┐
  │ Analysis finds: OLEDB_DW_Corporativo           │
  │ → LOOKUP: Found in Connection Registry!        │
  │ → NO FEEDBACK NEEDED                           │
  │ → Auto-apply: databricks_target = ...          │
  └────────────────────────────────────────────────┘
```

---

## 3. Schema Design

### 3.1 Core Tables for Shared Context

```sql
-- Connection Registry (project-level, shared across packages)
CREATE TABLE migration_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Identity (from SSIS)
    connection_name TEXT NOT NULL,           -- "OLEDB_DW_Corporativo"
    connection_type TEXT NOT NULL,           -- oledb | flatfile | ftp | etc.
    
    -- Source details (resolved by human)
    source_server TEXT,
    source_database TEXT,
    source_schema TEXT DEFAULT 'dbo',
    auth_method TEXT,                        -- windows_auth | sql_auth | etc.
    credential_reference TEXT,               -- Pointer to secrets manager
    
    -- Target mapping (Databricks)
    target_catalog TEXT,
    target_schema TEXT,
    target_format TEXT DEFAULT 'delta',
    network_requirements TEXT,               -- VPN, private endpoint, etc.
    
    -- Usage tracking
    used_by_package_count INTEGER DEFAULT 0,
    
    -- Audit
    discovered_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    resolved_by_user_id UUID REFERENCES users(id),
    
    UNIQUE (project_id, connection_name)
);

-- Track which packages use which connections
CREATE TABLE package_connection_usage (
    package_id UUID REFERENCES etl_packages(id) ON DELETE CASCADE,
    connection_id UUID REFERENCES migration_connections(id) ON DELETE CASCADE,
    direction TEXT NOT NULL,                 -- source | target | control
    tables_accessed TEXT[],
    PRIMARY KEY (package_id, connection_id)
);

-- Business Rule Catalog (project-level, shared)
CREATE TABLE migration_business_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Identity
    rule_code TEXT NOT NULL,                 -- "BR-001"
    rule_name TEXT NOT NULL,                 -- "7-Hour Deduplication"
    
    -- Description
    description TEXT NOT NULL,               -- Full explanation
    implementation_pattern TEXT,             -- SQL pattern, code snippet
    
    -- Source (where discovered)
    discovered_in_package_id UUID REFERENCES etl_packages(id),
    source_location TEXT,                    -- "ESQL_Dedup, line 45"
    
    -- Resolution
    status TEXT DEFAULT 'discovered',        -- discovered | confirmed | deprecated
    confirmed_by_user_id UUID REFERENCES users(id),
    confirmed_at TIMESTAMPTZ,
    sme_contact TEXT,                        -- Who confirmed this
    
    -- Applicability
    applies_to_packages TEXT[],              -- Package names/patterns
    applies_to_domains TEXT[],               -- "weighing", "billing", etc.
    
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE (project_id, rule_code)
);

-- Pattern Library (transformation patterns)
CREATE TABLE migration_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Identity
    pattern_code TEXT NOT NULL,              -- "PAT-001"
    pattern_name TEXT NOT NULL,              -- "DELETE-INSERT to MERGE"
    
    -- Description
    description TEXT NOT NULL,
    
    -- Source pattern (SSIS)
    source_technology TEXT NOT NULL,         -- "ssis" | "airflow" | "talend"
    source_component TEXT,                   -- "Execute SQL Task"
    source_pattern_signature TEXT,           -- How to detect this pattern
    source_example TEXT,                     -- Example from real package
    
    -- Target pattern (Databricks)
    target_implementation TEXT,              -- Code template
    target_example TEXT,
    
    -- Usage
    times_applied INTEGER DEFAULT 0,
    packages_using TEXT[],
    
    -- Audit
    discovered_at TIMESTAMPTZ DEFAULT now(),
    verified BOOLEAN DEFAULT false,
    
    UNIQUE (project_id, pattern_code)
);

-- Resolved Decisions (answers to feedback items that apply to multiple packages)
CREATE TABLE migration_resolved_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Decision identity
    decision_code TEXT NOT NULL,             -- "DEC-001"
    topic TEXT NOT NULL,                     -- "MRS vs VALE tie-breaker"
    
    -- The decision
    decision TEXT NOT NULL,                  -- "MRS wins ties per business policy"
    rationale TEXT,                          -- Why this decision was made
    documentation_link TEXT,                 -- Link to email, meeting notes, etc.
    
    -- Applicability
    applies_to_pattern TEXT,                 -- Regex or LIKE pattern for package names
    applies_to_rule_code TEXT,               -- Links to business rule
    applies_to_connection TEXT,              -- Links to connection
    
    -- Who decided
    decided_by TEXT NOT NULL,                -- Name or role
    decided_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE (project_id, decision_code)
);

-- Package Registry (2,000 packages with status)
CREATE TABLE etl_packages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Identity
    package_name TEXT NOT NULL,              -- "PKG_FatoPesagem_Full"
    package_path TEXT,                       -- Original location in SSISDB
    artifact_id UUID REFERENCES project_artifacts(id),  -- Uploaded .dtsx
    
    -- Classification
    domain TEXT,                             -- "weighing", "billing", "inventory"
    subdomain TEXT,
    complexity TEXT DEFAULT 'medium',        -- simple | medium | complex | critical
    migration_wave INTEGER,                  -- 1, 2, 3... for batching
    
    -- Scheduling
    original_schedule TEXT,                  -- "daily 2am", "hourly", etc.
    target_schedule TEXT,
    
    -- Status
    status TEXT DEFAULT 'registered',
    -- registered | analyzing | analyzed | needs_feedback | ready | 
    -- migrating | migrated | verified | deprecated
    
    -- Progress tracking
    analysis_id UUID REFERENCES artifact_analyses(id),
    pending_feedback_count INTEGER DEFAULT 0,
    blocking_feedback_count INTEGER DEFAULT 0,
    
    -- Dependencies
    depends_on_packages TEXT[],              -- Package names this depends on
    triggers_packages TEXT[],                -- Packages triggered after this
    
    -- Metrics
    original_avg_duration_minutes INTEGER,
    original_row_count BIGINT,
    estimated_effort_hours NUMERIC(5,1),
    
    -- Audit
    registered_at TIMESTAMPTZ DEFAULT now(),
    analyzed_at TIMESTAMPTZ,
    migrated_at TIMESTAMPTZ,
    verified_at TIMESTAMPTZ,
    
    UNIQUE (project_id, package_name)
);

-- Package Similarity Clustering
CREATE TABLE package_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    
    cluster_name TEXT NOT NULL,              -- "Full-reload fact tables"
    description TEXT,
    
    -- Clustering criteria
    pattern_signature TEXT,                  -- What makes packages similar
    
    -- Members
    package_count INTEGER DEFAULT 0,
    
    -- Status
    cluster_status TEXT DEFAULT 'identified',  -- identified | template_ready | batch_migrated
    template_package_id UUID REFERENCES etl_packages(id),  -- The "golden" example
    
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE package_cluster_members (
    cluster_id UUID REFERENCES package_clusters(id) ON DELETE CASCADE,
    package_id UUID REFERENCES etl_packages(id) ON DELETE CASCADE,
    similarity_score NUMERIC(3,2),           -- 0.00 - 1.00
    PRIMARY KEY (cluster_id, package_id)
);
```

### 3.2 Indexes for Performance

```sql
-- Fast lookups for connection reuse
CREATE INDEX ix_migration_connections_name 
    ON migration_connections(project_id, connection_name);

-- Fast status filtering for dashboards
CREATE INDEX ix_etl_packages_status 
    ON etl_packages(project_id, status);

-- Fast wave filtering for batch operations
CREATE INDEX ix_etl_packages_wave 
    ON etl_packages(project_id, migration_wave);

-- Fast domain filtering
CREATE INDEX ix_etl_packages_domain 
    ON etl_packages(project_id, domain);
```

---

## 4. Knowledge Propagation Workflow

### 4.1 First Package in Cluster (Template Package)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PACKAGE: PKG_FatoPesagem_Full (First in "Full-reload fact tables" cluster) │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. ANALYZE                                                                 │
│     - Extract tasks, variables, connections, SQL                            │
│     - Identify patterns: "DELETE + INSERT into staging"                     │
│     - Identify business rules: "7-hour dedup"                               │
│                                                                             │
│  2. DISCOVER CONNECTIONS                                                    │
│     - OLEDB_DW_Corporativo → NEW, needs resolution                         │
│     - OLEDB_Staging → NEW, needs resolution                                │
│     → Create migration_connections entries (status: pending)                │
│                                                                             │
│  3. DISCOVER PATTERNS                                                       │
│     - DELETE+INSERT → Create migration_patterns entry                       │
│     → PAT-001: "DELETE-INSERT to MERGE"                                    │
│                                                                             │
│  4. GENERATE FEEDBACK                                                       │
│     - Connection auth for OLEDB_DW_Corporativo?                            │
│     - Tie-breaker rule: why MRS wins?                                      │
│                                                                             │
│  5. HUMAN RESOLVES                                                          │
│     - Connection: Windows Auth, SRVDW01, DW_Corp                           │
│       → UPDATE migration_connections SET resolved_at = now()               │
│     - Tie-breaker: Business policy per João Silva (2023)                   │
│       → CREATE migration_resolved_decisions                                 │
│                                                                             │
│  6. MARK AS TEMPLATE                                                        │
│     - Set as template_package_id for cluster                               │
│     - All similar packages will inherit these decisions                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Subsequent Packages (Inherit Context)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PACKAGE: PKG_FatoPesagem_Incremental (Same cluster, analyzed later)        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. ANALYZE                                                                 │
│     - Extract tasks, variables, connections, SQL                            │
│                                                                             │
│  2. CONNECTION LOOKUP                                                       │
│     - OLEDB_DW_Corporativo → FOUND in registry! (resolved)                 │
│     - OLEDB_Staging → FOUND in registry! (resolved)                        │
│     → NO FEEDBACK NEEDED for connections                                    │
│                                                                             │
│  3. PATTERN LOOKUP                                                          │
│     - DELETE+INSERT → FOUND as PAT-001                                     │
│     → Auto-suggest MERGE implementation                                     │
│                                                                             │
│  4. DECISION LOOKUP                                                         │
│     - 7-hour dedup → FOUND as DEC-001                                      │
│     → Apply same resolution (MRS wins)                                      │
│                                                                             │
│  5. GENERATE FEEDBACK (only NEW items)                                      │
│     - Incremental filter: DT_ALTERACAO or DT_MODIFICACAO?                  │
│       (This is new - not in template package)                               │
│                                                                             │
│  6. ANALYSIS SUMMARY                                                        │
│     "This package shares 80% of its patterns with PKG_FatoPesagem_Full.    │
│      Only 1 new decision needed."                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. UI: Migration Dashboard

### 5.1 Project Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Client XYZ SSIS Migration — 2,000 Packages                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PROGRESS                                                                   │
│  ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░  500/2000 (25%)                  │
│                                                                             │
│  BY STATUS                                                                  │
│  ┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐ │
│  │ Registered      │ Analyzed        │ Needs Feedback  │ Migrated        │ │
│  │ 1,200           │ 300             │ 50              │ 450             │ │
│  └─────────────────┴─────────────────┴─────────────────┴─────────────────┘ │
│                                                                             │
│  BY WAVE                                                                    │
│  Wave 1 (Simple):   200 packages  ████████████████████  100% migrated      │
│  Wave 2 (Medium):   500 packages  ████████████░░░░░░░░   60% migrated      │
│  Wave 3 (Complex):  800 packages  ███░░░░░░░░░░░░░░░░░   15% migrated      │
│  Wave 4 (Critical): 500 packages  ░░░░░░░░░░░░░░░░░░░░    0% migrated      │
│                                                                             │
│  SHARED CONTEXT                                                             │
│  • 42 connections registered (38 resolved, 4 pending)                       │
│  • 67 business rules catalogued                                             │
│  • 23 transformation patterns identified                                    │
│  • 156 decisions resolved (applicable to 1,800 packages)                   │
│                                                                             │
│  CLUSTERS                                                                   │
│  • "Full-reload fact tables": 150 packages (template ready)                │
│  • "Incremental dimension loads": 200 packages (template ready)            │
│  • "Staging ETL": 300 packages (analyzing)                                 │
│  • Unclustered: 1,350 packages                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Pending Feedback (Aggregated)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PENDING DECISIONS (Apply to Multiple Packages)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  🔴 CRITICAL (Blocks 200 packages)                                          │
│  ├─ Connection: OLEDB_LEGACY_SYSTEM (auth unknown)                         │
│  │  Affects: PKG_001, PKG_002, PKG_003, ... +197 more                      │
│  │  [Resolve]                                                               │
│  │                                                                          │
│  └─ Business Rule: Soft-delete semantics for archived records              │
│     Affects: PKG_100, PKG_101, PKG_102, ... +50 more                       │
│     [Resolve]                                                               │
│                                                                             │
│  🟠 HIGH (Blocks 50 packages)                                               │
│  ├─ Pattern: EXECUTE SQL Task with dynamic SQL generation                  │
│  │  Affects: PKG_500, PKG_501, PKG_502, ... +30 more                       │
│  │  [Resolve]                                                               │
│  │                                                                          │
│  └─ Connection: FTP_VENDOR_FEED (network path unknown)                     │
│     Affects: PKG_800, PKG_801, PKG_802, ... +15 more                       │
│     [Resolve]                                                               │
│                                                                             │
│  🟡 MEDIUM (Blocks 20 packages)                                             │
│  └─ ...                                                                     │
│                                                                             │
│  [Resolve All Critical] [Export Pending to Excel]                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Batch Operations

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BATCH OPERATIONS                                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ANALYZE BATCH                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ Select packages to analyze:                                             ││
│  │ ○ All registered (1,200 packages)                                       ││
│  │ ● By domain: [Weighing ▾] (300 packages)                               ││
│  │ ○ By wave: [Wave 2 ▾]                                                  ││
│  │ ○ By cluster: [Full-reload fact tables ▾]                              ││
│  │                                                                         ││
│  │ [Start Batch Analysis] (Est. 2 hours for 300 packages)                 ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│  APPLY TEMPLATE                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ Template package: [PKG_FatoPesagem_Full ▾]                             ││
│  │ Apply to cluster: [Full-reload fact tables] (150 packages)              ││
│  │                                                                         ││
│  │ Will auto-resolve:                                                      ││
│  │ • 3 connections (already resolved in template)                          ││
│  │ • 5 business rules (same as template)                                   ││
│  │ • 2 transformation patterns                                             ││
│  │                                                                         ││
│  │ [Apply Template to Cluster]                                             ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. API Endpoints for Batch Operations

```python
# Batch analyze packages
@router.post("/projects/{project_id}/packages/analyze-batch")
async def analyze_batch(
    project_id: UUID,
    filter: PackageFilter,  # domain, wave, cluster, status
    max_concurrent: int = 10,
):
    """Enqueue batch analysis for filtered packages."""
    packages = await get_packages(project_id, filter)
    for pkg in packages:
        analyze_artifact.send(str(pkg.artifact_id))
    return {"queued": len(packages)}

# Apply template to cluster
@router.post("/projects/{project_id}/clusters/{cluster_id}/apply-template")
async def apply_template(
    project_id: UUID,
    cluster_id: UUID,
):
    """Apply template package's resolved decisions to all cluster members."""
    cluster = await get_cluster(cluster_id)
    template = await get_package(cluster.template_package_id)
    
    # Get resolved items from template
    connections = await get_package_connections(template.id)
    rules = await get_package_rules(template.id)
    decisions = await get_package_decisions(template.id)
    
    # Apply to all cluster members
    members = await get_cluster_members(cluster_id)
    for member in members:
        await apply_resolutions(member.package_id, connections, rules, decisions)
    
    return {"applied_to": len(members)}

# Get aggregated pending feedback (across packages)
@router.get("/projects/{project_id}/feedback/aggregated")
async def get_aggregated_feedback(project_id: UUID):
    """Get feedback items grouped by topic, showing affected package count."""
    return await aggregate_feedback_by_topic(project_id)

# Resolve feedback with propagation
@router.post("/projects/{project_id}/feedback/{topic}/resolve-all")
async def resolve_feedback_with_propagation(
    project_id: UUID,
    topic: str,
    resolution: FeedbackResolution,
):
    """Resolve a feedback item and apply to all packages with same question."""
    # Create resolved decision
    decision = await create_resolved_decision(project_id, topic, resolution)
    
    # Find all packages with same feedback topic
    packages = await find_packages_with_feedback(project_id, topic)
    
    # Mark feedback as resolved in all packages
    for pkg in packages:
        await apply_decision_to_package(pkg.id, decision)
    
    return {"resolved_for_packages": len(packages)}
```

---

## 7. Analysis Prompt Enhancement

When analyzing Package N, include shared context:

```python
def build_analysis_prompt(package: EtlPackage, project_context: SharedMigrationContext):
    """Build analysis prompt with shared context."""
    
    prompt_parts = [
        f"# Analyzing Package: {package.package_name}",
        "",
        "## Shared Migration Context",
        "",
        "### Resolved Connections (reuse these, don't ask again)",
    ]
    
    # Include resolved connections
    for conn in project_context.resolved_connections:
        prompt_parts.append(f"- {conn.connection_name}: {conn.source_server}/{conn.source_database}")
        prompt_parts.append(f"  → Databricks: {conn.target_catalog}.{conn.target_schema}")
    
    prompt_parts.append("")
    prompt_parts.append("### Confirmed Business Rules (apply these)")
    
    # Include confirmed rules
    for rule in project_context.confirmed_rules:
        prompt_parts.append(f"- {rule.rule_code}: {rule.rule_name}")
        prompt_parts.append(f"  {rule.description}")
    
    prompt_parts.append("")
    prompt_parts.append("### Resolved Decisions (don't re-ask these)")
    
    # Include resolved decisions
    for decision in project_context.resolved_decisions:
        prompt_parts.append(f"- {decision.topic}: {decision.decision}")
    
    prompt_parts.append("")
    prompt_parts.append("### Package Content")
    prompt_parts.append(package.content_md)
    
    prompt_parts.append("")
    prompt_parts.append("## Instructions")
    prompt_parts.append("""
Analyze this package. For any connection, rule, or decision that matches 
the shared context above, REUSE the existing resolution. Only create 
feedback items for NEW issues not already resolved at the project level.
""")
    
    return "\n".join(prompt_parts)
```

---

## 8. Key Benefits

| Without Shared Context | With Shared Context |
|------------------------|---------------------|
| 2,000 × "What's OLEDB_DW auth?" | 1 × resolved, 1,999 × inherited |
| 2,000 × "What's tie-breaker?" | 1 × resolved, applies to 500 |
| Each package analyzed in isolation | Clusters batch-migrate together |
| Learning curve flat | Accelerates: Package 100 takes 10% of Package 1 time |
| 10,000 feedback items | ~500 unique feedback items |

---

## 9. Implementation Phases

### Phase 1: Package Registry (Week 1)
- [ ] `etl_packages` table and API
- [ ] Bulk import from SSISDB or folder scan
- [ ] Basic status tracking

### Phase 2: Connection Registry (Week 2)
- [ ] `migration_connections` table and API
- [ ] Auto-extract connections during analysis
- [ ] Connection reuse lookup in analysis prompt

### Phase 3: Business Rules & Decisions (Week 3)
- [ ] `migration_business_rules` table
- [ ] `migration_resolved_decisions` table
- [ ] Propagation to subsequent packages

### Phase 4: Pattern Library (Week 4)
- [ ] `migration_patterns` table
- [ ] Pattern detection in analysis
- [ ] Pattern suggestion in cards

### Phase 5: Clustering & Batch Ops (Week 5-6)
- [ ] `package_clusters` tables
- [ ] Similarity clustering algorithm
- [ ] Template application UI
- [ ] Batch analysis operations

---

## 10. Summary

For a 2,000-package migration, you need:

1. **Package Registry** — Track all packages with status, domain, wave
2. **Connection Registry** — Resolve once, apply everywhere
3. **Business Rule Catalog** — Document rules across packages
4. **Resolved Decisions** — Apply answers to similar questions
5. **Pattern Library** — Reusable transformation templates
6. **Clustering** — Group similar packages for batch processing
7. **Enhanced Analysis Prompt** — Include shared context to avoid re-asking

**The key insight**: Migration knowledge is a **project-level asset**, not a package-level asset. Design the system to accumulate and propagate learning.
