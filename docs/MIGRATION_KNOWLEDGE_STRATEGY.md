# Migration Knowledge Strategy
## From Hardcoded Skills to Learned Patterns

**Context:** Instead of hardcoding migration-specific skills (like `disabled-task-audit`), this document explores how to capture migration patterns as **meta-knowledge** that informs skill generation, and how to preserve learned context across 2,000+ package migrations.

---

## Part 1: Technology Profiles for Skill Generation

### The Problem with Hardcoded Skills

Current approach in the comparison document:
```
Add skill: disabled-task-auditor
Add skill: change-history-analyzer  
Add skill: delta-merge-designer
```

**Issues:**
- Specific to SSIS → Databricks
- Doesn't scale to Airflow → Databricks, dbt → Spark, etc.
- New technology pairs require new hardcoded skills

### Proposed: Technology Profiles

Instead of skills, define **technology profiles** that describe what patterns exist in each source technology. The LLM uses these profiles during skill generation.

```yaml
# technology_profiles/ssis.yaml
technology:
  name: "SQL Server Integration Services (SSIS)"
  file_extension: ".dtsx"
  format: "xml"
  
structural_patterns:
  - name: "disabled_tasks"
    description: "SSIS packages often contain disabled tasks that may be dead code, superseded logic, or accidentally disabled"
    detection: "DTS:Executable with DTS:Disabled='True'"
    migration_implication: "Must audit each disabled task before migration to avoid missing functionality"
    skill_suggestion: "Include a task audit step in discovery phase"
    
  - name: "change_annotations"
    description: "Developers leave annotations in AnnotationLayout blocks documenting changes"
    detection: "AnnotationLayout elements in package XML"
    migration_implication: "These contain risk information and evolution history"
    skill_suggestion: "Parse annotations during discovery for risk register"
    
  - name: "connection_managers"
    description: "External connectivity defined via ConnectionManager elements"
    detection: "DTS:ConnectionManager elements"
    migration_implication: "Each connection must be mapped to target platform equivalent"
    skill_suggestion: "Include connectivity mapping in foundation phase"
    
  - name: "execution_modes"
    description: "Packages support multiple execution modes via expression variables"
    detection: "Variables with EvaluateAsExpression=True controlling precedence constraints"
    migration_implication: "All modes must be replicated in target"
    skill_suggestion: "Document all execution modes during analysis"

  - name: "control_flow_only_vs_data_flow"
    description: "Some packages are SQL-only (ExecuteSQLTask), others have Data Flow Tasks"
    detection: "DTS:ExecutableType values"
    migration_implication: "Data Flow Tasks require different migration patterns than SQL tasks"
    skill_suggestion: "Classify task types early to choose migration strategy"

execution_patterns:
  - name: "incremental_vs_full_reload"
    description: "Many ETL packages support both incremental and full reload modes"
    detection: "Control flags like 'processamento_full' or date-range parameters"
    migration_implication: "Target must support both MERGE and OVERWRITE patterns"
    
  - name: "soft_deletes"
    description: "Logical deletion via flag columns rather than physical DELETE"
    detection: "UPDATE statements setting exclusao_logica or similar flags"
    migration_implication: "Business rule must be preserved exactly"

validation_requirements:
  - name: "parallel_run"
    description: "Production ETL requires side-by-side validation before cutover"
    rationale: "Cannot rely on unit tests alone for data pipelines"
    skill_suggestion: "Include parallel run phase with reconciliation metrics"
    
  - name: "static_code_comparison"
    description: "Rule-by-rule comparison between source SQL and target code"
    rationale: "Ensures no business logic drift during migration"
    skill_suggestion: "Include static analysis step before parallel run"
```

### How Skill Generation Uses Profiles

During `ProposeSkillSet`, the LLM receives:

```
You are generating skills for a migration project.

Source technology: SSIS
Target technology: Databricks

TECHNOLOGY PROFILE FOR SSIS:
{technology_profiles/ssis.yaml}

Based on the structural patterns and validation requirements in this profile,
propose skills that address:
1. Each structural pattern that needs analysis
2. Each execution pattern that needs replication
3. Each validation requirement

Do NOT create generic skills. Create skills specific to the patterns found
in the technology profile.
```

**Result:** Skills are generated dynamically based on technology characteristics, not hardcoded.

---

## Part 2: Pattern Catalog (Cross-Technology)

Some patterns are technology-agnostic and apply across migrations:

