"""Pydantic schemas for Technology Profiles."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StructuralPattern(BaseModel):
    """A structural pattern found in source technology packages.
    
    Describes code structures that have implications for migration.
    """
    
    id: str = Field(..., description="Unique identifier for the pattern")
    name: str = Field(..., description="Human-readable pattern name")
    description: str = Field(..., description="What this pattern represents")
    detection_hint: str | None = Field(
        None, 
        description="How to detect this pattern (XPath, regex, etc.)"
    )
    migration_implication: str = Field(
        ..., 
        description="What this means for migration"
    )
    skill_suggestion: str | None = Field(
        None, 
        description="Suggested skill to handle this pattern"
    )
    equivalent_in: dict[str, str] = Field(
        default_factory=dict,
        description="Equivalent pattern in other technologies"
    )


class ExecutionPattern(BaseModel):
    """An execution pattern describing runtime behavior.
    
    Describes how packages execute and what modes they support.
    """
    
    id: str = Field(..., description="Unique identifier for the pattern")
    name: str = Field(..., description="Human-readable pattern name")
    description: str = Field(..., description="What this execution pattern does")
    detection_hint: str | None = Field(
        None,
        description="How to detect this pattern"
    )
    migration_implication: str = Field(
        ...,
        description="What this means for target implementation"
    )


class ValidationRequirement(BaseModel):
    """A validation requirement for migration quality assurance.
    
    Describes what must be validated before considering migration complete.
    """
    
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="What needs to be validated")
    rationale: str = Field(..., description="Why this validation is important")
    skill_suggestion: str | None = Field(
        None,
        description="Suggested skill to perform validation"
    )


class TechnologyProfile(BaseModel):
    """Complete profile for a source technology.
    
    Contains all patterns and requirements needed for technology-aware
    skill generation and migration analysis.
    """
    
    name: str = Field(..., description="Full technology name")
    slug: str = Field(..., description="URL-safe identifier")
    file_extension: str = Field(..., description="Primary file extension")
    format: str = Field(..., description="File format (xml, python, json)")
    
    structural_patterns: list[StructuralPattern] = Field(
        default_factory=list,
        description="Code structure patterns"
    )
    execution_patterns: list[ExecutionPattern] = Field(
        default_factory=list,
        description="Runtime behavior patterns"
    )
    validation_requirements: list[ValidationRequirement] = Field(
        default_factory=list,
        description="QA validation requirements"
    )
    
    def get_pattern(self, pattern_id: str) -> StructuralPattern | ExecutionPattern | None:
        """Get a pattern by ID from any category."""
        for pattern in self.structural_patterns:
            if pattern.id == pattern_id:
                return pattern
        for pattern in self.execution_patterns:
            if pattern.id == pattern_id:
                return pattern
        return None
    
    def get_skill_suggestions(self) -> list[str]:
        """Get all skill suggestions from patterns."""
        suggestions = []
        for pattern in self.structural_patterns:
            if pattern.skill_suggestion:
                suggestions.append(pattern.skill_suggestion)
        for req in self.validation_requirements:
            if req.skill_suggestion:
                suggestions.append(req.skill_suggestion)
        return list(set(suggestions))
