# workshop-core

The core service package: FastAPI HTTP API, Dramatiq async workers, SQLAlchemy + Alembic, LLM provider abstraction, template-family rendering, validators, exporters, and seed loaders.

See [`../../docs/SPEC.md`](../../docs/SPEC.md) for the full architecture.

## Layout (evolves with each implementation step)

```
app/
├── main.py                # FastAPI app factory (Step 0.3)
├── worker.py              # Dramatiq entrypoint (Step 0.9)
├── api/                   # routers (Step 0.5+)
├── domain/                # SQLAlchemy + Pydantic models (Step 0.4–0.5)
├── families/              # template families (Step 1.5)
├── llm/                   # provider abstraction (Step 1.1+)
├── prompts/               # the five LLM prompts (Step 1.6–1.10)
├── extractors/            # markitdown, pdfplumber, csv (Step 0.10)
├── jobs/                  # Dramatiq actors (Step 0.11)
├── validators/            # DAG, refs, frontmatter, paths (Step 1.11)
├── exporters/             # filesystem, zip, mermaid (Step 1.12)
└── seed/                  # tech catalog + reference PoCs (Step 0.7–0.8)
```
