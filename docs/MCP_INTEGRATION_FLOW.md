# MCP Integration Flow — Agents Workshop

> How MCP (Model Context Protocol) servers are configured, stored, and used by AI agents in the Migration Workbench workflow.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           Agents Workshop — MCP Integration                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  👤 User                    🖥️ Web UI                      🔌 FastAPI Backend        │
│  (Engineer)                 (Next.js)                      (packages/core)           │
│       │                          │                               │                   │
│       │  Opens Project Settings  │                               │                   │
│       ├─────────────────────────►│                               │                   │
│       │                          │  GET /api/projects/{id}/      │                   │
│       │                          │      mcp-configs              │                   │
│       │                          ├──────────────────────────────►│                   │
│       │                          │                               │                   │
│       │                          │     List[MCPConfigView]       │                   │
│       │                          │◄──────────────────────────────┤                   │
│       │                          │                               │                   │
│       │  ┌────────────────────┐  │                               │                   │
│       │  │ MCP Config Wizard  │  │                               │                   │
│       │  │ ├─ Browse Catalog  │  │                               │                   │
│       │  │ ├─ Select Server   │  │                               │                   │
│       │  │ ├─ Fill Secrets    │  │                               │                   │
│       │  │ └─ Preview JSON    │  │                               │                   │
│       │  └────────────────────┘  │                               │                   │
│       │                          │                               │                   │
│       │  Clicks "Add MCP"        │  POST /api/projects/{id}/     │                   │
│       ├─────────────────────────►│       mcp-configs             │                   │
│       │                          ├──────────────────────────────►│                   │
│       │                          │                               │                   │
│       │                          │    ┌─────────────────────┐    │                   │
│       │                          │    │ MCPConfigService    │    │                   │
│       │                          │    │ ├─ Validate config  │    │                   │
│       │                          │    │ ├─ Encrypt secrets  │    │                   │
│       │                          │    │ └─ Store in DB      │    │                   │
│       │                          │    └─────────────────────┘    │                   │
│       │                          │                               │                   │
│       │                          │    201 Created                │                   │
│       │                          │◄──────────────────────────────┤                   │
│       │                          │                               │                   │
│       │  ✅ "MCP server added"   │                               │                   │
│       │◄─────────────────────────┤                               │                   │
│                                                                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                           Export to Cursor / AI CLI                                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│       │  Clicks "Export for Cursor"                              │                   │
│       ├─────────────────────────►│  GET /api/projects/{id}/      │                   │
│       │                          │      mcp-configs/export       │                   │
│       │                          ├──────────────────────────────►│                   │
│       │                          │                               │                   │
│       │                          │    ┌─────────────────────┐    │                   │
│       │                          │    │ MCPExportService    │    │                   │
│       │                          │    │ ├─ Decrypt secrets  │    │                   │
│       │                          │    │ ├─ Build Cursor fmt │    │                   │
│       │                          │    │ └─ Return JSON      │    │                   │
│       │                          │    └─────────────────────┘    │                   │
│       │                          │                               │                   │
│       │                          │    CursorMCPConfig JSON       │                   │
│       │                          │◄──────────────────────────────┤                   │
│       │                          │                               │                   │
│       │  📥 Downloads .cursor/mcp.json                           │                   │
│       │◄─────────────────────────┤                               │                   │
│                                                                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                           AI Agent Uses MCP Tools                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  🤖 Cursor Agent              📂 .cursor/mcp.json              🔌 MCP Servers        │
│  (or Claude Code)             (in workspace)                   (external)            │
│       │                              │                              │                │
│       │  Discovers config            │                              │                │
│       ├─────────────────────────────►│                              │                │
│       │                              │                              │                │
│       │  Starts MCP servers          │                              │                │
│       ├──────────────────────────────┼─────────────────────────────►│                │
│       │                              │                              │                │
│       │  ┌────────────────────────────────────────────────────┐     │                │
│       │  │ Available Tools:                                    │     │                │
│       │  │ ├─ memory: create_entities, search_nodes, ...      │     │                │
│       │  │ ├─ databricks: run_sql, list_tables, ...           │     │                │
│       │  │ ├─ notion: search_pages, create_page, ...          │     │                │
│       │  │ └─ filesystem: read_file, write_file, ...          │     │                │
│       │  └────────────────────────────────────────────────────┘     │                │
│       │                              │                              │                │
│       │  Calls tool: memory.search_nodes("Customer")                │                │
│       ├─────────────────────────────────────────────────────────────►│                │
│       │                              │                              │                │
│       │  Returns: entities, relations, observations                 │                │
│       │◄─────────────────────────────────────────────────────────────┤                │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase Breakdown

