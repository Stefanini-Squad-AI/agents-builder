# SPEC: MCP Server Configuration Interface

**Feature ID:** W-INT-00-UI
**Status:** Planned
**Depends on:** Existing `GapStatus.COVERED_BY_MCP`, `ProjectGap.covered_by_mcp_key`, `GapService.mark_covered_by_mcp()`
**Source analysis:** `docs/STRENGTHENING_ANALYSIS.md` W-INT-00

---

## 1. Objective

Provide a per-project interface where users can configure MCP servers -- entering connection details, API keys, and other secrets -- so that:

1. Workshop can enrich LLM prompts with live data from MCP servers at generation time.
2. The `.agents/` export emits `mcp.config.json` + `.cursor/mcp.json` so consuming agents (Cursor, Claude Code) inherit the same MCP access.
3. Gaps can be marked `covered_by_mcp` with a real, configured MCP backing them.

---

## 2. Domain Model

### 2.1 New table: `project_mcps`

```sql
CREATE TABLE project_mcps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    mcp_key         TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    config_json     JSONB NOT NULL DEFAULT '{}',
    secrets_json    JSONB NOT NULL DEFAULT '{}',
    recommended_by  TEXT,
    approved_by     UUID REFERENCES users(id),
    approved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(project_id, mcp_key)
);

CREATE INDEX ix_project_mcps_project_id ON project_mcps(project_id);
```

**Field semantics:**

| Field | Purpose |
|-------|---------|
| `mcp_key` | Foreign key into the MCP catalog (YAML entries). Identifies which MCP server this row configures. |
| `config_json` | Non-sensitive parameters. Shape is defined by the catalog entry `config_fields`. Example: `{"owner": "my-org", "repo": "my-app"}` |
| `secrets_json` | Sensitive values. Stored as `{"_encrypted": "<fernet_ciphertext>"}` -- a single encrypted blob, not per-key, to avoid partial exposure. Decrypted shape matches the catalog entry `env_vars` keys. |
| `recommended_by` | How this MCP was added: LLM recommendation, manual user action, or team default. |
| `approved_by` / `approved_at` | Human approval gate for MCPs that require it (N3 risk level tools). |

### 2.2 ORM model: `packages/core/app/domain/mcps.py`

Follow the pattern in `packages/core/app/domain/projects.py`:

```python
class ProjectMcp(Base):
    __tablename__ = "project_mcps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    mcp_key: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    secrets_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    recommended_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="mcps")
```

Add `mcps` relationship to `Project` in `domain/projects.py`.

---

## 3. MCP Catalog

### 3.1 Directory structure

```
packages/core/app/mcp_catalog/
  __init__.py
  schema.py          # Pydantic models for catalog entries
  loader.py          # Parse YAML entries, validate against schema
  service.py         # Query/filter catalog
  entries/
    github.yaml
    postgres.yaml
    jira-atlassian.yaml
    fetch.yaml
    filesystem.yaml
    slack.yaml
    confluence.yaml
    sentry.yaml
    memory.yaml
```

### 3.2 Catalog entry schema (`schema.py`)

```python
class MCPCatalogEnvVar(BaseModel):
    required: bool
    secret: bool
    label: str
    hint: str = ""

class MCPCatalogConfigField(BaseModel):
    type: Literal["string", "number", "boolean", "url"]
    required: bool
    label: str
    hint: str = ""
    default: str | None = None

class MCPCatalogTool(BaseModel):
    name: str
    risk_level: Literal["N1", "N2", "N3"]

class MCPCatalogEntry(BaseModel):
    key: str
    name: str
    description: str
    vendor: str
    category: Literal[
        "source_control", "database", "project_management",
        "documentation", "messaging", "monitoring", "utility", "cloud"
    ]
    run_command: str
    env_vars: dict[str, MCPCatalogEnvVar]
    config_fields: dict[str, MCPCatalogConfigField] = {}
    tools: list[MCPCatalogTool] = []
    requires_approval: bool = False
```

