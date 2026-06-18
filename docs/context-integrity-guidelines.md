# Context Integrity Guidelines

> Operational rules for preserving, using, and propagating context in AI-accelerated technology migrations.
> Companion to `context-management-universal.md` (architecture) and `poc-architecture-standards.md` (requirements).

---

## The Problem

Context management architecture answers **where** to store and **how** to inject context. But the real failures in practice are operational:

- A decision approved in step N is forgotten by step N+3 because it was trimmed from the context window
- An agent proposes a migration without knowing a blocking dependency exists
- A wrong pattern from item A silently contaminates the context for item B
- The agent outputs code but can't explain which context led to the decision
- Vector DB goes down and the agent stops functioning entirely

These are **integrity hazards** — they don't come from bad architecture, they come from bad discipline. This document defines 8 rules to prevent them.

---

## Rule 1: No Silent Loss

**Hazard:** Information that was explicitly approved or decided is lost because it was trimmed from the context window, not persisted to the knowledge store, or overwritten by a newer interaction.

**Rule:** If a human approved it, it must be retrievable by the next interaction.

### Checklist

- [ ] Every HITL-approved decision is written to the knowledge store (Postgres) BEFORE the next item starts
- [ ] Write-back is synchronous — the agent does not proceed until persistence is confirmed
- [ ] Trimmed context is summarized, not discarded — summary stored in `learning_notes` on the technology profile
- [ ] The `reflect` step in AgentState explicitly checks: "what did I learn that isn't yet persisted?"
- [ ] On agent restart/crash, the last approved decision is recoverable from the knowledge store

### Anti-Patterns

| Anti-Pattern | What Happens | Fix |
|--------------|-------------|-----|
| **Trim-and-forget** | Context window trimmed, older decisions dropped, never persisted | Write-back before trim; trim only conversation turns, never decisions |
| **Batch write-back** | Decisions accumulated in memory, written at end of session; crash loses all | Write-back after each HITL approval |
| **Override without history** | New decision overwrites old without preserving the old rationale | Append-only decisions table; new decision gets new row with `supersedes` reference |

### Example (Data Domain)

Agent migrates SSIS package `LoadPatients`. Human approves decision: "Map OLE DB source to Unity Catalog using Service Principal." Agent proceeds to next package. If this decision is only in the conversation history and the context window is trimmed before the next interaction, the agent may re-discover the same mapping from scratch — or worse, propose a different mapping (e.g., OAuth) for a similar package, creating inconsistency.

**Correct:** Decision persisted to Postgres immediately after approval. Next interaction's `context_snapshot` includes this decision via `resolved_decisions` query.

---

## Rule 2: No Blind Spots

**Hazard:** Agent proposes a migration action without having the context needed to make a good decision — missing dependency, constraint, or technology-specific knowledge.

**Rule:** No proposal without profile + dependencies + constraints.

### Checklist

- [ ] `context_snapshot` builder validates that required fields are present before returning
- [ ] Required fields per item: `technology_profile`, `dependency_context` (depth >= 1), `constraints`
- [ ] If any required field is missing, agent returns a **context gap** message instead of a proposal
- [ ] Context gap message lists what's missing and suggests how to obtain it
- [ ] Dependency context includes at minimum: direct dependencies (depth=1) and their current status

### Anti-Patterns

| Anti-Pattern | What Happens | Fix |
|--------------|-------------|-----|
| **Propose-on-empty** | Agent generates migration code with only the prompt, no context_snapshot | Mandatory snapshot validation before `act` step |
| **Shallow dependencies** | Only the item itself, not its dependencies; proposes migration that breaks downstream | Minimum dependency depth = 1; depth = 2 for critical items |
| **Missing constraints** | Agent doesn't know about compliance constraint (e.g., PII column) and proposes insecure migration | Constraints always injected from project_manifest + technology_profile |

### Example (App Domain)

Agent proposes migrating EJB `PatientService` to Spring Boot. But `PatientService` depends on `AuditLogEJB` (depth=1) which hasn't been migrated yet. Without dependency context, the agent proposes code that references `AuditLogEJB` — which won't compile in the target environment.

**Correct:** `context_snapshot` includes `dependency_context` showing `AuditLogEJB` with status `discovered`. Agent either: (a) proposes migration for `AuditLogEJB` first, or (b) flags the dependency and asks human for ordering.

---

## Rule 3: No Stale State

**Hazard:** context_snapshot is built once and cached; between interactions, the state of the world changes (dependency fails, constraint is added, item status changes) but the agent operates on outdated information.