### 📋 Phase 1: Browse MCP Catalog (Read-Only)

**Purpose:** User explores available MCP servers from the curated catalog.

```
User                    Web UI                   API                      Service
 │                        │                       │                          │
 │  Opens MCP Settings    │                       │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │                        │  GET /api/mcp-catalog │                          │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │                       │  MCPCatalogLoader.list() │
 │                        │                       ├─────────────────────────►│
 │                        │                       │                          │
 │                        │                       │  Load from YAML files:   │
 │                        │                       │  ├─ memory.yaml          │
 │                        │                       │  ├─ databricks.yaml      │
 │                        │                       │  ├─ notion.yaml          │
 │                        │                       │  ├─ github.yaml          │
 │                        │                       │  └─ ... (14 total)       │
 │                        │                       │◄─────────────────────────┤
 │                        │                       │                          │
 │                        │  List[MCPCatalogEntry]│                          │
 │                        │◄──────────────────────┤                          │
 │                        │                       │                          │
 │  Shows catalog grid    │                       │                          │
 │  with categories:      │                       │                          │
 │  ├─ database           │                       │                          │
 │  ├─ utility            │                       │                          │
 │  ├─ documentation      │                       │                          │
 │  └─ integration        │                       │                          │
 │◄───────────────────────┤                       │                          │
```

**Catalog entries include:**
- `key`: Unique identifier (e.g., `memory`, `databricks`)
- `name`: Display name
- `description`: What the server does
- `vendor`: Who maintains it
- `category`: database | utility | documentation | integration
- `run_command`: How to start (e.g., `npx @modelcontextprotocol/server-memory`)
- `env_vars`: Required environment variables
- `config_fields`: Additional configuration options
- `tools`: Available tools with risk levels (N1=read, N2=write, N3=destructive)

---

### ✏️ Phase 2: Configure MCP for Project

**Purpose:** User selects MCP servers and provides credentials for a specific project.

```
User                    Web UI                   API                      Service
 │                        │                       │                          │
 │  Clicks "Add Databricks MCP"                   │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │  ┌──────────────────────────────────┐          │                          │
 │  │ Configure Databricks MCP         │          │                          │
 │  │                                  │          │                          │
 │  │ Workspace URL:                   │          │                          │
 │  │ [https://dbc-xxx.cloud.databricks.com]      │                          │
 │  │                                  │          │                          │
 │  │ Personal Access Token: (secret)  │          │                          │
 │  │ [dapi_xxxxxxxxxxxxxxxxxx]        │          │                          │
 │  │                                  │          │                          │
 │  │ Catalog: [prod_catalog]          │          │                          │
 │  │ Schema:  [bronze]                │          │                          │
 │  │                                  │          │                          │
 │  │ [x] Enabled                      │          │                          │
 │  │                                  │          │                          │
 │  │ ┌─────────────────────────────┐  │          │                          │
 │  │ │ Preview JSON:               │  │          │                          │
 │  │ │ {                           │  │          │                          │
 │  │ │   "databricks": {           │  │          │                          │
 │  │ │     "command": "npx",       │  │          │                          │
 │  │ │     "args": ["-y", ...],    │  │          │                          │
 │  │ │     "env": {                │  │          │                          │
 │  │ │       "DATABRICKS_HOST":... │  │          │                          │
 │  │ │     }                       │  │          │                          │
 │  │ │   }                         │  │          │                          │
 │  │ │ }                           │  │          │                          │
 │  │ └─────────────────────────────┘  │          │                          │
 │  │                                  │          │                          │
 │  │        [Cancel]  [Save]          │          │                          │
 │  └──────────────────────────────────┘          │                          │
 │                        │                       │                          │
 │  Clicks "Save"         │                       │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │                        │  POST /api/projects/{id}/mcp-configs             │
 │                        │  {                    │                          │
 │                        │    "catalog_key": "databricks",                  │
 │                        │    "enabled": true,   │                          │
 │                        │    "config": {        │                          │
 │                        │      "workspace_url": "https://...",             │
 │                        │      "catalog": "prod_catalog",                  │
 │                        │      "schema": "bronze"                          │
 │                        │    },                 │                          │
 │                        │    "secrets": {       │                          │
 │                        │      "DATABRICKS_TOKEN": "dapi_xxx"              │
 │                        │    }                  │                          │
 │                        │  }                    │                          │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │                       │  MCPConfigService        │
 │                        │                       │  .create_config()        │
 │                        │                       ├─────────────────────────►│
 │                        │                       │                          │
 │                        │                       │  1. Validate config      │
 │                        │                       │  2. Encrypt secrets      │
 │                        │                       │     (Fernet + HKDF)      │
 │                        │                       │  3. Store in             │
 │                        │                       │     project_mcp_configs  │
 │                        │                       │◄─────────────────────────┤
 │                        │                       │                          │
 │                        │  201 Created          │                          │
 │                        │  MCPConfigView        │                          │
 │                        │◄──────────────────────┤                          │
 │                        │                       │                          │
 │  ✅ "Databricks MCP    │                       │                          │
 │     configured"        │                       │                          │
 │◄───────────────────────┤                       │                          │
```

