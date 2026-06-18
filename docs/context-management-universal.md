# Universal Context Management for Technology Migrations

## 1. Purpose

Context management patterns for AI-accelerated technology migrations. Generic across all domains:

| Domain | Example Migration |
|--------|-------------------|
| Data | SSIS -> Databricks, SQL Server DW -> Lakehouse, Informatica -> dbt |
| App | Java EE -> Spring Boot, .NET Framework -> .NET Core, Monolith -> Microservices |
| Infra | VMware -> Kubernetes, On-prem -> Cloud, Bare metal -> IaC |
| Frontend | AngularJS -> React, jQuery -> Vue, JSP -> SPA |

**Key principle:** migration knowledge accumulates per item and flows through agent interactions. Two complementary paradigms compose via `context_snapshot` injection.

---

## 2. Core Abstractions

### 2.1 Migration Item

Generic unit of migration work. NOT domain-specific (not "table", not "VM").

```yaml
migration_item:
  id: string                    # unique identifier
  item_type: enum               # table | package | service | vm | component | endpoint | job | dashboard
  domain: enum                  # data | app | infra | frontend
  source_tech: string           # e.g., "ssis", "java-ee-7", "vmware-6.5", "angularjs-1.5"
  target_tech: string           # e.g., "databricks", "spring-boot-3", "k8s-1.28", "react-18"
  source_fqdn: string           # fully qualified source name
  target_fqdn: string           # fully qualified target name (null pre-migration)
  status: enum                  # discovered | analyzing | migrating | validating | completed | failed
  complexity: enum              # trivial | low | medium | high | critical
  priority: integer             # 1-5, migration ordering
  dependencies: list[string]    # IDs of items this depends on
  dependents: list[string]      # IDs of items that depend on this
  metadata: map                 # domain-specific key-value pairs
```

### 2.2 Migration Integration

Connection between items. Generic across all integration types.

```yaml
migration_integration:
  id: string
  integration_type: enum        # database | api | queue | file | network | service | message-bus | cache
  source_item: string           # migration_item.id
  target_item: string           # migration_item.id
  protocol: string              # e.g., "jdbc", "rest", "amqp", "smb", "grpc"
  direction: enum               # inbound | outbound | bidirectional
  data_contract: ref            # optional reference to contract/spec defining the interface
  migration_strategy: enum      # lift-and-shift | re-platform | re-architect | replace | decompose
```

### 2.3 Item Cluster

Grouping by similarity for batch migration:

```yaml
item_cluster:
  id: string
  cluster_type: enum            # same-tech | same-pattern | same-owner | same-dependency-graph
  items: list[string]           # migration_item IDs
  representative: string        # canonical item - agent learns from this, applies to rest
  shared_context: map           # knowledge that applies to ALL items in cluster
```

---

## 3. Two Context Paradigms

### 3.1 Accumulative Context (Migration Knowledge)

Project-level knowledge that **GROWS** as items are migrated. Each resolved item adds to the shared context, reducing effort for similar items.

**Structure:**
```
SharedMigrationContext/
+-- project_manifest.yaml          # project metadata, source->target mapping
+-- technology_profiles/           # YAML per source technology (see section 4)
|   +-- ssis.yaml
|   +-- java-ee.yaml
|   +-- vmware.yaml
|   +-- angularjs.yaml
+-- resolved_decisions/            # PostgreSQL - structured, queryable
|   +-- decisions table            # item_id, decision_type, rationale, timestamp
|   +-- patterns table             # generalized from decisions
+-- pattern_library/               # Vector DB - semantic search over resolved patterns
|   +-- embeddings of (decision + code_diff + rationale)
+-- migration_graph/               # dependency graph - items + integrations
    +-- nodes = items, edges = integrations
```

**Lifecycle:**
1. Item starts -> agent reads shared context (technology profile + similar resolved patterns)
2. Agent proposes migration -> human approves
3. Item completes -> decision + pattern written back to shared context
4. Next similar item -> agent has MORE context than previous item

