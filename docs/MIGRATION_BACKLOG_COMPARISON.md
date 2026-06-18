# Migration Backlog Comparison: Proposed vs VLI Real-World Project

**Purpose:** Compare the proposed `MigrationFamily` template in Agents Workshop against the actual VLI SSIS-to-Databricks migration project to identify gaps and improvements.

---

## Executive Summary

| Dimension | Agents Workshop (Proposed) | VLI Project (Real) | Gap Assessment |
|---|---|---|---|
| **Phases** | 5 fixed | 7 phases | ⚠️ Missing 2 critical phases |
| **Cards** | ~15-20 typical | 25 cards | ⚠️ Missing specific card types |
| **Skills** | Generic migration | 6 specialized skills | ⚠️ Need domain-specific skills |
| **Human Gates** | ✅ Supported | ✅ Well-defined | ✅ Parity |
| **Master Reference** | ❌ Not proposed | ✅ CORP-900 | ⚠️ Missing consolidation doc |
| **Parallel Run** | ❌ Not in phases | ✅ Phase 7 | 🔴 Critical gap |

---

## Phase Structure Comparison

### Proposed: 5 Phases

```
1. Discovery & Assessment
2. Compatibility Analysis
3. Code Refactoring & Conversion
4. Orchestration Recreation
5. Validation & Cutover
```

### VLI Reality: 7 Phases

```
1. Discovery (4 cards)
2. Foundation (6 cards)        ← NOT IN PROPOSED
3. Silver (4 cards)
4. Gold (2 cards)
5. Soft Deletes (3 cards)
6. Cutover (4 cards)
7. Parallel Run (2 cards)      ← NOT IN PROPOSED
```

### Gap Analysis

| VLI Phase | Maps to Proposed? | Gap |
|---|---|---|
| Phase 1 - Discovery | ✅ → Phase 1 Discovery | OK |
| Phase 2 - Foundation | ⚠️ Partially → Phase 2 Compatibility | Missing: DDL generation, profiling, bronze ingest |
| Phase 3 - Silver | ✅ → Phase 3 Refactoring | OK but too generic |
| Phase 4 - Gold | ✅ → Phase 3 Refactoring | OK but too generic |
| Phase 5 - Soft Deletes | ❌ Not covered | **GAP**: Business rule implementation deserves own phase |
| Phase 6 - Cutover | ✅ → Phase 5 Validation | OK |
| Phase 7 - Parallel Run | ❌ Not covered | **CRITICAL GAP**: No production validation phase |

---

## Card-by-Card Comparison

### VLI Full Card Inventory (25 cards)

#### Phase 1: Discovery (4 cards)
| Card | Description | In Proposed? |
|---|---|---|
| CORP-101: SSIS Package Analyzer | Full 10-section analysis | ⚠️ Implicit, not explicit |
| CORP-102: ETL Business Rule Extractor | Catalog all rules with migration impact | ⚠️ Implicit, not explicit |
| CORP-103: Disabled Task Audit | Classify disabled tasks | ❌ **Missing** |
| CORP-104: Change History Risk Analysis | Analyze annotations/change history | ❌ **Missing** |

#### Phase 2: Foundation (6 cards)
| Card | Description | In Proposed? |
|---|---|---|
| CORP-201: Connectivity Design | JDBC connection mapping | ⚠️ In Compatibility |
| CORP-202: Delta DDL | Generate Bronze/Silver/Gold schemas | ❌ **Missing** |
| CORP-203: Data Quality Profiling Notebook | Pre-migration data quality | ❌ **Missing** |
| CORP-204: Verify Processing Dates | Control table date handling | ❌ **Missing** |
| CORP-205: Ingest Bronze | Raw data landing notebook | ❌ **Missing** |
| CORP-206: Workflow Bundle Skeleton | Databricks workflow YAML | ⚠️ In Orchestration |