### 3.3 YAML entry examples

**`entries/github.yaml`:**
```yaml
key: github
name: GitHub
description: Read repositories, issues, pull requests, and search code
vendor: github
category: source_control
run_command: "npx @modelcontextprotocol/server-github"
env_vars:
  GITHUB_PERSONAL_ACCESS_TOKEN:
    required: true
    secret: true
    label: "Personal Access Token"
    hint: "Generate at github.com/settings/tokens -- needs repo and issues scopes"
config_fields:
  owner:
    type: string
    required: true
    label: "Repository Owner"
    hint: "GitHub org or user that owns the repo"
  repo:
    type: string
    required: false
    label: "Repository Name"
    hint: "Optional -- if blank, all repos in the org are accessible"
tools:
  - name: search_repositories
    risk_level: N1
  - name: get_file_contents
    risk_level: N1
  - name: list_commits
    risk_level: N1
  - name: create_issue
    risk_level: N3
  - name: create_pull_request
    risk_level: N3
requires_approval: false
```

**`entries/postgres.yaml`:**
```yaml
key: postgres
name: PostgreSQL
description: Query database schemas, tables, procedures, and run read-only SQL
vendor: postgresql
category: database
run_command: "npx @modelcontextprotocol/server-postgres"
env_vars:
  POSTGRES_CONNECTION_STRING:
    required: true
    secret: true
    label: "Connection String"
    hint: "Format: postgresql://user:password@host:5432/database"
config_fields: {}
tools:
  - name: query
    risk_level: N2
  - name: list_tables
    risk_level: N1
  - name: describe_table
    risk_level: N1
requires_approval: true
```

**`entries/jira-atlassian.yaml`:**
```yaml
key: jira-atlassian
name: Jira (Atlassian)
description: Read and manage Jira issues, projects, and boards
vendor: atlassian
category: project_management
run_command: "npx @modelcontextprotocol/server-jira"
env_vars:
  JIRA_URL:
    required: true
    secret: false
    label: "Jira Base URL"
    hint: "e.g. https://mycompany.atlassian.net"
  JIRA_USERNAME:
    required: true
    secret: false
    label: "Email"
    hint: "Your Atlassian account email"
  JIRA_API_TOKEN:
    required: true
    secret: true
    label: "API Token"
    hint: "Generate at atlassian.com/my-tokens"
config_fields:
  project_key:
    type: string
    required: true
    label: "Project Key"
    hint: "e.g. PROJ"
tools:
  - name: get_issue
    risk_level: N1
  - name: search_issues
    risk_level: N1
  - name: create_issue
    risk_level: N3
  - name: update_issue
    risk_level: N3
requires_approval: false
```

**`entries/fetch.yaml`:**
```yaml
key: fetch
name: Web Fetch
description: Fetch web pages and APIs for documentation and reference
vendor: modelcontextprotocol
category: utility
run_command: "npx @modelcontextprotocol/server-fetch"
env_vars: {}
config_fields: {}
tools:
  - name: fetch
    risk_level: N1
requires_approval: false
```

**`entries/filesystem.yaml`:**
```yaml
key: filesystem
name: Filesystem
description: Read and write files on the local filesystem
vendor: modelcontextprotocol
category: utility
run_command: "npx @modelcontextprotocol/server-filesystem"
env_vars: {}
config_fields:
  allowed_paths:
    type: string
    required: true
    label: "Allowed Paths"
    hint: "Comma-separated list of directory paths the MCP can access"
tools:
  - name: read_file
    risk_level: N1
  - name: list_directory
    risk_level: N1
  - name: write_file
    risk_level: N3
  - name: create_directory
    risk_level: N3
requires_approval: true
```

