# Agents Workshop — MVP Specification

**Status:** **Approved** (v2) · **Scope:** P1 (CLI core) + P2 (minimal web UI)
**Approved on:** 2026-05-11

> Source of truth for the planning phase. Edits live as PRs against this file. Code does not land until this doc is signed off.

---

## Changelog v1 → v2

Major additions and changes versus v1:

| Area | v1 | v2 |
|---|---|---|
| Information input | Single "Objective" text + raw artifact uploads | Four discovery channels: objective, Q&A wizard, tech panorama, artifacts (§4.5) |
| Tech panorama | Not modeled | New tables `tech_dimensions`, `tech_items`, `project_tech_choices` (§4.2) + curated seed catalog (§12.2) + LLM-suggested mode (§7.5) |
| Q&A wizard | Not modeled | New table `project_qa_answers` with 7 questions, first 3 required (§4.2, §11.2) |
| Artifact uploads | Sync, markdown only | **Always async** via Dramatiq + Redis worker (§7a); extractors for PDF, DOCX, MD, TXT, CSV, code files |
| LLM provider default | All three configured | **Anthropic only** as default; OpenAI + Ollama opt-in (§6) |
| LLM reasoning capture | Not addressed | Schema + interface in MVP, providers wired in P3 (§6.4, §7.4) |
| LLM model storage | Env-only | **Columns on `projects`** (`llm_provider`, `llm_model`, `llm_temperature`) + Settings UI (§4.2) |
| Card code prefix | User-chosen | **Auto-derived from slug** (§4.2) |
| Skill `kind: context` | Exactly one per project | **0–N**, no enforcement (§8) |
| Analyzer-skill resources | Warning *(default)* | Confirmed: **warning, not block** (§8) |
| Open questions | 8 unresolved | All 16 resolved (§16) |
| Repo layout | api + web only | Adds `redis` + `worker` services (§3, §13) |
| LLM prompts | 4 | 5 (added `SuggestTechStack`) (§7) |

---

## Table of contents