#### Phase 3: Silver (4 cards)
| Card | Description | In Proposed? |
|---|---|---|
| CORP-301: Silver Design | Architecture for silver layer | ⚠️ In Refactoring |
| CORP-302-304: Stream notebooks | Per-source-system transformation | ⚠️ Implicit |

#### Phase 4: Gold (2 cards)
| Card | Description | In Proposed? |
|---|---|---|
| CORP-401: Gold Merge Incremental | Delta MERGE upsert logic | ❌ **Missing pattern** |
| CORP-402: Gold Full Reload | DELETE+INSERT pattern | ❌ **Missing pattern** |

#### Phase 5: Soft Deletes (3 cards)
| Card | Description | In Proposed? |
|---|---|---|
| CORP-501: Soft Delete Cancelled VLI | Business rule for VLI cancellations | ❌ **Missing** |
| CORP-502: Soft Delete Cancelled Vale | Business rule for Vale cancellations | ❌ **Missing** |
| CORP-503: Soft Delete Missing Source | Handle missing source rows | ❌ **Missing** |

#### Phase 6: Cutover (4 cards)
| Card | Description | In Proposed? |
|---|---|---|
| CORP-601: Reconciliation Check | Automated data comparison | ✅ In Validation |
| CORP-602: Update Fim Processamento | Control table update | ❌ **Missing** |
| CORP-603: Workflow Bundle Finalize | Validate bundle syntax | ⚠️ Implicit |
| CORP-604: Static Code Analysis | Rule-by-rule comparison | ❌ **Missing** |

#### Phase 7: Parallel Run (2 cards)
| Card | Description | In Proposed? |
|---|---|---|
| CORP-605: Parallel Run Cycle 1 | First production comparison | ❌ **CRITICAL MISSING** |
| CORP-606: Parallel Run Cycle 2 Sign-off | Final validation & go-live | ❌ **CRITICAL MISSING** |

---

## Skills Comparison

### VLI Skills (6 specialized)

| Skill | Purpose | In Proposed? |
|---|---|---|
| `ssis-package-analyzer` | 10-section SSIS analysis | ⚠️ Generic "source-analyzer" |
| `etl-business-rule-extractor` | Catalog migration rules | ❌ **Missing** |
| `delta-merge-designer` | Design MERGE vs reload logic | ❌ **Missing** |
| `workflow-job-builder` | Build Databricks workflows | ❌ **Missing** |
| `databricks-migration-planner` | Medallion architecture design | ⚠️ Generic |
| `etl-migration-reconciler` | Reconciliation & sign-off | ❌ **Missing** |

### Proposed Skills (implicit in template)

- Generic source analyzer
- Compatibility assessor
- Code converter
- Orchestration mapper
- Validation runner

---

## Critical Missing Elements

### 1. 🔴 Parallel Run Phase
**Impact:** Without parallel-run cards, there's no structured approach to validate the migrated pipeline against production SSIS runs.

**VLI Example:**
- CORP-605 runs Databricks in parallel with SSIS
- Compares metrics per (company × month) tuple
- Documents PASS/FAIL with tolerance thresholds
- CORP-606 requires 2 clean cycles for sign-off

**Recommendation:** Add Phase 6: "Parallel Run & Production Validation" with cards:
- `MIGR-601: Parallel Run Cycle 1`
- `MIGR-602: Parallel Run Cycle 2 Sign-off`
- `MIGR-603: Production Cutover Approval`

---

### 2. 🔴 Static Code Analysis Card
**Impact:** No formal rule-by-rule comparison between source and target.

**VLI Example:**
- CORP-701-static-code-analysis.md documents every SSIS rule
- Shows side-by-side: SSIS SQL vs Databricks notebook code
- Classifies each as: MATCHED, INTENTIONAL DIVERGENCE, or FIXED
- Requires human sign-off before parallel run

**Recommendation:** Add card to Phase 5:
- `MIGR-504: Static Code Analysis` with skill `etl-code-comparator`

---