**`entries/slack.yaml`:**
```yaml
key: slack
name: Slack
description: Read channels, messages, and post to Slack workspaces
vendor: slack
category: messaging
run_command: "npx @modelcontextprotocol/server-slack"
env_vars:
  SLACK_BOT_TOKEN:
    required: true
    secret: true
    label: "Bot Token"
    hint: "xoxb-... token from Slack app configuration"
config_fields:
  default_channel:
    type: string
    required: false
    label: "Default Channel"
    hint: "Optional default channel ID"
tools:
  - name: list_channels
    risk_level: N1
  - name: get_messages
    risk_level: N1
  - name: post_message
    risk_level: N3
requires_approval: false
```

**`entries/confluence.yaml`:**
```yaml
key: confluence
name: Confluence
description: Read Confluence pages and spaces for design docs and decisions
vendor: atlassian
category: documentation
run_command: "npx @modelcontextprotocol/server-confluence"
env_vars:
  CONFLUENCE_URL:
    required: true
    secret: false
    label: "Confluence Base URL"
    hint: "e.g. https://mycompany.atlassian.net/wiki"
  CONFLUENCE_USERNAME:
    required: true
    secret: false
    label: "Email"
  CONFLUENCE_API_TOKEN:
    required: true
    secret: true
    label: "API Token"
config_fields:
  space_key:
    type: string
    required: false
    label: "Default Space Key"
    hint: "Optional -- limit to a specific Confluence space"
tools:
  - name: search
    risk_level: N1
  - name: get_page
    risk_level: N1
requires_approval: false
```

**`entries/sentry.yaml`:**
```yaml
key: sentry
name: Sentry
description: Read error reports and performance metrics
vendor: sentry
category: monitoring
run_command: "npx @modelcontextprotocol/server-sentry"
env_vars:
  SENTRY_AUTH_TOKEN:
    required: true
    secret: true
    label: "Auth Token"
    hint: "Generate in Sentry Settings > API Keys"
config_fields:
  organization_slug:
    type: string
    required: true
    label: "Organization Slug"
  project_slug:
    type: string
    required: false
    label: "Project Slug"
tools:
  - name: list_issues
    risk_level: N1
  - name: get_issue_details
    risk_level: N1
requires_approval: false
```

**`entries/memory.yaml`:**
```yaml
key: memory
name: Memory
description: Persistent key-value store for cross-session context and decisions
vendor: modelcontextprotocol
category: utility
run_command: "npx @modelcontextprotocol/server-memory"
env_vars: {}
config_fields: {}
tools:
  - name: read
    risk_level: N1
  - name: write
    risk_level: N2
requires_approval: false
```

### 3.4 Loader (`loader.py`)

```python
def load_catalog() -> dict[str, MCPCatalogEntry]:
    """Load all YAML entries from entries/ directory, validate against schema.
    Returns dict keyed by entry.key.
    Raises on invalid entries.
    """
```

### 3.5 Service (`service.py`)

```python
class MCPCatalogService:
    def list_entries() -> list[MCPCatalogEntry]
    def get_entry(key: str) -> MCPCatalogEntry | None
    def filter_by_category(category: str) -> list[MCPCatalogEntry]
    def filter_by_tech(tech_slugs: list[str]) -> list[MCPCatalogEntry]
```

---

## 4. Secret Encryption

### 4.1 Mechanism

- Use **Fernet symmetric encryption** (`cryptography.fernet.Fernet`).
- Encryption key sourced from env var `WORKSHOP_SECRET_KEY` (44-char URL-safe base64).
- If `WORKSHOP_SECRET_KEY` is not set at startup, **generate one**, log a warning, and write it to a `.env` file if possible. Never run without encryption.

### 4.2 Storage format

`secrets_json` is always stored as:
```json
{"_encrypted": "<fernet_ciphertext_base64>"}
```

A single encrypted blob -- not per-key encryption -- to prevent partial exposure via JSON queries.

### 4.3 Service methods

```python
class SecretService:
    @staticmethod
    def encrypt(secrets_dict: dict[str, str]) -> dict:
        # returns {"_encrypted": "..."}

    @staticmethod
    def decrypt(secrets_json: dict) -> dict[str, str]:
        # returns {"KEY": "value", ...}

    @staticmethod
    def mask_secrets(secrets_json: dict) -> dict[str, str]:
        # returns {"KEY": "........"} for UI
```