**Security model:**
- Secrets are encrypted using Fernet symmetric encryption
- Key derived via HKDF from `WORKSHOP_ENCRYPTION_KEY` env var
- Secrets never stored in plaintext
- Masked in UI when reading back (`dapi_***...***`)

---

### 💾 Phase 3: Export for Cursor/AI CLI

**Purpose:** Generate `.cursor/mcp.json` file for use in Cursor IDE or AI CLI.

```
User                    Web UI                   API                      Service
 │                        │                       │                          │
 │  Clicks "Export for Cursor"                    │                          │
 ├───────────────────────►│                       │                          │
 │                        │                       │                          │
 │                        │  GET /api/projects/{id}/mcp-configs/export       │
 │                        │  ?format=cursor       │                          │
 │                        ├──────────────────────►│                          │
 │                        │                       │                          │
 │                        │                       │  MCPExportService        │
 │                        │                       │  .export_cursor_format() │
 │                        │                       ├─────────────────────────►│
 │                        │                       │                          │
 │                        │                       │  1. Load project configs │
 │                        │                       │  2. Filter enabled only  │
 │                        │                       │  3. Decrypt secrets      │
 │                        │                       │  4. Build Cursor format  │
 │                        │                       │◄─────────────────────────┤
 │                        │                       │                          │
 │                        │  CursorMCPConfig      │                          │
 │                        │  {                    │                          │
 │                        │    "mcpServers": {    │                          │
 │                        │      "databricks": {...},                        │
 │                        │      "memory": {...}, │                          │
 │                        │      "notion": {...}  │                          │
 │                        │    }                  │                          │
 │                        │  }                    │                          │
 │                        │◄──────────────────────┤                          │
 │                        │                       │                          │
 │  📥 Downloads          │                       │                          │
 │  .cursor/mcp.json      │                       │                          │
 │◄───────────────────────┤                       │                          │
```

**Export format (Cursor-compatible):**

```json
{
  "mcpServers": {
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"],
      "env": {
        "MEMORY_FILE_PATH": "./data/memory.jsonl"
      }
    },
    "databricks": {
      "command": "npx",
      "args": ["-y", "@anthropic/databricks-mcp"],
      "env": {
        "DATABRICKS_HOST": "https://dbc-xxx.cloud.databricks.com",
        "DATABRICKS_TOKEN": "dapi_xxxxxxxxxx",
        "DATABRICKS_CATALOG": "prod_catalog",
        "DATABRICKS_SCHEMA": "bronze"
      }
    },
    "notion": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-notion"],
      "env": {
        "NOTION_API_KEY": "secret_xxxxxxxxxx"
      }
    }
  }
}
```

---

### 🔄 Phase 4: AI Agent Discovery & Usage

**Purpose:** AI agents (Cursor, Claude Code) discover and use configured MCP tools.