### 3. 🟠 Disabled Task Audit
**Impact:** SSIS packages often have disabled tasks that may be dead code, superseded logic, or accidentally disabled. Without explicit audit, migration may miss required functionality.

**VLI Example:**
- CORP-103 audits all 4 disabled tasks
- Classifies each: SUPERSEDED, DEAD CODE, PROCEED, UNKNOWN
- One disabled task (ESQL_Updata_exclusao_logica) was reclassified via CORP-503 amendment

**Recommendation:** Add to Phase 1:
- `MIGR-103: Disabled Task Audit` with decision framework

---

### 4. 🟠 Change History Risk Analysis
**Impact:** SSIS packages contain `AnnotationLayout` blocks with developer notes about past changes. These are critical for understanding evolution and potential risks.

**VLI Example:**
- CORP-104 parses all annotations
- Documents 14 risks with dates, authors, and migration implications
- Feeds into risk register for Phase 7 validation

**Recommendation:** Add to Phase 1:
- `MIGR-104: Change History Risk Analysis`

---

### 5. 🟠 Data Quality Profiling
**Impact:** Without pre-migration profiling, there's no baseline for reconciliation.

**VLI Example:**
- CORP-203 generates a profiling notebook with 7 queries
- Documents row volumes, null percentages, date ranges
- Establishes baselines for reconciliation thresholds

**Recommendation:** Add to Phase 2:
- `MIGR-203: Data Quality Profiling Notebook`

---

### 6. 🟠 Human Actions Guide
**Impact:** VLI has CORP-801 — a single document listing all human-required actions with owners and blockers.

**VLI Example:**
```
H1 — Static code analysis sign-off
H2 — Populate Databricks secrets  
H3 — Confirm cluster sizing
H4 — Tolerance threshold approval
H5 — VAL-003 policy decision
H6 — Parallel run sign-off
```

**Recommendation:** Add as final card in Phase 5:
- `MIGR-505: Human Actions Guide` — consolidates all HITL items

---

### 7. 🟠 Master Reference Document
**Impact:** VLI has CORP-900 — a single authoritative reference that consolidates all decisions, rules, and sign-offs.

**VLI Example:**
- 10+ sections covering scope, ADRs, rules, connectivity
- Links to all source artifacts (CORP-101 through CORP-801)
- Living document updated through parallel run

**Recommendation:** Add as deliverable:
- `MIGR-900: Master Technical Reference` — auto-generated from card outputs

---

## Recommended Phase Structure (Revised)

Based on VLI learnings, recommend **7 phases** for MigrationFamily:

```python
MIGRATION_PHASES = [
    {
        "code": "phase-1-discovery",
        "name": "Discovery & Assessment",
        "order_no": 1,
        "typical_cards": [
            "ssis-package-analyzer",      # CORP-101
            "business-rule-extractor",    # CORP-102
            "disabled-task-audit",        # CORP-103 ← NEW
            "change-history-risks"        # CORP-104 ← NEW
        ]
    },
    {
        "code": "phase-2-foundation",      # ← NEW PHASE
        "name": "Infrastructure Foundation",
        "order_no": 2,
        "typical_cards": [
            "connectivity-design",        # CORP-201
            "delta-ddl-generation",       # CORP-202 ← NEW
            "data-quality-profiling",     # CORP-203 ← NEW
            "control-table-handling",     # CORP-204 ← NEW
            "bronze-ingest-notebook",     # CORP-205 ← NEW
            "workflow-skeleton"           # CORP-206
        ]
    },
    {
        "code": "phase-3-transformation",
        "name": "Data Transformation (Silver)",
        "order_no": 3,
        "typical_cards": [
            "silver-layer-design",        # CORP-301
            "source-stream-notebooks"     # CORP-302-304
        ]
    },
    {
        "code": "phase-4-aggregation",
        "name": "Data Aggregation (Gold)",
        "order_no": 4,
        "typical_cards": [
            "gold-merge-incremental",     # CORP-401 ← NEW
            "gold-full-reload",           # CORP-402 ← NEW
            "soft-delete-rules"           # CORP-501-503 ← NEW
        ]
    },
    {
        "code": "phase-5-cutover-prep",
        "name": "Cutover Preparation",
        "order_no": 5,
        "typical_cards": [
            "reconciliation-notebook",    # CORP-601
            "control-table-update",       # CORP-602 ← NEW
            "workflow-bundle-finalize",   # CORP-603
            "static-code-analysis",       # CORP-604 ← NEW
            "human-actions-guide"         # CORP-801 ← NEW
        ]
    },
    {
        "code": "phase-6-parallel-run",    # ← NEW PHASE
        "name": "Parallel Run & Validation",
        "order_no": 6,
        "typical_cards": [
            "parallel-run-cycle-1",       # CORP-605 ← NEW
            "parallel-run-cycle-2",       # CORP-606 ← NEW
            "production-sign-off"
        ]
    },
    {
        "code": "phase-7-go-live",
        "name": "Go-Live & Handover",
        "order_no": 7,
        "typical_cards": [
            "master-reference-doc",       # CORP-900 ← NEW
            "runbook-documentation",
            "ssis-retirement"
        ]
    }
]
```

