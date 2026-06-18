# Code Quality System — Code Review Agent + Architecture Fitness Evaluator

> Two complementary modules for reviewing AI-generated code: a file-scope review agent and an application-scope fitness evaluator.
> **Universal** — applies to any application, modernization, migration, or greenfield project. Not HAE-specific.
> Date: 2026-05-29 | Status: Study (debate concluded, design ready for spike)
> Cross-cuts: contract-driven-architecture.md, tooling-study.md, context-management-universal.md

---

## 1. Problem Statement

AI-generated code has **different failure modes** than human code:

| Human Code Failure | AI-Generated Code Failure |
|---|---|
| Typos, syntax errors | Rare — AI produces syntactically valid code |
| Missing error handling | Rare — AI adds excessive try/catch |
| Inconsistent style | Rare — AI is highly consistent |
| **Plausible but wrong logic** | **Common** — looks correct, passes review, fails on edge cases |
| **Hallucinated APIs** | **Common** — calls methods that don't exist on that class |
| **Dead scaffolding** | **Common** — generates "just in case" branches that never execute |
| **Verbose but hollow** | **Common** — 40-line function that does what 5 lines should |
| **Missing domain context** | **Common** — doesn't know the project's domain constraints |
| **Dirtiness from fixes** | **Common** — incremental patches accumulate, contradict, leave zombies |

Additionally, fixes made during building make code "dirty" — and architectural decay happens at the application level, not the file level. We need both a **microscope** (file-scope review) and a **telescope** (application-scope fitness).

This system is **universal** — it applies to:
- **Migrations** (legacy → modern: SSIS→Databricks, Java EE→Spring, AngularJS→React)
- **Modernizations** (strangler fig, lift-and-shift, refactor)
- **Greenfield applications** (new services, APIs, data pipelines)
- **Container/infrastructure** (Dockerfiles, Kubernetes manifests, Terraform)
- **Service validation** (MCP servers, APIs, databases, message brokers — are they healthy + correct?)

---

## 2. Dead End — Refined Definition

```
Dead End ≠ "code that exists but isn't used yet"
Dead End = "a pathway in a running process that became unreachable
           due to subsequent code changes, while the pathway still exists in code"

Future Feature ≠ Dead End
Future Feature = has minimal scaffold config + TODOs + missing integrations
                 Those TODOs/missing integrations = BUGS (not dead ends)
```

