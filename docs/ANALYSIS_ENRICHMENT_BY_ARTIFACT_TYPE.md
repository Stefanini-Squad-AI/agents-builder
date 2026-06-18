# Analysis: Enrichment Applicability by Artifact Type

**Date**: 2026-05-14  
**Question**: Which entities consume artifact context, and how does enrichment apply across different file types?

---

## 1. Current System: Who Consumes Artifact Context?

### Flow of Artifact Data

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        ARTIFACT DATA FLOW (CURRENT)                              │
└─────────────────────────────────────────────────────────────────────────────────┘

Upload .dtsx, .pdf, .docx, .py ...
         │
         ▼
┌─────────────────┐
│   Extractor     │  → content_md (raw text/markdown)
│   (per type)    │     
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ArtifactSummary│  → content_md_excerpt (first ~2000 chars)
│  (view model)   │     truncated flag
└────────┬────────┘
         │
         ├──────────────────────────────────────────────┐
         │                                              │
         ▼                                              ▼
┌─────────────────┐                         ┌─────────────────┐
│ ProposeSkillSet │                         │ ProposeBacklog  │
│ Prompt          │                         │ Prompt          │
│ → Skills        │                         │ → Cards         │
└─────────────────┘                         └────────┬────────┘
                                                     │
                                                     ▼
                                            ┌─────────────────┐
                                            │ DraftCard       │
                                            │ Prompt          │
                                            │ → Card Details  │
                                            └─────────────────┘