---

## New Skills to Add

| Skill | Description | Based on VLI |
|---|---|---|
| `etl-business-rule-extractor` | Extract and catalog business rules with migration impact | CORP-102 |
| `disabled-task-auditor` | Classify disabled tasks with decision framework | CORP-103 |
| `change-history-analyzer` | Parse annotations and build risk register | CORP-104 |
| `delta-ddl-generator` | Generate Bronze/Silver/Gold DDL from analysis | CORP-202 |
| `data-quality-profiler` | Generate profiling notebook with baselines | CORP-203 |
| `delta-merge-designer` | Design MERGE vs reload patterns | CORP-401/402 |
| `workflow-job-builder` | Build Databricks workflow YAML | CORP-206/603 |
| `etl-migration-reconciler` | Reconciliation queries and sign-off evidence | CORP-601/605 |
| `business-rules-compliance-analyzer` | Rule-by-rule source vs target comparison | CORP-701 |

---

## Skill Definition: business-rules-compliance-analyzer

This skill is missing from VLI (CORP-701 is ad-hoc) and should be a **pre-built, reusable skill** for static code analysis.

### SKILL.md Template

```markdown
---
name: business-rules-compliance-analyzer
description: >
  Compare source ETL business rules against target implementation code.
  Produces a structured compliance report with verdicts for each rule.
  Use when validating that migrated code faithfully implements all
  documented business rules. Supports SSIS→Databricks, Airflow→Databricks,
  and other migration patterns.
---

# Business Rules Compliance Analyzer

## Purpose

After business rules are extracted (via `etl-business-rule-extractor`)
and target code is written, this skill validates that every rule is
correctly implemented. It produces evidence for human sign-off.

## Inputs Required

1. **Rule Catalog** — from discovery phase (e.g., `discovery/CORP-102-rule-catalog.md`)
   - Each rule has: ID, description, source implementation, expected behavior
   
2. **Target Code** — notebooks or scripts implementing the migration
   - For Databricks: `databricks/notebooks/**/*.py`
   - For Airflow: `dags/**/*.py`
   
3. **Tolerance Thresholds** (optional) — for numeric comparisons
   - e.g., "row counts may differ by ≤0.1%"

## Output Structure

Produce a markdown report with:

### Section 1 — Summary

| Metric | Value |
|---|---|
| Total rules analyzed | N |
| MATCHED | N |
| INTENTIONAL DIVERGENCE | N |
| FIXED (improvement) | N |
| OPEN GAP | N |

### Section 2 — Rule-by-Rule Comparison

For each rule in the catalog:

#### RULE-001: [Rule Name]

| Aspect | Source (SSIS) | Target (Databricks) |
|---|---|---|
| **Location** | `ESQL_TaskName` | `03_silver_vli.py` Cell 5 |
| **Logic** | `WHERE dt_operacao >= @dt_inicio` | `WHERE dt_operacao >= processing_start` |
| **Verdict** | — | ✅ MATCHED |

If INTENTIONAL DIVERGENCE:
- **Reason:** [explain why target differs]
- **Approved by:** [owner name, date]

If FIXED:
- **Bug in source:** [describe]
- **Fix in target:** [describe]

If OPEN GAP:
- **Missing:** [what's not implemented]
- **Blocker:** YES/NO
- **Owner:** [who will resolve]

### Section 3 — Cross-Cutting Concerns

Check these patterns across ALL rules:

| Pattern | Source Behavior | Target Behavior | Status |
|---|---|---|---|
| NULL handling | ISNULL(x, '') | COALESCE(x, '') | ✅ Equivalent |
| Date truncation | CONVERT(DATE, x) | TO_DATE(x) | ✅ Equivalent |
| String case | Mixed case | UPPER(TRIM(x)) | ⚠️ INTENTIONAL: normalize |
| Timezone | Server local | UTC | ⚠️ INTENTIONAL: standardize |

### Section 4 — Sign-off Checklist

Before proceeding to parallel run:

- [ ] All OPEN GAP items resolved or accepted
- [ ] All INTENTIONAL DIVERGENCE items approved by business owner
- [ ] All FIXED items documented with bug reference
- [ ] Engineering lead sign-off: _____________ Date: _______
- [ ] Business SME sign-off: _____________ Date: _______

## Verdict Classification

| Verdict | Meaning | Blocks Parallel Run? |
|---|---|---|
| ✅ MATCHED | Source and target implement same logic | No |
| ⚠️ INTENTIONAL DIVERGENCE | Target differs intentionally (approved) | No (if approved) |
| 🔧 FIXED | Target fixes a bug in source | No |
| ❌ OPEN GAP | Target missing or incorrect | **YES** |

## Comparison Techniques

### For SQL-based rules:
1. Normalize both SQL (remove whitespace, standardize aliases)
2. Compare WHERE clauses semantically
3. Compare JOIN conditions
4. Compare aggregation logic

### For business logic rules:
1. Trace data flow from source to target
2. Verify same columns participate
3. Verify same conditions apply
4. Verify same output produced

### For control flow rules:
1. Map SSIS precedence constraints to Databricks task dependencies
2. Verify error handling paths match
3. Verify retry/timeout behavior

## Example Output

```markdown
# CORP-701 — Static Code Analysis Report
## CORP_fdCargasDescargasVagoes Migration