```
Cursor Agent            .cursor/mcp.json         MCP Servers              Memory MCP
     │                        │                       │                       │
     │  Start session         │                       │                       │
     ├───────────────────────►│                       │                       │
     │                        │                       │                       │
     │  Parse mcpServers      │                       │                       │
     │  {memory, databricks,  │                       │                       │
     │   notion}              │                       │                       │
     │◄───────────────────────┤                       │                       │
     │                        │                       │                       │
     │  Start MCP servers     │                       │                       │
     ├────────────────────────┼──────────────────────►│                       │
     │                        │                       │                       │
     │  ┌─────────────────────────────────────────────────────────────────┐   │
     │  │ Tools now available:                                            │   │
     │  │                                                                 │   │
     │  │ memory:                                                         │   │
     │  │ ├─ create_entities(entities) → Create nodes in knowledge graph  │   │
     │  │ ├─ create_relations(relations) → Link entities                  │   │
     │  │ ├─ add_observations(entityName, observations) → Add facts       │   │
     │  │ ├─ search_nodes(query) → Find by name/type/observation          │   │
     │  │ ├─ open_nodes(names) → Get specific nodes + relations           │   │
     │  │ └─ read_graph() → Full knowledge graph                          │   │
     │  │                                                                 │   │
     │  │ databricks:                                                     │   │
     │  │ ├─ run_sql(sql) → Execute SQL statement                         │   │
     │  │ ├─ list_catalogs() → Show Unity Catalog catalogs                │   │
     │  │ ├─ list_schemas(catalog) → Show schemas                         │   │
     │  │ ├─ list_tables(catalog, schema) → Show tables                   │   │
     │  │ └─ describe_table(catalog, schema, table) → Table schema        │   │
     │  │                                                                 │   │
     │  │ notion:                                                         │   │
     │  │ ├─ search_pages(query) → Find Notion pages                      │   │
     │  │ ├─ get_page(id) → Read page content                             │   │
     │  │ └─ create_page(parent, title, content) → Create new page        │   │
     │  └─────────────────────────────────────────────────────────────────┘   │
     │                        │                       │                       │
     │  User: "What tables read from dbo.Customer?"   │                       │
     ├────────────────────────┼───────────────────────┼──────────────────────►│
     │                        │                       │                       │
     │                        │                       │  search_nodes         │
     │                        │                       │  ("Customer")         │
     │                        │                       │◄──────────────────────┤
     │                        │                       │                       │
     │  Returns:              │                       │                       │
     │  - entity: source:table:dbo.Customer           │                       │
     │  - relations:          │                       │                       │
     │    - read_by → package:TTR_001                 │                       │
     │    - read_by → package:PCT_003                 │                       │
     │    - migrates_to → target:table:bronze.crm_customer                    │
     │  - observations:       │                       │                       │
     │    - "Has 250,000 rows, 23 columns"            │                       │
     │    - "Soft-delete pattern (IsActive flag)"     │                       │
     │◄───────────────────────┼───────────────────────┼──────────────────────┤
     │                        │                       │                       │
     │  Agent responds with   │                       │                       │
     │  knowledge from graph  │                       │                       │
```

---

## Database Schema

```sql
-- Per-project MCP configurations
CREATE TABLE project_mcp_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Which MCP server from catalog
    catalog_key TEXT NOT NULL,           -- 'memory', 'databricks', 'notion'
    
    -- Configuration (non-sensitive)
    config_json JSONB NOT NULL DEFAULT '{}',
    
    -- Encrypted secrets
    secrets_encrypted TEXT,              -- Fernet-encrypted JSON
    
    -- State
    enabled BOOLEAN NOT NULL DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (project_id, catalog_key)
);
```

---

## MCP Catalog Entries

Located in `packages/core/app/mcp_catalog/entries/*.yaml`:

| Key | Name | Category | Use Case |
|-----|------|----------|----------|
| `memory` | Memory | utility | Persistent knowledge graph for LLM agents |
| `databricks` | Databricks | database | Unity Catalog, SQL execution, workspace management |
| `notion` | Notion | documentation | Page search, creation, knowledge base access |
| `github` | GitHub | integration | Repository operations, issues, PRs |
| `postgres` | PostgreSQL | database | Direct PostgreSQL queries |
| `sqlserver` | SQL Server | database | Direct SQL Server queries |
| `filesystem` | Filesystem | utility | Local file read/write |
| `fetch` | Fetch | utility | Web scraping for documentation |
| `brave-search` | Brave Search | utility | Web search for up-to-date info |
| `slack` | Slack | integration | Channel messages, search |
| `jira` | Jira | integration | Issue tracking, sprint management |
| `confluence` | Confluence | documentation | Wiki pages, documentation |
| `figma` | Figma | integration | Design file access, components |
| `linear` | Linear | integration | Issue tracking, project management |