### 3.2 Conversational Context (Agent Interaction)

Per-interaction context that flows through the agent reasoning graph. Based on LangGraph AgentState pattern.

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]     # conversation history
    current_item: str                           # migration_item.id being worked
    context_snapshot: dict                      # injected from accumulative context
    think: str                                  # analysis/reasoning
    act: dict                                   # proposed action (code, config, decision)
    reflect: str                                # self-evaluation of action quality
    respond: str                                # human-readable output
    artifacts: list[dict]                       # generated files, configs, scripts
```

**Flow:** think -> act -> reflect -> respond -> (human review) -> update shared context

### 3.3 Composition: context_snapshot Injection

At the start of each agent interaction, the accumulative context is distilled into a `context_snapshot` and injected into the conversational AgentState:

```python
context_snapshot = {
    "technology_profile":  load_yaml(f"technology_profiles/{item.source_tech}.yaml"),
    "similar_patterns":    vector_search(pattern_library, item.description, top_k=5),
    "resolved_decisions":  sql_query(decisions_db, item.cluster_id),
    "dependency_context":  graph_traverse(migration_graph, item.id, depth=2),
    "constraints":         project_manifest.constraints
}
```

**This is the KEY integration point** - accumulative knowledge flows into each conversation.

---

## 4. Technology Profiles

Generic YAML schema that captures migration-relevant knowledge per source technology. Agents use these to generate appropriate migration strategies, code patterns, and validation rules.

### 4.1 Generic Profile Schema

```yaml
technology_profile:
  name: string                    # e.g., "ssis", "java-ee-7", "vmware-6.5"
  domain: enum                    # data | app | infra | frontend
  version: string
  category: string                # human-readable category

  source_patterns:                # patterns found in source technology
    - name: string
      description: string
      detection: string           # how to identify this pattern (regex, AST query, etc.)
      complexity: enum            # trivial | low | medium | high | critical
      migration_strategy: enum    # lift-and-shift | re-platform | re-architect | replace | decompose
      target_mapping:
        technology: string
        pattern: string
        code_template: string     # reference to template file
      common_issues:
        - issue: string
          resolution: string
          severity: enum

  constraints:
    - name: string
      description: string
      impact: string

  validation_rules:
    - name: string
      type: enum                  # structural | behavioral | performance | security
      check: string
      automated: boolean

  learning_notes: []              # populated as migrations complete - THE ACCUMULATIVE PART
```

### 4.2 Example: SSIS (Data Domain)

```yaml
technology_profile:
  name: ssis
  domain: data
  version: "2016-2019"
  category: "ETL Orchestration"

  source_patterns:
    - name: data_flow_task
      description: "SSIS Data Flow Task with source->transformations->destination"
      detection: ".dtsx XML: Dts:Executable Dts:ExecutableType=SSIS.Pipeline.2"
      complexity: medium
      migration_strategy: re-platform
      target_mapping:
        technology: databricks
        pattern: "Spark DataFrame pipeline (read->transform->write)"
        code_template: "templates/ssis-to-databricks-dataflow.py"
      common_issues:
        - issue: "OLE DB source uses Windows auth - not available in Databricks"
          resolution: "Map to Service Principal or OAuth in Unity Catalog"
          severity: high
        - issue: "Slowly Changing Dimension transform has no Spark equivalent"
          resolution: "Implement SCD2 as merge operation with explicit type 2 columns"
          severity: medium

    - name: foreach_loop
      description: "SSIS Foreach Loop container iterating over files/records"
      detection: ".dtsx XML: Dts:Executable Dts:ExecutableType=SSIS.ForEachLoop.2"
      complexity: low
      migration_strategy: re-platform
      target_mapping:
        technology: databricks
        pattern: "dbutils.fs.ls + parallel collection map"
        code_template: "templates/ssis-to-databricks-foreach.py"
      common_issues: []

    - name: script_task_csharp
      description: "SSIS Script Task with C# custom logic"
      detection: ".dtsx XML: ScriptTask + language=CSharp"
      complexity: high
      migration_strategy: re-architect
      target_mapping:
        technology: databricks
        pattern: "Python UDF or notebook - requires manual rewrite"
        code_template: null
      common_issues:
        - issue: "C# logic has no automatic translation to Python"
          resolution: "Manual rewrite with AI-assisted code translation + human review"
          severity: critical

  constraints:
    - name: windows_authentication
      description: "SSIS packages often use Windows Integrated Auth"
      impact: "Must map to cloud-native auth (Service Principal, Managed Identity, OAuth)"
    - name: package_configurations
      description: "SSIS uses XML/SQL Server package configurations for environment variables"
      impact: "Map to Databricks widgets, environment variables, or secret scope"

  validation_rules:
    - name: row_count_match
      type: behavioral
      check: "Source and target row counts match within tolerance"
      automated: true
    - name: data_type_preservation
      type: structural
      check: "Column data types map correctly (SQL Server -> Spark SQL types)"
      automated: true
    - name: nullability_preservation
      type: structural
      check: "NULL/NOT NULL constraints preserved or explicitly relaxed"
      automated: true

  learning_notes: []
