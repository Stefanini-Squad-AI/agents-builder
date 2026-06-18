"""Cross-cutting enums used by ORM models, Pydantic schemas, and validators.

Lives at the top of `app/` (not inside `app/domain/`) so importing one enum
does NOT pull in SQLAlchemy via `app.domain.__init__` / `app.domain.base`.
Schemas, validators, prompts, and exporters all import from here directly.

All enums are `StrEnum`s and are stored in Postgres as plain `TEXT` with a
CHECK constraint emitted by `values_csv(enum_cls)`. This avoids the
`ALTER TYPE` pain of native Postgres ENUMs.
"""

from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    EXPORTED = "exported"
    ARCHIVED = "archived"


class ProjectType(StrEnum):
    """Type of project determining available features."""

    APPLICATION = "application"  # Standard application development
    MIGRATION = "migration"  # ETL migration project


class CardTemplate(StrEnum):
    PHASE_VLI = "phase_vli"
    MIGRATION = "migration"  # 7-phase ETL migration template
    STRICT_9 = "strict_9"  # reserved for P5+
    FREE_FORM = "free_form"  # reserved for P5+


class Grouping(StrEnum):
    PHASE = "phase"
    EPIC = "epic"
    FLAT = "flat"


class LlmProvider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
    BEDROCK = "bedrock"


class ArtifactKind(StrEnum):
    DOC = "doc"
    CODE = "code"
    SPEC = "spec"
    GLOSSARY = "glossary"
    OTHER = "other"
    # Lakebridge integration
    ANALYZER_REPORT = "analyzer_report"
    TRANSPILED_CODE = "transpiled_code"
    RECONCILE_RESULT = "reconcile_result"


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    FAILED = "failed"


class SkillKind(StrEnum):
    CONTEXT = "context"
    AUTHORING = "authoring"
    ANALYZER = "analyzer"
    PROCEDURE = "procedure"


class SkillResourceLanguage(StrEnum):
    MARKDOWN = "markdown"
    SQL = "sql"
    YAML = "yaml"
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    JSON = "json"
    BASH = "bash"
    DOCKERFILE = "dockerfile"
    HTML = "html"
    CSS = "css"
    PLAIN = "plain"


class SkillDraftStatus(StrEnum):
    """Tracks the drafting status of a skill body via LLM."""

    NONE = "none"  # Never drafted
    PENDING = "pending"  # Queued for drafting
    DRAFTING = "drafting"  # Currently being drafted
    SUCCESS = "success"  # Drafted successfully
    ERROR = "error"  # Draft failed


class GapStatus(StrEnum):
    """Lifecycle of a coverage gap identified at the project level."""

    OPEN = "open"  # Identified, no decision yet
    ADDRESSED_BY_SKILL = "addressed_by_skill"  # A skill covers this gap
    COVERED_BY_MCP = "covered_by_mcp"  # An external MCP covers this gap
    OUT_OF_SCOPE = "out_of_scope"  # Explicitly excluded from this project


class GapSource(StrEnum):
    """Where a gap was first surfaced."""

    PROPOSE_SKILL_SET = "propose_skill_set"
    MANUAL = "manual"


class CardType(StrEnum):
    TASK = "Task"
    STORY = "Story"
    BUG = "Bug"
    SPIKE = "Spike"
    DEMO = "Demo"


class Priority(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class CardStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class CardDepRelation(StrEnum):
    DEPENDS_ON = "depends_on"
    PARALLEL_WITH = "parallel_with"


class CardInputKind(StrEnum):
    SKILL_RESOURCE = "skill_resource"
    ARTIFACT = "artifact"
    EXTERNAL = "external"


class TechChoiceRole(StrEnum):
    TARGET = "target"
    LEGACY = "legacy"
    OPTIONAL = "optional"
    MUST_AVOID = "must_avoid"
    TBD = "tbd"


class TechChoiceSource(StrEnum):
    CATALOG = "catalog"
    USER_ADDED = "user_added"
    LLM_SUGGESTED = "llm_suggested"


class LlmRunKind(StrEnum):
    PROPOSE_SKILL_SET = "propose_skill_set"
    DRAFT_SKILL_BODY = "draft_skill_body"
    PROPOSE_BACKLOG = "propose_backlog"
    DRAFT_CARD = "draft_card"
    SUGGEST_TECH = "suggest_tech"
    OTHER = "other"


class LlmRunStatus(StrEnum):
    SUCCESS = "success"
    PARSE_ERROR = "parse_error"
    PROVIDER_ERROR = "provider_error"
    IN_PROGRESS = "in_progress"


class ExportKind(StrEnum):
    FILESYSTEM = "filesystem"
    ZIP = "zip"
    JIRA_CSV = "jira_csv"


class UserRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"
    READONLY = "readonly"


# -----------------------------------------------------------------------------
# Lakebridge Integration Enums
# -----------------------------------------------------------------------------


class LakebridgeJobType(StrEnum):
    """Types of Lakebridge CLI operations."""

    ANALYZE = "analyze"
    TRANSPILE_BLADEBRIDGE = "transpile_bladebridge"
    TRANSPILE_MORPHEUS = "transpile_morpheus"
    TRANSPILE_SWITCH = "transpile_switch"
    RECONCILE = "reconcile"


class LakebridgeJobStatus(StrEnum):
    """Status of a Lakebridge job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def values_csv(enum_cls: type[StrEnum]) -> str:
    """Return `'a','b','c'` for use inside a SQL CHECK constraint."""
    return ", ".join(f"'{m.value}'" for m in enum_cls)