### Summary
| Metric | Value |
|---|---|
| Total rules | 34 |
| MATCHED | 29 |
| INTENTIONAL DIVERGENCE | 3 |
| FIXED | 2 |
| OPEN GAP | 0 |

### Rule Comparison

#### RULE-CDV-001: Cross-operator deduplication (±7 hours)

| Aspect | SSIS | Databricks |
|---|---|---|
| Location | ESQL_Remove_Duplicatas | 03_silver_vale.py Cell 8 |
| Logic | `DATEDIFF(HOUR, vli.dt, vale.dt) BETWEEN -7 AND 7` | `ABS(unix_timestamp(vli.dt) - unix_timestamp(vale.dt)) <= 25200` |
| Verdict | ✅ MATCHED | 25200 seconds = 7 hours |

#### RULE-CDV-015: String normalization

| Aspect | SSIS | Databricks |
|---|---|---|
| Location | (none) | 02_bronze_ingest.py Cell 3 |
| Logic | Raw values passed through | `UPPER(TRIM(column))` |
| Verdict | ⚠️ INTENTIONAL DIVERGENCE |

**Reason:** Source data has inconsistent casing causing downstream join failures.
Normalizing at Bronze layer prevents data quality issues.
**Approved by:** J. Silva, 2026-04-15
```

## Resources

This skill should include these resource files:

### resources/verdict-decision-tree.md
```
Is the logic identical?
  YES → MATCHED
  NO → Is the difference approved?
    YES → Was it fixing a bug?
      YES → FIXED
      NO → INTENTIONAL DIVERGENCE
    NO → Is it a known gap?
      YES → OPEN GAP (assign owner)
      NO → Investigate further