1. [Product summary](#1-product-summary)
2. [End-to-end workflow](#2-end-to-end-workflow)
3. [Architecture overview](#3-architecture-overview)
4. [Domain model](#4-domain-model)
5. [Template-family contract](#5-template-family-contract)
6. [LLM provider abstraction](#6-llm-provider-abstraction)
7. [The five LLM prompts](#7-the-five-llm-prompts)
8. [Async job orchestration](#8-async-job-orchestration)
9. [Deterministic validators](#9-deterministic-validators)
10. [Export pipeline](#10-export-pipeline)
11. [CLI surface (P1)](#11-cli-surface-p1)
12. [Web UI surface (P2)](#12-web-ui-surface-p2)
13. [Seed data](#13-seed-data)
14. [Repository layout](#14-repository-layout)
15. [Configuration & secrets](#15-configuration--secrets)
16. [Non-goals (MVP out-of-scope)](#16-non-goals-mvp-out-of-scope)
17. [Open questions — resolved](#17-open-questions--resolved)
18. [Sign-off](#18-sign-off)

---

## 1. Product summary

**Agents Workshop** is a tool that, given a programming objective plus structured discovery inputs, produces the `.agents/` contract for that project — a coherent **skill library** plus a **phase-organized backlog of Jira cards** that AI agents (Cursor, Claude Code, Gemini CLI) and humans can execute one card per session.

It is not a code generator for the target project. It generates the *agent contract* that other agents then use.

**Primary user persona:** an architect / engineering lead bootstrapping a new PoC who wants the skill+card scaffolding produced consistently across projects without copy-pasting from previous repos.

**MVP success criteria:**
- Create a project, run discovery, propose a skill set, draft each skill body, propose a phase-based backlog, draft each card body, validate the graph, export the `.agents/` folder to disk — all from CLI and from the web UI.
- A second user can `git clone` the exported `.agents/` folder into a Cursor workspace and immediately have a working skill-driven backlog without any further editing.
- Three reference PoCs (Caixa-2, Enel, VLI) are loaded as seed data and serve as few-shot exemplars for the LLM prompts.

---

## 2. End-to-end workflow

```
┌─────────────────────────────────────────┐
│ 1. Discovery                            │
│    1a. Objective paragraph              │
│    1b. Q&A wizard (3 required + 4 opt.) │
│    1c. Tech panorama picker             │
│    1d. Artifact upload (async extract)  │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│ 2. ProposeSkillSet (LLM)                │
│    proposes 5–10 skills; user curates   │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│ 3. DraftSkillBody × N (LLM, one/skill)  │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│ 4. ProposeBacklog (LLM)                 │
│    phases + cards with deps & gates     │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│ 5. DraftCard × N (LLM, one/card)        │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│ 6. Validate (deterministic)             │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│ 7. Export → .agents/{skills,jira-cards} │
└─────────────────────────────────────────┘
```

Every step is **resumable** and **rerunnable**: drafts go to DB, user edits stay, regenerating preserves user-overridden fields unless `--force` is passed.

---

## 3. Architecture overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              agents-workshop                                  │
│                                                                               │
│   ┌──────────────────────┐         ┌─────────────────────────────────┐       │
│   │  packages/web        │  HTTP   │  packages/core (FastAPI)        │       │
│   │  Next.js 14 + shadcn │ ──────► │  - api/  (routers)              │       │
│   │  React Flow + Monaco │  REST   │  - domain/                      │       │
│   └──────────────────────┘         │  - llm/  (provider abstraction) │       │
│                                     │  - prompts/                     │       │
│   ┌──────────────────────┐         │  - templates/                   │       │
│   │  packages/cli        │  Python │  - validators/                  │       │
│   │  Typer commands      │ ──────► │  - exporters/                   │       │
│   └──────────────────────┘  import │  - families/                    │       │
│                                     │  - jobs/ (Dramatiq actors)      │       │
│                                     │  - extractors/ (markitdown…)   │       │
│                                     └──────────┬──────────────────────┘       │
│                                                │ SQLAlchemy / Dramatiq        │
│                                     ┌──────────▼──────────────────────┐      │
│                                     │ Postgres 16   │   Redis 7        │      │
│                                     │ Alembic       │   broker + cache │      │
│                                     └──────────────────────────────────┘      │
│                                                ▲                              │
│                                     ┌──────────┴──────────────────────┐      │
│                                     │  worker (Dramatiq)              │      │
│                                     │  - artifact_extract             │      │
│                                     │  - (future) async_llm_call      │      │
│                                     └─────────────────────────────────┘      │
│                                                                               │
│   ┌──────────────────────┐         ┌─────────────────────────────────┐       │
│   │  data/projects/<id>/ │ ◄─────► │  exporters write target files   │       │
│   │  artifacts/  exports/│  files  │  here (or to user-chosen path)  │       │
│   └──────────────────────┘         └─────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Runtime topology** (docker-compose):

| Service | Image / build | Port | Notes |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | 5432 | Volume-backed, default DB `workshop` |
| `redis` | `redis:7-alpine` | 6379 | Broker + light cache |
| `api` | `packages/core` (FastAPI + uvicorn) | 8000 | Hot-reload in dev |
| `worker` | `packages/core` (Dramatiq workers) | — | Same image as api, different entrypoint |
| `web` | `packages/web` (Next.js) | 3000 | Hot-reload in dev |
| `ollama` *(optional)* | `ollama/ollama` | 11434 | Off by default; enabled via compose profile `ollama` |

CLI runs locally (no container), connects to the same Postgres + Redis.

---

## 4. Domain model

### 4.1 Entity-relationship diagram

```
users (1) ─────── owns ──────────► (N) projects
tenants (1) ───── contains ──────► (N) projects
projects (1) ──── has many ──────► (N) project_artifacts
projects (1) ──── has many ──────► (N) project_qa_answers
projects (1) ──── has many ──────► (N) project_tech_choices
projects (1) ──── has many ──────► (N) skills
projects (1) ──── has many ──────► (N) phases
projects (1) ──── has many ──────► (N) llm_runs
projects (1) ──── has many ──────► (N) exports

tech_dimensions (1) ── contains ─► (N) tech_items
tech_items (1) ─ referenced by ──► (N) project_tech_choices

skills (1) ─────── has many ─────► (N) skill_resources
phases (1) ─────── has many ─────► (N) cards
cards  (N) ──── many-to-many ────► (N) skills        via card_skills
cards  (N) ──── self-many-many ──► (N) cards (deps)  via card_deps
cards  (1) ─────── has many ─────► (N) card_inputs
```

### 4.2 Tables, fields, types

Naming: snake_case, plural tables, `id` is `UUID PRIMARY KEY DEFAULT gen_random_uuid()`. Timestamps are `TIMESTAMPTZ`.

#### `users`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| email | TEXT UNIQUE NOT NULL | |
| name | TEXT NOT NULL | |
| role | TEXT NOT NULL DEFAULT `'owner'` | reserved for future RBAC |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |

In MVP we seed one user (`local@workshop`) and stamp all rows with that ID.

#### `tenants`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | TEXT NOT NULL | |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |

#### `projects`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| tenant_id | UUID FK → tenants | |
| owner_user_id | UUID FK → users | |
| slug | TEXT NOT NULL | URL-safe, unique per tenant |
| name | TEXT NOT NULL | |
| objective | TEXT NOT NULL | one-paragraph intent |
| context_md | TEXT | accumulated by the system (Q&A + tech choices + artifact summaries) |
| card_code_prefix | TEXT NOT NULL | derived from slug at project creation (uppercase, 3–5 chars); editable in Settings |
| card_template | TEXT NOT NULL DEFAULT `'phase_vli'` | family slug; only `phase_vli` valid in MVP |
| grouping | TEXT NOT NULL DEFAULT `'phase'` | `'phase'` \| `'epic'` \| `'flat'`; constrained by family |
| status | TEXT NOT NULL DEFAULT `'draft'` | `'draft'` \| `'in_progress'` \| `'exported'` \| `'archived'` |
| llm_provider | TEXT NOT NULL DEFAULT `'anthropic'` | per-project override |
| llm_model | TEXT NOT NULL DEFAULT `'claude-sonnet-4-5'` | per-project override |
| llm_temperature | NUMERIC(3,2) NOT NULL DEFAULT `0.20` | |
| llm_enable_reasoning | BOOLEAN NOT NULL DEFAULT false | provider must support; ignored in MVP |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| updated_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| UNIQUE (tenant_id, slug) | | |

**Card code prefix derivation** (deterministic, computed at project creation):
1. Split slug by `-` or `_`.
2. Take the first letter of each token, uppercase.
3. If result is shorter than 3 chars, append additional letters from the first token until ≥ 3 (e.g. slug `siglm-poc` → `SP` → fallback → `SIGLM`).
4. Truncate to 5 chars.
5. User can edit in Settings; uniqueness across cards in the project is the only constraint.

#### `project_artifacts`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK → projects ON DELETE CASCADE | |
| kind | TEXT NOT NULL | `'doc'` \| `'code'` \| `'spec'` \| `'glossary'` \| `'other'` |
| filename | TEXT NOT NULL | |
| mime_type | TEXT | inferred from upload |
| path | TEXT NOT NULL | relative to `data/projects/<id>/artifacts/` |
| size_bytes | BIGINT NOT NULL | |
| extraction_status | TEXT NOT NULL DEFAULT `'pending'` | `'pending'` \| `'extracting'` \| `'extracted'` \| `'failed'` |
| extraction_error | TEXT | populated when status = `'failed'` |
| extracted_at | TIMESTAMPTZ | |
| extractor_used | TEXT | `'markitdown'` \| `'pdfplumber'` \| `'raw_text'` \| `'csv_to_md'` |
| content_md | TEXT | extracted markdown; NULL until extracted |
| content_md_truncated | BOOLEAN NOT NULL DEFAULT false | when content > 1 MB, store head/tail with marker |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |

Hybrid storage: original binary always lives on disk; extracted text up to 1 MB is mirrored into `content_md`. Larger content is truncated to head 500 KB + tail 500 KB with a `... [truncated, N bytes omitted] ...` marker.

#### `project_qa_answers`

| Column | Type | Notes |
|---|---|---|
| project_id | UUID FK → projects ON DELETE CASCADE | |
| question_key | TEXT NOT NULL | enum: see §11.2 |
| answer_md | TEXT NOT NULL | |
| updated_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| PRIMARY KEY (project_id, question_key) | | |

The seven question keys: `business_problem`, `success_definition`, `users_and_actors`, `must_preserve`, `must_change`, `compliance`, `known_gaps`. Required to create the project: first three.

#### `tech_dimensions` (seeded; user may add custom dimensions in Settings, P3+)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| slug | TEXT UNIQUE NOT NULL | e.g. `'backend_framework'` |
| name | TEXT NOT NULL | display name e.g. `'Frameworks backend'` |
| description | TEXT | |
| order_no | INTEGER NOT NULL DEFAULT 0 | |

#### `tech_items` (seeded; user-added items have `is_custom=true`)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| dimension_id | UUID FK → tech_dimensions | |
| slug | TEXT NOT NULL | e.g. `'fastapi'` |
| name | TEXT NOT NULL | e.g. `'FastAPI'` |
| description | TEXT | |
| tags | TEXT[] | e.g. `['python','async','rest']` |
| is_custom | BOOLEAN NOT NULL DEFAULT false | true for user-added items |
| created_by_user_id | UUID FK → users | NULL for seed items |
| UNIQUE (dimension_id, slug) | | |

#### `project_tech_choices`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK → projects ON DELETE CASCADE | |
| dimension_id | UUID FK → tech_dimensions | |
| tech_item_id | UUID FK → tech_items | NULL when `role='tbd'` (dimension marked but no item) |
| role | TEXT NOT NULL | `'target'` \| `'legacy'` \| `'optional'` \| `'must_avoid'` \| `'tbd'` |
| source | TEXT NOT NULL DEFAULT `'catalog'` | `'catalog'` \| `'user_added'` \| `'llm_suggested'` |
| accepted | BOOLEAN NOT NULL DEFAULT true | flipped to true when user accepts an LLM suggestion |
| llm_rationale | TEXT | populated when source = `'llm_suggested'` |
| llm_confidence | NUMERIC(3,2) | 0.00–1.00, populated by LLM |
| notes | TEXT | free-text user note |
| order_no | INTEGER NOT NULL DEFAULT 0 | per (project, dimension) ordering |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| UNIQUE (project_id, dimension_id, tech_item_id) | partial: `WHERE tech_item_id IS NOT NULL` |

#### `skills`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK → projects ON DELETE CASCADE | |
| slug | TEXT NOT NULL | kebab-case, used in folder name |
| name | TEXT NOT NULL | YAML frontmatter `name` |
| description | TEXT NOT NULL | YAML frontmatter `description` (trigger-rich) |
| kind | TEXT NOT NULL | `'context'` \| `'authoring'` \| `'analyzer'` \| `'procedure'` |
| body_md | TEXT NOT NULL DEFAULT `''` | SKILL.md body below frontmatter |
| order_no | INTEGER NOT NULL DEFAULT 0 | |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| updated_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| UNIQUE (project_id, slug) | | |

#### `skill_resources`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| skill_id | UUID FK → skills ON DELETE CASCADE | |
| filename | TEXT NOT NULL | e.g. `merge-patterns.md` |
| content | TEXT NOT NULL | |
| language | TEXT NOT NULL DEFAULT `'markdown'` | `'markdown'` \| `'sql'` \| `'yaml'` \| `'python'` \| `'plain'` |
| order_no | INTEGER NOT NULL DEFAULT 0 | |
| UNIQUE (skill_id, filename) | | |

#### `phases` (or epics — family decides label)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK → projects ON DELETE CASCADE | |
| code | TEXT NOT NULL | e.g. `phase-1-discovery` |
| name | TEXT NOT NULL | display name |
| description_md | TEXT | |
| order_no | INTEGER NOT NULL DEFAULT 0 | |
| UNIQUE (project_id, code) | | |

#### `cards`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| phase_id | UUID FK → phases ON DELETE CASCADE | |
| code | TEXT NOT NULL | e.g. `SIGLM-101` (project.card_code_prefix + sequence) |
| title | TEXT NOT NULL | |
| type | TEXT NOT NULL | `'Task'` \| `'Story'` \| `'Bug'` \| `'Spike'` \| `'Demo'` |
| story_points | INTEGER | nullable |
| priority | TEXT | `'Low'` \| `'Medium'` \| `'High'` |
| status | TEXT NOT NULL DEFAULT `'draft'` | `'draft'` \| `'ready'` \| `'in_progress'` \| `'done'` |
| human_gate | BOOLEAN NOT NULL DEFAULT false | |
| human_gate_checklist_md | TEXT | when `human_gate=true` |
| context_md | TEXT | |
| task_md | TEXT | |
| outputs_md | TEXT | |
| acceptance_criteria_md | TEXT | |
| order_no | INTEGER NOT NULL DEFAULT 0 | |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| updated_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| UNIQUE (phase_id, code) | also UNIQUE within project, enforced at app level | |

Body fields are kept as separate markdown columns (not a single blob) so:
- The Jinja2 template can stamp each section into its named heading.
- Validators can act on a single section without parsing.
- The editor can offer per-section diff and per-section regenerate.

#### `card_skills` (ordered many-to-many)

| Column | Type | Notes |
|---|---|---|
| card_id | UUID FK → cards ON DELETE CASCADE | |
| skill_id | UUID FK → skills ON DELETE RESTRICT | RESTRICT prevents deleting a skill referenced by cards |
| position | INTEGER NOT NULL | |
| PRIMARY KEY (card_id, skill_id) | | |

#### `card_deps` (DAG edges)

| Column | Type | Notes |
|---|---|---|
| card_id | UUID FK → cards ON DELETE CASCADE | the dependent |
| depends_on_card_id | UUID FK → cards ON DELETE RESTRICT | the predecessor |
| relation | TEXT NOT NULL DEFAULT `'depends_on'` | `'depends_on'` \| `'parallel_with'` |
| PRIMARY KEY (card_id, depends_on_card_id, relation) | | |

#### `card_inputs`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| card_id | UUID FK → cards ON DELETE CASCADE | |
| kind | TEXT NOT NULL | `'skill_resource'` \| `'artifact'` \| `'external'` |
| path | TEXT NOT NULL | resolved relative to `.agents/` or `data/` |
| label | TEXT | |
| order_no | INTEGER NOT NULL DEFAULT 0 | |

#### `llm_runs` (audit log + reasoning capture)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK → projects | NULL allowed for project-creation prompts |
| kind | TEXT NOT NULL | `'propose_skill_set'` \| `'draft_skill_body'` \| `'propose_backlog'` \| `'draft_card'` \| `'suggest_tech'` \| `'other'` |
| provider | TEXT NOT NULL | `'anthropic'` \| `'openai'` \| `'ollama'` |
| model | TEXT NOT NULL | |
| prompt_messages_json | JSONB NOT NULL | full message array sent |
| response_text | TEXT | raw assistant message |
| response_json | JSONB | parsed structured output |
| reasoning_md | TEXT | provider reasoning trace (P3+; NULL in MVP) |
| reasoning_tokens | INTEGER | |
| reasoning_truncated | BOOLEAN NOT NULL DEFAULT false | |
| extended_thinking_enabled | BOOLEAN NOT NULL DEFAULT false | per-run flag |
| tokens_in | INTEGER | |
| tokens_out | INTEGER | |
| cost_usd | NUMERIC(10,6) | |
| status | TEXT NOT NULL | `'success'` \| `'parse_error'` \| `'provider_error'` |
| error | TEXT | |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |

#### `exports`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK → projects ON DELETE CASCADE | |
| kind | TEXT NOT NULL | `'filesystem'` \| `'zip'` \| `'jira_csv'` |
| target_path | TEXT | absolute path or NULL for zip |
| manifest_json | JSONB NOT NULL | files written with sizes and SHA256 |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |

### 4.3 Indexes

- `cards(phase_id, order_no)`
- `cards(code)` — cross-phase lookup
- `card_deps(depends_on_card_id)` — used in topological sort
- `llm_runs(project_id, created_at DESC)` — audit log UI
- `project_artifacts(project_id, extraction_status)` — UI filters
- `project_tech_choices(project_id, dimension_id, order_no)` — picker rendering
- `tech_items(dimension_id, name)` — autocomplete

### 4.4 Lifecycle / state transitions

```
project.status:
   draft ──► in_progress ──► exported ──► archived
                 ▲                │
                 └────────────────┘  (re-edit after export flips back)

card.status:
   draft ──► ready ──► in_progress ──► done

project_artifacts.extraction_status:
   pending ──► extracting ──► extracted
                          └─► failed
```

### 4.5 Input channels — how discovery feeds the LLM context

```
┌─────────────────┐
│ Objective text  │ ────────────────┐
│ (paragraph)     │                  │
└─────────────────┘                  │
                                      │
┌─────────────────┐                  │
│ Q&A wizard      │ ────────────────┤
│ 3 required +    │                  │
│ 4 optional      │                  │
└─────────────────┘                  │
                                      ├──► project.objective + project.context_md
┌─────────────────┐                  │       (auto-assembled by the system)
│ Tech panorama   │                  │
│ - catalog picks │ ────────────────┤
│ - user-added    │                  │       project_tech_choices
│ - LLM-suggested │                  │       (also queried directly by prompts)
│ - TBD per dim   │                  │
└─────────────────┘                  │
                                      │
┌─────────────────┐                  │
│ Artifact upload │   async extract  │
│ PDF/DOCX/MD/    │ ───── markitdown ┘       project_artifacts.content_md
│ TXT/CSV/code    │       pdfplumber          (head/tail-truncated to 1 MB)
└─────────────────┘
```

**Context assembly for LLM prompts:**

Every prompt that needs project context builds a structured **`ProjectContext`** payload in this exact shape:

```python
class ProjectContext(BaseModel):
    objective: str
    qa: dict[str, str]                       # question_key → answer_md
    tech_choices_by_dimension: dict[str, list[TechChoiceView]]
    artifact_summaries: list[ArtifactSummary]   # filename + first 2000 chars
    context_notes_md: str                       # free-form notes appended over time
```

The prompts render this into a single user-message context block (see §7).

---

## 5. Template-family contract

### 5.1 Abstract base

```python
# packages/core/app/families/_base.py

class CardDraftContext(BaseModel):
    project: ProjectView
    project_context: ProjectContext
    phase: PhaseView
    card: CardView
    skills_used: list[SkillView]
    sibling_cards_in_phase: list[CardView]
    upstream_cards: list[CardView]

class TemplateFamily(ABC):
    slug: str
    display_name: str
    grouping: Literal["phase", "epic", "flat"]
    grouping_label_singular: str
    grouping_label_plural: str
    card_filename_pattern: str
    grouping_folder_pattern: str

    @abstractmethod
    def render_card(self, card: CardView) -> str: ...
    @abstractmethod
    def render_grouping_readme(self, ctx: GroupingReadmeContext) -> str: ...
    @abstractmethod
    def render_project_readme(self, ctx: ProjectReadmeContext) -> str: ...
    @abstractmethod
    def draft_card_prompt(self, ctx: CardDraftContext) -> ChatPrompt: ...
    @abstractmethod
    def few_shot_card_examples(self) -> list[CardExample]: ...
    @abstractmethod
    def propose_backlog_prompt(self, ctx: BacklogProposalContext) -> ChatPrompt: ...
    @abstractmethod
    def validate_card(self, card: CardView, project: ProjectView) -> list[ValidationError]: ...
    @abstractmethod
    def validate_project(self, project: ProjectView) -> list[ValidationError]: ...
```

### 5.2 PhaseVliFamily (MVP)

- `grouping = "phase"`; labels `"Phase"`/`"Phases"`.
- Card filename: `{code}-{title-slug}.md` (e.g. `SIGLM-101-ssis-package-analyzer.md`).
- Phase folder: `phase-{order}-{slug}` (e.g. `phase-1-discovery`).
- Card sections, in order:
  1. `# {code} — {title}`
  2. `## Context`
  3. `## Skill to invoke` (resolved as `` `.agents/skills/<slug>/SKILL.md` ``)
  4. `## Inputs` (from `card_inputs`)
  5. `## Task`
  6. `## Outputs`
  7. `## Acceptance criteria`
  8. `## Depends on`
  9. `## Can run in parallel with`
  10. `## Human gate after this card`

Validation rules:
- Every card must have ≥ 1 `card_skill`.
- Every `card_input.kind='skill_resource'` must reference an existing resource on a skill in `card_skills`.
- `Depends on` must respect phase order (no forward-phase deps).
- Last card of each phase **should** have `human_gate=true` (warning).

### 5.3 Registry & wiring

```python
TEMPLATE_REGISTRY: dict[str, TemplateFamily] = {
    "phase_vli": PhaseVliFamily(),
    # "strict_9":  Strict9Family(),   # P5+
    # "free_form": FreeFormFamily(),  # P5+
}

def get_family(slug: str) -> TemplateFamily:
    if slug not in TEMPLATE_REGISTRY:
        raise ValueError(f"Unknown template family: {slug}")
    return TEMPLATE_REGISTRY[slug]
```

Adding a new family = create `families/<slug>/family.py`, register. Zero API/CLI/web/schema changes.

---

## 6. LLM provider abstraction

### 6.1 Defaults

| Item | Default |
|---|---|
| Provider | `anthropic` |
| Model | `claude-sonnet-4-5` |
| Temperature | `0.20` |
| Reasoning | `false` (schema accepts it, providers ignore in MVP) |

OpenAI and Ollama are wired but **not the default**. Their `chat()` requires the corresponding API key / base URL to be configured; otherwise they raise `ProviderNotConfigured`.

### 6.2 Interfaces

```python
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class ChatPrompt(BaseModel):
    messages: list[ChatMessage]
    response_schema: type[BaseModel] | None = None
    temperature: float = 0.2
    max_tokens: int = 4000
    enable_reasoning: bool = False                # accepted in MVP, ignored
    reasoning_budget_tokens: int | None = None

class ChatResult(BaseModel):
    text: str
    parsed: BaseModel | None
    reasoning: str | None = None                  # P3+; always None in MVP
    reasoning_tokens: int | None = None
    reasoning_truncated: bool = False
    tokens_in: int
    tokens_out: int
    cost_usd: float
    model: str
    provider: str

class LLMProvider(ABC):
    name: str
    @abstractmethod
    def chat(self, prompt: ChatPrompt, model: str) -> ChatResult: ...
```

### 6.3 Provider implementations (MVP)

| Provider | Default model | Structured output | Reasoning support (P3) |
|---|---|---|---|
| Anthropic | `claude-sonnet-4-5` | tool-use call with the schema, parse from `tool_use` block | Extended Thinking via `thinking: { type: "enabled", budget_tokens: N }` |
| OpenAI | `gpt-5` | JSON mode + `response_format` | reasoning models expose `reasoning_summary` |
| Ollama | `llama3.1:8b` | none — "respond with JSON inside ` ```json ... ``` `" + lenient parser | post-parse `<think>...</think>` in raw text |

### 6.4 Reasoning capture — MVP behavior, P3 plan

In MVP every provider accepts `enable_reasoning=True` but **does nothing with it**; `ChatResult.reasoning` stays `None`. The schema columns `llm_runs.reasoning_*` are added now so we never have to migrate.

In P3 each provider wires its native channel; UI gets a **collapsed** "Show thinking" expander on `/projects/[slug]/llm-runs/[id]` and on per-section regenerate panels.

### 6.5 `LLMService.run()`

Single entry point — every call goes through it:

```
1. Resolve provider + model (per-call → per-project columns → env default).
2. Insert llm_runs row with status='in_progress'.
3. Provider.chat(prompt, model).
4. On success: parse, update row (success / parse_error), return ChatResult.
5. On exception: update row (provider_error), re-raise.
6. Cost is computed from pricing.py (per-model rate × tokens), NEVER from provider response.
```

---

## 7. The five LLM prompts

All five prompts share the same skeleton:

```
[system]
You are an expert in <role>. <method statement>.
You produce structured output that conforms to the schema given by the user.
You never fabricate file paths, skill names, or card codes that were not in the context.

[user]
<ProjectContext block>
<task-specific context>
<task instruction>
<output format reminder>
```

Structured output is enforced via Pydantic schemas. Each prompt has 2–3 few-shot examples drawn from the three reference PoCs.

### 7.1 `ProposeSkillSet`

**Input:** `ProjectContext` (full).
**Output:**

```python
class ProposedSkill(BaseModel):
    slug: str
    name: str
    description: str
    kind: Literal["context", "authoring", "analyzer", "procedure"]
    rationale: str
    sibling_refs: list[str]

class ProposedSkillSet(BaseModel):
    skills: list[ProposedSkill]    # 5–10
    coverage_notes: str
    gaps: list[str]
```

**Few-shot mapping:** Caixa-2 `siglm-context` + `siglm-cobol-to-rules`; VLI `ssis-package-analyzer`; Enel `add-full-stack-feature`.

### 7.2 `DraftSkillBody`

**Input:** target `ProposedSkill` + `ProjectContext.objective` + `tech_choices_by_dimension` (compact) + sibling skill slugs+descriptions (no bodies).
**Output:**

```python
class DraftedSkillBody(BaseModel):
    body_md: str
    resources: list[DraftedResource]
    sibling_skills_referenced: list[str]

class DraftedResource(BaseModel):
    filename: str
    language: Literal["markdown", "sql", "yaml", "python", "plain"]
    content: str
    purpose: str
```

Per kind, the system message biases resource generation:
- `context` → 0 resources.
- `authoring` → 0–1 resources.
- `analyzer` → 2–6 resources (templates, decision frameworks, code/SQL skeletons).
- `procedure` → 1–4 resources (reusable code/query skeletons).

### 7.3 `ProposeBacklog`

**Input:** `ProjectContext` + full skill list (slug + name + description + kind).
**Output:**

```python
class ProposedCard(BaseModel):
    code: str
    title: str
    type: Literal["Task", "Story", "Bug", "Spike", "Demo"]
    story_points: int
    skill_slugs: list[str]
    depends_on_codes: list[str]
    parallel_with_codes: list[str]
    human_gate: bool
    short_scope_summary: str

class ProposedPhase(BaseModel):
    code: str
    name: str
    description: str
    cards: list[ProposedCard]

class ProposedBacklog(BaseModel):
    phases: list[ProposedPhase]
    rationale_md: str
    critical_path_codes: list[str]
```

Rules in the system message: per-phase human gate at the end; no forward-phase deps; codes use `<project.card_code_prefix>-<phase_index><card_index>` (e.g. `SIGLM-101`).

### 7.4 `DraftCard`

**Input:** `CardDraftContext` (card + bodies of invoked skills + upstream card titles + project context).
**Output:**

```python
class DraftedCardInput(BaseModel):
    kind: Literal["skill_resource", "artifact", "external"]
    path: str
    label: str | None

class DraftedCard(BaseModel):
    context_md: str
    task_md: str
    outputs_md: str
    acceptance_criteria_md: str
    human_gate_checklist_md: str | None
    inputs: list[DraftedCardInput]
```

The family's `draft_card_prompt()` injects family-specific instructions (paths, sections).

### 7.5 `SuggestTechStack` (per-dimension, on-demand)

**Triggered by:** "Suggest with AI" button on a single tech dimension card.
**Input:**

```python
class SuggestTechContext(BaseModel):
    project_context: ProjectContext
    target_dimension: TechDimensionView          # slug + name + description
    existing_choices_in_dimension: list[TechChoiceView]
    catalog_items: list[TechItemView]            # all known items in this dimension (slim)
```

**Output:**

```python
class SuggestedTechItem(BaseModel):
    catalog_slug: str | None            # match an existing catalog item if possible
    free_form_name: str | None          # else propose a new free-form item
    role: Literal["target", "legacy", "optional", "must_avoid", "tbd"]
    rationale: str
    confidence: float                   # 0.0–1.0

class SuggestedTechForDimension(BaseModel):
    dimension_slug: str
    items: list[SuggestedTechItem]      # typically 2–5
    reasoning_summary: str
```

**Persistence flow:** API receives suggestions → inserts `project_tech_choices` rows with `source='llm_suggested'`, `accepted=false`, `llm_rationale`, `llm_confidence` → UI shows ✨-badged chips → user clicks accept → `accepted=true`.

---

## 8. Async job orchestration

Dramatiq + Redis from day one (per "always async" decision).

### 8.1 Jobs in MVP

| Actor | Trigger | Idempotency |
|---|---|---|
| `extract_artifact(artifact_id)` | After upload row inserted (status=`'pending'`) | Yes — sets row to `'extracting'`; refuses if already `'extracting'` or `'extracted'` |

### 8.2 Artifact extraction lifecycle

```
HTTP POST /api/projects/{id}/artifacts (multipart)
   │
   ▼
1. Save file to data/projects/<id>/artifacts/<uuid>-<filename>
2. INSERT project_artifacts(... status='pending')
3. dramatiq.send(extract_artifact, artifact_id=<uuid>)
4. Return 202 with artifact_id and polling URL
   │
   ▼ (worker process)
5. UPDATE status='extracting', extractor_used=<chosen>
6. Run extractor:
   - PDF        → markitdown (primary); pdfplumber (fallback)
   - DOCX       → markitdown
   - MD / TXT   → read as-is
   - CSV        → csv_to_md formatter
   - code files → wrap in ```{lang} fence
7. Truncate content_md if > 1 MB (head 500 KB + tail 500 KB + marker)
8. UPDATE status='extracted', content_md=..., extracted_at=now()
   │ on exception:
   ▼
9. UPDATE status='failed', extraction_error=<short msg>
```

### 8.3 Polling and UI

- `GET /api/artifacts/{id}` returns the full row including status.
- The web upload widget polls every 1500 ms (with exponential backoff after 30 s) until `'extracted'` or `'failed'`.
- The CLI `workshop artifact upload <path>` blocks by default (polls internally), with `--no-wait` to return immediately.

### 8.4 Failure semantics

- Failed extractions surface as a banner on `/projects/[slug]/artifacts` with a "Retry" button (re-enqueues the job).
- A failed extraction never blocks LLM prompts — the artifact simply contributes nothing to context until re-extracted or removed.

### 8.5 Future async jobs (out of MVP)

- `async_llm_call` — for slow generations users want to dispatch and forget.
- `async_export` — for large exports.
- `import_existing_agents_folder` — P3 re-import feature.

These follow the same actor + status-column pattern.

---

## 9. Deterministic validators

| Check | Severity | Detail |
|---|---|---|
| Skill slug unique within project | Error | DB UNIQUE |
| Card code unique within project | Error | trigger or app check |
| Card has ≥ 1 skill | Error | phase-VLI rule |
| All `depends_on` resolve | Error | every code exists in same project |
| No DAG cycles | Error | Kahn's algorithm; report cycle path |
| Forward-phase dependency | Error | phase-VLI rule |
| Phase has ≥ 1 card | Warning | |
| Phase ends with `human_gate=true` card | Warning | |
| Skill `kind='analyzer'` has 0 resources | Warning | per §17 |
| Skill reference in body | Warning | body mentions slug not in project |
| Frontmatter required fields | Error | name, description present |
| Description trigger words | Warning | description lacks "use when" / "trigger when" |
| Card input path resolvability | Warning | for `skill_resource` kind |
| Filesystem path safety on export | Error | refuse `..`, absolute paths, control chars |
| Q&A required answered | Error | first 3 questions present (§11.2) |
| Tech panorama has any choice OR any TBD across dimensions | Warning | "you appear to have no tech context — LLM proposals may be generic" |

Validator output: `ValidationIssue { severity, code, message, location }`. CLI prints; web shows side panel with deep links.

---

## 10. Export pipeline

```
1. Advisory lock on project_id.
2. Re-run all validators; abort on any Error.
3. For each skill:
     a. Render YAML frontmatter from name/description.
     b. Concatenate body_md.
     c. Write .agents/skills/<slug>/SKILL.md.
     d. For each skill_resource: write .agents/skills/<slug>/resources/<filename>.
4. For each phase:
     a. Render phase README (Jinja2).
     b. Write .agents/jira-cards/<phase-folder>/README.md.
5. For each card:
     a. Family renders card to a string.
     b. Resolve filename: <code>-<title-slug>.md.
     c. Write .agents/jira-cards/<phase-folder>/<filename>.
6. Render project README with:
     - Skill routing table.
     - Mermaid DAG (top-down; human-gate cards highlighted).
     - Parallelization waves (DAG levels).
   Write .agents/jira-cards/README.md.
7. Build manifest { files: [{path, size, sha256}], generated_at, project_slug }.
8. Write .agents/MANIFEST.json.
9. Record exports row.
10. Release lock.
```

Targets: `filesystem` (in-place write), `zip` (streamed download), `jira_csv` (deferred to P5).

Idempotency: byte-identical output across runs except for `generated_at` in manifest.

---

## 11. CLI surface (P1)

`packages/cli` is a Typer app installed as `workshop`. Commands take `--project <slug>` or read it from `WORKSHOP_PROJECT` env / a `.workshop` file in cwd.

### 11.1 Commands

```
workshop init                                # workspace config
workshop db migrate                          # Alembic
workshop db seed                             # reference PoCs + tech catalog

workshop project new                         # interactive wizard
workshop project list
workshop project show
workshop project edit                        # opens settings (provider, model, temp)
workshop project set-context                 # append free-form context note

workshop qa list
workshop qa set <question_key>               # opens $EDITOR with current answer

workshop tech list                           # show dimensions + current choices
workshop tech pick <dimension> <item_slug> [--role target|legacy|optional|must-avoid]
workshop tech add  <dimension> "<free name>" [--role ...]
workshop tech tbd  <dimension>               # mark dimension as TBD
workshop tech suggest <dimension>            # LLM call

workshop artifact upload <path> [--kind doc|code|spec|glossary] [--no-wait]
workshop artifact list
workshop artifact retry <id>                 # re-enqueue extraction

workshop skill propose                       # LLM
workshop skill list
workshop skill draft <skill-slug>            # LLM
workshop skill show <skill-slug>
workshop skill edit <skill-slug>

workshop backlog propose                     # LLM
workshop phase list
workshop card list [--phase CODE]
workshop card draft <card-code>              # LLM
workshop card show <card-code>
workshop card edit <card-code>

workshop validate                            # all validators, non-zero exit on errors
workshop dag                                 # Mermaid to stdout

workshop export --target filesystem --path /abs/path
workshop export --target zip --out ./project.zip

workshop llm-runs [--kind KIND] [--last N]   # audit log
workshop llm-runs show <id>                  # full prompt + response
```

### 11.2 Q&A wizard — questions

| Key | Prompt | Required |
|---|---|---|
| `business_problem` | What business problem does this project solve? | **Yes** |
| `success_definition` | What does success look like, operationally? | **Yes** |
| `users_and_actors` | Who uses or interacts with this system? (humans, jobs, upstream/downstream systems) | **Yes** |
| `must_preserve` | What legacy behaviors must be preserved exactly? | No |
| `must_change` | What current behaviors are being explicitly modernized or removed? | No |
| `compliance` | Are there regulatory or security constraints? (LGPD, PCI-DSS, banking, etc.) | No |
| `known_gaps` | What is currently unknown or undocumented that the team will need to clarify? | No |

---

## 12. Web UI surface (P2)

Next.js App Router. No multi-tenant chrome in MVP. Routes:

| Route | Purpose |
|---|---|
| `/` | Project list + "New project" |
| `/projects/new` | Wizard: 1) Identity & objective · 2) Q&A · 3) Tech panorama · 4) Artifacts |
| `/projects/[slug]` | Overview, status, setup progress card, next-step CTA |
| `/projects/[slug]/setup` | **Setup Wizard**: 1) Artifacts · 2) Q&A · 3) Tech panorama · 4) Review |
| `/projects/[slug]/qa` | 7-question editor; required fields marked |
| `/projects/[slug]/tech` | Per-dimension cards; chips for choices; "Suggest with AI" / "Add custom" / "Mark TBD" actions |
| `/projects/[slug]/artifacts` | Drop-zone upload, status badges, retry button |
| `/projects/[slug]/skills` | Library grid + "Propose skill set" CTA |
| `/projects/[slug]/skills/[skillSlug]` | Editor: Monaco body + frontmatter form + resources tab |
| `/projects/[slug]/cards` | Backlog grouped by phase + "Propose backlog" CTA |
| `/projects/[slug]/cards/[cardCode]` | Per-section editors with per-section regenerate |
| `/projects/[slug]/dag` | React Flow top-down; click → card drawer |
| `/projects/[slug]/export` | Tree preview, validate, download zip, write to local path |
| `/projects/[slug]/llm-runs` | Audit log with cost totals; expandable rows |
| `/projects/[slug]/llm-runs/[id]` | Full prompt + response; reasoning collapsed (P3) |
| `/settings` | Default provider/model/temperature; API keys status |

### 12.1 Editor conventions

- shadcn/ui primitives, `lucide-react` icons, `next-themes` dark mode.
- TanStack Query for fetching; optimistic mutations.
- Monaco for markdown editing; YAML highlighting in frontmatter pane.
- React Flow 12 for DAG; layout top-down (per §17).
- Auto-save on debounce (1 s).

### 12.2 New-project wizard flow

```
Step 1 — Identity & objective
  • name
  • slug (auto from name, editable)
  • card_code_prefix (auto from slug, editable, 3–5 chars)
  • objective (paragraph)
                ▼
Step 2 — Q&A
  • 3 required questions (business_problem, success_definition, users_and_actors)
  • 4 optional questions (must_preserve, must_change, compliance, known_gaps)
                ▼
Step 3 — Tech panorama
  • All seeded dimensions listed as cards
  • Per dimension: chips picker + "Suggest with AI" + "Add custom" + "Mark TBD"
  • Continue allowed at any state (warning if 0 dimensions answered)
                ▼
Step 4 — Artifacts (optional)
  • Drop-zone; uploads happen async; user can finish creating before extractions complete
                ▼
Project created → /projects/[slug]
```

### 12.3 Setup wizard flow (existing projects)

For existing projects that need to complete discovery, `/projects/[slug]/setup` provides a guided 4-step wizard:

```
Step 1 — Artifacts (optional)
  • Drag & drop upload zone (PDF, DOCX, MD, code files)
  • Auto-detect kind from extension
  • Status badges (pending → extracting → extracted → failed)
  • Retry button for failed extractions
  • Continue allowed regardless of status
                ▼
Step 2 — Q&A (required: first 3)
  • 3 required questions (business_problem, success_definition, users_and_actors)
  • 4 optional questions (must_preserve, must_change, compliance, known_gaps)
  • Auto-save on blur; manual save button
  • Progress bar with completion %
  • Cannot proceed without required questions
                ▼
Step 3 — Tech panorama (optional)
  • Accordion layout for 13 dimensions
  • Chip selection with role dropdown (Target/Legacy/Optional/Avoid/TBD)
  • Search/filter across all items
  • Coverage progress bar
  • Continue allowed at any state
                ▼
Step 4 — Review
  • Summary cards for artifacts, Q&A, tech choices
  • Readiness check via /api/projects/{slug}/qa/readiness
  • "Continue to Skills" button (disabled if not ready)
                ▼
Skills page → /projects/[slug]/skills
```

The project detail page (`/projects/[slug]`) shows a **Setup Progress** card with:
- Completion percentage and progress bar
- Status icons for artifacts, Q&A, tech
- "Continue Setup" or "Review Setup" button

---

## 13. Seed data

### 13.1 Reference PoCs

`workshop db seed` loads three projects (mirroring the analyzed PoCs, scrubbed of proprietary content):

| Slug | Source | Family in MVP | Role |
|---|---|---|---|
| `ref-siglm` | Caixa-2 | `phase_vli` (adapted) | Legacy-modernization skill kinds |
| `ref-cronos` | Enel | `phase_vli` (adapted) | Authoring skill kinds |
| `ref-corp-vli` | VLI | `phase_vli` (native) | Analyzer skill kinds |

Seed content lives in `packages/core/app/seed/reference/<slug>/` as plain `.md`, `.yaml`, `.json` files — the same artifact shape the tool produces. Dogfooding.

### 13.2 Tech catalog seed (`packages/core/app/seed/tech_catalog.yaml`)

Dimensions and items reflect the "Panorama Técnico Consolidado":

| Dimension slug | Display | Sample items |
|---|---|---|
| `languages` | Linguagens | Python, Java, JavaScript, TypeScript, C# (.NET 9), SQL, PL/SQL |
| `backend_framework` | Frameworks backend | Flask, Spring Boot, Quarkus, FastAPI, Express.js, .NET 9 |
| `frontend_framework` | Frameworks frontend | React 18, Angular 18, Angular 21, Vite |
| `messaging` | Mensageria | Apache Kafka, RabbitMQ, AWS SQS |
| `database` | Banco de dados | PostgreSQL, MySQL, Oracle, DB2, DynamoDB, Redis |
| `cloud_infra` | Cloud & infra | Azure (Key Vault, DevOps, ARM), AWS (S3, SQS, DynamoDB), Docker, Kubernetes |
| `architecture_patterns` | Padrões de arquitetura | Microserviços, DDD, Clean Architecture, Event-Driven, Pass-through API, Batch Processing, ETL |
| `observability` | Observabilidade | OpenTelemetry, Prometheus, Grafana, ELK, structured logging |
| `security` | Segurança | OAuth2, mTLS, LDAP/AD, Keycloak/OIDC, PCI-DSS, LGPD, Azure Key Vault |
| `testing` | Testes | pytest, JUnit, Mockito, OpenAPI contract testing, Testcontainers |
| `ai_automation` | IA & automação | LLMs, Cursor Skills/Agents, SAI APP, engenharia de prompts, geração de documentação, análise de código legado |
| `legacy_modernized` | Legados modernizados | COBOL/DB2/JCL, Oracle Forms 10g, Visual FoxPro, SSIS/T-SQL, Java legado |
| `sector` | Setores atendidos | Financeiro, Automotivo, Energia, Varejo, Logística Ferroviária, Educação, Telecom |

Items are tagged for filtering (e.g. FastAPI → `['python', 'async', 'rest']`). User-added items have `is_custom=true` and `created_by_user_id` set.

---

## 14. Repository layout

```
agents-workshop/
├── docker-compose.yml
├── .env.example
├── README.md
├── docs/
│   ├── SPEC.md                       # this file
│   ├── adr/                          # architecture decision records
│   └── images/
├── packages/
│   ├── core/
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── alembic/versions/
│   │   ├── app/
│   │   │   ├── main.py               # FastAPI app factory
│   │   │   ├── worker.py             # Dramatiq entrypoint
│   │   │   ├── api/
│   │   │   │   ├── projects.py
│   │   │   │   ├── qa.py
│   │   │   │   ├── tech.py
│   │   │   │   ├── artifacts.py
│   │   │   │   ├── skills.py
│   │   │   │   ├── cards.py
│   │   │   │   ├── llm.py
│   │   │   │   └── exports.py
│   │   │   ├── domain/
│   │   │   │   ├── models.py         # SQLAlchemy
│   │   │   │   ├── schemas.py        # Pydantic
│   │   │   │   └── enums.py
│   │   │   ├── families/
│   │   │   │   ├── _base.py
│   │   │   │   └── phase_vli/
│   │   │   │       ├── family.py
│   │   │   │       ├── templates/
│   │   │   │       └── few_shots/
│   │   │   ├── llm/
│   │   │   │   ├── base.py
│   │   │   │   ├── anthropic_provider.py
│   │   │   │   ├── openai_provider.py
│   │   │   │   ├── ollama_provider.py
│   │   │   │   ├── pricing.py
│   │   │   │   └── service.py
│   │   │   ├── prompts/
│   │   │   │   ├── propose_skill_set.py
│   │   │   │   ├── draft_skill_body.py
│   │   │   │   ├── propose_backlog.py
│   │   │   │   ├── draft_card.py
│   │   │   │   └── suggest_tech_stack.py
│   │   │   ├── extractors/
│   │   │   │   ├── base.py
│   │   │   │   ├── markitdown_extractor.py
│   │   │   │   ├── pdfplumber_extractor.py
│   │   │   │   ├── csv_extractor.py
│   │   │   │   └── code_extractor.py
│   │   │   ├── jobs/
│   │   │   │   ├── extract_artifact.py
│   │   │   │   └── _broker.py
│   │   │   ├── validators/
│   │   │   ├── exporters/
│   │   │   └── seed/
│   │   │       ├── seeder.py
│   │   │       ├── tech_catalog.yaml
│   │   │       └── reference/
│   │   │           ├── ref-siglm/
│   │   │           ├── ref-cronos/
│   │   │           └── ref-corp-vli/
│   │   └── tests/
│   ├── cli/
│   │   ├── pyproject.toml
│   │   ├── workshop/
│   │   │   ├── __main__.py
│   │   │   └── commands/
│   │   └── tests/
│   └── web/
│       ├── package.json
│       ├── next.config.ts
│       ├── tsconfig.json
│       ├── tailwind.config.ts
│       ├── src/
│       │   ├── app/
│       │   ├── components/
│       │   ├── hooks/
│       │   ├── lib/
│       │   └── services/
│       └── tests/
├── data/                             # gitignored
│   └── projects/
│       └── <project-id>/
│           ├── artifacts/
│           └── exports/
└── .agents/                          # dogfood: skills + cards for THIS tool
    ├── skills/
    └── jira-cards/
```

`packages/core` and `packages/cli` share the same Python venv (`uv` workspaces, or `pip install -e ../core` from CLI). `packages/web` is standalone Node.

---

## 15. Configuration & secrets

`.env` (repo root, gitignored):

```
# Postgres
DATABASE_URL=postgresql+psycopg://workshop:workshop@localhost:5432/workshop

# Redis (broker + cache)
REDIS_URL=redis://localhost:6379/0

# LLM defaults (Anthropic only as default; others enabled by setting their key)
WORKSHOP_DEFAULT_PROVIDER=anthropic
WORKSHOP_DEFAULT_MODEL=claude-sonnet-4-5
WORKSHOP_TEMPERATURE=0.20

# Provider keys (presence enables the provider)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434

# Storage
WORKSHOP_DATA_DIR=./data

# Web
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Missing provider keys disable that provider cleanly: the class loads but `chat()` raises `ProviderNotConfigured`. Settings page shows which providers are configured.

---

## 16. Non-goals (MVP out-of-scope)

- Multi-tenant UI / authentication. Single local user.
- Real-time collaboration. Last-write-wins.
- AI **execution** of cards. The tool produces the contract; running it is Cursor/Claude Code/Gemini's job.
- Live Jira REST push.
- Jira CSV export (deferred to P5).
- Strict-9 and free-form families (P5+).
- Skill marketplace / cross-project reuse.
- Card version history (only `updated_at` stored).
- Embedding-based artifact retrieval (naïve head/tail truncation).
- **Reasoning capture from providers** (interface ready; wiring is P3).
- Re-importing existing `.agents/` folders (P3).
- PPTX/XLSX/OCR artifact extraction (P3+).

---

## 17. Open questions — resolved

| # | Topic | Resolution |
|---|---|---|
| 1 | LLM defaults storage | **Columns on `projects`** + Settings UI |
| 2 | Artifact extraction depth | **markitdown + pdfplumber**, core file types only |
| 3 | Skill kind `context` cardinality | **0–N**, no enforcement |
| 4 | Card code prefix | **Auto-derived from slug**, editable in Settings |
| 5 | Analyzer skill resources | **Warning** when zero; do not block |
| 6 | Re-import existing `.agents/` | **P3 feature** |
| 7 | Mermaid DAG direction | **Top-down** |
| 8 | LLM streaming | **Wait for full structured response** |
| 9 | Default LLM provider | **Anthropic only**; OpenAI + Ollama opt-in |
| 10 | LLM reasoning capture | **Schema + interface in MVP**; provider wiring in P3 |
| 11 | Reasoning UI default | **Collapsed**, click "Show thinking" to expand |
| 12 | Tech panorama editability | **Seed catalog + user-added items + LLM-suggested + TBD per dimension** |
| 13 | Tech suggest trigger | **Per-dimension "Suggest with AI" button**, on demand |
| 14 | Artifact upload mode | **Always async** (Redis + Dramatiq) |
| 15 | Q&A required subset | **First 3 required**: business_problem, success_definition, users_and_actors |
| 16 | Artifact extractors scope | **Core set**: PDF, DOCX, MD, TXT, CSV, code files |

---

## 18. Sign-off

When this document is approved (file marked `Status: Approved` at the top), the next deliverable is the **P0 plumbing slice**:

1. Monorepo skeleton matching §14.
2. `docker-compose.yml` with `postgres` + `redis` + `api` (FastAPI `/health`) + `worker` services.
3. Alembic baseline migration matching §4.
4. `workshop init`, `workshop db migrate`, `workshop db seed` working end-to-end:
   - Three reference PoCs loaded (`ref-siglm`, `ref-cronos`, `ref-corp-vli`).
   - Tech catalog loaded with 13 dimensions and the seeded items.
   - One local user, one default tenant.
5. `GET /projects` returning the seeded projects.
6. `GET /tech/dimensions` returning the panorama.
7. One end-to-end async artifact extraction test: upload a sample PDF → poll status → extracted markdown present.

No LLM call yet. No web UI yet. No family rendering yet. P0 proves the plumbing works. P1 LLM prompts and P2 web UI follow as separate PRs.
