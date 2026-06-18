# SPEC: Jira Integration & Time Tracking

**Feature ID:** W-JIRA-INT
**Status:** Planned
**Depends on:** `Card`, `CardStatus`, `LlmRun`, `LLMService`, `ExportService`, `ExportKind.JIRA_CSV`, Fernet encryption (from MCP config spec)

---

## 1. Objective

Provide bidirectional Jira integration so that:

1. Workshop cards can be **pushed to Jira** as issues, creating a live link between Workshop planning and Jira execution tracking.
2. Status changes in Jira **sync back** to Workshop, keeping the backlog view current without manual updates.
3. LLM execution time (calling + reasoning) per card is **tracked and pushed to Jira** as worklog entries or custom fields, giving teams visibility into AI-assisted effort.

Implementation is **phased**:
- **Phase 1** — Jira connection config, push creation, bidirectional sync, sync monitoring.
- **Phase 2** — LLM time tracking per card, aggregation, push to Jira time-tracking fields.

---

## 2. Phased Delivery

| Phase | Scope | Value |
|-------|-------|-------|
| Phase 1 | Jira config, push, sync, monitoring | Cards appear in Jira; status stays in sync; teams track work where they already are |
| Phase 2 | LLM time tracking, Jira worklog push | Teams see AI effort (calling time + reasoning time) per card in Jira |

---

# Phase 1: Jira Integration

---

## 3. Domain Model

### 3.1 New table: `jira_configs`

Per-project Jira connection configuration. One row per project (1:1).

```sql
CREATE TABLE jira_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    base_url        TEXT NOT NULL,
    email           TEXT NOT NULL,
    api_token_enc   TEXT NOT NULL,
    project_key     TEXT NOT NULL,
    status_map_json JSONB NOT NULL DEFAULT '{}',
    field_map_json  JSONB NOT NULL DEFAULT '{}',
    webhook_secret  TEXT,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(project_id)
);

CREATE INDEX ix_jira_configs__project_id ON jira_configs(project_id);
```

**Field semantics:**

| Field | Purpose |
|-------|---------|
| `base_url` | Jira Cloud or Server base URL (e.g. `https://myorg.atlassian.net`) |
| `email` | Atlassian account email used for API auth |
| `api_token_enc` | Fernet-encrypted API token. Never returned in API responses. |
| `project_key` | Jira project key (e.g. `PROJ`) — issues will be created in this project |
| `status_map_json` | Mapping from Workshop `CardStatus` to Jira status name. Example: `{"draft": "To Do", "ready": "Ready", "in_progress": "In Progress", "done": "Done"}` |
| `field_map_json` | Mapping from Workshop card fields to Jira custom field IDs. Example: `{"story_points": "customfield_10021", "phase": "customfield_10030"}` |
| `webhook_secret` | Optional shared secret for validating incoming Jira webhook signatures |
| `enabled` | Toggle sync on/off without deleting config |

### 3.2 ORM: `JiraConfig`

Add to `packages/core/app/domain/jira.py`:

```python
class JiraConfig(UuidPkMixin, TimestampsMixin, Base):
    __tablename__ = "jira_configs"
    __table_args__ = (
        UniqueConstraint("project_id", name="project_jira_config_unique"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    api_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    project_key: Mapped[str] = mapped_column(Text, nullable=False)
    status_map_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="'{}'")
    field_map_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="'{}'")
    webhook_secret: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    project: Mapped[Project] = relationship(back_populates="jira_config")
```

Add relationship to `Project`:

```python
jira_config: Mapped[JiraConfig | None] = relationship(
    back_populates="project",
    uselist=False,
    cascade="all, delete-orphan",
)
```

### 3.3 New table: `jira_issue_links`

Links a Workshop `Card` to a Jira issue. One card maps to at most one Jira issue.

