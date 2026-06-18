# Implementation Plan: Jira Bidirectional Integration

**Status:** Planning
**Created:** 2026-05-18
**Inspired by:** Real VLI migration project ([reference](../../VLI/VLI-ssis-databricks-migration/discovery/jira-import/))
**Scope:** Push cards to Jira (JSON-via-API and CSV-via-wizard) + consume Jira column-move webhooks to trigger agent flows

---

## Why This Plan Exists (And Why VLI Validates It)

The VLI project hand-built a Jira import pipeline (`generate_csv.py` + `import_to_jira.ps1`) because:
1. Past CSV imports silently lost data on custom-field name collisions, missing screen fields, multi-value delimiter quirks
2. The team needed both a **wizard path** (CSV) and a **scripted path** (REST API JSON)
3. They needed **idempotency** to safely re-run after partial failures
4. They learned to **discover fields dynamically** instead of hardcoding mappings

This plan productizes those hard-won lessons inside Agents Workshop.

---

## Goals

1. **Push** generated cards from Workshop → Jira via two interchangeable paths: JSON (REST API) and CSV (wizard)
2. **Receive** column-move events from Jira → trigger configurable agent flows
3. **Survive Jira instance variance** — different field IDs, custom workflows, missing screen fields
4. **Track every per-card outcome** in the UI — success, partial, failed, with diagnostics

---

## Non-Goals

- ❌ No bidirectional field sync (Jira → Workshop edits propagated back) in MVP
- ❌ No Epic / Sprint / Component sync — labels are the grouping mechanism (per VLI)
- ❌ No issue link creation at import time — listed in description, optional second-pass
- ❌ No custom field reliance — Workshop content goes into Description blob

---

## VLI Lessons Encoded in This Plan

| VLI Practice | Plan Section |
|---|---|
| `createmeta` discovery before push | § 3.2 JSON Push Service |
| Description as `=== SECTION ===` blob | § 2.2 Description Format |
| Repeated `Labels` columns / array | § 2.3 Labels Strategy |
| Idempotency via persistent key map | § 3.3 Idempotency |
| Sample-first test pattern | § 3.6 Sample Mode |
| Auto-retry without Story Points if rejected | § 3.2 JSON Push Service |
| No epics, labels substitute | § 2.3 Labels Strategy |
| Dual-path delivery (CSV + JSON/API) | § 2 Two Delivery Paths |

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AGENTS WORKSHOP (OUTBOUND)                          │
│                                                                             │
│   ┌───────────────────────────────────────────────────────────────────┐    │
│   │            Card Renderer (shared between both paths)              │    │
│   │  • Description blob with === SECTION === separators               │    │
│   │  • Label set (phase-N, blocker, human-gate, skill-*, ...)         │    │
│   │  • Field set built from createmeta (story points, priority, ...)  │    │
│   └───────────────────────────────────────────────────────────────────┘    │
│              │                                          │                    │
│              ▼                                          ▼                    │
│   ┌──────────────────────┐                ┌──────────────────────────────┐ │
│   │ Path A: JSON via API │                │ Path B: CSV download         │ │
│   │                      │                │                              │ │
│   │ POST /rest/api/2/    │                │ GET /export.csv              │ │
│   │   issue              │                │  → user uploads via Jira     │ │
│   │ per-card, dramatiq   │                │    wizard manually           │ │
│   │ + per-card status    │                │                              │ │
│   └──────────────────────┘                └──────────────────────────────┘ │
│              │                                          │                    │
│              ▼                                          ▼                    │
│       Live progress UI                          User clicks Done            │
│       (per-card success/failure)                + paste log file path       │
│                                                  to reconcile keys          │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ (Jira)
┌─────────────────────────────────────────────────────────────────────────────┐
│                              JIRA CLOUD                                      │
│   To Do          │   In Progress    │   Code Review    │   Done            │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ Webhook: jira:issue_updated
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AGENTS WORKSHOP (INBOUND)                              │
│   Webhook receiver → event audit → trigger rules engine → agent flow runs   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Shared Card Rendering

Both paths consume the same renderer so output is identical regardless of delivery.

### 2.1 The Renderer

