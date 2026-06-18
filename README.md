# Agents Workshop

> A tool that, given a programming objective + structured discovery inputs, produces a `.agents/` contract folder (skill library + phase-organized Jira card backlog) that AI coding agents like Cursor, Claude Code, and Gemini CLI can execute one card per session.

**Status:** MVP complete (Phase P2). See [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) for roadmap. Architecture and decisions live in [`docs/SPEC.md`](docs/SPEC.md).

---

## Features

- **Project Management** - Create and manage multiple agent projects with context documents
- **Skills Library** - Define reusable skills (coding guidelines, domain rules, tooling specs) with AI-assisted proposals
- **Backlog Generation** - AI proposes phased implementation cards with dependencies and story points
- **DAG Visualization** - Interactive dependency graph for cards using React Flow
- **In-place Editing** - Edit any skill or card section and regenerate just that section
- **LLM Audit Trail** - Track all AI interactions with cost, tokens, and timing
- **Export** - Download complete `.agents/` folder as ZIP for use with AI coding agents
- **Settings** - Configure LLM provider (Anthropic, OpenAI, Ollama, Bedrock), model, and temperature

---

## Repository layout

```
agents-workshop/
├── docker-compose.yml             # postgres + redis + api + worker
├── pyproject.toml                 # uv workspace marker
├── packages/
│   ├── core/                      # FastAPI + Dramatiq + LLM + templates
│   ├── cli/                       # Typer CLI ("workshop")
│   └── web/                       # Next.js 14 web UI
├── data/                          # runtime artifacts + exports (gitignored)
└── docs/
    ├── SPEC.md                    # architecture, schema, decisions
    └── IMPLEMENTATION_PLAN.md     # phase-by-phase execution script
```

---

## Quick start

### Prerequisites

- **uv** ≥ 0.11
- **Python** 3.12 (managed by uv: `uv python install 3.12`)
- **Docker** + **Docker Compose** v2
- **Node** 22 LTS
- **Git**

### 1. Install Python dependencies

```powershell
uv sync
```

This resolves and installs all workspace member dependencies (`packages/core` and `packages/cli`) into a single shared `.venv` at the repo root.

### 2. Start infrastructure and API

```powershell
# Start PostgreSQL and Redis
docker compose up -d postgres redis

# Run database migrations
uv run alembic -c packages/core/alembic.ini upgrade head

# Start the API server
uv run uvicorn app.main:app --reload --app-dir packages\core
```

The API will be available at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

### 3. Start the Web UI

```powershell
cd packages/web
npm install
npm run dev
```

The web UI will be available at `http://localhost:3000`.

### 4. Configure LLM Provider

1. Navigate to Settings (`http://localhost:3000/settings`)
2. Select your LLM provider (Anthropic, OpenAI, Ollama, or Bedrock)
3. Choose a model and set temperature
4. Set the appropriate API key environment variable:
   - `ANTHROPIC_API_KEY` for Anthropic
   - `OPENAI_API_KEY` for OpenAI
   - Ollama runs locally (no key needed)
   - AWS credentials for Bedrock

---

## Usage

1. **Create a project** - Add a name, slug, and objective
2. **Complete project setup** - Use the Setup Wizard (`/projects/[slug]/setup`) to:
   - Upload context documents (artifacts)
   - Answer 7 discovery questions (3 required)
   - Select your tech stack from the panorama
3. **Propose skills** - Use AI to generate a skill set based on your project context
4. **Review & edit skills** - Customize the proposed skills or add your own
5. **Generate backlog** - AI creates phased implementation cards with dependencies
6. **Visualize DAG** - See the dependency graph and card relationships
7. **Export** - Download the `.agents/` folder for use with AI coding agents

---

## Running Tests

### E2E Tests (Web)

```powershell
cd packages/web
npx playwright install
npm run test:e2e
```

---

## Documentation

- [Architecture & decisions (`docs/SPEC.md`)](docs/SPEC.md)
- [Implementation plan (`docs/IMPLEMENTATION_PLAN.md`)](docs/IMPLEMENTATION_PLAN.md)

---

## License

TBD.
