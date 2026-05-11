"""Domain layer — SQLAlchemy 2.0 ORM models.

All persistent entities for Agents Workshop. See docs/SPEC.md section 4.2 for
the field-by-field schema and section 4.3 for indexes.

Importing this package registers all models on `Base.metadata`, which is what
Alembic uses for autogeneration.
"""

# Importing every model module registers them on Base.metadata.
# Order does not matter for SQLAlchemy resolution thanks to string-based
# relationship() targets, but the listed order roughly follows the ERD
# (identity -> projects -> tech -> skills -> backlog -> llm -> exports).
from app.domain import (  # noqa: F401 - registration side-effect
    backlog,
    exports,
    identity,
    llm,
    projects,
    skills,
    tech,
)
from app.domain.base import Base

__all__ = ["Base"]