```python
# packages/core/app/integrations/jira/renderer.py

@dataclass
class RenderedCard:
    summary: str
    issue_type: str
    description: str       # plain text blob with === SECTION === separators
    priority: str          # "Medium" | "High" | "Highest" | "Low"
    story_points: int | None
    labels: list[str]

    # Source linkage (NOT sent to Jira)
    workshop_card_id: UUID
    workshop_card_code: str

class CardRenderer:
    def render(self, card: Card) -> RenderedCard:
        return RenderedCard(
            summary=self._build_summary(card),
            issue_type=card.type,
            description=self._build_description(card),
            priority=card.priority or 'Medium',
            story_points=card.story_points,
            labels=self._build_labels(card),
            workshop_card_id=card.id,
            workshop_card_code=card.code,
        )
```

### 2.2 Description Format (VLI-Proven)

```
=== KEY ===
{card.code}

=== PHASE ===
{phase.order_no} — {phase.name}

=== SKILLS ===
- {skill_slug_1}
- {skill_slug_2}

=== INPUTS ===
- {input.path}

=== OUTPUT ===
{outputs_md}

=== ACCEPTANCE CRITERIA ===
{acceptance_criteria_md}

=== DEPENDENCIES ===
- {depends_on_code}

=== HUMAN GATE ===
Yes — {checklist_first_200_chars}

=== BLOCKER ===
Yes
```

Plain text, no markdown. Renders identically in any Jira version, no ADF conversion, no CLOUD vs DC drift.

### 2.3 Labels Strategy

Labels replace Epic / Sprint / Components. Every card gets:

```
{card_code_prefix}        ← e.g. "ttr", "pct"
{project_type}            ← e.g. "migration", "application"
phase-{order_no}          ← e.g. "phase-1"
skill-{slug}              ← one per linked skill, sanitized
human-gate                ← if card.human_gate
blocker                   ← if 'blocker' in card.flags
```

Labels are sanitized: spaces/slashes → `-`, drop non-alphanum-or-`_-`, collapse runs.

---

## 3. Path A — JSON via REST API

The default path. Fast, automated, idempotent, full per-card status reporting.

### 3.1 Connection Setup

| Step | UI | Backend |
|---|---|---|
| 1 | User enters Jira URL, project key, email, API token | Encrypt token (Fernet) |
| 2 | Click "Test Connection" | `GET /rest/api/2/myself` |
| 3 | Click "Discover Fields" | `GET /rest/api/2/issue/createmeta?projectKeys=...&issuetypeNames=Task` |
| 4 | Map workshop statuses → Jira statuses | `GET /rest/api/2/project/{key}/statuses` |
| 5 | Click "Register Webhook" (optional, for inbound) | `POST /rest/api/3/webhook` |

### 3.2 JSON Push Service (`createmeta` Discovery + Auto-Retry)