```

### Entities That Consume Artifact Context

| Entity | Consumes | Currently Uses |
|--------|----------|----------------|
| **ProposeSkillSetPrompt** | `ArtifactSummary` list | `content_md_excerpt` (first 2K chars) |
| **ProposeBacklogPrompt** | Project context string | Includes artifact snippets |
| **DraftCardPrompt** | `CardDraftContext` | Skills, upstream cards, project context |
| **Card Inputs** | `artifact` kind | File path reference to original |
| **Skill Resources** | N/A | Skills don't directly reference artifacts |
| **Validators** | Artifact paths | Check file existence for card inputs |

### Key Insight: Bottleneck is `content_md_excerpt`

All LLM prompts currently receive only **2,000 characters** from each artifact. For:
- **SSIS packages**: 2K chars might cover metadata + 1-2 tasks, missing 90% of business logic
- **Large PDFs**: Captures title/intro, misses detailed requirements
- **Code files**: Shows imports + maybe one function

**Enrichment addresses this** by generating a **compact but complete summary** that fits in context windows.

---

## 2. Enrichment Applicability by Artifact Type

### Enrichment Spectrum

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  HIGH VALUE                                                     LOW VALUE       │
│  (Complex Structure)                                      (Already Readable)    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  SSIS (.dtsx)      Airflow (.py)      PDF/DOCX        Markdown      Code        │
│  Talend (.job)     dbt (.sql+yml)     (specs)         (README)      (simple)    │
│  Informatica       NiFi (.xml)                                                  │
│                                                                                 │
│  ◄────────── NEEDS DEEP ENRICHMENT ──────────►  ◄── LIGHT/OPTIONAL ──►        │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Type-by-Type Analysis

#### A. **SSIS Packages (.dtsx)** — HIGH VALUE

| Aspect | Raw Extraction | Enriched Analysis |
|--------|----------------|-------------------|
| **What's Extracted** | XML → Markdown tables (tasks, vars, connections) | Business purpose, data journey, rules with WHY |
| **Feedback Need** | ❌ None | ✅ Critical (tie-breakers, undocumented logic) |
| **Sections** | Metadata, Variables, Tasks, SQL | Executive Summary, User Journey, Business Rules |
| **Why Enrichment Helps** | Raw says "ROW_NUMBER ORDER BY company". Enriched asks "Why does MRS win ties?" |

**Template**: `artifact_analysis.md.j2` (full version)  
**Prompt**: `AnalyzeArtifactPrompt` with SSIS-specific examples

---

#### B. **Airflow DAGs (.py)** — HIGH VALUE

| Aspect | Raw Extraction | Enriched Analysis |
|--------|----------------|-------------------|
| **What's Extracted** | Python code with line numbers | DAG structure, task dependencies, scheduling |
| **Feedback Need** | ✅ Moderate (naming conventions, failure handling) | |
| **Sections** | Code as-is | Schedule Analysis, Retry Strategy, Data Dependencies |
| **Why Enrichment Helps** | Code shows `@daily` but enrichment explains SLA impact |

**Requires**: New `AirflowAnalysisPrompt` variant
- Extract `dag_id`, `schedule_interval`, `default_args`
- Map `>>` operators to dependency graph
- Identify XCom usage, Variables, Connections

---

#### C. **dbt Models (.sql + schema.yml)** — MEDIUM-HIGH VALUE

| Aspect | Raw Extraction | Enriched Analysis |
|--------|----------------|-------------------|
| **What's Extracted** | SQL + YAML separately | Unified model card with tests, docs, lineage |
| **Feedback Need** | ✅ Moderate (freshness SLAs, column-level lineage) | |
| **Sections** | SQL code, YAML config | Lineage Graph, Quality Checks, Materialization |
| **Why Enrichment Helps** | Shows which columns propagate PII |

**Requires**: Cross-file analysis (models/ + schema.yml)

---

#### D. **PDF/DOCX Specifications** — MEDIUM VALUE

| Aspect | Raw Extraction | Enriched Analysis |
|--------|----------------|-------------------|
| **What's Extracted** | Text extraction (paragraphs, tables) | Structured requirements, acceptance criteria |
| **Feedback Need** | ✅ Low (ambiguous requirements) | |
| **Sections** | Document text | Requirements Table, Stakeholders, Risks |
| **Why Enrichment Helps** | Extracts "shall" statements into testable criteria |

**Template**: Simplified `requirements_analysis.md.j2`  
**Focus**: Extract SHALL/MUST requirements, identify gaps

---

#### E. **Markdown Documentation** — LOW VALUE

| Aspect | Raw Extraction | Enriched Analysis |
|--------|----------------|-------------------|
| **What's Extracted** | Already markdown | Optional: TOC, key terms, cross-references |
| **Feedback Need** | ❌ Rarely | |
| **Why Skip**: Already human-readable; extraction = enrichment |

**Recommendation**: Skip enrichment, use raw directly

---

#### F. **Simple Code Files (.py, .sql)** — LOW-MEDIUM VALUE

| Aspect | Raw Extraction | Enriched Analysis |
|--------|----------------|-------------------|
| **What's Extracted** | Code with line numbers | Function signatures, dependencies, complexity |
| **Feedback Need** | ❌ Rarely (unless large/complex) | |
| **Sections** | Code | API Summary, Imports, Key Functions |
| **Why Sometimes Helpful**: Large files (>1000 lines) benefit from summary |

**Recommendation**: Enrichment optional, triggered by size threshold

---

## 3. Proposed Enrichment Strategy Matrix

```python
# Enrichment decision logic

ENRICHMENT_CONFIG = {
    # File extension → (enrichment_type, auto_trigger)
    ".dtsx": ("technical_assessment", True),      # Always enrich
    ".ispac": ("technical_assessment", True),     # SSIS project
    ".py": ("code_analysis", "conditional"),      # Enrich if Airflow DAG detected
    ".job": ("etl_analysis", True),               # Talend
    ".xml": ("etl_analysis", "conditional"),      # NiFi if detected
    ".sql": ("code_analysis", "conditional"),     # Enrich if >500 lines or dbt
    
    ".pdf": ("requirements_extraction", "conditional"),  # Enrich if >10 pages
    ".docx": ("requirements_extraction", "conditional"), # Enrich if spec-like
    
    ".md": (None, False),                         # Skip enrichment
    ".txt": (None, False),
    ".csv": ("data_profile", "conditional"),      # Enrich if >1000 rows
}

