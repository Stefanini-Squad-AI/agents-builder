"""CLI command groups.

Each module here exposes either a single Typer callback function (wired via
`app.command()`) or a `app` Typer sub-app (wired via `app.add_typer()`) in
`workshop/__main__.py`.

Step 0.6: only `init` and `db migrate` are fully wired. The rest print a
stub message via `_common.stub()` indicating which later step lands them.
"""
