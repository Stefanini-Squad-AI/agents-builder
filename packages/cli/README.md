# workshop-cli

Typer-based CLI for Agents Workshop. Installed as the `workshop` console script.

See [`../../docs/SPEC.md`](../../docs/SPEC.md) §11 for the full command surface.

## Layout

```
workshop/
├── __main__.py            # Typer app entrypoint (Step 0.6)
└── commands/              # one module per command group (Step 0.6+)
    ├── db.py
    ├── project.py
    ├── artifact.py
    ├── qa.py
    ├── tech.py
    ├── skill.py
    ├── backlog.py
    ├── card.py
    ├── validate.py
    ├── export.py
    └── llm_runs.py
```
