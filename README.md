# Agents Workshop

> A tool that, given a programming objective + structured discovery inputs, produces a `.agents/` contract folder (skill library + phase-organized Jira card backlog) that AI coding agents like Cursor, Claude Code, and Gemini CLI can execute one card per session.

**Status:** in active implementation. See [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) for current phase. Architecture and decisions live in [`docs/SPEC.md`](docs/SPEC.md).

---

## Repository layout

```
agents-workshop/
├── docker-compose.yml             # postgres + redis + api + worker (added in P0)
├── pyproject.toml                 # uv workspace marker
├── packages/
│   ├── core/                      # FastAPI + Dramatiq + LLM + templates
│   ├── cli/                       # Typer CLI ("workshop")
│   └── web/                       # Next.js 14 web UI (P2)
├── data/                          # runtime artifacts + exports (gitignored)
└── docs/
    ├── SPEC.md                    # architecture, schema, decisions
    └── IMPLEMENTATION_PLAN.md     # phase-by-phase execution script
```

---

## Quick start (will be filled in as steps land)

### Prerequisites

- **uv** ≥ 0.11
- **Python** 3.12 (managed by uv: `uv python install 3.12`)
- **Docker** + **Docker Compose** v2
- **Node** 22 LTS (only needed for the web UI in P2)
- **Git**

### Install Python dependencies

```powershell
uv sync
```

This resolves and installs all workspace member dependencies (`packages/core` and `packages/cli`) into a single shared `.venv` at the repo root.

### Run the API (coming in Step 0.3)

```powershell
docker compose up -d postgres redis
uv run uvicorn app.main:app --reload --app-dir packages\core
```

---

## Documentation

- [Architecture & decisions (`docs/SPEC.md`)](docs/SPEC.md)
- [Implementation plan (`docs/IMPLEMENTATION_PLAN.md`)](docs/IMPLEMENTATION_PLAN.md)

---

## License

TBD.