```sql
CREATE TABLE jira_issue_links (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id         UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    jira_key        TEXT NOT NULL,
    jira_id         TEXT NOT NULL,
    sync_status     TEXT NOT NULL DEFAULT 'synced',
    push_version    INTEGER NOT NULL DEFAULT 1,
    last_synced_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(card_id),
    UNIQUE(jira_key)
);

CREATE INDEX ix_jira_issue_links__card_id ON jira_issue_links(card_id);
CREATE INDEX ix_jira_issue_links__jira_key ON jira_issue_links(jira_key);
CREATE INDEX ix_jira_issue_links__sync_status ON jira_issue_links(sync_status);
```

**Field semantics:**

| Field | Purpose |
|-------|---------|
| `jira_key` | Jira issue key (e.g. `PROJ-123`) |
| `jira_id` | Jira internal issue ID (for API calls that use ID) |
| `sync_status` | One of: `synced`, `push_pending`, `pull_pending`, `conflict`, `error` |
| `push_version` | Monotonically increasing counter — incremented on each push. Used for optimistic concurrency: if Jira version is ahead, we detect a conflict. |
| `last_synced_at` | Timestamp of last successful sync |
| `last_error` | Last sync error message (cleared on successful sync) |

### 3.4 ORM: `JiraIssueLink`

```python
class JiraIssueLink(UuidPkMixin, Base):
    __tablename__ = "jira_issue_links"
    __table_args__ = (
        UniqueConstraint("card_id", name="card_jira_link_unique"),
        UniqueConstraint("jira_key", name="jira_key_unique"),
        CheckConstraint(
            f"sync_status IN ({values_csv(JiraSyncStatus)})",
            name="sync_status_valid",
        ),
        Index("ix_jira_issue_links__sync_status", "sync_status"),
    )

    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
    )
    jira_key: Mapped[str] = mapped_column(Text, nullable=False)
    jira_id: Mapped[str] = mapped_column(Text, nullable=False)
    sync_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=JiraSyncStatus.SYNCED.value,
    )
    push_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    last_error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    card: Mapped[Card] = relationship(back_populates="jira_link")
```

Add relationship to `Card`:

```python
jira_link: Mapped[JiraIssueLink | None] = relationship(
    back_populates="card",
    uselist=False,
    cascade="all, delete-orphan",
)
```

### 3.5 New table: `jira_sync_log`

Audit log for all Jira sync operations.

```sql
CREATE TABLE jira_sync_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    direction       TEXT NOT NULL,
    jira_key        TEXT,
    card_id         UUID REFERENCES cards(id) ON DELETE SET NULL,
    operation       TEXT NOT NULL,
    status          TEXT NOT NULL,
    detail_json     JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_jira_sync_log__project_created ON jira_sync_log(project_id, created_at DESC);
```

**Field semantics:**

| Field | Purpose |
|-------|---------|
| `direction` | `push` (Workshop to Jira) or `pull` (Jira to Workshop) |
| `operation` | `create`, `update`, `transition`, `delete`, `bulk_push`, `bulk_pull` |
| `status` | `success`, `error`, `conflict`, `skipped` |
| `detail_json` | Structured details: changed fields, error messages, conflict info |

### 3.6 ORM: `JiraSyncLog`

```python
class JiraSyncLog(UuidPkMixin, Base):
    __tablename__ = "jira_sync_log"
    __table_args__ = (
        CheckConstraint(
            f"direction IN ({values_csv(JiraSyncDirection)})",
            name="direction_valid",
        ),
        CheckConstraint(
            f"status IN ({values_csv(JiraSyncLogStatus)})",
            name="log_status_valid",
        ),
        Index("ix_jira_sync_log__project_created", "project_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    jira_key: Mapped[str | None] = mapped_column(Text)
    card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", ondelete="SET NULL"),
    )
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    detail_json: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="'{}'")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
```

---

## 4. Enums

Add to `packages/core/app/enums.py`:

```python
class JiraSyncStatus(StrEnum):
    SYNCED = "synced"
    PUSH_PENDING = "push_pending"
    PULL_PENDING = "pull_pending"
    CONFLICT = "conflict"
    ERROR = "error"

class JiraSyncDirection(StrEnum):
    PUSH = "push"
    PULL = "pull"

class JiraSyncLogStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    CONFLICT = "conflict"
    SKIPPED = "skipped"
```