```yaml
# migration_patterns/etl_common.yaml
patterns:
  - id: "AUDIT_DISABLED_ELEMENTS"
    applies_to: ["ssis", "airflow", "informatica", "talend"]
    description: "All ETL tools have disabled/paused elements that need audit"
    ssis_manifestation: "DTS:Disabled='True'"
    airflow_manifestation: "is_paused=True on DAGs"
    informatica_manifestation: "Disabled flag on mappings"
    
  - id: "MULTI_MODE_EXECUTION"
    applies_to: ["ssis", "airflow", "informatica", "adf"]
    description: "ETL packages commonly support incremental vs full modes"
    migration_concern: "Both modes must work identically in target"
    
  - id: "SOFT_DELETE_BUSINESS_RULE"
    applies_to: ["any_fact_table_etl"]
    description: "Logical deletion preserves audit trail"
    migration_concern: "Flag semantics must match exactly"
    
  - id: "CROSS_SYSTEM_DEDUP"
    applies_to: ["multi_source_consolidation"]
    description: "Same event reported by multiple systems needs dedup"
    vli_example: "VLI and Vale report same wagon load within ±7 hours"
    migration_concern: "Dedup window and priority rules must match"
```

---

## Part 3: Knowledge Preservation Across 2,000 Packages

### Option Analysis

| Approach | Pros | Cons | Cost | Recommendation |
|---|---|---|---|---|
| **Fine-tuning** | Deep pattern learning | Expensive, needs retraining, black box | High | ❌ Not recommended |
| **RAG** | Easy updates, explainable | Retrieval quality varies | Medium | ✅ For similar package lookup |
| **Structured KB** | Precise, queryable | Manual schema design | Low | ✅ For resolved decisions |
| **Few-shot** | Simple, effective | Context length limits | Very Low | ✅ For prompts |

### Why NOT Fine-Tuning?

**2,000 packages is not enough data:**
```
Fine-tuning typically requires:
- 10,000+ examples for meaningful improvement
- Consistent format across examples
- High-quality human-validated outputs

2,000 SSIS packages would yield:
- ~2,000 analysis documents
- ~2,000 rule catalogs
- ~2,000 migration notebooks

Total: ~6,000-10,000 documents — borderline for fine-tuning
```

**Fine-tuning loses explainability:**
- Can't trace why the model made a decision
- Can't update individual rules without retraining
- Client may ask "why did you migrate this way?" — no answer

**Knowledge changes:**
- Databricks releases new features (Unity Catalog, Liquid Clustering)
- Best practices evolve
- Fine-tuned model is frozen in time

### Recommended: Hybrid Knowledge Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Knowledge Preservation Stack                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐    ┌──────────────────┐    ┌────────────────┐ │
│  │  Technology      │    │  Pattern         │    │  Resolved      │ │
│  │  Profiles        │    │  Library         │    │  Decisions     │ │
│  │  (YAML)          │    │  (Vector DB)     │    │  (Postgres)    │ │
│  └────────┬─────────┘    └────────┬─────────┘    └───────┬────────┘ │
│           │                       │                       │          │
│           │    ┌──────────────────┴───────────────────┐  │          │
│           │    │                                      │  │          │
│           ▼    ▼                                      ▼  ▼          │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                      PROMPT ASSEMBLY                             ││
│  │                                                                  ││
│  │  "You are migrating package X. Here is:                         ││
│  │   - Technology profile for SSIS                                 ││
│  │   - 3 similar packages from vector search                       ││
│  │   - All resolved decisions for this project"                    ││
│  │                                                                  ││
│  └─────────────────────────────────────────────────────────────────┘│
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                         LLM CALL                                 ││
│  │                   (Claude, GPT-4, etc.)                         ││
│  └─────────────────────────────────────────────────────────────────┘│
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                  KNOWLEDGE EXTRACTION                            ││
│  │                                                                  ││
│  │  After each package migration:                                   ││
│  │  - Extract new patterns → Pattern Library                       ││
│  │  - Store resolved decisions → Decisions DB                      ││
│  │  - Update connection registry → Shared Context                  ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Part 4: Implementation Details

### 4.1 Technology Profiles (Static YAML)

```
packages/core/app/profiles/
├── ssis.yaml           # SSIS patterns, detection rules
├── airflow.yaml        # Airflow patterns
├── informatica.yaml    # Informatica patterns
├── adf.yaml            # Azure Data Factory patterns
└── common_etl.yaml     # Cross-technology patterns
```

**Loaded at skill generation time:**
```python
def propose_skillset(project: Project) -> list[Skill]:
    source_tech = project.source_technology  # "ssis"
    profile = load_profile(f"profiles/{source_tech}.yaml")
    
    prompt = f"""
    Generate skills for migrating from {source_tech}.
    
    TECHNOLOGY PROFILE:
    {profile.to_yaml()}
    
    PROJECT ARTIFACTS:
    {project.artifact_summaries}
    """
    
    return llm.generate(prompt, schema=SkillSetSchema)
```

### 4.2 Pattern Library (Vector DB for RAG)

**Store completed migrations as embeddings:**