### 4.4 Security rules

- **Never** return decrypted secrets in any API response.
- **Never** log decrypted secret values.
- `GET` endpoints return masked secrets: `{"GITHUB_PERSONAL_ACCESS_TOKEN": "........"}` with a `has_value: bool` flag.
- Decryption only happens in:
  - `MCPConfigService.get_decrypted_config()` -- server-side only, for runtime MCP invocation.
  - `MCPConfigService.test_connection()` -- server-side only, to validate credentials.

---

## 5. Service Layer

### 5.1 `packages/core/app/services/mcp_config_service.py`

```python
class MCPConfigService:
    def list_project_mcps(self, session, project_id: UUID) -> list[ProjectMcp]
    def get_project_mcp(self, session, mcp_id: UUID) -> ProjectMcp | None
    def add_mcp(self, session, project_id, mcp_key, config, secrets, recommended_by="user") -> ProjectMcp
    def update_config(self, session, mcp_id, config) -> ProjectMcp
    def update_secrets(self, session, mcp_id, secrets) -> ProjectMcp
    def toggle_enabled(self, session, mcp_id, enabled) -> ProjectMcp
    def remove_mcp(self, session, mcp_id) -> None
    def approve_mcp(self, session, mcp_id, user_id) -> ProjectMcp
    def test_connection(self, session, mcp_id) -> McpTestResult
    def get_decrypted_env(self, session, mcp_id) -> dict[str, str]
    def render_mcp_config_json(self, session, project_id) -> dict
    def render_cursor_mcp_json(self, session, project_id) -> dict
```

### 5.2 `McpTestResult`

```python
class McpTestResult(BaseModel):
    success: bool
    message: str
    latency_ms: float | None = None
    server_info: dict | None = None
```

### 5.3 Test connection implementation

For each MCP type, attempt a lightweight connection:

| MCP | Test method |
|-----|-------------|
| **postgres** | `SELECT 1` via psycopg2/asyncpg using decrypted connection string |
| **github** | `GET /user` using decrypted PAT via httpx |
| **jira** | `GET /rest/api/3/myself` using decrypted credentials via httpx |
| **fetch** | No-op (always available, no credentials) |
| **filesystem** | Check that `allowed_paths` directories exist via `os.path.isdir()` |
| **slack** | `auth.test` API call using decrypted bot token via httpx |
| **confluence** | `GET /rest/api/content?limit=1` using decrypted credentials via httpx |
| **sentry** | `GET /api/0/organizations/{org}/` using decrypted auth token via httpx |
| **memory** | No-op (always available, no credentials) |

---

## 6. API Endpoints

### 6.1 Router: `packages/core/app/api/mcps.py`

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/mcps/catalog` | List all catalog entries (what is available) |
| GET | `/api/mcps/catalog/{key}` | Single catalog entry with field definitions |
| GET | `/api/projects/{slug}/mcps` | List MCPs configured for this project |
| POST | `/api/projects/{slug}/mcps` | Add MCP to project (key + config + secrets) |
| PATCH | `/api/projects/{slug}/mcps/{mcp_id}` | Update config/secrets, toggle enabled |
| DELETE | `/api/projects/{slug}/mcps/{mcp_id}` | Remove MCP from project |
| POST | `/api/projects/{slug}/mcps/{mcp_id}/test` | Test connection with stored secrets |
| GET | `/api/projects/{slug}/mcps/{mcp_id}/secrets` | Return secret keys + masked values (never raw) |

### 6.2 Request/response schemas (`packages/core/app/schemas/mcp_schemas.py`)

```python
class AddMcpRequest(BaseModel):
    mcp_key: str
    config: dict[str, Any] = {}
    secrets: dict[str, str] = {}