---

## 5. Card to Jira Issue Field Mapping

When pushing a Workshop card to Jira, the following fields are mapped:

| Workshop Card field | Jira issue field | Notes |
|---------------------|------------------|-------|
| `code` | `summary` prefix | Summary becomes `[PROJ-101] Card title` |
| `title` | `summary` | Appended after code prefix |
| `type` | `issuetype` | Task to Task, Story to Story, Bug to Bug, Spike to Story (label "spike"), Demo to Task (label "demo") |
| `status` | `status` | Via `status_map_json` |
| `priority` | `priority` | Low to Low, Medium to Medium, High to High |
| `story_points` | Custom field | Via `field_map_json.story_points` |
| `context_md` | `description` | Rendered as Jira wiki markup (basic MD to Jira conversion) |
| `task_md` | Description section | Appended to description under `h2. Tasks` |
| `outputs_md` | Description section | Appended under `h2. Outputs` |
| `acceptance_criteria_md` | Description section | Appended under `h2. Acceptance Criteria` |
| `phase.code + phase.name` | Custom field or label | Via `field_map_json.phase`, or as a Jira label `phase:PHASE_CODE` |
| `human_gate` | Label | `human-gate` label if true |
| `skill_links` | Labels | One label per skill slug: `skill:slug` |

### 5.1 Markdown to Jira Wiki Markup

A lightweight converter handles the most common patterns:

| Markdown | Jira Wiki Markup |
|----------|-----------------|
| `# Heading` | `h1. Heading` |
| `## Heading` | `h2. Heading` |
| `**bold**` | `*bold*` |
| `*italic*` | `_italic_` |
| `- item` | `* item` |
| `[text](url)` | `[text|url]` |

Unrecognized markdown is passed through verbatim — Jira renders plain text acceptably.

---

## 6. Jira API Client

### 6.1 `JiraClient`

Add to `packages/core/app/jira/client.py`:

```python
class JiraClient:
    """Low-level Jira REST API v3 client.

    Uses Atlassian email + API token auth (Basic auth).
    All methods raise JiraApiError on HTTP errors.
    """

    def __init__(self, base_url: str, email: str, api_token: str) -> None: ...

    async def create_issue(
        self,
        project_key: str,
        issuetype: str,
        summary: str,
        description: str | None = None,
        priority: str | None = None,
        labels: list[str] | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> JiraIssueResponse: ...

    async def update_issue(
        self,
        issue_key: str,
        *,
        summary: str | None = None,
        description: str | None = None,
        priority: str | None = None,
        labels: list[str] | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> JiraIssueResponse: ...

    async def transition_issue(
        self,
        issue_key: str,
        transition_id: str,
    ) -> None: ...

    async def get_issue(self, issue_key: str) -> JiraIssueResponse: ...

    async def get_transitions(self, issue_key: str) -> list[JiraTransition]: ...

    async def search_issues(
        self,
        jql: str,
        fields: list[str] | None = None,
    ) -> list[JiraIssueResponse]: ...

    async def add_worklog(
        self,
        issue_key: str,
        time_seconds: int,
        comment: str | None = None,
        started: str | None = None,
    ) -> JiraWorklogResponse: ...
```

### 6.2 Response models

```python
class JiraIssueResponse(BaseModel):
    key: str
    id: str
    summary: str
    status: str
    issuetype: str
    priority: str | None = None
    labels: list[str] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    updated: datetime | None = None

class JiraTransition(BaseModel):
    id: str
    name: str

class JiraWorklogResponse(BaseModel):
    id: str
    time_seconds: int
    comment: str | None = None
    created: datetime | None = None
```

### 6.3 Error handling

```python
class JiraApiError(Exception):
    """Raised on Jira API HTTP errors."""

    def __init__(self, status_code: int, message: str, issue_key: str | None = None):
        self.status_code = status_code
        self.message = message
        self.issue_key = issue_key
        super().__init__(f"Jira API error {status_code}: {message}")
```

