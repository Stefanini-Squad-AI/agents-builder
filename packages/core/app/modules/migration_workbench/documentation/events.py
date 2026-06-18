"""Event hooks for auto-regeneration of documentation.

These hooks integrate with the context service and registry
to trigger documentation regeneration when significant events occur.
"""

from __future__ import annotations

import uuid
from functools import wraps
from typing import Callable, ParamSpec, TypeVar

from sqlalchemy.orm import Session

from app.modules.migration_workbench.documentation.service import DocumentationService


P = ParamSpec("P")
R = TypeVar("R")


# Event types that trigger documentation regeneration
TRIGGER_EVENTS = {
    "package_registered": "Package registered",
    "package_analyzed": "Package analysis completed",
    "package_status_changed": "Package status changed",
    "connection_resolved": "Connection mapping resolved",
    "rule_implemented": "Business rule implemented",
    "decision_recorded": "Decision recorded",
    "blocker_added": "New blocker identified",
    "blocker_resolved": "Blocker resolved",
}


def trigger_doc_regeneration(
    db: Session,
    project_id: uuid.UUID,
    event: str,
    package_id: uuid.UUID | None = None,
) -> None:
    """Trigger documentation regeneration for an event.
    
    Args:
        db: Database session
        project_id: The project to regenerate docs for
        event: Event type from TRIGGER_EVENTS
        package_id: Optional package that triggered the event
    """
    service = DocumentationService(db)
    service.generate_snapshot(
        project_id=project_id,
        trigger_event=event,
        trigger_package_id=package_id,
    )


def auto_regenerate_docs(event: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to auto-regenerate documentation after a service method.
    
    Usage:
        @auto_regenerate_docs("connection_resolved")
        def resolve_connection(self, project_id, ...):
            ...
    
    The decorated method must:
    - Have `self.db` as the database session
    - Take `project_id` as first positional arg
    - Optionally return an object with `package_id` attribute
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            result = func(*args, **kwargs)
            
            # Extract self and project_id from args
            if len(args) >= 2:
                self = args[0]
                project_id = args[1]
                
                # Try to get package_id from result
                package_id = None
                if hasattr(result, "package_id"):
                    package_id = result.package_id
                elif hasattr(result, "id") and hasattr(result, "project_id"):
                    # It's a package itself
                    package_id = result.id
                
                # Trigger regeneration
                if hasattr(self, "db"):
                    trigger_doc_regeneration(
                        db=self.db,
                        project_id=project_id,
                        event=event,
                        package_id=package_id,
                    )
            
            return result
        return wrapper
    return decorator


class DocumentationEventMixin:
    """Mixin class that provides documentation event methods.
    
    Include this in services that should trigger documentation updates.
    """
    
    db: Session  # Must be set by the including class
    
    def _trigger_doc_event(
        self,
        project_id: uuid.UUID,
        event: str,
        package_id: uuid.UUID | None = None,
    ) -> None:
        """Trigger a documentation regeneration event."""
        trigger_doc_regeneration(
            db=self.db,
            project_id=project_id,
            event=event,
            package_id=package_id,
        )
    
    def on_package_registered(self, project_id: uuid.UUID, package_id: uuid.UUID) -> None:
        """Call when a new package is registered."""
        self._trigger_doc_event(project_id, "package_registered", package_id)
    
    def on_package_analyzed(self, project_id: uuid.UUID, package_id: uuid.UUID) -> None:
        """Call when package analysis completes."""
        self._trigger_doc_event(project_id, "package_analyzed", package_id)
    
    def on_connection_resolved(self, project_id: uuid.UUID) -> None:
        """Call when a connection mapping is resolved."""
        self._trigger_doc_event(project_id, "connection_resolved")
    
    def on_rule_implemented(self, project_id: uuid.UUID) -> None:
        """Call when a business rule is implemented."""
        self._trigger_doc_event(project_id, "rule_implemented")
    
    def on_decision_recorded(self, project_id: uuid.UUID) -> None:
        """Call when a new decision is recorded."""
        self._trigger_doc_event(project_id, "decision_recorded")
