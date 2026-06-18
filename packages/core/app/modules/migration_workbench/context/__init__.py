"""Context sub-module for shared migration context.

Provides services for managing:
- Connection registrations across packages
- Business rules discovery and sharing
- Resolved decisions propagation
"""

from app.modules.migration_workbench.context.router import router
from app.modules.migration_workbench.context.schemas import (
    BusinessRuleCreate,
    BusinessRuleView,
    ConnectionCreate,
    ConnectionView,
    DecisionCreate,
    DecisionView,
    ProjectContext,
)
from app.modules.migration_workbench.context.service import ContextService

__all__ = [
    "router",
    "ContextService",
    "ConnectionCreate",
    "ConnectionView",
    "BusinessRuleCreate",
    "BusinessRuleView",
    "DecisionCreate",
    "DecisionView",
    "ProjectContext",
]