---

## 7. Service Layer

### 7.1 `JiraConfigService`

Add to `packages/core/app/services/jira_config_service.py`:

```python
class JiraConfigService:
    """CRUD for Jira connection config with Fernet encryption."""

    def get_config(self, project_slug: str) -> JiraConfig | None: ...
    def create_config(self, project_slug: str, request: CreateJiraConfigRequest) -> JiraConfig: ...
    def update_config(self, project_slug: str, request: UpdateJiraConfigRequest) -> JiraConfig: ...
    def delete_config(self, project_slug: str) -> None: ...
    def test_connection(self, project_slug: str) -> JiraConnectionTestResult: ...
```

**Encryption:** `api_token_enc` is encrypted/decrypted using the same Fernet key and pattern as MCP secrets (see SPEC_MCP_CONFIG.md section 2.1). The `api_token` is never stored plaintext and never returned in API responses.

**`test_connection()`** calls `JiraClient.get_myself()` to validate credentials and returns:

```python
class JiraConnectionTestResult(BaseModel):
    connected: bool
    display_name: str | None = None
    error: str | None = None
```

### 7.2 `JiraPushService`

Add to `packages/core/app/services/jira_push_service.py`:

```python
class JiraPushService:
    """Push Workshop cards to Jira as issues."""

    def push_card(self, project_slug: str, card_id: UUID) -> JiraIssueLink:
        """Push a single card to Jira.

        - If card has no existing link: create Jira issue, create JiraIssueLink.
        - If card has an existing link: update Jira issue fields.
        - Sets sync_status = SYNCED on success, ERROR on failure.
        - Logs to jira_sync_log.
        """

    def push_all(self, project_slug: str, *, status_filter: list[CardStatus] | None = None) -> BulkPushResult:
        """Push all (or filtered) cards for a project.

        Creates Jira issues for unlinked cards, updates existing links.
        Returns summary of created/updated/errored counts.
        """
```

```python
class BulkPushResult(BaseModel):
    created: int
    updated: int
    errored: int
    errors: list[BulkPushError] = Field(default_factory=list)

class BulkPushError(BaseModel):
    card_id: UUID
    card_code: str
    error: str
```

### 7.3 `JiraSyncService`

Add to `packages/core/app/services/jira_sync_service.py`:

```python
class JiraSyncService:
    """Bidirectional sync between Workshop cards and Jira issues."""

    def pull_status(self, project_slug: str) -> SyncResult:
        """Pull status changes from Jira for all linked cards.

        For each JiraIssueLink:
        1. Fetch current Jira issue status via JiraClient.get_issue().
        2. Map Jira status back to CardStatus via inverse of status_map_json.
        3. If status changed: update Card.status, set link sync_status = SYNCED.
        4. If Jira issue was updated after last_synced_at: mark PULL_PENDING first.
        Logs each operation to jira_sync_log.
        """

    def push_status(self, project_slug: str, card_id: UUID) -> None:
        """Push a single card status change to Jira.

        1. Look up JiraIssueLink for the card.
        2. Map Card.status to Jira status via status_map_json.
        3. Find the transition ID via JiraClient.get_transitions().
        4. Execute transition via JiraClient.transition_issue().
        """

    def resolve_conflict(
        self,
        project_slug: str,
        card_id: UUID,
        resolution: ConflictResolution,
    ) -> None:
        """Resolve a sync conflict.

        resolution:
        - "use_workshop": overwrite Jira with Workshop values
        - "use_jira": overwrite Workshop with Jira values
        - "skip": leave both as-is, clear conflict status
        """
```

```python
class SyncResult(BaseModel):
    pulled: int
    pushed: int
    conflicts: int
    errors: int

class ConflictResolution(StrEnum):
    USE_WORKSHOP = "use_workshop"
    USE_JIRA = "use_jira"
    SKIP = "skip"
```