def should_enrich(artifact: ProjectArtifact) -> tuple[str | None, str]:
    """Determine if artifact should be enriched.
    
    Returns: (analysis_type, reason)
    """
    ext = Path(artifact.filename).suffix.lower()
    config = ENRICHMENT_CONFIG.get(ext)
    
    if config is None:
        return (None, "No enrichment configured for extension")
    
    analysis_type, trigger = config
    
    if trigger is True:
        return (analysis_type, "Always enrich this type")
    
    if trigger == "conditional":
        # Apply heuristics
        if ext == ".py" and _is_airflow_dag(artifact.content_md):
            return ("airflow_dag_analysis", "Detected Airflow DAG")
        if ext == ".sql" and len(artifact.content_md) > 50_000:
            return ("code_analysis", "Large SQL file (>50K chars)")
        if ext == ".pdf" and artifact.size_bytes > 500_000:
            return ("requirements_extraction", "Large PDF (>500KB)")
        return (None, "Did not meet conditional threshold")
    
    return (None, "Unknown trigger type")
```

---

## 4. Updated Flow: How Each Entity Uses Enrichment

### New Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     ARTIFACT DATA FLOW (WITH ENRICHMENT)                         │
└─────────────────────────────────────────────────────────────────────────────────┘

Upload .dtsx, .pdf, .py ...
         │
         ▼
┌─────────────────┐
│   Extractor     │  → content_md (raw text/markdown)
│   (per type)    │     
└────────┬────────┘
         │
         ├───────────────────────────────────────┐
         │                                       │
         ▼                                       ▼
┌─────────────────┐                   ┌─────────────────────────┐
│  ArtifactSummary│                   │  Enrichment Job         │
│  (raw excerpt)  │                   │  (if should_enrich=True)│
└────────┬────────┘                   └───────────┬─────────────┘
         │                                        │
         │                                        ▼
         │                            ┌─────────────────────────┐
         │                            │  ArtifactAnalysis       │
         │                            │  (analysis_md)          │
         │                            │  (summary_md)           │
         │                            │  (feedback_items[])     │
         │                            └───────────┬─────────────┘
         │                                        │
         │◄───────────────────────────────────────┤
         │                                        │
         ▼                                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EnrichedArtifactView                          │
│  - content_md_excerpt (raw, always available)                    │
│  - analysis_summary_md (if enriched & approved)                  │
│  - has_pending_feedback                                          │
│  - readiness_score                                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ ProposeSkillSet │ │ ProposeBacklog  │ │ DraftCard       │
│ Prompt          │ │ Prompt          │ │ Prompt          │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Updated Schema: `EnrichedArtifactView`

```python
class EnrichedArtifactView(BaseModel):
    """Artifact view with both raw and enriched data."""
    
    # Identity
    id: UUID
    filename: str
    kind: ArtifactKind
    
    # Raw extraction
    extraction_status: ExtractionStatus
    content_md_excerpt: str | None = None  # First 2K chars of raw
    content_md_truncated: bool = False
    
    # Enrichment (if applicable)
    analysis_status: str | None = None  # pending | analyzing | approved | skipped
    analysis_summary_md: str | None = None  # ~500 char summary
    analysis_full_md: str | None = None  # Full analysis (loaded on demand)
    readiness_score: float | None = None  # 1.0 - 5.0
    
    # Feedback tracking
    has_pending_feedback: bool = False
    blocking_feedback_count: int = 0
    
    # Resolved decisions (if any)
    resolved_decisions: list[ResolvedDecision] = []


class ResolvedDecision(BaseModel):
    """A feedback item that was resolved by human."""
    topic: str
    selected_option: str
    rationale: str | None = None
```

---

## 5. How Each Consumer Changes

### A. ProposeSkillSetPrompt

**Current**: Uses `content_md_excerpt` (~2K chars)

**With Enrichment**:
```python
# In propose_skillset.py

def _build_artifact_context(artifacts: list[EnrichedArtifactView]) -> str:
    parts = []
    for artifact in artifacts:
        if artifact.analysis_status == "approved":
            # Use enriched summary (compact but complete)
            parts.append(f"**{artifact.filename}** (analyzed)")
            parts.append(f"Summary: {artifact.analysis_summary_md}")
            parts.append(f"Readiness: {artifact.readiness_score}/5")
            if artifact.resolved_decisions:
                parts.append("Key Decisions:")
                for d in artifact.resolved_decisions[:3]:  # Top 3
                    parts.append(f"  - {d.topic}: {d.selected_option}")
        else:
            # Fallback to raw excerpt
            parts.append(f"**{artifact.filename}** (raw)")
            parts.append(artifact.content_md_excerpt or "No content")
        parts.append("")
    return "\n".join(parts)
