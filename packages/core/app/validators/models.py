"""Import all domain models to ensure proper SQLAlchemy mapper initialization."""

# Import all domain models to ensure proper mapper relationships are established
from app.domain.backlog import Card, CardDep, CardInput, CardSkill, Phase  # noqa: F401
from app.domain.exports import Export  # noqa: F401
from app.domain.identity import Tenant, User  # noqa: F401
from app.domain.llm import LlmRun  # noqa: F401
from app.domain.projects import Project, ProjectQaAnswer  # noqa: F401
from app.domain.skills import Skill, SkillResource  # noqa: F401
from app.domain.tech import ProjectTechChoice, TechDimension, TechItem  # noqa: F401

# This ensures all SQLAlchemy relationships are properly configured
# when validators import this module