---

## 8. API Endpoints

Add to `packages/core/app/api/jira.py`:

```
router = APIRouter(tags=["jira"])
```

### 8.1 Config endpoints

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| POST | `/api/projects/{slug}/jira/config` | `create_jira_config` | Create Jira connection config. Encrypts `api_token`. |
| GET | `/api/projects/{slug}/jira/config` | `get_jira_config` | Get config (api_token masked). |
| PATCH | `/api/projects/{slug}/jira/config` | `update_jira_config` | Update config fields. Re-encrypts token if changed. |
| DELETE | `/api/projects/{slug}/jira/config` | `delete_jira_config` | Delete config and all links (cascade). |
| POST | `/api/projects/{slug}/jira/config/test` | `test_jira_connection` | Test Jira credentials. Returns `JiraConnectionTestResult`. |

### 8.2 Push endpoints

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| POST | `/api/projects/{slug}/jira/push` | `push_all_to_jira` | Push all cards. Optional `status_filter` query param. |
| POST | `/api/projects/{slug}/jira/push/{card_id}` | `push_card_to_jira` | Push single card. |
| DELETE | `/api/projects/{slug}/jira/links/{card_id}` | `unlink_card` | Remove JiraIssueLink (does NOT delete Jira issue). |

### 8.3 Sync endpoints

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| POST | `/api/projects/{slug}/jira/sync` | `sync_from_jira` | Pull status changes from Jira for all linked cards. |
| POST | `/api/projects/{slug}/jira/sync/{card_id}` | `push_status_to_jira` | Push single card status to Jira. |
| POST | `/api/projects/{slug}/jira/conflicts/{card_id}/resolve` | `resolve_sync_conflict` | Resolve a sync conflict. |

### 8.4 Monitoring endpoints

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/api/projects/{slug}/jira/links` | `list_jira_links` | List all JiraIssueLinks for project. |
| GET | `/api/projects/{slug}/jira/links/{card_id}` | `get_jira_link` | Get link for specific card. |
| GET | `/api/projects/{slug}/jira/sync-log` | `list_sync_log` | List sync log entries (paginated, newest first). |
| GET | `/api/projects/{slug}/jira/status` | `get_jira_status` | Summary: total linked, by sync_status, last sync time. |

### 8.5 Webhook endpoint

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| POST | `/api/jira/webhook` | `jira_webhook` | Receive Jira webhook events. Validates signature. Triggers pull for affected issue. |

---

## 9. Pydantic Schemas

Add to `packages/core/app/schemas/jira.py`:

```python
class CreateJiraConfigRequest(BaseModel):
    base_url: str
    email: str
    api_token: str
    project_key: str
    status_map: dict[str, str] = Field(default_factory=dict)
    field_map: dict[str, str] = Field(default_factory=dict)
    webhook_secret: str | None = None

class UpdateJiraConfigRequest(BaseModel):
    base_url: str | None = None
    email: str | None = None
    api_token: str | None = None
    project_key: str | None = None
    status_map: dict[str, str] | None = None
    field_map: dict[str, str] | None = None
    webhook_secret: str | None = None
    enabled: bool | None = None

class JiraConfigView(BaseModel):
    id: UUID
    project_id: UUID
    base_url: str
    email: str
    project_key: str
    status_map: dict[str, str]
    field_map: dict[str, str]
    enabled: bool
    created_at: datetime
    updated_at: datetime

class JiraIssueLinkView(BaseModel):
    id: UUID
    card_id: UUID
    jira_key: str
    jira_id: str
    sync_status: JiraSyncStatus
    push_version: int
    last_synced_at: datetime
    last_error: str | None
    created_at: datetime

class JiraSyncLogView(BaseModel):
    id: UUID
    direction: JiraSyncDirection
    jira_key: str | None
    card_id: UUID | None
    operation: str
    status: JiraSyncLogStatus
    detail: dict[str, Any]
    created_at: datetime