```

**Benefit**: Skills generated with understanding of business rules, not just code structure.

---

### B. ProposeBacklogPrompt

**Current**: Receives project context string with artifact snippets

**With Enrichment**:
```python
# When building backlog context

def build_backlog_context(project: ProjectView, artifacts: list[EnrichedArtifactView]) -> str:
    # Group artifacts by readiness
    ready = [a for a in artifacts if a.analysis_status == "approved"]
    pending = [a for a in artifacts if a.has_pending_feedback]
    raw = [a for a in artifacts if a.analysis_status in (None, "skipped")]
    
    context = []
    
    if ready:
        context.append("## Analyzed Artifacts (Ready for Migration)")
        for a in ready:
            context.append(f"- **{a.filename}** — {a.analysis_summary_md}")
            context.append(f"  Readiness: {a.readiness_score}/5")
    
    if pending:
        context.append("## Artifacts Awaiting Human Input")
        for a in pending:
            context.append(f"- **{a.filename}** — {a.blocking_feedback_count} decisions needed")
            # Backlog should include "resolve feedback" cards for these
    
    return "\n".join(context)
```

**Benefit**: Backlog can include cards like "SPIKE-001: Resolve deduplication tie-breaker rule" for artifacts with pending feedback.

---

### C. DraftCardPrompt

**Current**: Suggests inputs from skills and upstream cards

**With Enrichment**:
```python
# Card input suggestions now include analysis documents

def suggest_card_inputs(context: CardDraftContext) -> list[dict]:
    suggestions = []
    
    for artifact in context.relevant_artifacts:
        if artifact.analysis_status == "approved":
            # Reference BOTH raw and analysis
            suggestions.append({
                "kind": "artifact_analysis",
                "artifact_id": str(artifact.id),
                "path": f"analyses/{artifact.filename.replace('.dtsx', '_assessment.md')}",
                "label": "AI-generated technical assessment (for orientation)"
            })
            suggestions.append({
                "kind": "artifact_source",
                "artifact_id": str(artifact.id),
                "path": f"artifacts/{artifact.filename}",
                "label": "Original source file (for verification)"
            })
        else:
            # Raw only
            suggestions.append({
                "kind": "artifact",
                "artifact_id": str(artifact.id),
                "path": f"artifacts/{artifact.filename}",
                "label": "Source file"
            })
    
    return suggestions
```

**Benefit**: Cards explicitly guide agents to use analysis for understanding, raw for verification.

---

### D. Skill Resources

**Current**: Skills don't directly reference artifacts

**With Enrichment**: No change needed at skill level. Skills remain reusable templates. However, **cards that use skills** will now have richer artifact context.

---

### E. Card Inputs (New Kinds)

**Current**:
```python
class CardInputKind(StrEnum):
    SKILL_RESOURCE = "skill_resource"
    ARTIFACT = "artifact"
    EXTERNAL = "external"
```

**Proposed Addition**:
```python
class CardInputKind(StrEnum):
    SKILL_RESOURCE = "skill_resource"
    ARTIFACT = "artifact"              # Raw source file
    ARTIFACT_ANALYSIS = "artifact_analysis"  # Enriched analysis document
    EXTERNAL = "external"
```

---

## 6. Technology-Specific Enrichment Templates

### SSIS Packages → Full Technical Assessment

```yaml
analysis_type: technical_assessment
template: artifact_analysis.md.j2
prompt: AnalyzeArtifactPrompt
sections:
  - executive_summary
  - data_user_journey
  - business_rules
  - connection_landscape
  - objective_metrics
  - execution_modes
  - known_gaps
  - readiness_score
feedback_categories:
  - business_rule
  - technical_decision
  - data_quality
  - ownership
```

### Airflow DAGs → DAG Analysis

```yaml
analysis_type: dag_analysis
template: dag_analysis.md.j2  # NEW
prompt: AnalyzeAirflowDagPrompt  # NEW
sections:
  - dag_summary (id, schedule, owner)
  - task_graph (mermaid diagram)
  - schedule_analysis (SLA, timezone)
  - dependency_map (XCom, Variables, Connections)
  - failure_handling (retries, alerts)
  - data_lineage (sources → transformations → sinks)
  - migration_considerations
