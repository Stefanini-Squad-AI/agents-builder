"""Lakebridge CLI Client — wrapper for Databricks CLI commands.

Provides async subprocess execution with timeout, stdout/stderr capture,
and structured result handling. Used by:
- Prerequisites check (Phase 1c)
- Analyzer execution (Phase 1d)
- Transpiler execution (Phase 2)
- Reconciler execution (Phase 3)
"""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass
from typing import Any

import structlog

from app.domain.lakebridge import DatabricksConfig
from app.schemas.lakebridge import PrerequisitesView

log = structlog.get_logger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60


@dataclass
class CLIResult:
    """Result of a CLI command execution."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class LakebridgeCLIClient:
    """Wrapper for Databricks CLI and Lakebridge extension commands.

    Executes CLI commands asynchronously with:
    - Timeout protection
    - stdout/stderr capture
    - PAT passed via environment variable (not CLI args)
    - Structured result objects

    Usage:
        client = LakebridgeCLIClient()
        result = await client.run_command(["databricks", "--version"])
        if result.success:
            print(result.stdout)
    """

    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        working_dir: str | None = None,
    ):
        self._timeout = timeout_seconds
        self._working_dir = working_dir

    async def run_command(
        self,
        args: list[str],
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> CLIResult:
        """Execute a CLI command asynchronously.

        Args:
            args: Command and arguments (e.g., ["databricks", "--version"])
            env: Additional environment variables (merged with os.environ)
            timeout: Override default timeout in seconds

        Returns:
            CLIResult with exit code, stdout, stderr, and timing
        """
        import time

        command_str = " ".join(args)
        effective_timeout = timeout or self._timeout

        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        log.debug(
            "cli_command_start",
            command=command_str,
            timeout=effective_timeout,
        )

        start_time = time.monotonic()
        timed_out = False
        exit_code = -1
        stdout = ""
        stderr = ""

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env,
                cwd=self._working_dir,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=effective_timeout,
                )
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                exit_code = process.returncode or 0

            except asyncio.TimeoutError:
                timed_out = True
                process.kill()
                await process.wait()
                stderr = f"Command timed out after {effective_timeout}s"
                log.warning(
                    "cli_command_timeout",
                    command=command_str,
                    timeout=effective_timeout,
                )

        except FileNotFoundError:
            exit_code = 127
            stderr = f"Command not found: {args[0]}"
            log.warning("cli_command_not_found", command=args[0])

        except Exception as e:
            exit_code = 1
            stderr = str(e)
            log.error("cli_command_error", command=command_str, error=str(e))

        duration_ms = int((time.monotonic() - start_time) * 1000)

        result = CLIResult(
            command=command_str,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            timed_out=timed_out,
        )

        log.debug(
            "cli_command_complete",
            command=command_str,
            exit_code=exit_code,
            duration_ms=duration_ms,
            success=result.success,
        )

        return result

    async def check_databricks_cli(self) -> tuple[bool, str | None]:
        """Check if Databricks CLI is installed.

        Returns:
            (is_installed, version_or_error)
        """
        if not shutil.which("databricks"):
            return False, "databricks command not found in PATH"

        result = await self.run_command(["databricks", "--version"], timeout=10)

        if result.success:
            version = result.stdout.strip().split("\n")[0]
            return True, version

        return False, result.stderr or "Unknown error"

    async def check_lakebridge_extension(self) -> tuple[bool, str | None]:
        """Check if Lakebridge extension is installed.

        Returns:
            (is_installed, version_or_error)
        """
        result = await self.run_command(
            ["databricks", "labs", "lakebridge", "--help"],
            timeout=15,
        )

        if result.success:
            return True, "Lakebridge extension available"

        if "unknown command" in result.stderr.lower():
            return False, "Lakebridge extension not installed. Run: databricks labs install lakebridge"

        return False, result.stderr or "Unknown error"

    async def check_workspace_reachable(
        self,
        workspace_url: str,
        pat: str,
        profile: str = "DEFAULT",
    ) -> tuple[bool, str | None]:
        """Check if workspace is reachable with the provided PAT.

        Args:
            workspace_url: Databricks workspace URL
            pat: Personal Access Token (plaintext)
            profile: CLI profile name

        Returns:
            (is_reachable, message_or_error)
        """
        env = {
            "DATABRICKS_HOST": workspace_url,
            "DATABRICKS_TOKEN": pat,
        }

        result = await self.run_command(
            ["databricks", "auth", "token", "--profile", profile],
            env=env,
            timeout=15,
        )

        if result.success:
            return True, "Workspace authenticated successfully"

        if "401" in result.stderr or "unauthorized" in result.stderr.lower():
            return False, "Authentication failed: Invalid or expired PAT"

        if "could not resolve" in result.stderr.lower():
            return False, f"Cannot reach workspace: {workspace_url}"

        return False, result.stderr or "Unknown error"

    async def check_all_prerequisites(
        self,
        config: DatabricksConfig | None,
        decrypted_pat: str | None,
    ) -> PrerequisitesView:
        """Run all prerequisite checks.

        Args:
            config: Databricks configuration (or None if not configured)
            decrypted_pat: Decrypted PAT (or None if no config)

        Returns:
            PrerequisitesView with all check results
        """
        cli_ok, cli_msg = await self.check_databricks_cli()

        if not cli_ok:
            return PrerequisitesView(
                cli_installed=False,
                lakebridge_installed=False,
                workspace_reachable=False,
                all_ok=False,
            )

        lb_ok, lb_msg = await self.check_lakebridge_extension()

        if not config or not decrypted_pat:
            return PrerequisitesView(
                cli_installed=cli_ok,
                lakebridge_installed=lb_ok,
                workspace_reachable=False,
                all_ok=False,
            )

        ws_ok, ws_msg = await self.check_workspace_reachable(
            workspace_url=config.workspace_url,
            pat=decrypted_pat,
            profile=config.cli_profile,
        )

        all_ok = cli_ok and lb_ok and ws_ok

        log.info(
            "lakebridge_prerequisites_check",
            cli_installed=cli_ok,
            lakebridge_installed=lb_ok,
            workspace_reachable=ws_ok,
            all_ok=all_ok,
        )

        return PrerequisitesView(
            cli_installed=cli_ok,
            lakebridge_installed=lb_ok,
            workspace_reachable=ws_ok,
            all_ok=all_ok,
        )

    async def run_analyzer(
        self,
        source_dialect: str,
        input_path: str,
        output_path: str,
        workspace_url: str,
        pat: str,
        catalog: str = "remorph",
        schema: str = "transpiler",
        extra_args: list[str] | None = None,
    ) -> CLIResult:
        """Run Lakebridge analyzer command.

        Args:
            source_dialect: Source SQL dialect (e.g., oracle, snowflake, tsql)
            input_path: Path to input files
            output_path: Path for output report
            workspace_url: Databricks workspace URL
            pat: Personal Access Token
            catalog: Unity Catalog name
            schema: Schema name within catalog
            extra_args: Additional CLI arguments

        Returns:
            CLIResult with command output
        """
        env = {
            "DATABRICKS_HOST": workspace_url,
            "DATABRICKS_TOKEN": pat,
        }

        args = [
            "databricks",
            "labs",
            "lakebridge",
            "analyze",
            "--source",
            source_dialect,
            "--input-path",
            input_path,
            "--output-path",
            output_path,
            "--catalog",
            catalog,
            "--schema",
            schema,
        ]

        if extra_args:
            args.extend(extra_args)

        return await self.run_command(args, env=env, timeout=300)

    async def run_transpiler(
        self,
        source_dialect: str,
        transpiler: str,
        input_path: str,
        output_path: str,
        workspace_url: str,
        pat: str,
        catalog: str = "remorph",
        schema: str = "transpiler",
        extra_args: list[str] | None = None,
    ) -> CLIResult:
        """Run Lakebridge transpiler command.

        Args:
            source_dialect: Source SQL dialect
            transpiler: Transpiler to use (bladebridge, morpheus, switch)
            input_path: Path to input files
            output_path: Path for output files
            workspace_url: Databricks workspace URL
            pat: Personal Access Token
            catalog: Unity Catalog name
            schema: Schema name
            extra_args: Additional CLI arguments

        Returns:
            CLIResult with command output
        """
        env = {
            "DATABRICKS_HOST": workspace_url,
            "DATABRICKS_TOKEN": pat,
        }

        args = [
            "databricks",
            "labs",
            "lakebridge",
            "transpile",
            "--source",
            source_dialect,
            "--transpiler",
            transpiler,
            "--input-path",
            input_path,
            "--output-path",
            output_path,
            "--catalog",
            catalog,
            "--schema",
            schema,
        ]

        if extra_args:
            args.extend(extra_args)

        return await self.run_command(args, env=env, timeout=600)


def get_cli_client(
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    working_dir: str | None = None,
) -> LakebridgeCLIClient:
    """Factory function for LakebridgeCLIClient."""
    return LakebridgeCLIClient(
        timeout_seconds=timeout_seconds,
        working_dir=working_dir,
    )