class JiraStatusSummary(BaseModel):
    total_linked: int
    by_sync_status: dict[str, int]
    last_sync_at: datetime | None
    config_enabled: bool

class ResolveConflictRequest(BaseModel):
    resolution: ConflictResolution
```

**Security note:** `JiraConfigView` never includes `api_token` or `api_token_enc`. The token is write-only.

---

## 10. UI Components

### 10.1 Jira Config Panel

Location: Project settings tab "Jira Integration"

- Form fields: base URL, email, API token (password input), project key
- "Test Connection" button — calls `POST /api/projects/{slug}/jira/config/test`
- Status map editor: 4 rows (draft, ready, in_progress, done) with Jira status name inputs
- Field map editor: key-value pairs for custom field IDs
- Enable/disable toggle
- Save button — `POST` or `PATCH` config

### 10.2 Card Jira Link Badge

On each card in the backlog view:

- If linked: show `Jira: PROJ-123` badge (clickable, opens Jira in new tab)
- Sync status indicator: green (synced), yellow (pending), red (conflict/error)
- If unlinked: "Push to Jira" button

### 10.3 Bulk Push Dialog

Triggered from backlog toolbar "Push to Jira" button:

- Shows count of cards to push (unlinked = create, linked = update)
- Optional status filter checkboxes
- Progress indicator during push
- Result summary: created/updated/errored

### 10.4 Sync Status Dashboard

Project-level Jira status panel:

- Total linked cards, by sync status
- Last sync timestamp
- "Sync Now" button — calls `POST /api/projects/{slug}/jira/sync`
- Conflict list with resolution buttons (Use Workshop / Use Jira / Skip)
- Sync log table (paginated, newest first)

---

## 11. Webhook Integration

### 11.1 Jira Webhook Setup

When Jira config is created or updated, the UI displays instructions for setting up a Jira webhook:

- Webhook URL: `{WORKSHOP_BASE_URL}/api/jira/webhook`
- Events: `jira:issue_updated` (status transitions)
- The `webhook_secret` is used for HMAC-SHA256 signature validation

### 11.2 Webhook Processing Flow

1. Receive POST at `/api/jira/webhook`
2. Validate HMAC signature using `webhook_secret`
3. Extract `issue.key` and `issue.fields.status.name` from payload
4. Look up `JiraIssueLink` by `jira_key`
5. If found and `sync_status != CONFLICT`: map Jira status to CardStatus, update Card
6. Log to `jira_sync_log`

---

## 12. Alembic Migration

```python
def upgrade() -> None:
    op.create_table("jira_configs", ...)
    op.create_table("jira_issue_links", ...)
    op.create_table("jira_sync_log", ...)

def downgrade() -> None:
    op.drop_table("jira_sync_log")
    op.drop_table("jira_issue_links")
    op.drop_table("jira_configs")
```

---

## 13. Export Integration

The existing `ExportKind.JIRA_CSV` placeholder is replaced by a real `JiraCsvExporter` that:

1. Generates a CSV file with columns: `code, title, type, status, priority, story_points, phase, description, jira_key`
2. Includes `jira_key` from `JiraIssueLink` if linked, empty otherwise
3. Is registered in the exporter factory alongside `FilesystemExporter` and `ZipExporter`

---

# Phase 2: LLM Time Tracking

---

## 14. Objective

Track LLM execution time per card and push it to Jira, giving teams visibility into AI-assisted effort:

- **Calling time**: wall-clock time the LLM provider took to respond (`duration_ms` already tracked in `LlmRun`)
- **Reasoning time**: estimated reasoning effort via `reasoning_tokens` (already tracked)
- **Cost**: `cost_usd` already tracked

---

## 15. Domain Model Changes

### 15.1 Add `card_id` to `LlmRun`

Add nullable FK to `packages/core/app/domain/llm.py`:

```python
card_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("cards.id", ondelete="SET NULL"),
    nullable=True,
)

