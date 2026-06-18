"""LLM service factory for creating LLM services from project configuration."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.db
from app.domain.projects import Project
from app.enums import LlmProvider
from app.llm.factory import create_provider
from app.llm.service import LLMService
from app.settings import Settings


class LlmServiceFactory:
    """Factory for creating LLM services configured for specific projects."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the factory with application settings.
        
        Args:
            settings: Application settings. If None, will load from environment.
        """
        self.settings = settings or Settings()

    def create_for_project(self, project_slug: str, session: Session) -> LLMService:
        """Create an LLM service configured for a specific project.
        
        Args:
            project_slug: Project slug to get LLM configuration from
            session: Database session for LLM audit logging
            
        Returns:
            Configured LLMService instance
            
        Raises:
            ValueError: If project not found or LLM provider not configured
        """
        # Get project
        project = session.execute(
            select(Project).where(Project.slug == project_slug)
        ).scalar_one_or_none()
        
        if not project:
            raise ValueError(f"Project '{project_slug}' not found")
        
        # Get LLM configuration from project
        provider_type = LlmProvider(project.llm_provider)
        model = project.llm_model
        temperature = float(project.llm_temperature)
        
        # Create provider
        provider = create_provider(
            provider_type=provider_type,
            settings=self.settings,
            model_override=model,
            temperature_override=temperature
        )
        
        # Create service with project_id for audit logging
        return LLMService(session=session, provider=provider, project_id=project.id)

    def create_for_project_id(self, project_id: UUID, session: Session) -> LLMService:
        """Create an LLM service configured for a specific project by ID.
        
        Args:
            project_id: Project UUID to get LLM configuration from
            session: Database session for LLM audit logging
            
        Returns:
            Configured LLMService instance
            
        Raises:
            ValueError: If project not found or LLM provider not configured
        """
        project = session.get(Project, project_id)
        
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found")
        
        # Get LLM configuration from project
        provider_type = LlmProvider(project.llm_provider)
        model = project.llm_model
        temperature = float(project.llm_temperature)
        
        # Create provider
        provider = create_provider(
            provider_type=provider_type,
            settings=self.settings,
            model_override=model,
            temperature_override=temperature
        )
        
        # Create service with project_id for audit logging
        return LLMService(session=session, provider=provider, project_id=project.id)

    def create_default(self, session: Session) -> LLMService:
        """Create an LLM service with default configuration.
        
        Args:
            session: Database session for LLM audit logging
            
        Returns:
            LLMService with default provider configuration
        """
        # Use default provider from settings
        provider_type = LlmProvider(self.settings.llm_provider)
        
        provider = create_provider(
            provider_type=provider_type,
            settings=self.settings
        )
        
        return LLMService(session=session, provider=provider)

    def list_available_providers(self) -> list[dict[str, str]]:
        """List available LLM providers and their configuration status.
        
        Returns:
            List of provider info dictionaries
        """
        from app.llm.factory import get_provider_status
        
        providers = []
        for provider_enum in LlmProvider:
            status = get_provider_status(provider_enum, self.settings)
            
            providers.append({
                "provider": provider_enum.value,
                "name": provider_enum.value.title(),
                "configured": status["configured"],
                "error": status.get("error")
            })
        
        return providers


def create_llm_service_for_project(project_slug: str) -> LLMService:
    """Convenience function to create LLM service for a project with new session.
    
    Args:
        project_slug: Project slug
        
    Returns:
        Configured LLMService instance
    """
    factory = LlmServiceFactory()
    
    with app.db.session_scope() as session:
        return factory.create_for_project(project_slug, session)


def create_default_llm_service() -> LLMService:
    """Convenience function to create default LLM service with new session.
    
    Returns:
        LLMService with default configuration
    """
    factory = LlmServiceFactory()
    
    with app.db.session_scope() as session:
        return factory.create_default(session)