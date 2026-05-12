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


class CardTemplate(StrEnum):
    PHASE_VLI = "phase_vli"
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
    PLAIN = "plain"


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


def values_csv(enum_cls: type[StrEnum]) -> str:
    """Return `'a','b','c'` for use inside a SQL CHECK constraint."""
    return ", ".join(f"'{m.value}'" for m in enum_cls)