class UpdateMcpRequest(BaseModel):
    config: dict[str, Any] | None = None
    secrets: dict[str, str] | None = None
    enabled: bool | None = None

class McpConfigResponse(BaseModel):
    id: UUID
    mcp_key: str
    name: str              # from catalog
    description: str       # from catalog
    category: str          # from catalog
    enabled: bool
    config: dict[str, Any]
    secrets: dict[str, str]  # MASKED values only
    recommended_by: str | None
    approved: bool
    tools: list[dict]       # [{name, risk_level}]
    requires_approval: bool

class McpCatalogEntryResponse(BaseModel):
    key: str
    name: str
    description: str
    category: str
    vendor: str
    env_vars: dict         # full schema for UI form rendering
    config_fields: dict    # full schema for UI form rendering
    tools: list[dict]
    requires_approval: bool

class McpTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: float | None = None
    server_info: dict | None = None
```

### 6.3 Router registration

Add to `packages/core/app/main.py` (or wherever routers are mounted):
```python
app.include_router(mcps_router, prefix="/api")
```

---

## 7. UI

### 7.1 New page: `packages/web/src/app/(dashboard)/projects/[slug]/mcps/page.tsx`

Layout:
```
+---------------------------------------------------+
|  Project MCP Servers                               |
+---------------------------------------------------+
|                                                    |
|  [+ Add MCP Server]                               |
|                                                    |
|  +-- GitHub ---------------------- [Enabled v] --+ |
|  |  Owner: my-org       Repo: my-app             | |
|  |  Token: ........      [Test] [Edit] [Remove]   | |
|  +-----------------------------------------------+ |
|                                                    |
|  +-- PostgreSQL ---------------- [Enabled v] ----+ |
|  |  Connection: ........                          | |
|  |  [Test] [Edit] [Remove]                       | |
|  +-----------------------------------------------+ |
+---------------------------------------------------+
```

### 7.2 Add MCP Dialog flow

1. Dropdown populated from `/api/mcps/catalog` -- shows name + description + category
2. On select, renders dynamic form fields from `config_fields` + `env_vars` from the catalog entry
3. Secret fields (where `secret: true`) use `<Input type="password" />` with show/hide toggle
4. Non-secret env vars (where `secret: false`, e.g. JIRA_URL) use regular `<Input />`
5. Each field shows `label`, `hint`, and `required` indicator
6. "Test Connection" button before saving
7. "Save" calls POST with config + secrets

### 7.3 Components

| Component | File | Purpose |
|-----------|------|---------|
| `McpCatalogPicker` | `components/mcp/mcp-catalog-picker.tsx` | Searchable dropdown of available MCPs from catalog |
| `McpConfigForm` | `components/mcp/mcp-config-form.tsx` | Dynamic form driven by catalog entry schema (config_fields + env_vars) |
| `McpSecretField` | `components/mcp/mcp-secret-field.tsx` | Password input with mask/show toggle + has_value indicator |
| `McpCard` | `components/mcp/mcp-card.tsx` | Configured MCP display card with enable toggle, edit, remove |
| `McpTestButton` | `components/mcp/mcp-test-button.tsx` | Async test connection button with loading/success/error states |
| `McpCategoryBadge` | `components/mcp/mcp-category-badge.tsx` | Category label (database, source_control, etc.) |

### 7.4 API client: `packages/web/src/lib/api/mcps.ts`

TanStack Query hooks following existing pattern in `lib/api/`:

```typescript
export function useMcpCatalog()                    // GET /api/mcps/catalog
export function useMcpCatalogEntry(key: string)     // GET /api/mcps/catalog/{key}
export function useProjectMcps(slug: string)        // GET /api/projects/{slug}/mcps
export function useAddMcp(slug: string)             // POST mutation
export function useUpdateMcp(slug: string)          // PATCH mutation
export function useRemoveMcp(slug: string)          // DELETE mutation
export function useTestMcp(slug: string)            // POST .../test mutation
```

---

## 8. Export Integration

### 8.1 `mcp.config.json` format (neutral)

Generated by `MCPConfigService.render_mcp_config_json()`:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<decrypted_value>"
      }
    },
    "postgres": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-postgres", "postgresql://..."],
      "env": {}
    }
  }
}
```