```

### 4.3 Example: Java EE (Application Domain)

```yaml
technology_profile:
  name: java-ee-7
  domain: app
  version: "7"
  category: "Enterprise Application Server"

  source_patterns:
    - name: ejb_stateless
      description: "Stateless Session Bean with @Stateless annotation"
      detection: "Java AST: @Stateless class implementing interface"
      complexity: medium
      migration_strategy: re-platform
      target_mapping:
        technology: spring-boot-3
        pattern: "@Service or @Component with @RestController"
        code_template: "templates/ejb-to-spring-service.java"
      common_issues:
        - issue: "EJB container-managed transactions -> Spring @Transactional"
          resolution: "Map @TransactionAttribute to @Transactional with equivalent propagation"
          severity: medium

    - name: jpa_entity
      description: "JPA Entity with ORM mappings"
      detection: "Java AST: @Entity class with @Table, @Column annotations"
      complexity: low
      migration_strategy: lift-and-shift
      target_mapping:
        technology: spring-boot-3
        pattern: "Same JPA entity - Spring Boot uses same JPA/Hibernate"
        code_template: null
      common_issues:
        - issue: "JPA 2.1 -> JPA 3.0 jakarta namespace migration"
          resolution: "javax.persistence -> jakarta.persistence automated replacement"
          severity: low

    - name: jms_mdb
      description: "JMS Message-Driven Bean"
      detection: "Java AST: @MessageDriven class"
      complexity: high
      migration_strategy: re-architect
      target_mapping:
        technology: spring-boot-3
        pattern: "@RabbitListener or @KafkaListener with cloud-native messaging"
        code_template: "templates/jms-mdb-to-spring-listener.java"
      common_issues:
        - issue: "JMS API != RabbitMQ/Kafka API - semantic mismatch"
          resolution: "Choose target broker first, then adapt listener pattern"
          severity: critical

  constraints:
    - name: jakarta_namespace
      description: "Java EE -> Jakarta EE namespace migration (javax -> jakarta)"
      impact: "All imports must be updated; automated but verify no reflection usage"
    - name: deployment_descriptor
      description: "ejb-jar.xml, web.xml, application.xml descriptors"
      impact: "Map to Spring Boot application.yml or auto-configuration"

  validation_rules:
    - name: api_contract_preserved
      type: behavioral
      check: "REST/SOAP endpoint contracts unchanged (same request/response schema)"
      automated: true
    - name: transaction_behavior
      type: behavioral
      check: "Transaction boundaries and rollback behavior preserved"
      automated: false

  learning_notes: []