card: Mapped[Card | None] = relationship(back_populates="llm_runs_for_card")
```

Add relationship to `Card`:

```python
llm_runs_for_card: Mapped[list[LlmRun]] = relationship(
    back_populates="card",
    foreign_keys="LlmRun.card_id",
)
```

Add index:

```python
Index("ix_llm_runs__card_id", "card_id"),
```

**Why nullable:** Not all LLM runs are card-specific (e.g. `propose_skill_set`, `suggest_tech`). Only `draft_card` and `draft_skill_body` runs are linked to a card.

### 15.2 Setting `card_id` on LLM Runs

Modify `LLMService.run()` to accept an optional `card_id`:

```python
def run(
    self,
    prompt: ChatPrompt[T],
    *,
    kind: LlmRunKind = LlmRunKind.OTHER,
    card_id: uuid.UUID | None = None,
) -> ChatResult[T]:
```

The `run()` method sets `run.card_id = card_id` when creating the `LlmRun` row.

Callers that should pass `card_id`:
- `draft_card` endpoint in `backlog.py` — passes the card being drafted
- `regenerate_card_section` endpoint — passes the card being regenerated

Callers that should NOT pass `card_id`:
- `propose_skill_set`, `propose_backlog`, `suggest_tech` — these are project-level, not card-level

---

## 16. Card Time Aggregation

### 16.1 `CardTimeService`

Add to `packages/core/app/services/card_time_service.py`:

```python
class CardTimeService:
    """Aggregate LLM execution metrics per card."""

    def get_card_time(self, project_slug: str, card_id: UUID) -> CardTimeSummary:
        """Aggregate LlmRun metrics for a single card.

        Sums: duration_ms, reasoning_tokens, tokens_in, tokens_out, cost_usd
        Counts: number of LLM runs
        """

    def get_project_time(self, project_slug: str) -> list[CardTimeSummary]:
        """Aggregate LLM metrics for all cards in a project."""

    def push_time_to_jira(self, project_slug: str, card_id: UUID) -> None:
        """Push aggregated time as a Jira worklog entry.

        Uses JiraClient.add_worklog() with:
        - time_seconds = total_duration_ms / 1000
        - comment = "AI effort: {count} LLM calls, {reasoning_tokens} reasoning tokens, ${cost_usd}"
        """
```

```python
class CardTimeSummary(BaseModel):
    card_id: UUID
    card_code: str
    card_title: str
    llm_run_count: int
    total_duration_ms: int
    total_reasoning_tokens: int
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: Decimal
    jira_key: str | None = None
```

### 16.2 SQL Aggregation

```sql
SELECT
    c.id AS card_id,
    c.code AS card_code,
    c.title AS card_title,
    COUNT(lr.id) AS llm_run_count,
    COALESCE(SUM(lr.duration_ms), 0) AS total_duration_ms,
    COALESCE(SUM(lr.reasoning_tokens), 0) AS total_reasoning_tokens,
    COALESCE(SUM(lr.tokens_in), 0) AS total_tokens_in,
    COALESCE(SUM(lr.tokens_out), 0) AS total_tokens_out,
    COALESCE(SUM(lr.cost_usd), 0) AS total_cost_usd
