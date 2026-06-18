"""Migration Workbench module configuration."""

from __future__ import annotations

from pydantic import BaseModel


class MigrationWorkbenchConfig(BaseModel):
    """Configuration for the Migration Workbench module."""

    # Feature flags
    enabled: bool = True
    enable_batch_operations: bool = True
    enable_knowledge_library: bool = True

    # Analysis settings
    max_packages_per_batch: int = 50
    analysis_timeout_seconds: int = 300

    # Map settings
    auto_detect_relationships: bool = True
    auto_assign_waves: bool = True

    # Supported technologies
    supported_source_technologies: list[str] = [
        "ssis",
        "airflow",
        "informatica",
        "talend",
    ]
    supported_target_technologies: list[str] = [
        "databricks",
        "snowflake",
        "bigquery",
        "synapse",
    ]


# Default configuration instance
default_config = MigrationWorkbenchConfig()


def get_config() -> MigrationWorkbenchConfig:
    """Get the Migration Workbench configuration."""
    return default_config