**Rule:** Snapshot is always rebuilt, never reused.

### Checklist

- [ ] `context_snapshot` is rebuilt at the START of every `think` step, not cached
- [ ] Rebuild queries live data: Postgres decisions, migration_graph status, Vector DB index
- [ ] Snapshot includes a `built_at` timestamp; agent logs if snapshot age > threshold
- [ ] If a dependency's status changed since last interaction (e.g., `migrating` -> `failed`), the snapshot reflects this
- [ ] No long-lived snapshot objects — snapshot is a value object, not a mutable reference

### Anti-Patterns

| Anti-Pattern | What Happens | Fix |
|--------------|-------------|-----|
| **Cached snapshot** | Snapshot built once at session start, reused for all items | Rebuild per interaction |
| **Stale status** | Dependency shows status `completed` but actually `failed` 5 minutes ago | Query live status from knowledge store |
| **Stale pattern library** | Vector DB index not refreshed after new decisions written | Upsert embeddings immediately after write-back; query fresh index |

### Example (Infra Domain)

Agent is migrating VM `web-app-01` to K8s Deployment. Between interactions, the migration of VM `db-server-01` (a dependency) fails. If the agent uses a cached snapshot, it still sees `db-server-01` as `completed` and proposes a Deployment that references the migrated database — which doesn't exist.

**Correct:** Snapshot rebuilt at start of interaction. `dependency_context` shows `db-server-01` status = `failed`. Agent flags the blocker and does not proceed.

---

## Rule 4: No Noise

**Hazard:** Too much context injected; the agent can't distinguish relevant information from historical noise. The signal-to-noise ratio drops, and the agent makes worse decisions despite having MORE context.

**Rule:** Every token in the snapshot must be justifiable as relevant to the current item.

### Checklist

- [ ] context_snapshot builder is budget-aware: estimates token count and adjusts `top_k` and `depth`
- [ ] Technology profile is loaded only for the current item's `source_tech` — not all profiles
- [ ] Similar patterns limited by relevance (top_k=5 default, reduced if budget tight)
- [ ] Resolved decisions limited to current cluster — not all decisions in the project
- [ ] Dependency context depth limited (default=2, reduced to 1 if budget tight)
- [ ] Cross-domain patterns are opt-in, not default — only injected if item has `cross_domain: true`

### Anti-Patterns

| Anti-Pattern | What Happens | Fix |
|--------------|-------------|-----|
| **Kitchen sink** | All technology profiles, all decisions, all patterns injected | Budget-aware builder; only current item's profile + cluster decisions |
| **Unbounded top_k** | Vector search returns 50 patterns; most irrelevant | top_k=5 default; budget-adjusted |
| **Deep dependency traversal** | depth=5 pulls in half the migration graph | depth=2 default; depth=1 when budget tight |

### Budget-Aware Builder

```python
def build_context_snapshot(item, budget_tokens=4000):
    snapshot = {}
    remaining = budget_tokens

    # Tier 1: Always include (highest priority)
    profile = load_yaml(f"technology_profiles/{item.source_tech}.yaml")
    snapshot["technology_profile"] = profile
    remaining -= estimate_tokens(profile)

    constraints = project_manifest.constraints
    snapshot["constraints"] = constraints
    remaining -= estimate_tokens(constraints)

    # Tier 2: Adjust to budget
    k = min(5, max(1, remaining // 200))
    snapshot["similar_patterns"] = vector_search(
        pattern_library, item.description, top_k=k
    )
    remaining -= k * 200

    # Tier 3: Reduce if budget tight
    depth = 2 if remaining > 500 else 1
    snapshot["dependency_context"] = graph_traverse(
        migration_graph, item.id, depth=depth
    )

    # Tier 4: Fill remaining with cluster decisions
    limit = max(1, remaining // 150)
    snapshot["resolved_decisions"] = sql_query(
        decisions_db, item.cluster_id, limit=limit
    )

    return snapshot
```

---

## Rule 5: No Bad Propagation

**Hazard:** A wrong or suboptimal decision from item A enters the knowledge store and silently influences the context for items B, C, D — propagating error without review.

**Rule:** Every pattern in the snapshot is verified or explicitly marked unverified.

### Checklist