```python
# After package migration completes
def store_migration_pattern(package: Package, artifacts: list[Artifact]):
    # Combine key artifacts into searchable document
    doc = f"""
    Package: {package.name}
    Domain: {package.domain}
    Task Types: {package.task_types}
    
    Business Rules:
    {artifacts['rule_catalog'].content}
    
    Key Decisions:
    {artifacts['decisions'].content}
    
    Migration Approach:
    {artifacts['silver_design'].content}
    """
    
    embedding = embed(doc)
    vector_db.upsert(
        id=package.id,
        embedding=embedding,
        metadata={
            "domain": package.domain,
            "task_types": package.task_types,
            "complexity": package.complexity
        }
    )
```

**Retrieve similar packages during analysis:**

```python
def get_similar_packages(package: Package, k: int = 3) -> list[dict]:
    query_doc = f"""
    Package: {package.name}
    Domain: {package.domain}
    Task Types: {package.task_types}
    """
    
    similar = vector_db.query(embed(query_doc), top_k=k)
    
    return [
        {
            "name": s.metadata["name"],
            "approach": load_artifact(s.id, "silver_design"),
            "decisions": load_artifact(s.id, "decisions")
        }
        for s in similar
    ]
```

### 4.3 Resolved Decisions (Structured DB)

Already designed in `LARGE_SCALE_MIGRATION_SHARED_CONTEXT.md`:

```sql
-- Connection resolved once, applied everywhere
SELECT * FROM migration_connections 
WHERE project_id = :project_id 
AND connection_name = :name;

-- Business rule documented once, referenced in all packages
SELECT * FROM migration_business_rules
WHERE project_id = :project_id
AND rule_applies_to @> ARRAY[:domain];

-- Decision made once, inherited by cluster
SELECT * FROM migration_resolved_decisions
WHERE project_id = :project_id
AND (scope = 'project' OR scope = 'cluster' AND cluster_id = :cluster_id);
```

### 4.4 Few-Shot Example Selection

**During card generation:**

```python
def draft_card(card: Card, project: Project) -> str:
    # Get 2-3 examples from same domain/complexity
    examples = select_few_shot_examples(
        card_type=card.type,  # e.g., "silver-design"
        domain=project.domain,  # e.g., "logistics"
        complexity=project.complexity  # e.g., "high"
    )
    
    prompt = f"""
    Generate a migration card for: {card.title}
    
    EXAMPLES FROM SIMILAR PROJECTS:
    {format_examples(examples)}
    
    CURRENT PACKAGE ANALYSIS:
    {project.current_package.analysis}
    
    RESOLVED DECISIONS:
    {project.resolved_decisions}
    """
    
    return llm.generate(prompt)
```

---

## Part 5: Knowledge Accumulation Workflow

### Per-Package Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Package N Migration                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. RETRIEVE CONTEXT                                             │
│     ├── Load technology profile (SSIS)                          │
│     ├── Query similar packages from vector DB                   │
│     ├── Load resolved decisions for project                     │
│     └── Select few-shot examples                                │
│                                                                  │
│  2. ANALYZE WITH CONTEXT                                         │
│     ├── LLM receives full context                               │
│     ├── Generates analysis, rules, decisions                    │
│     └── Flags items needing human input                         │
│                                                                  │
│  3. HUMAN RESOLVES (if needed)                                   │
│     ├── Resolves connection mappings                            │
│     ├── Confirms business rule interpretations                  │
│     └── Approves automation level decisions                     │
│                                                                  │
│  4. STORE NEW KNOWLEDGE                                          │
│     ├── New connections → connection registry                   │
│     ├── New business rules → rule catalog                       │
│     ├── Resolved decisions → decisions DB                       │
│     └── Package embedding → vector DB                           │
│                                                                  │
│  5. PROPAGATE TO SIMILAR PACKAGES                                │
│     ├── Find packages in same cluster                           │
│     ├── Apply resolved decisions automatically                  │
│     └── Reduce feedback items for remaining packages            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Knowledge Growth Over Time

```
Package 1-10:     Heavy human input, building initial knowledge
                  ├── 50+ feedback items per package
                  ├── All connections are new
                  └── No similar packages to reference

Package 11-100:   Knowledge acceleration
                  ├── 10-20 feedback items per package
                  ├── Most connections already resolved
                  └── Similar packages provide templates

Package 101-500:  Pattern dominance
                  ├── 2-5 feedback items per package
                  ├── Only edge cases need human input
                  └── Clusters batch-migrate with template

Package 501-2000: Near-automation
                  ├── <2 feedback items per package
                  ├── Only true outliers need attention
                  └── Human focuses on validation, not decisions
```

### Projected ROI

```
Without knowledge preservation:
- 2,000 packages × 30 feedback items × 5 min each = 5,000 hours

With knowledge preservation:
- Packages 1-10:    10 × 50 × 5 min = 42 hours
- Packages 11-100:  90 × 15 × 5 min = 112 hours
- Packages 101-500: 400 × 5 × 5 min = 167 hours
- Packages 501-2000: 1500 × 2 × 5 min = 250 hours
- Total: ~570 hours (89% reduction)
```

