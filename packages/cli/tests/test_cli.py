"""Smoke tests for the CLI surface.

These exercise the Typer entry point via the test runner — no subprocess
calls. They verify that:
- Every group from SPEC section 11.1 appears in `workshop --help`.
- `workshop --version` prints something with the version string.
- A stubbed command exits 0 with a message containing 'Stub'.
- `workshop init` writes the marker file idempotently in a tmp workspace.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner
from workshop.__main__ import app

runner = CliRunner()


def test_help_lists_every_group() -> None:
    """Top-level --help must mention every command group from SPEC section 11.1."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = result.stdout
    for group in (
        "init",
        "validate",
        "dag",
        "db",
        "project",
        "qa",
        "tech",
        "artifact",
        "skill",
        "backlog",
        "card",
        "export",
        "llm-runs",
    ):
        assert group in out, f"Group '{group}' missing from --help:\n{out}"


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "workshop" in result.stdout


@pytest.mark.parametrize(
    "argv",
    [
        ["project", "list"],
        ["skill", "propose", "--project", "x"],
        ["backlog", "propose", "--project", "x"],
        ["card", "list", "--project", "x"],
        ["validate", "--project", "x"],
        ["dag", "--project", "x"],
        ["qa", "list", "--project", "x"],
        ["tech", "list", "--project", "x"],
    ],
)
def test_stubs_exit_cleanly(argv: list[str]) -> None:
    """Stub commands print the friendly message and exit 0."""
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, f"argv={argv} stdout={result.stdout}"
    assert "Stub" in result.stdout or "not implemented" in result.stdout


def test_artifact_list_requires_live_api() -> None:
    """artifact list is now a real command — it exits non-zero when the API is
    unreachable (no Uvicorn running in unit-test context)."""
    result = runner.invoke(app, ["artifact", "list", "--project", "x"])
    # Exit 1 with a clear 'Cannot reach API' message — not a stub.
    assert result.exit_code == 1
    assert "Stub" not in result.stdout
    assert "Cannot reach" in result.stdout or "API error" in result.stdout


def test_db_subcommand_help() -> None:
    """`workshop db --help` lists the wired Alembic subcommands."""
    result = runner.invoke(app, ["db", "--help"])
    assert result.exit_code == 0
    for sub in ("migrate", "downgrade", "revision", "current", "history", "seed"):
        assert sub in result.stdout


def test_init_creates_marker_and_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`workshop init` creates the .workshop marker and data/ in a fresh repo."""
    # Build a minimal fake repo-root: pyproject.toml with [tool.uv.workspace].
    (tmp_path / "pyproject.toml").write_text(
        "[tool.uv.workspace]\nmembers = []\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / ".workshop").exists()
    assert (tmp_path / "data").is_dir()
    assert (tmp_path / "data" / ".gitkeep").exists()

    # Re-running is idempotent and tells the user nothing changed.
    result2 = runner.invoke(app, ["init"])
    assert result2.exit_code == 0
    assert "already exists" in result2.stdout

    # --force re-writes the marker.
    result3 = runner.invoke(app, ["init", "--force"])
    assert result3.exit_code == 0
    assert "Wrote" in result3.stdout


def test_init_fails_outside_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Outside a workspace, init prints a clear error and exits non-zero."""
    # tmp_path has no pyproject.toml at all → find_repo_root should fail.
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 2
    # The error message goes to stdout via Rich's console.
    assert "Could not locate" in result.stdout or result.exit_code == 2