| What | Detection | Treatment |
|------|-----------|-----------|
| Dead end (was reachable, now isn't) | Compare current control flow vs historical | Flag for removal or reconnection |
| Future scaffold (never was reachable) | Detect TODO/FIXME/stub + missing integrations | Flag as incomplete (bug), not dead |
| Dead end masquerading as future | No TODO, no scaffold config, no integration plan | Flag as dead end |

**Key insight**: Dead end detection requires **temporal analysis** — git history comparison. If a path was reachable at commit T but unreachable at T+N, it's a dead end. Current-code-only analysis can't distinguish dead ends from future scaffolds.

---

## 3. Analysis Dimensions

### D1: Dead Paths (reachability)

- **Unreachable branches**: `if x > 0 and x > 10` — first condition subsumes second
- **Dead CASE WHEN branches**: `WHEN status = 'X'` where status enum never includes 'X'
- **Dead dbt models**: built but never `ref()`'d downstream
- **Dead columns**: selected in Silver but never consumed by Gold
- **Dead tests**: `test_not_null` on a COALESCE'd column — can never fail
- **Dead MCP tools**: defined in server but no agent ever calls them

**Approach**: AST + dependency graph. Solvable statically for most cases.

### D2: Dead Logic (redundancy)

Code executes but does nothing meaningful:

- **Tautological conditions**: `WHERE 1=1`, `COALESCE(x, x)`
- **No-op transformations**: `SELECT * FROM ref('stg_x')` with no transformation
- **Redundant casts**: `CAST(CAST(x AS INT) AS INT)`
- **Shadowed variables**: inner scope redefines outer computation
- **Identity operations**: `df.select('*').filter(True)`

**Approach**: Pattern matching + semantic analysis.

### D3: Logical Gaps (correctness)

The **hardest and most valuable** dimension:

- **Missing edge cases**: nulls, empty sets, duplicates, concurrent writes
- **Wrong join semantics**: LEFT JOIN where INNER was intended (changes cardinality)
- **Implicit type coercion**: `'123' + 456` — silently wrong in some dialects
- **Off-by-one in window functions**: `ROWS 1 PRECEDING` vs `UNBOUNDED PRECEDING`
- **Missing SCD2 close-out**: new row inserted but old row's `eff_end_date` not updated
- **Hallucinated API**: method exists but with different signature
- **Contract violation**: generated model doesn't include all contract columns

**Intent = contract + tests + business rules**. You can't detect "wrong join" without knowing intended cardinality.

### D4: Performance

- **N+1 in dbt**: iterates over values instead of set-based
- **Missing partition pruning**: filter not on partition column → full scan
- **Cartesian join risk**: CROSS JOIN or missing join condition
- **Unnecessary shuffle**: GROUP BY on non-partition key in large table
- **Redundant CTEs**: same CTE computed multiple times
- **Missing Z-order**: Delta table queried by non-Z-ordered column
- **Broadcast join missed**: small dimension table not broadcast

**Approach**: Static pattern detection + EXPLAIN analysis on Databricks.

### D5: Improvements (quality)

- **Over-abstraction**: 3 layers of indirection for a simple SELECT
- **Copy-paste drift**: similar models with subtle differences that should be macro'd
- **Missing documentation**: no column descriptions, no model-level docs
- **Hardcoded values**: `'2024-01-01'` instead of variable or config
- **Non-idiomatic patterns**: Python loops instead of Spark native operations

---

## 4. Code Dirtiness from Incremental Fixes

```
Day 1: AI generates clean model
Day 3: Bug found — quick patch added (workaround, not refactor)
Day 7: Another bug — different patch on same model
Day 14: Edge case — another conditional branch added
Day 30: Model is now 3x original size, with 4 patches
        that partially overlap, 2 that contradict each other,
        and the original clean logic is buried
```

### 4.1 Dirtiness Signals

| Signal | What It Looks Like | Detection Method |
|--------|-------------------|-----------------|
| **Patch stacking** | Multiple COALESCE/IFNULL wrapping same column | AST: count nested null-handling on same column |
| **Contradictory fixes** | One path filters `status = 'A'`, another allows `status IN ('A','I')` | Control flow: overlapping conditions with different scopes |
| **Abandoned branches** | `if DEBUG:` or `if False:` blocks with real logic | AST: detect always-false conditions |
| **Comment drift** | Comment says "filter active" but code filters discharged | NLP: compare comment intent vs code behavior |
| **Inconsistent error handling** | Some paths try/catch, others let fail | Pattern: count error handling strategies per module |
| **Copy-paste fix drift** | Same bug fixed in 3 places differently | Similarity: near-duplicate code blocks with different fixes |
| **Type widening** | INT → BIGINT → STRING "just in case" | Schema diff: trace type changes over git history |
| **Zombie variables** | Variable set for fix no longer needed, assignment remains | Data flow: variable written but never read in current flow |

### 4.2 Detection: Git-Aware Temporal Analysis

Cannot detect dirtiness from current code alone. Requires:

```
Commit history for file
  ├── Blame: which lines were added by "fix" commits?
  ├── Diff sequence: how did the file evolve?
  ├── Patch density: fix_commits / total_lines → dirtiness_score
  └── Contradiction detection: do two patches conflict?
```

**Implementation**:
1. `git log --oneline --grep="fix|patch|hotfix|workaround"` → identify fix commits
2. `git blame` → tag lines as "original", "fix", "refactor"
3. AST of current code → build control flow graph
4. Fix-tagged lines in dead paths → **zombie fixes** (fix exists but path is dead)
5. Fix-tagged lines that contradict each other → **conflicting patches**

---

## 5. Architecture Fitness Functions

From *Building Evolutionary Architectures* (Ford, Parsons, Kua): a **fitness function** quantifies how well architecture satisfies a desired property. This is the "whole application checker" — it operates at application scope, not file scope.

### 5.1 Pattern Knowledge Base Sources

| Source | Patterns Relevant to HAE |
|--------|------------------------|
| *Designing Data-Intensive Applications* (Kleppmann) | Batch/streaming boundaries, schema evolution, exactly-once |
| *The Data Warehouse Toolkit* (Kimball) | Conformed dimensions, SCD, fact grain consistency |
| *Fundamentals of Data Engineering* (Reis, Housley) | Medallion invariants, idempotent pipelines, data contracts |
| *Software Architecture in Practice* (Bass, Clements, Kazman) | Layered architecture, dependency direction, separation of concerns |
| *Clean Architecture* (Martin) | Dependency rule (inward), interface segregation |
| *Refactoring* (Fowler) | Code smell catalog, displacement refactoring, mutation points |
| *Domain-Driven Design* (Evans) | Bounded context isolation, anti-corruption layer, aggregate consistency |
| HAE-specific | LGPD masking invariants, clinical data freshness SLAs, Unity Catalog governance |

### 5.2 Fitness Functions — Data Domain

```yaml
# fitness-functions/medallion.yaml
domain: data
source: "Fundamentals of Data Engineering §5 + Kimball"

functions:
  - id: FF-001
    name: "Medallion layer direction"
    description: "Dependencies must flow Bronze → Silver → Gold (never backward)"
    invariant: "No Gold model ref()'s a Bronze source directly"
    severity: critical
    auto_fix: false

  - id: FF-002
    name: "Contract enforcement on Gold"
    description: "All Gold models must have contract.enforced = true"
    invariant: "Every model in gold/ has contract.enforced in schema.yml"
    severity: critical
    auto_fix: true

  - id: FF-003
    name: "No cross-domain coupling without declaration"
    description: "Clinical Gold cannot ref() Financial Silver without explicit cross-domain dependency"
    invariant: "Cross-domain refs require meta.cross_domain: true"
    severity: high
    auto_fix: false

  - id: FF-004
    name: "PII masking in Gold"
    description: "All PII columns in Gold must have masking function or be excluded"
    invariant: "No PII column in Gold without masking policy"
    severity: critical
    auto_fix: false

  - id: FF-005
    name: "Freshness SLA compliance"
    description: "Every source has freshness defined; every Gold model has SLA"
    invariant: "All sources.yml have freshness; all Gold models have meta.sla"
    severity: high
    auto_fix: false

  - id: FF-006
    name: "No God models"
    description: "No model ref()'d by more than 50% of downstream models"
    invariant: "max(downstream_deps(model)) / total_models < 0.5"
    severity: medium
    auto_fix: false

  - id: FF-007
    name: "Test coverage per model"
    description: "Every model has at least PK test + not_null on PK"
    invariant: "test_count(model) >= 2 for all models"
    severity: high
    auto_fix: false

  - id: FF-008
    name: "No direct table access"
    description: "All table access goes through dbt ref() or source(), never hardcoded table names"
    invariant: "No SQL contains hardcoded catalog.schema.table references"
    severity: critical
    auto_fix: false

  - id: FF-009
    name: "Schema evolution additive-only on Gold"
    description: "Gold table schema changes must be additive (new columns only)"
    invariant: "No column drops or type narrowing in Gold layer schema diff"
    severity: critical
    auto_fix: false
```

### 5.3 Fitness Functions — API Domain

```yaml
# fitness-functions/api.yaml
domain: api
source: "Clean Architecture + Software Architecture in Practice"

functions:
  - id: FF-101
    name: "Layered dependency direction"
    description: "Dependencies point inward: Presentation → Application → Domain → Infrastructure"
    invariant: "No import from outer layer in inner layer"
    severity: critical
    auto_fix: false

  - id: FF-102
    name: "OpenAPI spec coverage"
    description: "Every REST endpoint has OpenAPI spec"
    invariant: "endpoint_count(code) == endpoint_count(openapi_spec)"
    severity: high
    auto_fix: false

  - id: FF-103
    name: "No circular dependencies"
    description: "Module dependency graph is a DAG"
    invariant: "topological_sort(deps) succeeds"
    severity: critical
    auto_fix: false

  - id: FF-104
    name: "Pact coverage for external APIs"
    description: "All external API consumers have Pact tests"
    invariant: "Every API client has corresponding pact test"
    severity: high
    auto_fix: false
```

### 5.4 Fitness Functions — Migration Domain

```yaml
# fitness-functions/migration.yaml
domain: migration
source: "Strangler Fig pattern + context-management-universal.md"

functions:
  - id: FF-201
    name: "Migration item coverage"
    description: "Every legacy component has a migration_item with status"
    invariant: "legacy_components ⊆ migration_items"
    severity: high
    auto_fix: false

  - id: FF-202
    name: "No orphan decisions"
    description: "Every resolved decision references a migration_item"
    invariant: "All decisions have valid migration_item_id"
    severity: medium
    auto_fix: false

  - id: FF-203
    name: "Context integrity compliance"
    description: "All 8 context integrity rules pass (see context-integrity-guidelines.md)"
    invariant: "No silent loss, no blind spots, no stale state for active items"
    severity: high
    auto_fix: false
```

---

## 6. Two Modules — Code Review Agent + Architecture Fitness Evaluator

### 6.1 Comparison

| Aspect | Code Review Agent (code-review-mcp) | Architecture Fitness Evaluator (fitness-mcp) |
|--------|--------------------------------------|---------------------------------------------|
| Scope | File / function | Whole application |
| Finds | Bugs in code | Architectural decay |
| Time model | Point-in-time | Trend analysis over time |
| Example finding | "This function has a dead branch" | "This module has become a God object" |
| Example finding | "This query is slow" | "This layer violates the dependency rule" |
| Execution | Per-PR + on-demand | Per-PR + scheduled (weekly fitness report) |
| Interfaces | MCP server + CI step | MCP server + CI step + dashboard |
| LLM usage | Phase 3 only (OpenAI for semantic review) | explain_violation only (OpenAI) |
| Primary analysis | AST + Semgrep + contract verify | Fitness function execution + temporal |

### 6.2 Code Review Agent — Four-Phase Pipeline

```
Code + Contract + Business Rules
  │
  ├─ Phase 1: Static (cheap, fast, deterministic)
  │    ├─ tree-sitter AST → dead paths, dead logic
  │    ├─ Semgrep → known anti-patterns (30+ rules)
  │    ├─ dbt manifest graph → dead models, dead columns
  │    ├─ sqlglot → schema drift vs contract
  │    └─ Ruff/Pylint → Python quality
  │
  ├─ Phase 2: Contract Verification (structural, deterministic)
  │    ├─ datacontract verify → Gold model matches contract?
  │    ├─ dbt test → all contract expectations covered?
  │    ├─ Business rule coverage → all rules from contract implemented?
  │    └─ diff(manifest_A, manifest_B) → breaking changes?
  │
  ├─ Phase 3: LLM Review (expensive, targeted)
  │    ├─ Only review code that passed Phase 1+2
  │    ├─ Use OpenAI (DIFFERENT model than generator)
  │    ├─ Provide: code + contract + business rules + static findings
  │    └─ Focus on: logical gaps, edge cases, domain constraints
  │
  └─ Phase 4: Differential Testing (execution-based, for migration)
       ├─ Run legacy query on SQL Server → result_A
       ├─ Run migrated query on Databricks → result_B
       └─ diff(result_A, result_B) → correctness check
```

**Phase ordering rationale**:
- Phase 1 catches 60-70% of issues at near-zero cost
- Phase 2 catches contract violations that Phase 1 can't see
- Phase 3 only runs on code that "looks correct" — LLM focuses on the hard stuff
- Phase 4 is the ultimate oracle for migration correctness but requires execution infrastructure

### 6.3 Architecture Fitness Evaluator — Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              ARCHITECTURE FITNESS EVALUATOR                  │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  PATTERN    │  │  FITNESS    │  │  ANALYSIS   │         │
│  │  KNOWLEDGE  │  │  FUNCTIONS  │  │  ENGINE     │         │
│  │  BASE       │  │  REGISTRY   │  │             │         │
│  │             │  │             │  │             │         │
│  │ Books       │  │ FF-001..009 │  │ AST Parser  │         │
│  │ Standards   │  │ FF-101..104 │  │ Dep Graph   │         │
│  │ HAE domain  │  │ FF-201..203 │  │ Git History │         │
│  │ Anti-pats   │  │ Custom      │  │ Schema Diff │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          │                                  │
│                    ┌─────▼──────┐                           │
│                    │  SCORER    │                           │
│                    │            │                           │
│                    │ Per FF:    │                           │
│                    │  pass/fail │                           │
│                    │  score 0-1 │                           │
│                    │  trend     │                           │
│                    └─────┬──────┘                           │
│                          │                                  │
│         ┌────────────────┼────────────────┐                │
│         │                │                │                 │
│  ┌──────▼──────┐  ┌─────▼──────┐  ┌──────▼──────┐        │
│  │  CI GATE    │  │  DASHBOARD │  │  MCP SERVER │        │
│  │             │  │             │  │             │        │
│  │ Block PR on │  │ Fitness     │  │ Interactive │        │
│  │ critical    │  │ scores +    │  │ queries     │        │
│  │ violations  │  │ trends +    │  │ + explain   │        │
│  │             │  │ heat map    │  │ violations  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

---

## 6b. Container + Infrastructure Quality

Containers are code too. AI-generated Dockerfiles, Kubernetes manifests, Terraform, and CI/CD configs have the same failure modes as application code — plus infrastructure-specific ones.

### 6b.1 Container Image Quality

| Dimension | What to Check | Tool | AI-Specific Risk |
|-----------|--------------|------|-----------------|
| **Dockerfile linting** | Best practices: single process, no root, minimal layers, .dockerignore | hadolint, dockle | AI generates verbose Dockerfiles with unnecessary packages |
| **Image security** | Vulnerabilities in base image + installed packages | Trivy, Grype, Snyk | AI pins to `latest` tag or outdated base |
| **Image size** | Unnecessary packages, missing multi-stage build | dive, docker-slim | AI installs build tools in runtime image |
| **Base image freshness** | Base image has available updates | Trivy `--ignore-unfixed` | AI uses Ubuntu when distroless/alpine suffices |
| **Layer caching** | COPY order maximizes cache hits | hadolint DL-3000 series | AI puts COPY before RUN pip install (breaks cache) |
| **Secret leakage** | No secrets in image layers | Trivy secret scan, dockle | AI embeds API keys in ENV or ARG |
| **Health check** | HEALTHCHECK instruction present | dockle DKL-302 | AI omits health check entirely |

### 6b.2 Dockerfile Fitness Functions

```yaml
# fitness-functions/container.yaml
domain: container
source: "Docker Best Practices + CIS Docker Benchmark"

functions:
  - id: FF-301
    name: "No root user in runtime"
    description: "Container must run as non-root user"
    invariant: "Dockerfile has USER directive with non-zero UID"
    severity: critical
    auto_fix: false

  - id: FF-302
    name: "Multi-stage build"
    description: "Production images must use multi-stage builds (build stage ≠ runtime stage)"
    invariant: "Dockerfile has ≥2 FROM statements"
    severity: high
    auto_fix: false

  - id: FF-303
    name: "Pinned base image digest"
    description: "FROM uses digest, not tag alone"
    invariant: "FROM image@sha256:... present"
    severity: high
    auto_fix: true  # can auto-pin current digest

  - id: FF-304
    name: "No latest tag"
    description: "FROM never uses :latest"
    invariant: "No FROM ...:latest in any Dockerfile"
    severity: high
    auto_fix: false

  - id: FF-305
    name: "Health check present"
    description: "Container has HEALTHCHECK or equivalent probe"
    invariant: "HEALTHCHECK in Dockerfile OR livenessProbe in K8s manifest"
    severity: high
    auto_fix: false

  - id: FF-306
    name: "No secrets in image"
    description: "No ENV/ARG with secret values; no COPY of .env, keys, certs"
    invariant: "No secret patterns in Dockerfile layers"
    severity: critical
    auto_fix: false

  - id: FF-307
    name: "Minimal base image"
    description: "Use distroless or alpine when possible, not full Ubuntu/Debian"
    invariant: "Base image size < 200MB for service containers"
    severity: medium
    auto_fix: false
```

### 6b.3 Kubernetes Manifest Quality

| Dimension | What to Check | Tool |
|-----------|--------------|------|
| **Resource limits** | Every container has requests + limits | kube-linter, checkov |
| **No host networking** | hostNetwork: false | kube-linter |
| **Readiness probe** | Service won't route traffic until ready | kube-linter |
| **Image pull policy** | Always for :latest, IfNotPresent for pinned | kube-linter |
| **No privileged containers** | securityContext.privileged: false | kube-linter, OPA |

### 6b.4 Infrastructure-as-Code Quality

| Dimension | What to Check | Tool |
|-----------|--------------|------|
| **Terraform validation** | `terraform validate` + tflint | tflint, checkov |
| **Security compliance** | No public S3 buckets, no open security groups | checkov, tfsec |
| **Drift detection** | Actual state matches declared state | terraform plan, driftctl |
| **Cost estimation** | Infracost on every PR | Infracost |

---

## 6c. Service Validation — Testing the Services We Use

Beyond reviewing code, we must validate that the **services and infrastructure** our code depends on are healthy, correctly configured, and behaving as expected. This is "testing the platform" — not just testing our code.

### 6c.1 What to Validate

| Service Type | What to Test | When | Tool |
|-------------|-------------|------|------|
| **MCP server** | Starts, responds to `tools/list`, each tool has valid schema, auth works | On deploy + scheduled | Custom pytest + FastMCP test client |
| **Databricks workspace** | Connectivity, cluster running, Unity Catalog accessible, SQL Warehouse responsive | On deploy + scheduled | databricks-sdk health check |
| **dbt project** | `dbt compile` succeeds, `dbt test` passes, manifest.json valid | Every PR | dbt-core CLI |
| **API endpoint** | Health check, OpenAPI spec matches implementation, auth flow works | On deploy + scheduled | Schemathesis, pytest + httpx |
| **Database** | Connectivity, schema matches contract, migrations applied, no drift | On deploy + scheduled | Alembic/liquibase validate, datacontract-cli |
| **Message broker** | Topic/queue exists, schema registered, consumer group active | On deploy + scheduled | kcat/kafkacat, Schema Registry API |
| **Container registry** | Image exists, signed, no critical CVEs | On deploy | Trivy, cosign |
| **Secrets manager** | Required secrets exist, not expired, correct format | On deploy | Custom validation script |
| **Identity provider** | OAuth2/OIDC endpoints reachable, tokens obtainable, RBAC correct | On deploy + scheduled | Custom auth flow test |

### 6c.2 Service Validation Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  SERVICE VALIDATION SUITE                     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  CONNECTIVITY │  │  CONTRACT    │  │  BEHAVIORAL  │       │
│  │  TESTS        │  │  TESTS       │  │  TESTS       │       │
│  │              │  │              │  │              │       │
│  │ Can reach    │  │ Schema/shape │  │ Does it do   │       │
│  │ the service? │  │ matches      │  │ what we       │       │
│  │ Auth works?  │  │ contract?    │  │ expect?       │       │
│  │ Healthy?     │  │ Version      │  │ Performance   │       │
│  │              │  │ compatible?  │  │ within SLA?   │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                 │                 │                │
│         └─────────────────┼─────────────────┘                │
│                           │                                  │
│                    ┌──────▼───────┐                          │
│                    │  REPORTER    │                          │
│                    │              │                          │
│                    │  Per service:│                          │
│                    │   status     │                          │
│                    │   latency   │                          │
│                    │   issues    │                          │
│                    └──────┬───────┘                          │
│                           │                                  │
│         ┌─────────────────┼─────────────────┐               │
│         │                 │                 │                │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐        │
│  │  CI GATE    │  │  DASHBOARD  │  │  ALERTING   │        │
│  │  Block on   │  │  Service    │  │  PagerDuty  │        │
│  │  critical   │  │  health     │  │  / Slack on │        │
│  │  failures   │  │  map        │  │  degradation│        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└──────────────────────────────────────────────────────────────┘
```

### 6c.3 Service Validation as Fitness Functions

```yaml
# fitness-functions/service.yaml
domain: service
source: "Site Reliability Engineering (Google) + Observability best practices"

functions:
  - id: FF-401
    name: "MCP server health"
    description: "All MCP servers respond to tools/list within 5s"
    invariant: "mcp_server.health() == OK for all registered servers"
    severity: critical
    auto_fix: false

  - id: FF-402
    name: "Database connectivity + schema"
    description: "All databases reachable and schema matches contract"
    invariant: "db.ping() == OK AND datacontract.verify() == pass"
    severity: critical
    auto_fix: false

  - id: FF-403
    name: "API spec alignment"
    description: "Live API matches OpenAPI spec"
    invariant: "schemathesis.run(spec) passes all checks"
    severity: high
    auto_fix: false

  - id: FF-404
    name: "Container image freshness"
    description: "No critical CVEs in running container images"
    invariant: "trivy.scan(image).critical == 0"
    severity: critical
    auto_fix: false

  - id: FF-405
    name: "Secret availability"
    description: "All required secrets exist and are not expired"
    invariant: "secrets.validate(required_keys) == pass"
    severity: critical
    auto_fix: false

  - id: FF-406
    name: "Message broker health"
    description: "Topics exist, schemas registered, consumers active"
    invariant: "broker.topics ⊇ required_topics AND consumers.active"
    severity: high
    auto_fix: false
```

### 6c.4 MCP Server Testing (specific to our architecture)

Since we're building 4+ custom MCP servers, they need their own validation:

```python
# tests/test_mcp_servers.py
import pytest
from fastmcp import FastMCP

class TestMcpServerHealth:
    """Connectivity tests — can we reach the server?"""

    @pytest.mark.parametrize("server", [
        "data4u-mcp:8001",
        "databricks-extended-mcp:8002",
        "dbt-extended-mcp:8003",
        "ssis-ssas-mcp:8004",
        "code-review-mcp:8005",
        "fitness-mcp:8006",
    ])
    async def test_server_responds(self, server):
        client = FastMCP.test_client(server)
        tools = await client.list_tools()
        assert len(tools) > 0

class TestMcpServerContracts:
    """Contract tests — does each tool have valid I/O schema?"""

    async def test_data4u_ingest_contract_schema(self):
        tool = get_tool("data4u-mcp", "ingest_contract")
        assert tool.input_schema.required == ["contract_path"]
        assert "contract_id" in tool.output_schema.properties

    async def test_databricks_lineage_schema(self):
        tool = get_tool("databricks-extended-mcp", "get_table_lineage")
        assert tool.input_schema.required == ["table_fqn"]
        assert "nodes" in tool.output_schema.properties
        assert "edges" in tool.output_schema.properties

class TestMcpServerBehavior:
    """Behavioral tests — does the tool do what it says?"""

    async def test_ingest_contract_roundtrip(self):
        result = await call_tool("data4u-mcp", "ingest_contract",
                                  contract_path="tests/fixtures/contract.yaml")
        assert result.contract_id == "CTR-001"
        assert len(result.columns) > 0

    async def test_sqlglot_transpile_in_code_review(self):
        result = await call_tool("code-review-mcp", "review_code",
                                  file_path="tests/fixtures/model.sql")
        # Should detect T-SQL-isms that need transpilation
        assert any(f.dimension == "logical_gap" for f in result.findings)
```

---

## 7. MCP Server Designs

### 7.1 code-review-mcp

| Aspect | Detail |
|--------|--------|
| Framework | FastMCP |
| Transport | Streamable HTTP (port 8005) |
| Auth | Azure AD OAuthProxy |
| Dependencies | tree-sitter, semgrep, sqlglot, pydantic, openai (Phase 3 only) |

**Tools**:

```
review_code(file_path: str, phases: list[int] = [1,2,3,4]) -> ReviewReport
  - Run selected phases against the file
  - Returns: {phase_results: [{phase, findings: [{severity, dimension, location, message, auto_fixable, suggested_fix}]}]}

review_diff(base_branch: str, target_branch: str) -> DiffReviewReport
  - Review only changed code in PR
  - Returns: {changed_files: [...], findings: [...], blocking: bool}

check_dead_ends(scope: str = "full", include_temporal: bool = True) -> DeadEndReport
  - Detect dead ends (unreachable paths that were once reachable)
  - If include_temporal: compare current CFG vs historical execution traces
  - Returns: {dead_ends: [...], zombie_fixes: [...], future_scaffolds: [...]}

check_dirtiness(file_path: str = None, since_commit: str = None) -> DirtinessReport
  - Detect code dirtiness from incremental fixes
  - Returns: {patch_stacks, contradictions, zombie_variables, comment_drift, dirtiness_score: 0.0-1.0}

auto_fix(file_path: str, finding_id: str) -> AutoFixResult
  - Apply safe auto-fix for a finding (dead imports, redundant casts, etc.)
  - Only works for findings where auto_fixable == true
  - Returns: {success, diff, backup_path}
```

### 7.2 fitness-mcp

| Aspect | Detail |
|--------|--------|
| Framework | FastMCP |
| Transport | Streamable HTTP (port 8006) |
| Auth | Azure AD OAuthProxy |
| Dependencies | pydantic, networkx, sqlglot, openai (explain only) |

**Tools**:

```
evaluate_fitness(scope: str = "full", severity_threshold: str = "high") -> FitnessReport
  - Run all fitness functions for the given scope
  - scope ∈ {full, data, api, migration}
  - Returns: {scores: {FF-001: 1.0, FF-002: 0.85, ...}, violations: [...], trend: {...}}

explain_violation(fitness_id: str, violation_detail: str) -> Explanation
  - Explain WHY a fitness function fails using LLM (OpenAI)
  - Searches pattern knowledge base for relevant architectural pattern
  - Returns: {root_cause, pattern_reference, suggested_remediation, effort_estimate}

get_fitness_trend(fitness_id: str, period: str = "30d") -> TrendReport
  - Track fitness score over time
  - Returns: {data_points: [{date, score}], direction: improving|stable|degrading, velocity: float}

add_fitness_function(spec: dict) -> FitnessFunctionId
  - Register a new fitness function (custom, per-project)
  - Returns: {id, validation_errors}

list_fitness_functions(domain: str = None) -> list[FitnessFunctionSummary]
  - List all registered fitness functions
  - Returns: [{id, name, domain, severity, last_score, last_run}]
```

---

## 8. HITL Integration — Who Approves What

### 8.1 Code Review Agent Severity Levels

| Finding Severity | Source Phase | Action | Human Role |
|-----------------|-------------|--------|------------|
| Critical (dead model, contract violation) | Phase 1/2 | **Block PR** | Review finding, fix or waive |
| High (logical gap, missing edge case) | Phase 3 | **Flag for review** | Human must acknowledge |
| Medium (performance anti-pattern) | Phase 1/4 | **Suggest** | Human can accept or dismiss |
| Low (style, verbosity) | Phase 1 | **Info** | Optional |

### 8.2 Fitness Evaluator Severity Levels

| Fitness Severity | Action | Human Role |
|-----------------|--------|------------|
| Critical (FF-001, FF-004, FF-008) | **Block deploy** | Must fix before production |
| High (FF-002, FF-003, FF-005, FF-007) | **Block merge** | Must fix or explicitly waive with rationale |
| Medium (FF-006) | **Warn** | Track in fitness dashboard, plan remediation |

### 8.3 Auto-Fix Policy

**Safe auto-fixes** (applied automatically, no human gate):
- Remove unused imports
- Remove redundant casts (`CAST(CAST(x AS INT) AS INT)` → `CAST(x AS INT)`)
- Remove tautological conditions (`WHERE 1=1 AND` → `WHERE`)
- Add `contract.enforced: true` to Gold models missing it (FF-002)

**Unsafe — flag only** (human must approve):
- Remove dead model (may be intentional future)
- Fix contradictory patches (which one is correct?)
- Refactor over-abstraction (subjective)
- Add missing edge case handling (requires domain knowledge)

---

## 9. Tooling

| Tool | Purpose | Used By | License |
|------|---------|---------|---------|
| tree-sitter | Multi-language AST parsing | code-review-mcp Phase 1 | MIT |
| Semgrep | Pattern-based static analysis (30+ custom rules) | code-review-mcp Phase 1 | LGPL 2.1 |
| Ruff | Python linting + import cleanup | code-review-mcp Phase 1 | MIT |
| sqlglot | SQL schema diff + transpilation validation | code-review-mcp Phase 1/2 | Apache 2.0 |
| datacontract-cli | Data contract verification | code-review-mcp Phase 2 | MIT |
| dbt-core | Manifest parsing + test execution | code-review-mcp Phase 2 | Apache 2.0 |
| OpenAI API | Semantic code review (Phase 3) + violation explanation | code-review-mcp Phase 3, fitness-mcp | Commercial |
| NetworkX | Dependency graph analysis | fitness-mcp | BSD-3 |
| Hypothesis | Property-based testing for edge cases | code-review-mcp Phase 4 | MPL 2.0 |
| LangFuse | Trace review + eval scoring | Both | MIT |
| Great Expectations / Soda | Runtime DQ verification | code-review-mcp Phase 4 | Apache 2.0 |
| **hadolint** | Dockerfile linting | code-review-mcp Phase 1 (container) | MIT |
| **dockle** | Container image best practices | code-review-mcp Phase 1 (container) | Apache 2.0 |
| **Trivy** | Container image vulnerability scanning | fitness-mcp FF-404 | Apache 2.0 |
| **dive** | Container layer analysis (size optimization) | code-review-mcp Phase 1 (container) | MIT |
| **kube-linter** | Kubernetes manifest linting | code-review-mcp Phase 1 (infra) | Apache 2.0 |
| **checkov** | IaC security scanning (Terraform, K8s, Docker) | code-review-mcp Phase 1 (infra) | Apache 2.0 |
| **tflint** | Terraform linting | code-review-mcp Phase 1 (infra) | MPL 2.0 |
| **Infracost** | Cloud cost estimation per PR | fitness-mcp | Apache 2.0 |
| **Schemathesis** | API fuzz testing against OpenAPI spec | service validation FF-403 | Apache 2.0 |
| **testcontainers** | Integration testing with real containers | service validation | MIT |

### 9.1 Semgrep Rules for AI-Generated Code (examples)

```yaml
# semgrep-rules/ai-dead-logic.yaml
rules:
  - id: ai-tautological-condition
    patterns:
      - pattern: |
          if $X and $X: ...
      - pattern: |
          WHERE 1=1
    message: "Tautological condition — likely AI scaffolding"
    severity: WARNING

  - id: ai-redundant-cast
    patterns:
      - pattern: CAST(CAST($X AS $TYPE) AS $TYPE)
    message: "Redundant double cast — AI being overly safe"
    severity: WARNING

  - id: ai-noop-select
    patterns:
      - pattern: |
          SELECT * FROM {{ ref($MODEL) }}
    message: "No-op model — SELECT * with no transformation. Is this intentional?"
    severity: INFO

  - id: ai-excessive-null-handling
    patterns:
      - pattern: COALESCE(COALESCE($X, $Y), $Z)
    message: "Nested COALESCE — likely patch stacking from incremental fixes"
    severity: WARNING
```

---

## 10. Integration with Development Workflow

### 10.1 Where Code Review Agent Fits (universal)

```
Any Contract/Spec → AI generates code (or human writes code)
                        │
                        ▼
              code-review-mcp.review_code()
                        │
                   ┌────┴────┐
                   │ Passed? │
                   └────┬────┘
                    Yes │   │ No
                        │   └─→ Auto-fix (safe) or Fix manually → re-review
                        ▼
              fitness-mcp.evaluate_fitness(scope=<project_scope>)
                        │
                   ┌────┴────┐
                   │ Passed? │
                   └────┬────┘
                    Yes │   │ No (waivable)
                        │   └─→ Document waiver → proceed
                        ▼
              HITL gate: human approves PR
                        │
                        ▼
              Merge → CI runs full test suite + service validation
```

### 10.2 Where Fitness Evaluator Fits

- **Per-PR**: `evaluate_fitness(scope=<changed_domain>)` on every PR
- **Nightly**: `evaluate_fitness(scope="full")` — full application fitness report
- **Weekly**: `get_fitness_trend(period="7d")` — trend dashboard for architecture review meeting
- **On-demand**: Interactive via MCP server in Cursor/SAI — "Why does FF-003 fail?"

### 10.3 Scope by Project Type

| Project Type | Code Review Depth | Fitness Functions | Service Validation |
|-------------|-------------------|-------------------|-------------------|
| Data pipeline (dbt) | Phase 1-4, depth varies by layer | FF-001-009 (medallion) | dbt compile + test, Databricks health |
| API / microservice | Phase 1-3 | FF-101-104 (API) | API health, OpenAPI alignment, Pact verify |
| Migration (legacy→modern) | Phase 1-4 + differential testing | FF-201-203 (migration) | Source + target DB health, CDC status |
| Container / infra | Phase 1 (Dockerfile/K8s/TF linting) | FF-301-307 (container) | Container scan, K8s dry-run, TF plan |
| Full-stack app | All phases | All applicable | All services |
| MCP server | Phase 1-3 + MCP protocol validation | FF-401 (MCP health) | MCP tool schema + behavior tests |

### 10.4 Service Validation in CI/CD

```yaml
# .github/workflows/service-validation.yml
name: Service Validation
on: [push, pull_request, schedule]  # schedule = nightly

jobs:
  connectivity:
    runs-on: ubuntu-latest
    steps:
      - name: Validate MCP servers
        run: pytest tests/test_mcp_servers.py::TestMcpServerHealth -m connectivity

  contracts:
    runs-on: ubuntu-latest
    steps:
      - name: Validate API specs
        run: schemathesis run openapi/api.yaml --base-url=http://localhost:8000
      - name: Validate data contracts
        run: datacontract verify datacontracts/gold-models.yaml
      - name: Validate dbt project
        run: dbt compile && dbt test

  security:
    runs-on: ubuntu-latest
    steps:
      - name: Scan container images
        run: trivy image --severity=CRITICAL --exit-code=1 $IMAGE
      - name: Scan IaC
        run: checkov -d terraform/ --severity=CRITICAL

  behavioral:
    runs-on: ubuntu-latest
    steps:
      - name: MCP server behavior tests
        run: pytest tests/test_mcp_servers.py::TestMcpServerBehavior
      - name: Integration tests (testcontainers)
        run: pytest tests/integration/ --timeout=120
```

---

## 11. Recommendations

### 11.1 Spike Plan

| Spike | What | Effort | Depends On |
|-------|------|--------|------------|
| Spike A | code-review-mcp Phase 1 (static: tree-sitter + Semgrep + dep graph) | 5d | AST + manifest access |
| Spike B | code-review-mcp Phase 2 (contract: datacontract-cli + test coverage) | 3d | Spike A + contract format |
| Spike C | code-review-mcp Phase 3 (LLM: OpenAI review) | 3d | Spike A + OpenAI API key |
| Spike D | fitness-mcp (fitness function engine + dashboard) | 5d | dep graph + NetworkX |
| Spike E | Dirtiness detection (git-aware temporal analysis) | 3d | git access + AST |
| Spike F | Dead end detection (temporal CFG comparison) | 4d | git history + tree-sitter |
| Spike G | Container + IaC quality (hadolint + Trivy + checkov + kube-linter) | 3d | Dockerfile + K8s + TF files |
| Spike H | Service validation suite (MCP health + API contract + DB schema) | 4d | MCP servers + APIs + DBs |
| **Total** | | **30d** | |

### 11.2 Priority Order

1. **Spike A first** — highest ROI: static analysis catches 60-70% of issues at near-zero cost
2. **Spike D second** — fitness functions are the "whole application" view that individual reviews miss
3. **Spike G third** — container/infra quality is often neglected but has high security impact
4. **Spike H fourth** — service validation catches deployment issues before they reach production
5. **Spike B fifth** — contract verification ties code to the spec
6. **Spike C sixth** — LLM review is expensive; only valuable after static + contract are solid
7. **Spike E + F** — temporal analysis is powerful but requires git history infrastructure

### 11.3 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Review LLM | OpenAI (different from generator) | Avoid shared blind spots between generator and reviewer |
| Auto-fix scope | Safe transformations only | Removing dead imports is safe; removing dead models is not |
| Dead end detection | Temporal (git-aware) | Current-code-only can't distinguish dead ends from future scaffolds |
| Intent representation | Contract + tests + business rules | Contract alone is partial; business rules capture domain constraints |
| Fitness function storage | YAML in Git repo | Version-controlled, reviewable, CI-enforced (like technology profiles) |
| Dashboard | Static site from fitness scores | Lightweight; no server; generated nightly and hosted on Pages |
| Code review scope | All AI-generated code, depth varies by project type | Gold/API = full review; Bronze/infra = Phase 1 only |
| Holistic view | fitness-mcp operates across all layers | Individual file reviews miss cross-cutting architectural decay |
| Container quality | Included in code-review-mcp Phase 1 | Dockerfiles are code too — same AI failure modes apply |
| Service validation | Separate test suite, runs in CI + scheduled | Services we depend on must be validated, not assumed |

---

## 12. References

- `contract-driven-architecture.md` — Contracts as the spec to verify against
- `tooling-study.md` — MCP server inventory + framework choice
- `context-management-universal.md` — Migration item context (generic across domains)
- `context-integrity-guidelines.md` — 8 integrity rules → FF-203
- `poc-architecture-standards.md` — PoC architecture standards (Cat 1-8)
- *Building Evolutionary Architectures* (Ford, Parsons, Kua) — Fitness function concept
- *Designing Data-Intensive Applications* (Kleppmann) — Data architecture patterns
- *The Data Warehouse Toolkit* (Kimball) — Dimensional modeling invariants
- *Refactoring* (Fowler) — Code smell catalog
- *Site Reliability Engineering* (Google) — Service validation + SLI/SLO/SLA
- *Docker Best Practices* (Docker Inc.) — Container image quality
- *CIS Docker Benchmark* — Container security baseline