- [ ] All decisions have a `confidence` field: `high` | `medium` | `low`
- [ ] Low-confidence decisions are flagged in the snapshot: agent must mention "this pattern is unverified"
- [ ] Patterns have a `verified` boolean — set to `true` only after human review or eval pass
- [ ] Unverified patterns are retrieved with lower priority (sorted after verified)
- [ ] HITL gate on write-back prevents obviously wrong decisions from entering the store
- [ ] Decisions can be `revoked` — revoked decisions are excluded from future snapshots but preserved for audit

### Anti-Patterns

| Anti-Pattern | What Happens | Fix |
|--------------|-------------|-----|
| **Blind write-back** | Agent decision persisted without human review | HITL gate mandatory for all write-backs |
| **No confidence tracking** | All decisions treated equally; lucky guess treated as expert knowledge | Confidence field on every decision; low-confidence flagged in snapshot |
| **No revocation** | Wrong decision can't be removed; perpetually contaminates context | Revocation mechanism; revoked decisions excluded from snapshots |

### Confidence Scoring

| Scenario | Confidence | Verified |
|----------|-----------|----------|
| Human approved + eval passed | high | true |
| Human approved, no eval yet | medium | false |
| Agent proposed, human not yet reviewed | low | false |
| Pattern generalized from 1 item | low | false |
| Pattern generalized from 3+ items with consistent results | medium | true |

---

## Rule 6: No Black Box

**Hazard:** Agent outputs migration code or decision but can't explain which context led to the proposal. When the output is wrong, there's no way to trace which piece of context caused the error.

**Rule:** Every claim in the output must be traceable to a context source.

### Checklist

- [ ] Agent output includes a `context_used` section listing which snapshot fields contributed
- [ ] Each proposed action cites specific sources: "Based on technology_profile.ssis.data_flow_task" or "Based on resolved_decision #42"
- [ ] When a pattern from the vector DB is used, the original decision ID is referenced
- [ ] Logging records: input, context_snapshot, output, and the mapping between them
- [ ] On error or rejection, the trace shows which context led to the wrong proposal

### Anti-Patterns

| Anti-Pattern | What Happens | Fix |
|--------------|-------------|-----|
| **Uncited output** | "Migrate to Spark DataFrame" with no explanation of why | Cite technology_profile pattern in output |
| **Mystery pattern** | Agent uses a pattern from vector search but doesn't show which one | Include pattern ID and source decision in output |
| **No error trace** | Human rejects proposal but can't tell which context was wrong | Log full context_snapshot with output; enable post-mortem |

### Output Format

```yaml
proposal:
  action: "Migrate SSIS DataFlowTask to Spark DataFrame pipeline"
  artifacts:
    - path: "transformations/load_patients.py"
      description: "Spark DataFrame pipeline replacing SSIS package"
  context_citations:
    - source: "technology_profile.ssis.data_flow_task"
      contribution: "Identified pattern as Data Flow Task -> Spark DataFrame"
    - source: "resolved_decision.42"
      contribution: "OLE DB auth mapping: Windows -> Service Principal"
    - source: "similar_pattern.7"
      contribution: "Similar migration for LoadEncounters package"
    - source: "constraint.pii_columns"
      contribution: "Columns patient_name, patient_ssn flagged as PII"
```

---

## Rule 7: No Scope Creep

**Hazard:** Agent sees all available context (every technology profile, every decision, every pattern) and proposes changes outside the current item's scope — modifying unrelated components or suggesting cross-domain changes that weren't requested.

**Rule:** Context scope is bounded by cluster + dependency graph, not "all available".

### Checklist

- [ ] context_snapshot only includes items in the same cluster or directly connected in the dependency graph
- [ ] Cross-domain patterns require explicit opt-in: `item.cross_domain = true`
- [ ] Agent prompt includes scope boundary: "You are migrating item X in domain Y. Do not propose changes to items outside this cluster."
- [ ] If the agent identifies a cross-domain opportunity, it logs it as a **suggestion** (not a proposal) — requires separate human decision
- [ ] Technology profiles from other domains are NOT loaded unless explicitly requested

### Anti-Patterns

| Anti-Pattern | What Happens | Fix |
|--------------|-------------|-----|
| **All-context injection** | Every decision ever made injected into snapshot | Bound by cluster + dependency graph |
| **Cross-domain without consent** | Agent migrating data pipeline also proposes frontend changes | Cross-domain as suggestion, not proposal |
| **Eager refactoring** | Agent proposes refactoring 5 other items while migrating 1 | Scope boundary in system prompt |

---

## Rule 8: No Single Point of Failure

