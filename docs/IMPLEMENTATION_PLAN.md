# Agents Workshop — Implementation Plan

**Status:** **Approved** · **Companion to:** `docs/SPEC.md` v2
**Approved on:** 2026-05-11

> The SPEC is the contract. This document is the **execution script** for a single AI agent implementing the system in this workspace, step by step, with checkpoints where you review and steer.

---

## Table of contents

1. [Execution model](#1-execution-model)
2. [Working agreements](#2-working-agreements)
3. [Phase P0 — Plumbing](#3-phase-p0--plumbing)
4. [Phase P1 — Core LLM + CLI](#4-phase-p1--core-llm--cli)
5. [Phase P2 — Web UI](#5-phase-p2--web-ui)
6. [Phase P3+ — Post-MVP](#6-phase-p3--post-mvp)
7. [Validation strategy](#7-validation-strategy)
8. [Things I will flag instead of deciding silently](#8-things-i-will-flag-instead-of-deciding-silently)
9. [Pre-flight: what I need before starting](#9-pre-flight-what-i-need-before-starting)

---

## 1. Execution model

- **Implementer:** the AI agent (me) running in this Cursor session.
- **Reviewer:** you.
- **Mode:** sequential. One step at a time. No parallelism, no card hand-offs, no story points.
- **Unit of progress:** a **step**. Each step ends with code in the workspace, relevant tests passing, and a short status message from me.
- **Unit of pause:** a **checkpoint**. After a defined cluster of steps, I stop. You review, then say `continue`, `edit X`, or `discuss Y`.
- **No artificial granularity.** Steps are sized by *coherence* (one cleanly testable chunk), not by ticket-shop conventions.

```
              one step                 one step                  one step
            ┌──────────┐             ┌──────────┐              ┌──────────┐
            │ code +   │             │ code +   │              │ code +   │
            │ tests    │  ─────►     │ tests    │  ─────►      │ tests    │
            └─────┬────┘             └─────┬────┘              └─────┬────┘
                  │                        │                         │
                  └────────── several steps ──────────┐              │
                                                       ▼              │
                                                ┌────────────┐        │
                                                │ CHECKPOINT │ ◄──────┘
                                                │ user review│
                                                └────────────┘
```

**Session-size hints** on each step (for your awareness of how long it'll take inside the chat):

| Size | Meaning |
|---|---|
| **S** | 1 assistant turn — a handful of files. |
| **M** | 2–4 turns — several files + tests + small iteration. |
| **L** | 5+ turns; may straddle a user check-in. The schema step is the only L. |

---

## 2. Working agreements

**I will NOT pause for:**
- Idiomatic Python / TypeScript style choices.
- Minor library version pinning (latest stable).
- Choosing between equivalent stdlib helpers.
- Adding `__init__.py`, formatting configs, gitignore entries.
- Adding obvious unit tests not explicitly listed in SPEC.

**I WILL pause and ask before:**
- Adding a dependency not implied by the SPEC.
- Changing the schema in SPEC §4.2 (any column added/removed/retyped).
- Choosing a UX behavior the SPEC doesn't specify (e.g. exact wording of error toasts).
- Decisions that affect cost (e.g. cranking up model max_tokens).
- Anything that touches the three reference projects' content (those are the few-shot exemplars and shouldn't drift).

**Surface format after each step:** I send a 4-line summary:
1. What landed
2. Files changed
3. Tests run + result
4. Next step's title (so you can preempt if needed)

**Git:** if the workspace is not a git repo, I recommend `git init` at Step 0.1 so each step is a commit you can read. **Recommendation: yes, init.**

**Commits:** one commit per step. Conventional Commits format (`feat:`, `chore:`, `test:`, etc.).

---

## 3. Phase P0 — Plumbing

**Goal at end of phase:** `docker compose up` brings up postgres + redis + api + worker; `workshop init && workshop db migrate && workshop db seed` populates the DB; uploading a sample PDF triggers async extraction that completes. No LLM, no UI.

### Steps

| # | Title | Size | Output check |
|---|---|---|---|
| **0.1** | Workspace bootstrap | S | Tree matches SPEC §14; `uv sync` passes |
| **0.2** | docker-compose (postgres + redis) | S | `docker compose up -d postgres redis` → both healthy |
| **0.3** | FastAPI skeleton + `/health` + settings + structured logging | S | `curl /health` → `{status,db,redis}` all green |
| **0.4** | SQLAlchemy models + Alembic baseline (all 17 tables from §4.2) | **L** | `alembic upgrade head` clean; `\d+` shows all tables/indexes |
| **0.5** | Pydantic schemas (domain views + LLM I/O DTOs) | M | Round-trip tests pass |
| **0.6** | CLI skeleton (Typer): `init`, `db migrate`, group stubs | S | `workshop --help` lists groups; migrate works |
| **0.7** | Tech catalog seed YAML + seeder loader | M | After seed: 13 dimensions, ≥ 70 items |
| **0.8** | Reference-PoC seed loaders (3 projects with skills/phases/cards) | M | `GET /api/projects` returns 3 projects with non-empty children |
| **0.9** | Dramatiq broker + worker entrypoint + ping actor | M | `worker` container starts; ping round-trip < 1 s |
| **0.10** | Extractors: markdown / code / csv / pdf / docx | M | Unit tests per extractor on fixture files |
| **0.11** | Artifact upload endpoint + `extract_artifact` actor + status polling | M | E2E: upload sample PDF → poll → `extracted` with non-empty `content_md` |

### Checkpoint P0 ✅

**What you can do at this checkpoint:**
- `docker compose up -d`
- `workshop db migrate && workshop db seed`
- `curl localhost:8000/health`
- `curl localhost:8000/api/projects | jq` → 3 seeded projects
- `curl localhost:8000/api/tech/dimensions | jq` → 13 dimensions
- Upload a PDF via `curl -F file=@sample.pdf localhost:8000/api/projects/{id}/artifacts` → poll until extracted

**What's intentionally absent at this checkpoint:**
- Any LLM call.
- Any rendering of skills or cards to markdown.
- Any web UI.

---

## 4. Phase P1 — Core LLM + CLI

**Goal at end of phase:** a fresh project, taken through the CLI alone (wizard → skill proposals → drafts → backlog → cards → validate → export), produces a `.agents/` folder that drops cleanly into a Cursor workspace.

### Steps

| # | Title | Size | Output check |
|---|---|---|---|
| **1.1** | LLM provider abstraction (`ChatPrompt`, `ChatResult`, `LLMProvider` ABC) | S | `DummyProvider` test round-trips |
| **1.2** | Pricing module + `LLMService.run()` with audit logging | M | Every test call leaves one `llm_runs` row in a terminal state |
| **1.3** | `AnthropicProvider` (tool-use for structured output, retry+fallback) | M | Live test against `claude-sonnet-4-5` parses a sample schema |
| **1.4** | `OpenAIProvider` + `OllamaProvider` (opt-in, graceful `ProviderNotConfigured`) | M | Each provider has a recorded-fixture test |
| **1.5** | Template-family base + `PhaseVliFamily` (Jinja templates: skill, card, phase README, project README) | **L→M** | Golden test: rendering a seeded card matches expected `.md` byte-for-byte (modulo trailing whitespace) |
| **1.6** | Prompt: `ProposeSkillSet` + few-shots from seed | M | Synthetic project → 5–8 proposed skills with valid kinds |
| **1.7** | Prompt: `DraftSkillBody` + per-kind resource biases | M | Analyzer draft has ≥ 2 resources; context draft has 0 |
| **1.8** | Prompt: `ProposeBacklog` + few-shots | M | Output has 3–7 phases, no forward-phase deps |
| **1.9** | Prompt: `DraftCard` + few-shots | M | Output has all phase-VLI sections; ≥ 1 input |
| **1.10** | Prompt: `SuggestTechStack` | S | "Banking modernization" → suggests `'financeiro'` sector with high confidence |
| **1.11** | Validators (DAG cycles, ref resolution, frontmatter, paths, Q&A required, analyzer-resources warning) | M | Each validator has positive + negative unit test |
| **1.12** | Exporters: filesystem + zip + Mermaid (top-down) + manifest with SHA256 | M | Export `ref-corp-vli` → byte-identical on re-run (modulo manifest timestamp) |
| **1.13** | CLI wiring: every command in SPEC §11.1, including the `project new` Rich-prompt wizard | M | `workshop project new` walks all 4 wizard stages and persists everything |
| **1.14** | End-to-end CLI smoke: fresh project → propose → draft × N → validate → export | S | Drops into a Cursor workspace and behaves as a skill-driven backlog |

### Checkpoint P1 ✅

**What you can do at this checkpoint:**
- Run the full workflow from the terminal on a brand-new project.
- Inspect every LLM call via `workshop llm-runs`.
- Export to a folder of your choice and verify the contents match SPEC §10.

**Reasonable thing to do here:** point the tool at your real next PoC objective and stop. If P1 is good enough for your day-to-day, P2 becomes optional rather than mandatory.

---

## 5. Phase P2 — Web UI

**Goal at end of phase:** the same workflow as P1, click-driven, with the DAG view and per-section regeneration that's hard to do well from a CLI.

### Steps

| # | Title | Size | Output check |
|---|---|---|---|
| **2.1** | Next.js 14 bootstrap + Tailwind + shadcn/ui + dark mode | S | `/` renders an empty layout |
| **2.2** | API client (axios + TanStack Query) + single-user auth shim | S | `useQuery(['health'])` returns green |
| **2.3** | Authentication layer (JWT, login/logout, route protection, user menu) | M | Login flow works, protected routes redirect, token refresh automatic |
| **2.4** | Project Management Interface (CRUD, dashboard, navigation, settings) | M | Projects list, create/edit forms, overview stats, navigation menu, React Hook Form + Zustand |
| **2.4.1** | Project Discovery: Q&A Wizard (7 fields, 3 required) | M | ✅ **DONE** — Merged into unified Setup Wizard at `/projects/[slug]/setup?step=2` |
| **2.4.2** | Project Discovery: Tech Panorama UI (chips + AI suggestions + custom + TBD) | M | ✅ **DONE** — Merged into unified Setup Wizard at `/projects/[slug]/setup?step=3` |
| **2.5** | Document Upload Interface (dropzone + status polling + preview) | M | ✅ **DONE** — Merged into unified Setup Wizard at `/projects/[slug]/setup?step=1` |
| **2.6** | Skill library + grid + Propose CTA | M | Propose returns and renders skills |
| **2.7** | Skill editor (Monaco body + frontmatter form + resources tab + regenerate-body button) | M | Edits save on debounce; regenerate preserves resources |
| **2.8** | Backlog page (table grouped by phase) + Propose CTA | M | Propose returns and renders phases + cards |
| **2.9** | Card editor (per-section panes + per-section regenerate + inputs editor + deps editor + gate toggle) | M | All edits persist; per-section regenerate isolated |
| **2.10** | DAG view (React Flow + `elkjs` top-down) — click → card drawer | M | Reference PoC seed renders without overlapping nodes |
| **2.11** | Export page (tree preview + validate panel + download zip + write-to-path) | M | Web export matches CLI export byte-for-byte |
| **2.12** | LLM runs audit page + Settings page (provider/model/temperature) | S | Cost totals match `SUM(llm_runs.cost_usd)` |
| **2.13** | Final integration testing + Polish (responsive design, error states, loading states) | S | Full workflow works end-to-end across all devices/browsers |

#### Revised Step 2.4 Approach (Risk Assessment Applied)

**Decision:** Step 2.4 focuses on core project management functionality while deferring complex "discovery channels" to dedicated sub-steps.

**Implementation Note (Completed):** Steps 2.4.1, 2.4.2, and 2.5 were implemented as a **unified Setup Wizard** at `/projects/[slug]/setup` with 4 steps:

| Step | Content | Source Step |
|------|---------|-------------|
| 1 | Artifacts upload (drag & drop, extraction status) | 2.5 |
| 2 | Q&A wizard (7 questions, 3 required, auto-save) | 2.4.1 |
| 3 | Tech panorama (accordion dimensions, chip selection, roles) | 2.4.2 |
| 4 | Review (summary cards, readiness check, continue to skills) | New |

The project detail page now shows a **Setup Progress** card with completion status and a link to the wizard.

**Original Rationale (preserved for context):**
- **Step 2.4**: Core project management with minimal complexity
  - Projects CRUD (list, create, edit, delete)  
  - Basic project creation form (name, description, objective)
  - Dashboard with overview statistics
  - Main navigation menu and settings
  - Includes React Hook Form + Zustand (low-risk, high-benefit tools)

- **Steps 2.4.1, 2.4.2 & 2.5**: Discovery channels ✅ COMPLETED
  - Implemented as unified 4-step wizard
  - Reused existing API hooks (artifacts, qa, tech)
  - Added accordion component for tech dimensions

### Checkpoint P2 ✅

**What you can do at this checkpoint:**
- The full workflow in the browser.
- Edit any skill or card section in place and regenerate just that section.
- Inspect the dependency DAG visually.

This is **MVP done**.

---

## 6. Phase P3+ — Post-MVP

Tracked at the SPEC level; not part of the execution script. We'll plan each P3 feature individually when you decide to start one.

In rough order of expected value-per-effort:

1. **Reasoning capture wiring** — Anthropic Extended Thinking first (already in the schema).
2. **Jira CSV exporter** — exporter is structurally ready.
3. **Re-import existing `.agents/` folder** — round-trip support.
4. **Second template family (`strict_9`)** — adds Enel-style output.
5. **WebSocket status push** — replace polling.
6. **OCR / PPTX / XLSX extractors** — heavier deps.
7. **Async LLM jobs** — batch generation of all cards at once.
8. **Embedding-based artifact retrieval** — replace head/tail truncation.

---

## 7. Validation strategy

Each step has a **passing test suite at the end** before I move on. If a step's test set is large, I run it once after the step lands and again after the next step (catches regressions early).

| Layer | Tooling | When run |
|---|---|---|
| Python unit | `pytest` | After every Python-side step |
| Python integration | `pytest` + `testcontainers` (postgres + redis) | After every step that touches the DB or worker |
| LLM | recorded fixtures via `vcr.py` + a manual live-smoke command | Live smoke run manually after `1.3` and again at each P1 checkpoint |
| Frontend unit | `vitest` + `@testing-library/react` | After every UI step that owns logic (forms, editors, DAG layout) |
| E2E | `playwright` | Once at P2 checkpoint |

**Golden-file tests** for the family rendering catch the export pipeline's most likely regressions immediately.

**No CI yet in MVP** — tests run locally. CI can land as a P3+ chore once the implementation is stable enough to deserve gating.

---

## 8. Things I will flag instead of deciding silently

If during execution any of these come up, I stop and ask before proceeding. Listing them here so you know the trigger points in advance.

1. **Anthropic tool-use returns no `tool_use` block** despite the retry — I'll surface the parser fallback decision rather than silently widen the parse.
2. **A SPEC §4.2 column needs a tweak** (e.g. an `enum` I missed, a nullable constraint) — I propose a migration; you approve before I run it.
3. **An extractor pulls in a heavy native dep** I didn't anticipate (e.g. system-level Tesseract) — I'll stop before adding it.
4. **A prompt's few-shot exemplar exceeds the model's reasonable context budget** — I'll truncate or summarize and surface the choice.
5. **Web UI hits a UX decision not in SPEC** (e.g. confirm-dialog vs inline confirm) — I'll pick a default and call it out.
6. **A reference PoC's seed content needs to grow** (because few-shots are insufficient) — I'll show the addition; you sign off before it lands.
7. **Cost on a live LLM smoke run** exceeds USD 1.00 in a single step — I'll report and pause.

---

## 9. Pre-flight: what I need before starting

| # | Item | Why |
|---|---|---|
| 1 | `ANTHROPIC_API_KEY` placed in your environment or a value to put in `.env` later | Needed at P1 step 1.3; not needed for P0 |
| 2 | Confirmation to `git init` at Step 0.1 | So each step is a reviewable commit |
| 3 | Approval of this plan (file marked `Status: Approved` at top) | Locks scope; deviations require a new pause |
| 4 | Confirmation of Python version (3.12 recommended; 3.11 acceptable) | Affects `pyproject.toml` and `uv` |
| 5 | Confirmation of Node version (20 LTS recommended) | Affects `package.json` engines |

Nothing else needed.

---

## Sign-off

When this plan is approved, I start with **Step 0.1 — Workspace bootstrap** and proceed step by step. After each step I send the 4-line status summary defined in §2. After each phase I stop at the checkpoint and wait for your `continue`.
