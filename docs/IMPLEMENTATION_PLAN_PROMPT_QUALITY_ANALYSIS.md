# Implementation Plan: Prompt Quality Analysis

**Status:** Planning
**Created:** 2026-05-15
**Inspired by:** [vscode-chat-customizations-evaluation](https://github.com/microsoft/vscode-chat-customizations-evaluation)
**Scope:** Async LLM-powered quality analysis of generated skills and cards with full frontend job tracking

---

## Goal

After a skill or card is **generated** by the LLM, automatically run a quality analysis in the background (async) that detects:
- **Contradictions** — logical/behavioral conflicts within the prompt
- **Ambiguity** — vague statements with rewrite suggestions
- **Cognitive Load** — overly complex/nested conditions
- **Coverage Gaps** — missing error paths, missing intents
- **Composition Conflicts** — conflicts between skills assigned to the same card

The user must be able to **track the job progress**, see **failures**, **retry** failed jobs, and view **results** without blocking generation latency.

---

## Non-Goals

- ❌ No real-time analysis as user edits (per user requirement)
- ❌ No blocking at export time (analysis runs earlier)
- ❌ No fine-tuning — uses existing LLM provider
- ❌ No analysis on artifact upload (only on skill/card generation)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            GENERATION FLOW                               │
│                                                                          │
│  POST /skills/{id}/draft-body                                            │
│       │                                                                  │
│       ├─▶ Generate via LLM (existing)         ← blocking, 3-8s          │
│       ├─▶ Save skill.body                                                │
│       ├─▶ Create analysis_job (status=pending)                           │
│       ├─▶ Enqueue analyze_prompt_quality.send(job_id)                    │
│       │                                                                  │
│       └─▶ Response: { skill, analysis_job_id }                           │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (background, async)
┌──────────────────────────────────────────────────────────────────────────┐
│                         DRAMATIQ WORKER                                  │
│                                                                          │
│  analyze_prompt_quality(job_id)                                          │
│       │                                                                  │
│       ├─▶ Update job.status='running', progress=10%                      │
│       ├─▶ Phase 1: Contradiction check (progress=30%)                    │
│       ├─▶ Phase 2: Ambiguity check (progress=50%)                        │
│       ├─▶ Phase 3: Cognitive load check (progress=70%)                   │
│       ├─▶ Phase 4: Coverage gaps check (progress=90%)                    │
│       ├─▶ Save issues to prompt_quality_issues                           │
│       └─▶ Update job.status='completed', issue_count=N                   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (polled by frontend)
┌──────────────────────────────────────────────────────────────────────────┐
│                          FRONTEND TRACKING                               │
│                                                                          │
│  • JobTracker (floating panel)        — all jobs for project             │
│  • AnalysisJobsBadge (header)         — quick indicator                  │
│  • useJobStatus hook                  — per-generation tracking          │
│  • Skill/Card quality badges          — show issue count                 │
│  • Issues panel in detail view        — view + dismiss + apply fixes     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: Backend Foundation (Week 1)                                    │
│  ├── 1.1: Database schema (analysis_jobs, prompt_quality_issues)        │
│  ├── 1.2: SQLAlchemy models + Pydantic schemas                          │
│  ├── 1.3: Jobs API (GET /jobs, retry, acknowledge, cancel)              │
│  └── 1.4: Quality flags on skills/cards                                 │
├─────────────────────────────────────────────────────────────────────────┤
│  PHASE 2: Analyzer Engine (Week 2)                                       │
│  ├── 2.1: PromptAnalyzer base class                                     │
│  ├── 2.2: ContradictionDetector                                         │
│  ├── 2.3: AmbiguityDetector                                             │
│  ├── 2.4: CognitiveLoadDetector                                         │
│  ├── 2.5: CoverageGapDetector                                           │
│  └── 2.6: CompositionConflictDetector (multi-skill cards)               │
├─────────────────────────────────────────────────────────────────────────┤
│  PHASE 3: Dramatiq Job (Week 3)                                          │
│  ├── 3.1: analyze_prompt_quality actor                                  │
│  ├── 3.2: Progress reporting (status, message, percentage)              │
│  ├── 3.3: Retry logic + error handling                                  │
│  └── 3.4: Wire into LLM generation endpoints                            │
├─────────────────────────────────────────────────────────────────────────┤
│  PHASE 4: Frontend - Job Tracking (Week 4)                               │
│  ├── 4.1: API client (jobs.ts)                                          │
│  ├── 4.2: useAnalysisJobs + useJobStatus hooks                          │
│  ├── 4.3: Job notifications Zustand store                               │
│  ├── 4.4: JobTracker floating panel                                     │
│  └── 4.5: AnalysisJobsBadge in header                                   │
├─────────────────────────────────────────────────────────────────────────┤
│  PHASE 5: Frontend - Issue Display (Week 5)                              │
│  ├── 5.1: useGenerateWithAnalysis hook                                  │
│  ├── 5.2: Quality badges on skill/card lists                            │
│  ├── 5.3: Issues panel in skill detail page                             │
│  ├── 5.4: Issues panel in card detail page                              │
│  └── 5.5: Apply suggestion / dismiss actions                            │
├─────────────────────────────────────────────────────────────────────────┤
│  PHASE 6: Polish & Testing (Week 6)                                      │
│  ├── 6.1: Bulk re-analyze action (for existing artifacts)               │
│  ├── 6.2: Export pre-flight check (warn if pending jobs)                │
│  ├── 6.3: Job cleanup (auto-acknowledge after 7 days)                   │
│  ├── 6.4: Unit + integration tests                                      │
│  └── 6.5: Documentation                                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

**Total: 6 weeks**

---

## Phase 1: Backend Foundation (Week 1)

### 1.1: Database Schema

**File:** `packages/core/alembic/versions/XXXX_add_prompt_quality_analysis.py`

```sql
-- Job tracking
CREATE TYPE job_status AS ENUM (
    'pending', 'running', 'completed', 'failed', 'retrying'
);

CREATE TABLE analysis_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    target_type TEXT NOT NULL CHECK (target_type IN ('skill', 'card')),
    target_id UUID NOT NULL,
    target_name TEXT NOT NULL,

    status job_status DEFAULT 'pending',
    progress_pct INTEGER DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),
    status_message TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    issue_count INTEGER,
    error_message TEXT,

    attempt_number INTEGER DEFAULT 1,
    max_attempts INTEGER DEFAULT 3,
    acknowledged_at TIMESTAMPTZ
);

CREATE INDEX idx_jobs_project_status ON analysis_jobs(project_id, status);
CREATE INDEX idx_jobs_active ON analysis_jobs(status)
    WHERE status IN ('pending', 'running');
CREATE INDEX idx_jobs_target ON analysis_jobs(target_type, target_id);

-- Quality issues
CREATE TABLE prompt_quality_issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    analysis_job_id UUID REFERENCES analysis_jobs(id) ON DELETE SET NULL,

    target_type TEXT NOT NULL CHECK (target_type IN ('skill', 'card')),
    target_id UUID NOT NULL,

    category TEXT NOT NULL CHECK (category IN (
        'contradiction', 'ambiguity', 'cognitive_load',
        'coverage_gap', 'composition_conflict'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('error', 'warning', 'info')),
    message TEXT NOT NULL,
    suggestion TEXT,

    line_number INTEGER,
    column_number INTEGER,
    snippet TEXT,

    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'dismissed', 'fixed')),
    dismissed_reason TEXT,
    dismissed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_issues_target ON prompt_quality_issues(target_type, target_id);
CREATE INDEX idx_issues_open ON prompt_quality_issues(target_type, target_id)
    WHERE status = 'open';

-- Quality flags on artifacts
ALTER TABLE skills
    ADD COLUMN has_quality_issues BOOLEAN DEFAULT FALSE,
    ADD COLUMN quality_issue_count INTEGER DEFAULT 0,
    ADD COLUMN last_analyzed_at TIMESTAMPTZ;

ALTER TABLE cards
    ADD COLUMN has_quality_issues BOOLEAN DEFAULT FALSE,
    ADD COLUMN quality_issue_count INTEGER DEFAULT 0,
    ADD COLUMN last_analyzed_at TIMESTAMPTZ;
```

**Effort:** 0.5 days

---

### 1.2: SQLAlchemy Models + Pydantic Schemas

**Files:**
- `packages/core/app/domain/jobs.py` — `AnalysisJob` model
- `packages/core/app/domain/quality.py` — `PromptQualityIssue` model
- `packages/core/app/schemas/jobs.py` — `JobStatus`, `JobList` schemas
- `packages/core/app/schemas/quality.py` — `QualityIssue`, `QualityIssueList` schemas

**Effort:** 1 day

---

### 1.3: Jobs API

**File:** `packages/core/app/api/jobs.py`

| Endpoint | Purpose |
|---|---|
| `GET /jobs/{job_id}` | Single job status |
| `GET /jobs?project_id=&status=` | List jobs (filtered) |
| `POST /jobs/{job_id}/retry` | Retry failed job |
| `POST /jobs/{job_id}/acknowledge` | Dismiss from tracker |
| `DELETE /jobs/{job_id}` | Cancel pending/running |

**File:** `packages/core/app/api/quality.py`

| Endpoint | Purpose |
|---|---|
| `GET /skills/{id}/issues` | Issues for a skill |
| `GET /cards/{id}/issues` | Issues for a card |
| `POST /issues/{id}/dismiss` | Mark issue dismissed |
| `POST /issues/{id}/applied` | Mark issue fixed |
| `POST /skills/{id}/analyze` | Trigger re-analysis |
| `POST /cards/{id}/analyze` | Trigger re-analysis |

**Effort:** 1.5 days

---

### 1.4: CLI Commands

```
workshop quality jobs list                    # List active jobs
workshop quality jobs retry <job-id>          # Retry failed
workshop quality analyze skill <skill-id>     # Trigger analysis
workshop quality analyze card <card-id>       # Trigger analysis
workshop quality issues list --project <id>   # List all issues
```

**Effort:** 1 day

---

## Phase 2: Analyzer Engine (Week 2)

### 2.1: Base Analyzer

**File:** `packages/core/app/analyzers/prompt_quality/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class DetectedIssue:
    category: str  # 'contradiction' | 'ambiguity' | ...
    severity: str  # 'error' | 'warning' | 'info'
    message: str
    suggestion: str | None = None
    line_number: int | None = None
    column_number: int | None = None
    snippet: str | None = None

class PromptAnalyzer(ABC):
    category: str

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    @abstractmethod
    async def analyze(
        self,
        content: str,
        context: list[str] | None = None,
    ) -> list[DetectedIssue]:
        ...
```

**Effort:** 0.5 days

---

### 2.2-2.6: Per-Category Detectors

Each detector:
- Owns its LLM prompt template
- Returns list of `DetectedIssue`
- Has unit tests with sample inputs

**Files:**
```
packages/core/app/analyzers/prompt_quality/
├── base.py
├── contradiction.py
├── ambiguity.py
├── cognitive_load.py
├── coverage_gap.py
├── composition_conflict.py
└── prompts/
    ├── detect_contradictions.md.j2
    ├── detect_ambiguity.md.j2
    ├── assess_cognitive_load.md.j2
    ├── find_coverage_gaps.md.j2
    └── detect_composition_conflicts.md.j2
```

**Each detector pattern:**

```python
class ContradictionDetector(PromptAnalyzer):
    category = 'contradiction'

    async def analyze(self, content: str, context=None) -> list[DetectedIssue]:
        prompt = render_template(
            'detect_contradictions.md.j2',
            content=content,
        )

        response = await self.llm.complete(
            prompt=prompt,
            response_format=ContradictionList,  # Pydantic model
            temperature=0.0,
        )

        return [
            DetectedIssue(
                category='contradiction',
                severity='warning',
                message=item.message,
                line_number=item.line,
                snippet=item.conflicting_text,
            )
            for item in response.contradictions
        ]
```

**Effort:** 4 days (5 detectors × ~0.8 days each)

---

## Phase 3: Dramatiq Job (Week 3)

### 3.1-3.3: The Worker

**File:** `packages/core/app/jobs/analyze_prompt_quality.py`

```python
@dramatiq.actor(max_retries=2, time_limit=120_000)
def analyze_prompt_quality(job_id: str):
    with get_db() as db:
        job = db.query(AnalysisJob).get(UUID(job_id))

        try:
            _mark_running(db, job)

            content, context = _load_artifact(db, job)

            detectors = [
                (ContradictionDetector(llm), 'Checking contradictions...', 30),
                (AmbiguityDetector(llm), 'Detecting ambiguity...', 50),
                (CognitiveLoadDetector(llm), 'Assessing complexity...', 70),
                (CoverageGapDetector(llm), 'Finding coverage gaps...', 90),
            ]

            all_issues = []
            for detector, message, progress in detectors:
                _update_progress(db, job, progress, message)
                issues = asyncio.run(detector.analyze(content, context))
                all_issues.extend(issues)

            # Composition check only for cards with multiple skills
            if job.target_type == 'card':
                comp_detector = CompositionConflictDetector(llm)
                issues = asyncio.run(comp_detector.analyze(content, context))
                all_issues.extend(issues)

            _save_issues(db, job, all_issues)
            _mark_complete(db, job, len(all_issues))

        except Exception as e:
            _mark_failed(db, job, str(e))
            raise  # Dramatiq retries
```

**Effort:** 2 days

---

### 3.4: Wire Into Generation Endpoints

**Modify existing endpoints to enqueue analysis:**

```python
# packages/core/app/api/skills.py

@router.post("/{skill_id}/draft-body")
async def draft_skill_body(skill_id: UUID, ...):
    # Existing: generate body via LLM
    body = await llm_service.draft_skill_body(skill_id, ...)
    skill.body = body
    db.commit()

    # NEW: enqueue analysis
    job = AnalysisJob(
        project_id=skill.project_id,
        target_type='skill',
        target_id=skill.id,
        target_name=skill.slug,
    )
    db.add(job)
    db.commit()

    analyze_prompt_quality.send(str(job.id))

    return {
        'skill': SkillSchema.from_orm(skill),
        'analysis_job_id': str(job.id),  # NEW
    }
```

**Endpoints to modify:**
- `POST /skills/{id}/draft-body`
- `POST /skills/propose-set` (bulk — enqueue per skill)
- `POST /cards/{id}/draft` (single card)
- `POST /backlog/propose` (bulk — enqueue per card)

**Effort:** 1 day

---

## Phase 4: Frontend — Job Tracking (Week 4)

### 4.1: API Client

**File:** `packages/web/src/api/jobs.ts`

Exports: `jobsApi` with `getJob`, `listJobs`, `retryJob`, `acknowledgeJob`, `cancelJob`.

**Effort:** 0.5 days

---

### 4.2: React Query Hooks

**File:** `packages/web/src/hooks/useAnalysisJobs.ts`

Two hooks:
- `useAnalysisJobs(projectId)` — list with dynamic polling (2s active, 30s idle)
- `useJobStatus(jobId)` — single job, polls until completed/failed

**Effort:** 1 day

---

### 4.3: Notifications Store

**File:** `packages/web/src/stores/job-notifications.ts`

Zustand store tracking last 50 notifications, seen/unseen state.

**Effort:** 0.5 days

---

### 4.4: JobTracker Component

**File:** `packages/web/src/components/JobTracker/JobTracker.tsx`

Floating panel (bottom-right) showing:
- Active jobs with progress bars
- Failed jobs with retry button
- Collapsed section for completed jobs
- Per-job cancel/dismiss actions

**Effort:** 2 days

---

### 4.5: Header Badge

**File:** `packages/web/src/components/Header/AnalysisJobsBadge.tsx`

Shows running count + failed count in header. Clicking opens JobTracker.

**Effort:** 0.5 days

---

## Phase 5: Frontend — Issue Display (Week 5)

### 5.1: Generation Hook

**File:** `packages/web/src/hooks/useGenerateWithAnalysis.ts`

Wraps generation mutation + tracks resulting job. Exposes `isAnalyzing`, `analysisProgress`, `analysisComplete`, `analysisIssueCount`.

**Effort:** 1 day

---

### 5.2: Quality Badges

Add to skill/card list rows:

```tsx
{skill.has_quality_issues && (
  <Badge variant="warning" className="gap-1">
    <AlertCircle className="h-3 w-3" />
    {skill.quality_issue_count}
  </Badge>
)}
```

**Effort:** 0.5 days

---

### 5.3-5.4: Issues Panels

**Files:**
- `packages/web/src/features/skills/QualityIssuesPanel.tsx`
- `packages/web/src/features/cards/QualityIssuesPanel.tsx`

Each panel shows:
- Issue category icon + severity color
- Message + line reference (clickable to scroll)
- Suggestion (if available) with "Apply" button
- Dismiss button

**Effort:** 2 days

---

### 5.5: Apply Suggestion Action

For suggestions with rewrite text:
1. Show diff preview (original vs suggested)
2. User confirms
3. Patch artifact content
4. Mark issue as `fixed`
5. Optionally re-analyze

**Effort:** 1.5 days

---

## Phase 6: Polish & Testing (Week 6)

### 6.1: Bulk Re-Analyze

`POST /projects/{id}/quality/reanalyze-all`

Enqueues analysis jobs for all skills + cards. Useful for:
- Existing projects before this feature existed
- After adopting new detector categories
- After updating LLM prompts

**Effort:** 1 day

---

### 6.2: Export Pre-Flight Check

Before export, check for:
- Active analysis jobs → warn "X analyses still running"
- Open `error`-severity issues → warn "X blocking quality issues"

User can:
- Wait for jobs to complete
- Acknowledge and proceed
- Cancel export

**Effort:** 1 day

---

### 6.3: Cleanup Job

Daily Dramatiq scheduled job:
- Auto-acknowledge completed jobs older than 7 days
- Delete acknowledged jobs older than 30 days
- Keep issues (they're attached to artifacts)

**Effort:** 0.5 days

---

### 6.4: Tests

- Unit tests for each detector (mock LLM, verify parsing)
- Integration test for full pipeline (generate → job → issues)
- API tests for jobs endpoints
- Frontend: test hooks with mock responses

**Effort:** 2 days

---

### 6.5: Documentation

Update:
- `SPEC.md` — add quality analysis section
- `docs/project-analysis.html` — add tab for quality analysis
- User-facing: how to interpret each issue category

**Effort:** 0.5 days

---

## Summary Table

| Phase | Duration | Key Deliverables |
|---|---|---|
| 1: Backend Foundation | Week 1 | Schema, models, jobs API, CLI |
| 2: Analyzer Engine | Week 2 | 5 detectors + LLM prompts |
| 3: Dramatiq Job | Week 3 | Worker, progress tracking, integration |
| 4: Frontend Job Tracking | Week 4 | API client, hooks, JobTracker UI |
| 5: Frontend Issue Display | Week 5 | Issues panels, badges, apply actions |
| 6: Polish & Testing | Week 6 | Bulk re-analyze, pre-flight, tests, docs |

**Total: 6 weeks**

---

## Dependencies

```
Phase 1 (Backend foundation)
    │
    ▼
Phase 2 (Analyzer engine) ────┐
    │                          │
    ▼                          │
Phase 3 (Dramatiq job) ◄───────┘
    │
    ▼
Phase 4 (Frontend tracking) ───┐
    │                          │
    ▼                          │
Phase 5 (Frontend issues) ◄────┘
    │
    ▼
Phase 6 (Polish & testing)
```

Phase 4 can start in parallel with Phase 2 (frontend doesn't depend on detector logic, only the job API from Phase 1).

---

## Risk & Mitigations

| Risk | Mitigation |
|---|---|
| Analysis LLM costs balloon | Track per-job tokens in `llm_runs`; add per-project monthly quota |
| Detector prompts produce false positives | Start with `info` severity; iterate based on dismissed counts |
| Polling overhead with many open tabs | Use exponential backoff when idle; pause polling when tab hidden |
| Worker queue backed up | Add separate Dramatiq queue for analysis (`quality_analysis`); scale workers independently |
| User overwhelmed by issues | Default-collapse completed jobs; group issues by category in panel |

---

## Configuration

Add to `packages/core/app/config.py`:

```python
class QualityAnalysisSettings(BaseSettings):
    enabled: bool = True
    auto_analyze_on_generation: bool = True

    enabled_detectors: list[str] = [
        'contradiction',
        'ambiguity',
        'cognitive_load',
        'coverage_gap',
        'composition_conflict',
    ]

    job_max_attempts: int = 3
    job_time_limit_seconds: int = 120

    cleanup_acknowledged_after_days: int = 30
    auto_acknowledge_after_days: int = 7
```

Per-project override possible via `projects.quality_analysis_config` JSONB column (future).

---

## Quick Start (Week 1)

1. Create migration with `analysis_jobs` + `prompt_quality_issues` tables
2. Add quality flag columns to `skills` and `cards`
3. Build `AnalysisJob` SQLAlchemy model
4. Stub `/jobs` API endpoints (return empty lists for now)
5. Verify migrations apply cleanly
