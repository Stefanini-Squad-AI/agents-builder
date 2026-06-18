"""Base parser interface for ETL package parsing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.modules.migration_workbench.analysis.schemas import SSISPackage


class ParserInterface(ABC):
    """Abstract base class for ETL package parsers.
    
    Each technology (SSIS, Airflow, etc.) implements this interface
    to provide consistent parsing output.
    """
    
    @property
    @abstractmethod
    def technology(self) -> str:
        """Return the technology slug this parser handles."""
        ...
    
    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Return the expected file extension (e.g., '.dtsx')."""
        ...
    
    @abstractmethod
    def parse(self, content: str) -> SSISPackage:
        """Parse package content into structured format.
        
        Args:
            content: Raw file content (XML, Python, etc.)
            
        Returns:
            Parsed package structure
            
        Raises:
            ParseError: If content cannot be parsed
        """
        ...
    
    @abstractmethod
    def can_parse(self, content: str) -> bool:
        """Check if this parser can handle the given content.
        
        Args:
            content: Raw file content
            
        Returns:
            True if parser can handle this content
        """
        ...
    
    def extract_metadata(self, content: str) -> dict[str, Any]:
        """Extract basic metadata without full parsing.
        
        Useful for quick inspection before committing to full parse.
        
        Args:
            content: Raw file content
            
        Returns:
            Dictionary with basic metadata
        """
        return {}


class ParseError(Exception):
    """Error during package parsing."""
    
    def __init__(self, message: str, line: int | None = None, details: str | None = None):
        super().__init__(message)
        self.line = line
        self.details = details