```

### resources/sql-normalization-rules.md
```
Before comparing SQL:
1. Remove comments
2. Normalize whitespace
3. Uppercase keywords
4. Expand aliases to full names
5. Order columns alphabetically in SELECT
6. Standardize date functions (CONVERT → CAST)
```

### resources/sign-off-template.md
```
## Static Code Analysis Sign-off

**Migration:** [package name]
**Analysis Date:** [date]
**Analyst:** [name]

### Certification

I certify that:
- [ ] All 34 business rules have been analyzed
- [ ] 0 OPEN GAP items remain
- [ ] All INTENTIONAL DIVERGENCE items have business approval
- [ ] All FIXED items have been documented

**Engineering Lead:** _________________ Date: _______
**Business Owner:** _________________ Date: _______
```
```

---

## Automation Level Recommendations

Based on VLI experience:

| Card Type | Recommended Level | Rationale |
|---|---|---|
| SSIS Package Analysis | `auto` | Deterministic XML parsing |
| Business Rule Extraction | `auto_hitl` | LLM identifies, human validates |
| Disabled Task Audit | `auto_hitl` | Classification needs human judgment |
| Connectivity Design | `hitl` | Requires environment knowledge |
| DDL Generation | `auto` | Derivable from analysis |
| Profiling Notebook | `auto` | Template-based generation |
| Silver/Gold Notebooks | `auto_hitl` | Complex business logic |
| Business Rules Compliance | `auto_hitl` | AI compares, human approves verdicts |
| Parallel Run | `hitl` | Requires production access |
| Sign-off | `hitl` | Human decision |

---

## Summary: Top 5 Action Items

1. **Add Phase 6: Parallel Run** — Critical for production validation
2. **Add Disabled Task Audit card** — Essential for SSIS migrations
3. **Add Static Code Analysis card** — Required for rule-by-rule sign-off
4. **Add Data Quality Profiling card** — Establishes reconciliation baselines
5. **Add Master Reference deliverable** — Consolidates all decisions

---

## Appendix: VLI File Structure Reference

```
VLI-ssis-databricks-migration/
├── AGENTS.md                      # Global agent rules
├── .agents/
│   ├── jira-cards/
│   │   ├── phase-1-discovery/     # 4 cards
│   │   ├── phase-2-foundation/    # 6 cards
│   │   ├── phase-3-silver/        # 4 cards
│   │   ├── phase-4-gold/          # 2 cards
│   │   ├── phase-5-soft-deletes/  # 3 cards
│   │   ├── phase-6-cutover/       # 4 cards
│   │   └── phase-7-parallel-run/  # 2 cards
│   └── skills/
│       ├── ssis-package-analyzer/
│       ├── etl-business-rule-extractor/
│       ├── delta-merge-designer/
│       ├── workflow-job-builder/
│       ├── databricks-migration-planner/
│       └── etl-migration-reconciler/
├── databricks/
│   ├── notebooks/                 # Migration notebooks
│   ├── schemas/                   # DDL files
│   └── workflows/                 # Workflow YAML
├── discovery/                     # Card outputs
│   ├── CORP-101-ssis-analysis.md
│   ├── CORP-102-rule-catalog.md
│   ├── ...
│   ├── CORP-900-master-reference.md
│   └── canvas/                    # HTML visualizations
├── legacy/
│   └── ssis/                      # Source .dtsx files
└── tests/
    └── test_harness_local.py      # Reconciliation harness
```