### 8.2 `.cursor/mcp.json` format (Cursor-specific)

Same structure as `mcp.config.json` -- Cursor uses the same format.

### 8.3 Export location

Both files written to the `.agents/` export root:
```
.agents/
  mcp.config.json
  .cursor/mcp.json
  skills/
  jira-cards/
  README.md
```

### 8.4 Security note on export

Exporting `mcp.config.json` with decrypted secrets is a **deliberate choice** -- the consuming agent needs real credentials to use the MCP servers. The `.agents/` folder is intended to live inside the project repo (which should be private). Add a `.gitignore` entry for `mcp.config.json` and `.cursor/mcp.json` by default, with a comment explaining why.

---

## 9. Alembic Migration

File: `packages/core/alembic/versions/<timestamp>_add_project_mcps_table.py`

Follow the pattern of existing migrations (e.g. `20260528_1100_add_project_gaps_table.py`):

```python
def upgrade() -> None:
    op.create_table(
        "project_mcps",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("project_id", sa.UUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mcp_key", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("config_json", sa.JSONB(), nullable=False, server_default="{}"),
        sa.Column("secrets_json", sa.JSONB(), nullable=False, server_default="{}"),
        sa.Column("recommended_by", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "mcp_key", name="uq_project_mcp_key"),
    )
    op.create_index("ix_project_mcps_project_id", "project_mcps", ["project_id"])

def downgrade() -> None:
    op.drop_index("ix_project_mcps_project_id")
    op.drop_table("project_mcps")
```

---

## 10. New Dependency

Add `cryptography` to `packages/core/pyproject.toml` (for Fernet encryption).

---

## 11. File Structure Summary

```
packages/core/app/
  mcp_catalog/
    __init__.py
    schema.py
    loader.py
    service.py
    entries/
      github.yaml
      postgres.yaml
      jira-atlassian.yaml
      fetch.yaml
      filesystem.yaml
      slack.yaml
      confluence.yaml
      sentry.yaml
      memory.yaml
  domain/
    mcps.py
  services/
    mcp_config_service.py
  api/
    mcps.py
  schemas/
    mcp_schemas.py
  alembic/versions/
    xxxx_add_project_mcps_table.py

packages/web/src/
  app/(dashboard)/projects/[slug]/mcps/
    page.tsx
  components/mcp/
    mcp-catalog-picker.tsx
    mcp-config-form.tsx
    mcp-secret-field.tsx
    mcp-card.tsx
    mcp-test-button.tsx
    mcp-category-badge.tsx
  lib/api/
    mcps.ts
```

---

## 12. Implementation Order

1. Alembic migration + domain model (`domain/mcps.py`)
2. MCP catalog schema + YAML entries + loader + service
3. Secret encryption service (`SecretService`)
4. MCP config service (CRUD + test + render)
5. API request/response schemas
6. API endpoints (`api/mcps.py`) + router registration
7. UI API client (`lib/api/mcps.ts`) + TanStack Query hooks
8. UI components (picker, form, card, test button)
9. UI page (`projects/[slug]/mcps/page.tsx`)
10. Export integration (mcp.config.json + .cursor/mcp.json generation)

---

## 13. Acceptance Criteria