FROM cards c
LEFT JOIN llm_runs lr ON lr.card_id = c.id AND lr.status = 'success'
WHERE c.phase_id IN (SELECT id FROM phases WHERE project_id = :project_id)
GROUP BY c.id, c.code, c.title
ORDER BY total_duration_ms DESC;
```

---

## 17. Time Tracking API Endpoints

Add to `packages/core/app/api/jira.py`:

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| GET | `/api/projects/{slug}/cards/{card_id}/time` | `get_card_time` | Get LLM time summary for a card. |
| GET | `/api/projects/{slug}/time` | `get_project_time` | Get LLM time summary for all cards. |
| POST | `/api/projects/{slug}/jira/push-time/{card_id}` | `push_time_to_jira` | Push card time as Jira worklog. |
| POST | `/api/projects/{slug}/jira/push-time` | `push_all_time_to_jira` | Push time for all linked cards. |

---

## 18. Time Tracking UI

### 18.1 Card Time Badge

On each card in the backlog view:

- Show AI effort summary: `AI: 12.3s | $0.04` (duration + cost)
- Tooltip: full breakdown (calls, tokens, reasoning tokens)

### 18.2 Project Time Dashboard

New tab "AI Effort" in project view:

- Table: card code, title, LLM run count, duration, reasoning tokens, cost, Jira link
- Sortable by any column
- "Push to Jira" button — pushes worklog entries for all linked cards
- Total row at bottom

### 18.3 Jira Worklog Display

After pushing time to Jira, the worklog entry appears in the Jira issue's "Work Log" tab with:
- Time: rounded to nearest minute (Jira worklog minimum)
- Comment: `AI effort: 3 LLM calls, 450 reasoning tokens, $0.04 cost`

---

## 19. Phase 2 Alembic Migration

```python
def upgrade() -> None:
    op.add_column("llm_runs", sa.Column("card_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_llm_runs__card_id__cards", "llm_runs", "cards", ["card_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_llm_runs__card_id", "llm_runs", ["card_id"])

def downgrade() -> None:
    op.drop_index("ix_llm_runs__card_id", "llm_runs")
    op.drop_constraint("fk_llm_runs__card_id__cards", "llm_runs", type_="foreignkey")
    op.drop_column("llm_runs", "card_id")
```

---

## 20. Frontend Hooks

Add to `packages/web/src/hooks/useJira.ts` (following existing TanStack Query patterns):

```typescript
export function useJiraConfig(slug: string) { ... }
export function useCreateJiraConfig(slug: string) { ... }
export function useUpdateJiraConfig(slug: string) { ... }
export function useDeleteJiraConfig(slug: string) { ... }
export function useTestJiraConnection(slug: string) { ... }
export function useJiraLinks(slug: string) { ... }
export function usePushToJira(slug: string) { ... }
export function useSyncFromJira(slug: string) { ... }
export function useJiraSyncLog(slug: string) { ... }
export function useJiraStatus(slug: string) { ... }
export function useCardTime(slug: string, cardId: string) { ... }
export function useProjectTime(slug: string) { ... }
export function usePushTimeToJira(slug: string) { ... }
```

---

## 21. Acceptance Criteria

### Phase 1

- [ ] Jira config CRUD works with encrypted API token
- [ ] Test connection validates credentials against Jira API
- [ ] Single card push creates Jira issue with correct field mapping
- [ ] Bulk push creates/updates all project cards
- [ ] Status sync pulls Jira status changes back to Workshop
- [ ] Status sync pushes Workshop status changes to Jira
- [ ] Conflict detection works when both sides change status
- [ ] Conflict resolution (use_workshop, use_jira, skip) works correctly
- [ ] Webhook endpoint validates HMAC signature
- [ ] Webhook triggers pull for affected issue
- [ ] Sync log records all push/pull operations
- [ ] API token never appears in API responses or logs
- [ ] JiraCsvExporter generates CSV with jira_key column
- [ ] UI: config panel with test connection button
- [ ] UI: card Jira link badge with sync status indicator
- [ ] UI: bulk push dialog with progress
- [ ] UI: sync status dashboard with conflict resolution

### Phase 2

- [ ] `card_id` FK added to `llm_runs` table
- [ ] `LLMService.run()` accepts optional `card_id` parameter
- [ ] `draft_card` endpoint passes `card_id` to `LLMService.run()`
- [ ] `regenerate_card_section` endpoint passes `card_id` to `LLMService.run()`
- [ ] `CardTimeService.get_card_time()` returns correct aggregation
- [ ] `CardTimeService.get_project_time()` returns correct aggregation for all cards
- [ ] `CardTimeService.push_time_to_jira()` creates Jira worklog entry
- [ ] Card time badge shows AI effort summary
- [ ] Project time dashboard shows sortable table with totals
- [ ] Jira worklog comment includes LLM call count, reasoning tokens, cost
- [ ] Time rounded to nearest minute for Jira worklog minimum