feedback_categories:
  - scheduling_decision
  - retry_strategy
  - alert_configuration
  - data_dependency
```

### PDF/DOCX Specs → Requirements Extraction

```yaml
analysis_type: requirements_extraction
template: requirements_analysis.md.j2  # NEW
prompt: ExtractRequirementsPrompt  # NEW
sections:
  - document_summary
  - stakeholders
  - functional_requirements (SHALL statements)
  - non_functional_requirements
  - constraints
  - assumptions
  - open_questions
feedback_categories:
  - ambiguous_requirement
  - missing_acceptance_criteria
  - stakeholder_clarification
```

### Code Files → Code Summary

```yaml
analysis_type: code_analysis
template: code_summary.md.j2  # NEW
prompt: SummarizeCodePrompt  # NEW
sections:
  - module_purpose
  - public_api (functions, classes)
  - dependencies (imports)
  - complexity_assessment
  - test_coverage_hint
feedback_categories:
  - design_pattern_question
  - dependency_concern
```

---

## 7. Implementation Roadmap

### Phase 1: SSIS Focus (Week 1-2)

Already designed:
- `artifact_analysis.md.j2` ✅
- `human_feedback_request.md.j2` ✅
- `analysis.py` schemas ✅
- Implementation blueprint ✅

Build:
- [ ] Database migration
- [ ] `AnalyzeArtifactPrompt` (SSIS variant)
- [ ] Dramatiq job
- [ ] API endpoints
- [ ] UI components

### Phase 2: Airflow Support (Week 3)

- [ ] Create `dag_analysis.md.j2` template
- [ ] Create `AnalyzeAirflowDagPrompt`
- [ ] Detection heuristic: `from airflow import DAG`
- [ ] Mermaid diagram generation for task graph

### Phase 3: PDF/DOCX Specs (Week 4)

- [ ] Create `requirements_analysis.md.j2`
- [ ] Create `ExtractRequirementsPrompt`
- [ ] Size/complexity threshold for triggering

### Phase 4: Generic Code Summary (Week 5)

- [ ] Create `code_summary.md.j2`
- [ ] Size threshold: >1000 lines or explicit request
- [ ] Language detection for syntax highlighting

---

## 8. Summary: Enrichment Decision Matrix

| File Type | Enrichment Type | Auto-Trigger | Feedback Likely? | Primary Consumer |
|-----------|-----------------|--------------|------------------|------------------|
| `.dtsx` | technical_assessment | ✅ Always | ✅ High | BacklogPrompt, CardPrompt |
| `.py` (Airflow) | dag_analysis | ✅ If DAG detected | ✅ Medium | BacklogPrompt, CardPrompt |
| `.sql` (large) | code_analysis | Conditional (>500 lines) | ⚠️ Low | CardPrompt |
| `.pdf` (spec) | requirements_extraction | Conditional (>10 pages) | ✅ Medium | SkillSetPrompt, BacklogPrompt |
| `.docx` | requirements_extraction | Conditional | ⚠️ Low | SkillSetPrompt |
| `.md` | None | ❌ Skip | ❌ No | Direct use |
| `.csv` | data_profile | Conditional (>1000 rows) | ⚠️ Low | CardPrompt |

---

## 9. Key Takeaways

1. **SSIS enrichment is HIGH VALUE** — Complex XML with business logic encoded in SQL. Enrichment extracts meaning, not just structure.

2. **Other ETL tools (Airflow, dbt, Talend) need similar treatment** — Each requires type-specific prompts and templates.

3. **Documentation (PDF/DOCX) benefits from requirements extraction** — But it's simpler than ETL enrichment.

4. **Simple files (Markdown, small code) should SKIP enrichment** — They're already readable; enrichment adds overhead without value.

5. **All prompts benefit from enrichment** — ProposeSkillSet, ProposeBacklog, and DraftCard all get better results with summarized artifacts.

6. **Feedback is most critical for ETL** — Business rules, tie-breakers, and undocumented logic require human decisions.

7. **Cards should reference BOTH raw and enriched** — Analysis for understanding, source for verification.