```

### 4.4 Example: VMware (Infrastructure Domain)

```yaml
technology_profile:
  name: vmware-6.5
  domain: infra
  version: "6.5"
  category: "Hypervisor / Virtualization Platform"

  source_patterns:
    - name: vm_with_stateful_data
      description: "VM with persistent disks and stateful application data"
      detection: "vSphere API: VM with thick-provisioned disks, no shared storage"
      complexity: high
      migration_strategy: re-platform
      target_mapping:
        technology: k8s-1.28
        pattern: "StatefulSet with PVC + cloud-native storage (EBS/Azure Disk)"
        code_template: "templates/vm-to-statefulset.yaml"
      common_issues:
        - issue: "Local disk data has no K8s equivalent - needs migration to PVC or object store"
          resolution: "Assess data: move to PVC if app needs it, S3/ADLS if archival"
          severity: critical

    - name: vm_stateless_web
      description: "Stateless web server VM behind load balancer"
      detection: "vSphere API: VM with thin disks, load balancer pool member"
      complexity: low
      migration_strategy: lift-and-shift
      target_mapping:
        technology: k8s-1.28
        pattern: "Deployment + Service + Ingress"
        code_template: "templates/vm-to-deployment.yaml"
      common_issues: []

    - name: vm_scheduled_job
      description: "VM running cron-scheduled batch jobs"
      detection: "vSphere API: VM with crontab entries, no always-on service"
      complexity: medium
      migration_strategy: re-platform
      target_mapping:
        technology: k8s-1.28
        pattern: "CronJob resource"
        code_template: "templates/vm-to-cronjob.yaml"
      common_issues:
        - issue: "Cron environment variables and paths differ in container"
          resolution: "Explicitly set ENV in CronJob spec, use absolute paths"
          severity: medium

  constraints:
    - name: network_topology
      description: "VLANs, firewall rules, NSX configurations"
      impact: "Must map to K8s NetworkPolicy + cloud VPC/security groups"
    - name: vm_snapshots
      description: "Existing VM snapshots used for rollback"
      impact: "K8s uses rolling deployments - snapshot strategy replaced by rollback deployment"

  validation_rules:
    - name: port_exposure
      type: structural
      check: "All required ports exposed in Service spec"
      automated: true
    - name: resource_limits
      type: performance
      check: "CPU/memory requests and limits set based on VM allocation"
      automated: true
    - name: health_checks
      type: behavioral
      check: "Liveness and readiness probes configured"
      automated: false

  learning_notes: []
```

### 4.5 Example: AngularJS (Frontend Domain)

```yaml
technology_profile:
  name: angularjs-1.5
  domain: frontend
  version: "1.5.x"
  category: "SPA Framework (deprecated)"

  source_patterns:
    - name: controller_scope
      description: "AngularJS controller with $scope binding"
      detection: "JS AST: app.controller('Name', function($scope, ...))"
      complexity: medium
      migration_strategy: re-architect
      target_mapping:
        technology: react-18
        pattern: "Function component with useState/useEffect hooks"
        code_template: "templates/angularjs-controller-to-react.jsx"
      common_issues:
        - issue: "$scope.$watch has no React equivalent - requires architectural change"
          resolution: "Replace with useEffect dependency array or state management library"
          severity: high

    - name: service_factory
      description: "AngularJS .service() or .factory() singleton"
      detection: "JS AST: app.service() or app.factory()"
      complexity: low
      migration_strategy: re-architect
      target_mapping:
        technology: react-18
        pattern: "Custom hook or context provider"
        code_template: "templates/angularjs-service-to-hook.js"
      common_issues: []

    - name: ng_route
      description: "AngularJS $routeProvider configuration"
      detection: "JS AST: $routeProvider.when()"
      complexity: low
      migration_strategy: re-architect
      target_mapping:
        technology: react-18
        pattern: "React Router <Route> components"
        code_template: "templates/angularjs-routes-to-react-router.jsx"
      common_issues:
        - issue: "Route resolve blocks -> React Router loaders (different API)"
          resolution: "Map resolve to loader function, handle with useLoaderData()"
          severity: medium

  constraints:
    - name: jquery_dependency
      description: "AngularJS apps often bundle jQuery for DOM manipulation"
      impact: "jQuery must be removed - React uses declarative rendering"
    - name: digest_cycle
      description: "AngularJS dirty-checking digest cycle"
      impact: "No equivalent in React - all data flow must be rewritten as unidirectional"

  validation_rules:
    - name: visual_regression
      type: behavioral
      check: "Rendered output matches source screenshots (pixel diff < threshold)"
      automated: true
    - name: accessibility
      type: structural
      check: "WCAG 2.1 AA compliance maintained"
      automated: true
    - name: bundle_size
      type: performance
      check: "Bundle size within budget (no larger than 1.5x source)"
      automated: true

  learning_notes: []