---

## Key Advantages

### 1. Zero Manual Configuration
- UI wizard with pre-configured templates
- Real-time JSON preview
- Validation before save

### 2. Database as Source of Truth
- Configs stored in `project_mcp_configs` table
- Full audit trail (created_at, updated_at)
- Per-project isolation

### 3. Security First
- Secrets encrypted with Fernet (AES-128-CBC)
- Key derived from `WORKSHOP_ENCRYPTION_KEY` via HKDF
- Secrets masked in API responses (`***...***`)
- Never logged or exposed in plaintext

### 4. Export Flexibility
- Cursor format (`.cursor/mcp.json`)
- Future: Claude Desktop, AI CLI formats

### 5. Migration Workbench Integration
- Memory MCP for knowledge graph persistence
- Databricks MCP for target workspace operations
- Notion/Confluence for documentation sync

---

## Example: Memory MCP for Migration Knowledge

```
┌─────────────────────────────────────────────────────────────────┐
│                     Memory MCP Usage Flow                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SSIS Parse                 Analysis                Generation   │
│  (Auto)                     (LLM)                   (LLM)        │
│      │                         │                        │        │
│      │  create_entities        │  add_observations      │        │
│      │  ├─ package:TTR_001     │  ├─ "CDC pattern"      │        │
│      │  ├─ table:dbo.Customer  │  ├─ "SCD Type 2"       │        │
│      │  └─ connection:CRM_DB   │  └─ "Decision: MERGE"  │        │
│      ├─────────────────────────┼────────────────────────┤        │
│      │                         │                        │        │
│      │  create_relations       │  create_relations      │        │
│      │  ├─ reads_from          │  ├─ verified_by        │        │
│      │  ├─ writes_to           │  └─ decision_applies   │        │
│      │  └─ uses_connection     │                        │        │
│      ├─────────────────────────┼────────────────────────┤        │
│      │                         │                        │        │
│      ▼                         ▼                        ▼        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Memory MCP (Knowledge Graph)           │    │
│  │                                                          │    │
│  │  Entities:                                               │    │
│  │  ├─ source:package:TTR_001                               │    │
│  │  ├─ source:table:dbo.Customer                            │    │
│  │  ├─ target:table:bronze.crm_customer                     │    │
│  │  └─ migration:decision:incremental_load                  │    │
│  │                                                          │    │
│  │  Relations:                                              │    │
│  │  ├─ TTR_001 → reads_from → dbo.Customer                  │    │
│  │  ├─ dbo.Customer → migrates_to → bronze.crm_customer     │    │
│  │  └─ decision → verified_by → Ana Silva                   │    │
│  │                                                          │    │
│  │  Observations:                                           │    │
│  │  ├─ "dbo.Customer has 250K rows, soft-delete pattern"    │    │
│  │  ├─ "TTR_001 uses CDC via Execute SQL Task"              │    │
│  │  └─ "Decision verified 2026-05-29 by Ana Silva"          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              │  search_nodes("Customer")         │
│                              ▼                                   │
│                    ┌─────────────────────┐                      │
│                    │ Returns full context │                      │
│                    │ for LLM prompts      │                      │
│                    └─────────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Summary Flow

```
User → MCP Wizard UI → API → MCPConfigService → PostgreSQL (encrypted)
                                                      │
                                                      ▼
                                              Export to Cursor
                                                      │
                                                      ▼
                              AI Agent → .cursor/mcp.json → MCP Servers
                                                      │
                                                      ▼
                                              Tools available for
                                              migration analysis,
                                              code generation,
                                              reconciliation
```

---

## File Locations

| Component | Path |
|-----------|------|
| MCP Catalog entries | `packages/core/app/mcp_catalog/entries/*.yaml` |
| Catalog loader | `packages/core/app/mcp_catalog/loader.py` |
| Config service | `packages/core/app/mcp_catalog/service.py` |
| Export service | `packages/core/app/mcp_catalog/export.py` |
| API routes | `packages/core/app/api/mcp_config.py` |
| Crypto utilities | `packages/core/app/crypto.py` |
| DB model | `packages/core/app/modules/migration_workbench/models.py` (ProjectMCPConfig) |
| Design doc | `docs/MEMORY_MCP_DESIGN.md` |