```python
# packages/core/app/integrations/jira/json_push.py

class JsonPushService:
    """VLI-validated pattern: discover screen fields first, gracefully skip what's missing,
    auto-retry without Story Points on field rejection."""

    def refresh_createmeta(self) -> CreateMetaResult:
        """Lines 109-145 of VLI's import_to_jira.ps1 ported to Python."""
        meta = self.client.get_createmeta(
            project_key=self.connection.jira_project_key,
            issue_type=self.connection.issue_type,
        )
        screen_fields = set(meta['projects'][0]['issuetypes'][0]['fields'].keys())

        # Find Story Points custom field that's ALSO on the screen
        all_fields = self.client.get_all_fields()
        sp_candidates = [
            f for f in all_fields
            if f.get('custom') and f['name'] in ('Story Points', 'Story point estimate')
        ]
        sp_field = next(
            (f for f in sp_candidates if f['id'] in screen_fields),
            None,
        )

        self.connection.create_screen_fields = list(screen_fields)
        self.connection.story_points_field_id = sp_field['id'] if sp_field else None
        self.connection.story_points_supported = sp_field is not None
        self.connection.priority_supported = 'priority' in screen_fields
        self.connection.labels_supported = 'labels' in screen_fields
        self.connection.last_createmeta_refresh_at = datetime.utcnow()
        self.db.commit()

        return CreateMetaResult(
            screen_field_count=len(screen_fields),
            story_points_field=sp_field['id'] if sp_field else None,
            warnings=self._warnings(screen_fields),
        )

    def push_card(self, card_id: UUID) -> PushOutcome:
        """Create or update one issue with per-card status tracking."""
        card = self.db.query(Card).get(card_id)
        outcome = self._begin_outcome(card)

        rendered = CardRenderer().render(card)
        fields = self._build_fields_dict(rendered)

        try:
            if card.jira_issue_key:
                self.client.update_issue(card.jira_issue_key, {'fields': fields})
                outcome.action = 'updated'
                outcome.jira_key = card.jira_issue_key
            else:
                resp = self.client.create_issue({'fields': fields})
                card.jira_issue_key = resp['key']
                card.jira_issue_id = resp['id']
                card.jira_url = f"{self.connection.jira_base_url}/browse/{resp['key']}"
                outcome.action = 'created'
                outcome.jira_key = resp['key']

            self._mark_synced(card, outcome)
            return outcome

        except JiraFieldRejectedError as e:
            # VLI auto-retry: if Story Points field rejected, drop it and retry
            if e.field_id == self.connection.story_points_field_id:
                fields.pop(self.connection.story_points_field_id, None)
                self.connection.story_points_supported = False
                self.db.commit()
                outcome.warnings.append('story_points_dropped')
                return self._retry_push(card, fields, outcome)
            return self._mark_failed(card, outcome, e)

        except JiraHttpError as e:
            return self._mark_failed(card, outcome, e)

    def _build_fields_dict(self, r: RenderedCard) -> dict:
        """Only include fields confirmed by createmeta."""
        fields = {
            'project': {'key': self.connection.jira_project_key},
            'summary': r.summary,
            'issuetype': {'name': r.issue_type},
            'description': r.description,
        }
        if self.connection.priority_supported:
            fields['priority'] = {'name': r.priority}
        if self.connection.labels_supported:
            fields['labels'] = r.labels
        if self.connection.story_points_supported and r.story_points:
            fields[self.connection.story_points_field_id] = int(r.story_points)
        return fields
```

### 3.3 Idempotency