- [ ] Catalog loads all 9 YAML entries, validates against `MCPCatalogEntry` schema
- [ ] `GET /api/mcps/catalog` returns all entries with field definitions
- [ ] `POST /api/projects/{slug}/mcps` adds MCP with config + encrypted secrets
- [ ] `GET /api/projects/{slug}/mcps` returns masked secrets (never raw values)
- [ ] `PATCH /api/projects/{slug}/mcps/{id}` updates config and/or secrets
- [ ] `POST /api/projects/{slug}/mcps/{id}/test` validates connection
- [ ] `DELETE /api/projects/{slug}/mcps/{id}` removes MCP
- [ ] Secrets are Fernet-encrypted at rest in `secrets_json`
- [ ] Decrypted secrets never appear in API responses or logs
- [ ] UI renders dynamic form from catalog entry `config_fields` + `env_vars`
- [ ] UI secret fields use password input with show/hide toggle
- [ ] UI test button shows success/error with latency
- [ ] Export generates valid `mcp.config.json` + `.cursor/mcp.json`
- [ ] `.agents/.gitignore` includes `mcp.config.json` and `.cursor/mcp.json`
- [ ] `WORKSHOP_SECRET_KEY` env var documented in README

---

## 14. Context Management Integration

### 14.1 `ProjectContext.mcp_context` — new field

Add to `ProjectContext` in `packages/core/app/schemas/views.py`:

```python
class ProjectContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str
    qa: dict[str, str] = {}
    tech_choices_by_dimension: dict[str, list[TechChoiceView]] = {}
    artifact_groups: dict[str, list[ArtifactSummary]] = {}   # from SPEC_ARTIFACT_GROUPS
    mcp_context: dict[str, str] = {}                         # NEW — mcp_key -> rendered markdown
    context_notes_md: str = ""
```

Each enabled MCP contributes a markdown string to `mcp_context`, keyed by `mcp_key`.

### 14.2 `ProjectContextService` — MCP context loading

In `load_project_context()`, after loading artifact groups:

```python
mcp_context: dict[str, str] = {}
for mcp in project.mcps:
    if not mcp.enabled:
        continue
    rendered = mcp_context_renderer.render(mcp)
    if rendered:
        mcp_context[mcp.mcp_key] = rendered
```

### 14.3 `MCPContextRenderer` — new service

File: `packages/core/app/services/mcp_context_renderer.py`

```python
class MCPContextRenderer:
    """Render MCP-sourced context as markdown for inclusion in LLM prompts."""

    def render(self, mcp: ProjectMcp) -> str | None:
        """Call the MCP server and render results as markdown.

        Returns None if the MCP is not reachable or has no context to contribute.
        """
```

Each MCP type has a specific rendering strategy:

| MCP | Render strategy |
|-----|----------------|
| **fetch** | Fetch configured URLs, return page content as markdown |
| **postgres** | List tables + schemas, render as structured markdown |
| **github** | List repo structure + recent issues, render as markdown |
| **jira** | List project issues, render as markdown |
| **confluence** | List space pages, render as markdown |
| **filesystem** | Not rendered in Workshop context (only in export) |
| **slack** | List recent channel messages, render as markdown |
| **sentry** | List recent issues, render as markdown |
| **memory** | Read stored keys, render as markdown |

### 14.4 `render_project_context()` — MCP section

In `packages/core/app/prompts/context_helpers.py`, after artifact groups:

```python
if context.mcp_context:
    parts.append("**MCP-Sourced Context:**")
    for mcp_key, rendered_md in context.mcp_context.items():
        label = mcp_key.replace('_', ' ').title()
        parts.append(f"- **{label}:** {rendered_md}")
    parts.append("")
```

### 14.5 Prompt impact

Same as artifact grouping: all 5 prompts receive MCP context automatically through `render_project_context()`. No structural changes to prompt classes.

### 14.6 Error handling

MCP context rendering is **best-effort**:
- If an MCP server is unreachable, log a warning and skip it (do not fail the prompt).
- If rendering times out (>10s), log a warning and skip.
- `mcp_context` may be partial — some MCPs contributed, others did not.
- The prompt still executes with whatever context was successfully gathered.

### 14.7 Caching

MCP context is **not cached** between prompt runs. Each LLM generation call fetches fresh MCP context. This ensures:
- Schema changes in postgres are reflected immediately.
- New GitHub issues appear in the next prompt.
- Stale data is never served.

If latency becomes an issue, a per-project TTL cache can be added later (not in MVP).