---

## Part 6: Schema Changes Required

### New Tables

```sql
-- Technology profiles (static, seeded)
CREATE TABLE technology_profiles (
    id UUID PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,       -- "ssis", "airflow"
    name TEXT NOT NULL,
    file_extension TEXT,
    format TEXT,                      -- "xml", "python", "json"
    profile_yaml TEXT NOT NULL,       -- Full YAML content
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pattern library (vector embeddings)
CREATE TABLE migration_patterns (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    package_id UUID REFERENCES etl_packages(id),
    
    -- Embedding for similarity search
    embedding VECTOR(1536),           -- OpenAI embedding dimension
    
    -- Searchable metadata
    domain TEXT,
    task_types TEXT[],
    complexity TEXT,
    
    -- Linked artifacts
    analysis_artifact_id UUID,
    rules_artifact_id UUID,
    decisions_artifact_id UUID,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for vector similarity search
CREATE INDEX ON migration_patterns 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Profile Loading in Code

```python
# app/services/knowledge_service.py

class KnowledgeService:
    def __init__(self, db: Session, vector_db: VectorStore):
        self.db = db
        self.vector_db = vector_db
    
    def get_context_for_package(
        self, 
        package: Package, 
        project: Project
    ) -> MigrationContext:
        """Assemble full context for package migration."""
        
        # 1. Technology profile
        profile = self.db.query(TechnologyProfile).filter_by(
            slug=project.source_technology
        ).first()
        
        # 2. Similar packages (RAG)
        similar = self.vector_db.query(
            embedding=embed(package.summary),
            filter={"project_id": str(project.id)},
            top_k=3
        )
        
        # 3. Resolved decisions
        decisions = self.db.query(ResolvedDecision).filter(
            ResolvedDecision.project_id == project.id,
            or_(
                ResolvedDecision.scope == "project",
                and_(
                    ResolvedDecision.scope == "cluster",
                    ResolvedDecision.cluster_id == package.cluster_id
                )
            )
        ).all()
        
        # 4. Connection registry
        connections = self.db.query(MigrationConnection).filter_by(
            project_id=project.id
        ).all()
        
        return MigrationContext(
            technology_profile=profile,
            similar_packages=similar,
            resolved_decisions=decisions,
            connections=connections
        )
```

---

## Part 7: Prompt Engineering for Profile-Driven Generation

### Skill Generation Prompt

```python
PROPOSE_SKILLSET_PROMPT = """
You are generating skills for a data pipeline migration project.

SOURCE TECHNOLOGY: {source_technology}
TARGET TECHNOLOGY: {target_technology}

TECHNOLOGY PROFILE:
{technology_profile_yaml}

PROJECT ARTIFACTS UPLOADED:
{artifact_summaries}

CROSS-TECHNOLOGY PATTERNS THAT APPLY:
{applicable_patterns}

---

Based on the technology profile, generate skills that:

1. ADDRESS STRUCTURAL PATTERNS
   For each pattern in the technology profile (disabled_tasks, change_annotations, etc.),
   consider whether a skill is needed to analyze or handle that pattern.

2. ADDRESS EXECUTION PATTERNS  
   For each execution pattern (incremental_vs_full, soft_deletes, etc.),
   consider whether a skill is needed to replicate that pattern in the target.

3. ADDRESS VALIDATION REQUIREMENTS
   For each validation requirement (parallel_run, static_code_comparison, etc.),
   consider whether a skill is needed to perform that validation.

4. LEVERAGE SIMILAR PACKAGES (if provided)
   {similar_packages_context}
   
Do NOT create generic skills like "analyze-source" or "convert-code".
Create skills SPECIFIC to the patterns found in this technology and these artifacts.

Output skills as JSON array with: name, description, triggers, resources.
"""
```

---

## Summary: Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Fine-tuning? | ❌ No | Not enough data, loses explainability, freezes knowledge |
| RAG for similar packages? | ✅ Yes | Enables learning from completed migrations |
| Structured KB for decisions? | ✅ Yes | Precise, queryable, auditable |
| Technology profiles? | ✅ Yes | Makes skill generation technology-aware |
| Pattern library? | ✅ Yes | Cross-technology learning |

### Implementation Priority

1. **Phase 1:** Technology profiles (YAML files) — immediate
2. **Phase 2:** Resolved decisions DB — builds on existing large-scale design
3. **Phase 3:** Vector DB for pattern library — after 50+ packages complete
4. **Phase 4:** Few-shot selection optimization — after 200+ packages

This approach scales to 2,000 packages while maintaining explainability and allowing knowledge updates without retraining.