- `cards.jira_issue_key` is the persistent key map (equivalent to VLI's tab-separated log file)
- On re-run:
  - If `jira_issue_key IS NULL` → CREATE
  - If `jira_issue_key IS NOT NULL` → UPDATE (full field overwrite)
- No duplicate issues on retry, even after partial failures

### 3.4 Dramatiq Job with Per-Card Status

```python
@dramatiq.actor(max_retries=2, time_limit=600_000, queue_name='jira_push')
def push_cards_json(job_id: str, refresh_meta: bool = True):
    """Bulk push job. Updates a JiraPushJob row that the frontend polls."""
    with get_db() as db:
        job = db.query(JiraPushJob).get(UUID(job_id))
        service = JsonPushService(db, job.project_id)

        if refresh_meta:
            try:
                service.refresh_createmeta()
            except Exception as e:
                _fail_entire_job(db, job, f"createmeta failed: {e}")
                return

        # Token bucket — Jira Cloud ~10 req/s
        bucket = TokenBucket(rate=8, capacity=10)

        for card_id in job.card_ids:
            bucket.acquire()

            outcome = JiraPushOutcome(
                push_job_id=job.id,
                card_id=card_id,
                status='in_progress',
            )
            db.add(outcome)
            db.commit()

            try:
                result = service.push_card(card_id)
                outcome.status = 'success'
                outcome.action = result.action
                outcome.jira_key = result.jira_key
                outcome.jira_url = result.jira_url
                outcome.warnings = result.warnings
                job.success_count += 1
            except RateLimitedError:
                time.sleep(60)
                # Retry once
                try:
                    result = service.push_card(card_id)
                    outcome.status = 'success'
                    outcome.action = result.action
                    outcome.jira_key = result.jira_key
                    job.success_count += 1
                except Exception as e:
                    _record_failure(outcome, e)
                    job.failure_count += 1
            except Exception as e:
                _record_failure(outcome, e)
                job.failure_count += 1

            outcome.completed_at = datetime.utcnow()
            job.progress_count += 1
            db.commit()

        job.status = 'completed' if job.failure_count == 0 else 'completed_with_errors'
        job.completed_at = datetime.utcnow()
        db.commit()


def _record_failure(outcome, exc):
    outcome.status = 'failed'
    outcome.error_code = _classify_error(exc)
    outcome.error_message = str(exc)
    outcome.error_payload = getattr(exc, 'response_body', None)
    outcome.is_retryable = _is_retryable(exc)
```

### 3.5 Error Classification

```python
ERROR_CODES = {
    # Auth
    'auth_invalid':         "Token rejected — verify credentials",
    'auth_expired':         "Token expired — regenerate at id.atlassian.com",

    # Permissions
    'permission_create':    "Account lacks 'Create Issues' permission on project",
    'permission_field':     "Account cannot set this field — ask Jira admin",

    # Field/data
    'field_not_on_screen':  "Field exists but is not on the Create screen — add it",
    'field_unknown':        "Field ID not recognized by this project",
    'value_invalid':        "Field value rejected — check allowed values",
    'value_too_long':       "Value exceeds Jira's max length",

    # Workflow
    'transition_invalid':   "Issue cannot be created in this status (workflow rule)",
    'issue_type_missing':   "Issue type does not exist in this project",

    # Quota / rate
    'rate_limited':         "Jira rate limit (429) — retrying with backoff",
    'quota_exceeded':       "Plan quota exceeded — contact Jira admin",

    # Network
    'network_timeout':      "Jira did not respond within timeout",
    'network_unreachable':  "Cannot reach Jira host",

    # Unknown
    'unknown_400':          "Jira rejected the request (400)",
    'unknown_500':          "Jira returned an internal error (500)",
}
```

### 3.6 Sample Mode (VLI Pattern)

```
[Connect Jira] ─▶ [Test Connection ✅] ─▶ [Discover Fields ✅]
                                                 │
                                                 ▼
                                    [Push 1 Test Card] (required)
                                                 │
                            ┌────────────────────┼─────────────────────┐
                            │                                          │
                       ✅ Success                                  ❌ Failed
                            │                                          │
                            ▼                                          ▼
                  [Push All Phase X]                       [Show diagnostics]
                  [Push All Project]                       (re-test after fix)
```

The bulk-push buttons stay disabled until a sample push succeeds. This catches 90% of misconfiguration before bulk damage.

---

## 4. Path B — CSV via Jira Wizard

Provided as fallback / offline-review option. Identical content, manual upload.

### 4.1 When to Use CSV

| Reason | Example |
|---|---|
| Jira admin blocks API token usage | Locked-down enterprise tenant |
| Want offline review before import | Compliance / change-control gate |
| Team prefers visual wizard mapping | Familiar with Jira CSV import UI |
| Initial bulk seed, then API for updates | Hybrid — CSV once, API thereafter |

### 4.2 CSV Format (Exact VLI Format)

| Column | Type | Notes |
|---|---|---|
| `Summary` | string | `{card.code} — {short title}` |
| `Issue Type` | string | Always `Task` (or per `connection.issue_type`) |
| `Description` | multi-line text | The `=== SECTION ===` blob |
| `Priority` | string | `Medium` / `High` / `Highest` / `Low` |
| `Story Points` | integer | May be ignored if field not on screen |
| `Labels` × N | string | **Repeated column header**; one label per column |

Header for a project where max labels = 6:
```
"Summary","Issue Type","Description","Priority","Story Points","Labels","Labels","Labels","Labels","Labels","Labels"
```

All values quoted (`csv.QUOTE_ALL`), line terminator `\n`.

### 4.3 CSV Generation Endpoint

```python
# packages/core/app/api/jira_export.py

@router.get("/projects/{id}/jira/export.csv")
def export_jira_csv(id: UUID, db: Session = Depends(get_db)):
    cards = db.query(Card).filter_by(project_id=id).order_by(Card.code).all()
    rendered = [CardRenderer().render(c) for c in cards]

    max_labels = max((len(r.labels) for r in rendered), default=0)

    def stream():
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator='\n')

        header = ['Summary', 'Issue Type', 'Description', 'Priority', 'Story Points'] + ['Labels'] * max_labels
        writer.writerow(header)
        yield buf.getvalue(); buf.seek(0); buf.truncate()

        for r in rendered:
            padded = r.labels + [''] * (max_labels - len(r.labels))
            writer.writerow([
                r.summary,
                r.issue_type,
                r.description,
                r.priority,
                r.story_points or '',
                *padded,
            ])
            yield buf.getvalue(); buf.seek(0); buf.truncate()

    return StreamingResponse(
        stream(),
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename=jira-cards-{id}.csv'},
    )
```

### 4.4 Wizard Mapping Cheat-Sheet (Shown in UI After Download)

```
Step in Jira wizard          → Map to
────────────────────────────────────────────────────
Summary                      → Summary
Issue Type                   → Issue Type
Description                  → Description
Priority                     → Priority
Story Points                 → Story Points (or your estimate field)
Labels (×N)                  → Labels — verify "(N values)" in preview

⚠️ If any column reports "won't be imported" → STOP, fix, retry.
```

### 4.5 Reconciliation After CSV Import

CSV path doesn't know what keys Jira assigned. To wire up later API updates, the user must reconcile:

| Approach | UX |
|---|---|
| **Manual** — paste a CSV mapping (workshop_code, jira_key) | Form with file upload, parses & updates `cards.jira_issue_key` |
| **JQL discovery** — search Jira for `labels = "{prefix}" AND summary ~ "{code}"` | Button "Reconcile from Jira"; matches by code prefix in summary |
| **Skip reconciliation** | User accepts cards are write-once via CSV |

Default offered: JQL discovery. Most reliable because the renderer always prefixes `card.code` to summary.

---

## 5. JSON vs CSV — Comparison Matrix

| Aspect | JSON via API | CSV via Wizard |
|---|---|---|
| **Setup complexity** | High (token, createmeta, webhook) | Low (just download) |
| **Per-card feedback** | Yes — live status per card | No — only end-of-import summary in Jira UI |
| **Idempotency** | Built in (`jira_issue_key` lookup) | Manual reconciliation needed |
| **Speed** | ~8 req/s (rate-limited) | Bulk upload — seconds for hundreds |
| **Field discovery** | Automatic via `createmeta` | User maps fields in wizard |
| **Auto-retry on field issues** | Yes (drops Story Points if rejected) | No (whole row may fail silently) |
| **Update existing issues** | Yes (UPDATE if `jira_issue_key` set) | No (would create duplicates) |
| **Webhook setup** | Done in same flow | Separate step needed |
| **Works on locked-down tenants** | Requires API token | Yes (just needs import permission) |
| **Audit trail** | Full DB row per push outcome | Only what wizard reports |
| **Error diagnostics** | Per-card error message + classified code | Wizard log only |
| **Default offered to users** | ✅ Recommended | Fallback / offline path |

**Rule of thumb:**
- API token available + write access → **JSON path**
- API blocked, one-time seed, or paranoid review → **CSV path**

Workshop offers both. The connection wizard's last step asks: *"Pick your default delivery method"* with both buttons enabled afterward.

---

## 6. Per-Card Failure Tracking in the Frontend

### 6.1 Data Model for Push Jobs

```sql
CREATE TABLE jira_push_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    method TEXT NOT NULL CHECK (method IN ('json', 'csv')),
    scope TEXT NOT NULL,                       -- 'all' | 'phase:UUID' | 'card:UUID' | 'selection'
    card_ids UUID[] NOT NULL,                  -- snapshot of cards in scope

    status TEXT DEFAULT 'queued' CHECK (status IN (
        'queued', 'discovering', 'pushing',
        'completed', 'completed_with_errors', 'failed', 'cancelled'
    )),

    total_count INTEGER NOT NULL,
    progress_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,

    job_error_message TEXT,                    -- entire job failed (e.g. createmeta failed)

    triggered_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE TABLE jira_push_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    push_job_id UUID NOT NULL REFERENCES jira_push_jobs(id) ON DELETE CASCADE,
    card_id UUID NOT NULL REFERENCES cards(id),

    status TEXT NOT NULL CHECK (status IN (
        'pending', 'in_progress', 'success', 'failed', 'skipped'
    )),
    action TEXT,                               -- 'created' | 'updated' | NULL
    jira_key TEXT,
    jira_url TEXT,

    -- Error breakdown for failures
    error_code TEXT,                           -- 'auth_invalid', 'field_not_on_screen', ...
    error_message TEXT,                        -- human-readable
    error_payload JSONB,                       -- raw Jira response body
    error_field TEXT,                          -- specific field that caused it
    error_http_status INTEGER,
    is_retryable BOOLEAN DEFAULT FALSE,

    warnings TEXT[] DEFAULT '{}',              -- e.g. ['story_points_dropped']

    attempt_number INTEGER DEFAULT 1,

    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    UNIQUE (push_job_id, card_id)
);

CREATE INDEX idx_outcomes_failed
    ON jira_push_outcomes(push_job_id) WHERE status = 'failed';
```

### 6.2 API Endpoints for Frontend

| Endpoint | Returns | Used For |
|---|---|---|
| `POST /projects/{id}/jira/push` | `{ push_job_id }` | Start bulk push |
| `GET /jira/push-jobs/{id}` | Job summary (counts, status, timing) | Header progress bar |
| `GET /jira/push-jobs/{id}/outcomes` | Paginated outcomes with filter `?status=failed` | Outcome table |
| `POST /jira/push-jobs/{id}/retry-failed` | New job containing only failed cards | "Retry failed" button |
| `POST /jira/push-outcomes/{id}/retry` | New single-card job | Per-row retry |
| `DELETE /jira/push-jobs/{id}` | 204 | Cancel queued job |

### 6.3 Frontend Components

#### 6.3.1 Push Trigger (Project header / Phase view)

```tsx
<Button onClick={() => mutate({ scope: 'phase:' + phase.id })}>
  Push {phase.cards.length} cards to Jira
</Button>
```

On success → set `currentPushJobId` in zustand, opens `PushJobProgress` panel.

#### 6.3.2 PushJobProgress — Live Progress Panel

Polls `GET /jira/push-jobs/{id}` every 2s while status ∈ `{queued, discovering, pushing}`.

```
┌────────────────────────────────────────────────────────────────────┐
│ Pushing to Jira  ─  Project CORP                       [Hide] [×] │
│                                                                    │
│ Progress: 47 / 60 ████████████████░░░░░░░░  78%                   │
│                                                                    │
│ ✅ 42 succeeded    ❌ 5 failed    ⏳ 13 remaining                  │
│                                                                    │
│ [View outcomes ▼]                                                  │
└────────────────────────────────────────────────────────────────────┘
```

#### 6.3.3 PushOutcomesTable — Per-Card Detail

Default filter: `status != success` (show problems first).

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ Push outcomes — CORP-push-job 7f4a                          [All] [Failed] ✓  │
│                                                                                │
│ ┌──────────┬─────────┬──────────┬──────────────────────────────┬───────────┐ │
│ │ Card     │ Status  │ Jira key │ Error                        │ Action    │ │
│ ├──────────┼─────────┼──────────┼──────────────────────────────┼───────────┤ │
│ │ CORP-101 │ ✅      │ CORP-501 │ —                            │ Open ↗    │ │
│ │ CORP-102 │ ✅ ⚠️   │ CORP-502 │ story_points_dropped         │ Open ↗    │ │
│ │ CORP-103 │ ❌      │ —        │ Field 'priority' not on      │ Retry     │ │
│ │          │         │          │ Create screen → ask admin    │ Diagnose  │ │
│ │ CORP-104 │ ❌      │ —        │ Account lacks 'Create        │ Retry     │ │
│ │          │         │          │ Issues' permission           │ Diagnose  │ │
│ │ CORP-105 │ ⏳      │ —        │ —                            │ —         │ │
│ │ CORP-106 │ ⏳      │ —        │ —                            │ —         │ │
│ └──────────┴─────────┴──────────┴──────────────────────────────┴───────────┘ │
│                                                                                │
│ Showing 5 of 60   [Retry all 5 failed]   [Export errors CSV]                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

#### 6.3.4 PushOutcomeDetail — "Diagnose" Modal

```
┌────────────────────────────────────────────────────────────┐
│ Push failure — CORP-103                              [×]   │
│                                                            │
│ ❌ Field 'priority' not on Create screen                   │
│                                                            │
│ Error code:    field_not_on_screen                         │
│ HTTP status:   400                                         │
│ Field:         priority                                    │
│ Attempt:       1                                           │
│ When:          2026-05-18 14:23:01                         │
│                                                            │
│ ── How to fix ──                                          │
│ The 'priority' field exists in Jira but is not on the     │
│ Create Issue screen for this project.                     │
│                                                            │
│ Ask your Jira admin to:                                   │
│   1. Open Project Settings → Screens                      │
│   2. Find the "Create Issue" screen for issue type Task   │
│   3. Add the 'Priority' field                             │
│                                                            │
│ Then click "Refresh field discovery" and retry.           │
│                                                            │
│ ── Raw Jira response ──                                   │
│ {                                                          │
│   "errorMessages": [],                                    │
│   "errors": {                                             │
│     "priority": "Field 'priority' cannot be set. It is   │
│                  not on the appropriate screen, or       │
│                  unknown."                               │
│   }                                                       │
│ }                                                          │
│                                                            │
│ [Refresh field discovery]  [Retry this card]  [Close]    │
└────────────────────────────────────────────────────────────┘
```

#### 6.3.5 Per-Card Badge in Card List

The cards list (existing UI) gets a small Jira badge per row:

```
CORP-101 SSIS analysis              [Task] [5 pts] ✅ CORP-501 ↗
CORP-102 Rule extraction            [Task] [5 pts] ⚠️ CORP-502 ↗  (warnings: 1)
CORP-103 Hash parity                [Task] [8 pts] ❌ Push failed — Diagnose
CORP-104 Disabled task audit        [Task] [3 pts] ◯  Not pushed
```

Tooltip on each:
- ✅ — "Pushed as CORP-501 · 2 min ago · Click to open in Jira"
- ⚠️ — "Pushed but warnings: story_points_dropped"
- ❌ — "Last push failed: {error_message} · Click to diagnose"
- ◯ — "Not yet pushed to Jira"

Driven by denormalized columns on `cards`:
```sql
ALTER TABLE cards
    ADD COLUMN jira_sync_status TEXT DEFAULT 'unsynced',
    ADD COLUMN jira_last_push_error TEXT,
    ADD COLUMN jira_last_push_error_code TEXT,
    ADD COLUMN jira_last_push_warnings TEXT[];
```

These are updated each time an outcome is recorded.

### 6.4 Filtering & Bulk Actions

Outcomes table supports:
- Filter by `status` (all / success / failed / pending / skipped)
- Filter by `error_code` (group all `field_not_on_screen` together)
- Filter by `phase`
- Bulk select → "Retry selected"

### 6.5 CSV Path Failure Surface

CSV path doesn't have per-card outcomes (Jira's wizard does the work). After download:

```
┌────────────────────────────────────────────────────────────┐
│ CSV exported — jira-cards-CORP.csv  [Downloaded]           │
│                                                            │
│ Imported 60 cards to Jira? Reconcile to enable updates:    │
│                                                            │
│   ○ Reconcile from Jira (recommended)                      │
│     Searches Jira for cards by code in summary             │
│                                                            │
│   ○ Upload mapping CSV                                     │
│     Format: workshop_code,jira_key                         │
│                                                            │
│   ○ Skip — I won't need API updates                        │
│                                                            │
│ [Reconcile]   [Cancel]                                    │
└────────────────────────────────────────────────────────────┘
```

After reconciliation, the same `jira_sync_status` columns are populated. Failures here surface as:
- "Reconciliation found X / 60 cards" → list missing ones with copy-paste help

---

## 7. Implementation Phases (8 weeks)

```
┌──────────────────────────────────────────────────────────────────────┐
│  PHASE 1: Connection + Renderer + Schema (Week 1)                     │
│  ├── 1.1: jira_connections, jira_push_jobs, jira_push_outcomes        │
│  ├── 1.2: Card columns (jira_issue_key, sync status, error fields)    │
│  ├── 1.3: CardRenderer (shared by JSON + CSV)                         │
│  ├── 1.4: Connection wizard (URL, key, token, encrypt)                │
│  └── 1.5: Test connection endpoint                                    │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 2: JSON Path — Service + createmeta (Week 2)                   │
│  ├── 2.1: JiraClient (httpx wrapper, retries)                         │
│  ├── 2.2: createmeta discovery + warnings                             │
│  ├── 2.3: JsonPushService.push_card (CREATE)                          │
│  ├── 2.4: Auto-retry without Story Points                             │
│  └── 2.5: UPDATE path for re-runs                                     │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 3: JSON Path — Dramatiq Job + Outcomes (Week 3)                │
│  ├── 3.1: push_cards_json dramatiq actor                              │
│  ├── 3.2: Per-card outcome recording                                  │
│  ├── 3.3: Error classifier (ERROR_CODES table)                        │
│  ├── 3.4: Token bucket rate limiting                                  │
│  ├── 3.5: Retry endpoints (whole job, single card)                    │
│  └── 3.6: Sample mode (single test card gate)                         │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 4: CSV Path (Week 4)                                           │
│  ├── 4.1: CSV export endpoint with streaming                          │
│  ├── 4.2: Wizard mapping cheat-sheet UI                               │
│  ├── 4.3: Reconciliation by JQL (label + summary match)               │
│  ├── 4.4: Reconciliation by mapping file upload                       │
│  └── 4.5: Reconciliation outcomes display                             │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 5: Frontend — Progress + Outcomes (Week 5)                     │
│  ├── 5.1: API client (push jobs, outcomes)                            │
│  ├── 5.2: usePushJob hook (polling with backoff)                      │
│  ├── 5.3: PushJobProgress floating panel                              │
│  ├── 5.4: PushOutcomesTable with filters                              │
│  ├── 5.5: PushOutcomeDetail diagnose modal                            │
│  └── 5.6: Per-card Jira badges in card list                           │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 6: Inbound Webhooks (Week 6)                                   │
│  ├── 6.1: jira_events, agent_flow_runs tables                         │
│  ├── 6.2: HMAC-verified webhook endpoint                              │
│  ├── 6.3: Delivery-ID dedup                                           │
│  ├── 6.4: process_jira_event actor                                    │
│  └── 6.5: Self-originated event filter                                │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 7: Trigger Rules + Agent Handlers (Week 7)                     │
│  ├── 7.1: jira_trigger_rules schema + matching                        │
│  ├── 7.2: Built-in actions: notify, custom_webhook                    │
│  ├── 7.3: execute_card / validate_acceptance / analyze_blocker        │
│  ├── 7.4: Jira comment poster                                         │
│  └── 7.5: Rules editor UI                                             │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 8: Polish (Week 8)                                             │
│  ├── 8.1: Reconciliation job (poll Jira for missed updates)           │
│  ├── 8.2: Activity tab (AgentFlowRun timeline)                        │
│  ├── 8.3: Documentation + screenshots                                 │
│  └── 8.4: Tests with mock Jira server (responses lib)                 │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 8. Quick Start (Week 1)

1. Schema migration (`jira_connections`, card columns)
2. `CardRenderer` with VLI description format
3. `JiraClient` httpx wrapper
4. Connection wizard UI: URL + key + token, test endpoint
5. CSV export endpoint (lowest-risk first deliverable)

---

## Key Decisions Locked In

| Decision | Rationale |
|---|---|
| Two delivery paths (JSON + CSV) | VLI proved both are needed |
| Plain-text `=== SECTION ===` description | VLI-proven Jira-version-agnostic |
| `createmeta` discovery before push | Avoids field-mapping config drift |
| Auto-retry without Story Points | VLI's empirical rescue path |
| Labels-only grouping (no epics) | VLI never needed them |
| Per-card outcomes table | The user explicitly required failure visibility |
| Idempotency via `jira_issue_key` | Persistent map, survives partial failures |
| Sample-mode gate before bulk | Catches 90% of misconfiguration cheaply |
| Error code classifier | Turns Jira's noisy errors into actionable messages |