```

---

## 5. Hybrid Knowledge Architecture

Three-tier knowledge system. NOT fine-tuning — combines structured (YAML), relational (Postgres), and semantic (Vector DB) storage.

| Tier | Storage | Content | Query Pattern |
|------|---------|---------|---------------|
| 1 - Declarative | YAML files | Technology profiles, project manifest, constraints | Direct load by source_tech |
| 2 - Relational | PostgreSQL | Resolved decisions, patterns, item status | SQL queries by cluster, domain, status |
| 3 - Semantic | Vector DB | Embeddings of (decision + code_diff + rationale) | Similarity search by description |

**Why NOT fine-tuning:**
- Migration knowledge is project-specific, not generalizable
- Decisions must be traceable and auditable (healthcare/compliance)
- Updates must be immediate (new decision available to next item instantly)
- Fine-tuning is slow, expensive, and opaque

**Write-back flow:**
```
item migrated successfully
  -> decision written to Postgres (tier 2)
  -> pattern generalized and written to Postgres (tier 2)
  -> embedding of (decision + diff + rationale) upserted to Vector DB (tier 3)
  -> learning_notes appended to technology profile YAML (tier 1)
```

---

## 6. Context Window Management

Based on Polymath patterns. LLM context windows are finite — must prioritize what stays.

### 6.1 Effective Budget

```
effective_budget = (context_window * 0.85) - max_output_tokens
```

The 0.85 factor accounts for system overhead, tool schemas, and formatting.

### 6.2 Trimming Strategy

When context exceeds budget, trim in this priority order (NEVER trim system):

| Priority | Content | Preservation Rule |
|----------|---------|-------------------|
| 1 (keep) | System prompt + technology profile | Always preserved |
| 2 (keep) | Current item context + constraints | Always preserved |
| 3 (trim last) | Recent conversation turns | Keep newest N turns |
| 4 (trim first) | Older conversation turns | Remove oldest first |
| 5 (summarize) | Long artifact outputs | Replace with summary |

### 6.3 Context Snapshot Sizing

The `context_snapshot` injected from accumulative context must fit within budget. Strategy:

```python
def build_context_snapshot(item, budget_tokens):
    snapshot = {}
    remaining = budget_tokens

    # Always include technology profile (typically 500-1500 tokens)
    profile = load_yaml(f"technology_profiles/{item.source_tech}.yaml")
    snapshot["technology_profile"] = profile
    remaining -= estimate_tokens(profile)

    # Similar patterns from vector DB (top_k adjusted to budget)
    k = min(5, remaining // 200)  # each pattern ~200 tokens
    snapshot["similar_patterns"] = vector_search(
        pattern_library, item.description, top_k=max(1, k)
    )
    remaining -= k * 200

    # Resolved decisions for cluster (limited)
    snapshot["resolved_decisions"] = sql_query(
        decisions_db, item.cluster_id, limit=max(1, remaining // 150)
    )

    # Dependency context (depth-limited)
    depth = 2 if remaining > 500 else 1
    snapshot["dependency_context"] = graph_traverse(
        migration_graph, item.id, depth=depth
    )

    return snapshot
```

---

## 7. ROI Model

### Without Shared Context

Each of N items requires full analysis from scratch:
```
Total_Effort = N * F_avg * T_resolve
```
Where F_avg = average friction per item, T_resolve = time to resolve each friction point.

### With Shared Context

Effort decreases as items are resolved (knowledge accumulates):
```
Total_Effort = F_avg * T_resolve * (1 + sum(i=1..N-1) of decay^i)
```
Where decay < 1 (typically 0.3-0.5) — each subsequent similar item requires less effort because:
- Technology profile provides known patterns (avoids rediscovery)
- Resolved decisions provide precedents (avoids re-analysis)
- Vector search finds similar migrations (avoids starting from scratch)

### Expected Reduction

| N (items) | Decay | Reduction vs. No Context |
|-----------|-------|--------------------------|
| 10 | 0.4 | ~40% |
| 50 | 0.4 | ~60% |
| 100 | 0.4 | ~67% |
| 500 | 0.4 | ~71% |

**Break-even:** N >= 5 items for the overhead of setting up shared context to pay off.

---

## 8. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

- [ ] Define `migration_item` and `migration_integration` schemas
- [ ] Create `project_manifest.yaml` for current migration project
- [ ] Write first technology profile YAML (primary source technology)
- [ ] Set up PostgreSQL schema for `decisions` and `patterns` tables
- [ ] Implement `context_snapshot` builder with budget-aware trimming

### Phase 2: Accumulation (Week 3-4)

- [ ] Set up Vector DB (pgvector or Qdrant) for pattern library
- [ ] Implement write-back flow: decision -> Postgres -> Vector DB -> YAML learning_notes
- [ ] Build dependency graph (migration_graph) from item relationships
- [ ] Implement item clustering (same-tech, same-pattern)
- [ ] Validate with 5-10 items: confirm context grows and effort decreases

### Phase 3: Agent Integration (Week 5-6)

- [ ] Implement AgentState with LangGraph (think -> act -> reflect -> respond)
- [ ] Wire context_snapshot injection into agent initialization
- [ ] Add HITL gate: agent proposes, human approves before write-back
- [ ] Implement recency-biased context window trimming
- [ ] End-to-end test: migrate one item, confirm knowledge propagates to next

### Phase 4: Multi-Domain (Week 7-8)

- [ ] Add technology profiles for remaining source technologies
- [ ] Cross-domain pattern search (e.g., "auth migration" patterns across data + app)
- [ ] Implement cluster-based batch migration (learn from representative, apply to cluster)
- [ ] Dashboard: items migrated, patterns discovered, effort reduction metrics
- [ ] Production readiness: error handling, audit logging, compliance checks

---

## 9. Cross-Domain Patterns

Some migration patterns span multiple domains. The universal model captures these:

| Pattern | Domains | Example |
|---------|---------|---------|
| Auth migration | data + app + infra | Windows Integrated Auth -> OAuth 2.0 / Managed Identity |
| Config externalization | all | Hardcoded config -> environment variables / secret store |
| Secret management | all | Inline credentials -> vault / secret scope |
| Logging standardization | app + infra | Proprietary logging -> structured JSON logging (OTEL) |
| Network policy migration | infra + app | VLAN/firewall -> K8s NetworkPolicy + cloud security groups |
| Data format migration | data + frontend | XML/SOAP -> JSON/REST, proprietary -> Parquet/Delta |

These cross-domain patterns are stored in the pattern library with `domain: cross-cutting` and are retrieved by semantic search regardless of the current item's domain.

---

## 10. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Knowledge representation | YAML + Postgres + Vector DB | Structured + queryable + semantic; NOT fine-tuning |
| Context composition | context_snapshot injection | Clean separation: accumulative <-> conversational |
| Item abstraction | migration_item (not domain-specific) | Reusable across data, app, infra, frontend |
| Trimming strategy | System-preserved, recency-biased | System context never trimmed; oldest turns removed first |
| HITL gate | Required for all write-backs | Compliance (HIPAA/LGPD): no auto-merge of decisions |
| Cluster strategy | Learn from representative | Exponential efficiency for N similar items |
| Decay factor | 0.3-0.5 per similar item | Conservative; measure and tune per project |