**Hazard:** The knowledge store (Vector DB, Postgres, or YAML files) becomes unavailable and the agent cannot function at all — losing all accumulated context and reverting to zero-knowledge operation.

**Rule:** Degraded context > no context > wrong context.

### Fallback Hierarchy

| Knowledge Store | Primary | Fallback | Degraded Behavior |
|-----------------|---------|----------|-------------------|
| Technology profiles (YAML) | File read | Embedded in project | Agent operates with profile only; no patterns, no decisions |
| Resolved decisions (Postgres) | SQL query | YAML export / cache | Agent sees last-known decisions; warns "decisions may be stale" |
| Pattern library (Vector DB) | Vector search | SQL LIKE search on decisions | Agent uses text search instead of semantic; lower relevance but functional |
| Dependency graph | Graph traversal | Static adjacency list in YAML | Agent sees direct dependencies only (depth=1) |

### Checklist

- [ ] Each knowledge store has a documented fallback
- [ ] Agent detects store unavailability and logs a warning with degraded mode
- [ ] Degraded mode is explicitly signaled in agent output: "Operating with degraded context: Vector DB unavailable"
- [ ] Agent never halts on store failure — it degrades, it doesn't crash
- [ ] Recovery: when store comes back online, agent re-builds snapshot on next interaction

### Anti-Patterns

| Anti-Pattern | What Happens | Fix |
|--------------|-------------|-----|
| **Hard dependency** | Agent crashes if Vector DB is down | Fallback to SQL text search |
| **Silent degradation** | Agent uses stale cache without telling human | Explicit degraded mode message in output |
| **All-or-nothing** | If any store is down, agent refuses to operate | Partial context is still better than zero context |

---

## Summary: Rule Interaction Matrix

The 8 rules are not independent — they interact:

| | R1: No Loss | R2: No Blind | R3: No Stale | R4: No Noise | R5: No Bad Prop | R6: No Black Box | R7: No Creep | R8: No SPOF |
|---|---|---|---|---|---|---|---|---|
| **R1** | — | R1 enables R2 | | R4 can cause R1 | | | | R8 fallback enables R1 |
| **R2** | | — | R3 prevents R2 | | | | | |
| **R3** | | | — | | | | | R8 recovery enables R3 |
| **R4** | | | | — | R4 limits R5 impact | | R4 enables R7 | |
| **R5** | | | | | — | R6 detects R5 | | |
| **R6** | | | | | | — | | |
| **R7** | | | | | | | — | |
| **R8** | | | | | | | | — |

Key interactions:
- **R1 + R4 tension:** R1 says "don't lose info", R4 says "don't include too much". Resolution: persist everything (R1), but inject only what's relevant (R4). The knowledge store is the full record; the snapshot is the relevant view.
- **R3 + R8:** R3 requires fresh snapshots; R8 provides fallback when stores are unavailable. Fallback snapshots are stale by definition — agent must flag this (R6).
- **R5 + R6:** R5 prevents bad propagation; R6 makes propagation traceable. Together: even if a bad pattern slips through (R5 imperfection), R6 lets you find and revoke it.

---

## Implementation Checklist (per PoC)

Use this checklist when building a PoC that uses context management:

### Before First Interaction

- [ ] Technology profile YAML exists for primary source technology
- [ ] project_manifest.yaml with constraints
- [ ] Knowledge stores provisioned (Postgres + Vector DB, or fallback YAML)
- [ ] Fallback strategy documented for each store (Rule 8)
- [ ] context_snapshot builder implemented with budget awareness (Rule 4)
- [ ] HITL write-back gate implemented (Rule 1 + Rule 5)

### Per Interaction

- [ ] Snapshot rebuilt from live data, not cached (Rule 3)
- [ ] Snapshot validated: profile + dependencies + constraints present (Rule 2)
- [ ] Snapshot scoped to current cluster + dependency graph (Rule 7)
- [ ] Snapshot within token budget (Rule 4)
- [ ] Agent output includes context_citations (Rule 6)

### After Each HITL Approval

- [ ] Decision persisted to knowledge store synchronously (Rule 1)
- [ ] Decision includes confidence field (Rule 5)
- [ ] Pattern embedding upserted to Vector DB (Rule 3 freshness)
- [ ] Learning note appended to technology profile YAML (Rule 1)

### On Store Failure

- [ ] Fallback activated per store type (Rule 8)
- [ ] Degraded mode signaled in output (Rule 8 + Rule 6)
- [ ] Recovery: snapshot rebuilt on next interaction when store returns (Rule 3)
