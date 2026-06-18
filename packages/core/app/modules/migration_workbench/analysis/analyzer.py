"""LLM-powered analysis for ETL packages.

Uses the LLM service to analyze parsed packages against technology profiles,
detect patterns, identify blockers, and generate migration recommendations.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.llm import ChatMessage, ChatPrompt, LLMService
from app.modules.migration_workbench.analysis.schemas import (
    BlockerItem,
    BlockerSeverity,
    BlockerType,
    BusinessRuleDiscovery,
    DecisionItem,
    DetectedPattern,
    PackageAnalysis,
    SSISPackage,
)
from app.modules.migration_workbench.analysis.strategy_classifier import (
    StrategyClassifier,
)
from app.modules.migration_workbench.profiles.loader import ProfileLoader


# -----------------------------------------------------------------------------
# Response Schemas for LLM
# -----------------------------------------------------------------------------


class PatternMatch(BaseModel):
    """Pattern match from LLM analysis."""
    
    pattern_id: str = Field(..., description="ID from the technology profile")
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: str = Field(..., description="Where/how the pattern was detected")
    migration_implication: str | None = Field(None, description="Impact on migration")


class DetectedBlocker(BaseModel):
    """Blocker detected by LLM analysis."""
    
    blocker_type: str = Field(..., description="technical, business, infrastructure, data_quality")
    title: str
    description: str | None = None
    severity: str = Field(..., description="low, medium, high, critical")
    affected_components: list[str] = Field(default_factory=list)
    suggested_action: str | None = None
    decision_type: str | None = Field(None, description="Type for auto-resolution lookup")


class DiscoveredRule(BaseModel):
    """Business rule discovered by LLM analysis."""
    
    rule_name: str
    description: str
    source_code: str | None = None
    category: str | None = None
    applies_to_tables: list[str] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    """Complete analysis response from LLM."""
    
    complexity: str = Field(..., description="low, medium, high, very_high")
    domain: str | None = Field(None, description="Business domain if identifiable")
    estimated_effort: str | None = Field(None, description="xs, s, m, l, xl")
    
    patterns: list[PatternMatch] = Field(default_factory=list)
    blockers: list[DetectedBlocker] = Field(default_factory=list)
    business_rules: list[DiscoveredRule] = Field(default_factory=list)
    
    target_notebook_structure: str | None = Field(
        None, description="Suggested Databricks notebook structure"
    )
    migration_notes: list[str] = Field(
        default_factory=list, description="Important migration considerations"
    )
    analysis_summary: str | None = Field(None, description="Brief summary of findings")


# -----------------------------------------------------------------------------
# Analyzer
# -----------------------------------------------------------------------------


class PackageAnalyzer:
    """LLM-powered analyzer for ETL packages.
    
    Uses technology profiles to guide analysis and provide context-aware
    pattern detection and migration recommendations.
    """
    
    def __init__(
        self,
        llm_service: LLMService,
        profile_loader: ProfileLoader | None = None,
    ):
        """Initialize analyzer.
        
        Args:
            llm_service: LLM service for running analysis
            profile_loader: Profile loader (creates default if not provided)
        """
        self.llm_service = llm_service
        self.profile_loader = profile_loader or ProfileLoader()
    
    def analyze(
        self,
        package: SSISPackage,
        package_id: uuid.UUID,
        source_technology: str = "ssis",
        target_technology: str = "databricks",
        project_context: dict[str, Any] | None = None,
    ) -> PackageAnalysis:
        """Analyze a parsed package using LLM.
        
        Args:
            package: Parsed SSIS package
            package_id: ID of the ETLPackage record
            source_technology: Source technology (e.g., 'ssis')
            target_technology: Target technology (e.g., 'databricks')
            project_context: Optional context (resolved decisions, rules, etc.)
            
        Returns:
            PackageAnalysis with patterns, blockers, and recommendations
        """
        # Load technology profile
        profile = self.profile_loader.load_profile(source_technology)
        
        # Build prompt
        prompt = self._build_analysis_prompt(
            package=package,
            profile=profile,
            target_technology=target_technology,
            project_context=project_context,
        )
        
        # Run LLM
        result = self.llm_service.run(prompt)
        
        # Backward analysis: classify target generation strategy from parsed package
        # (deterministic, runs regardless of LLM result)
        classifier = StrategyClassifier()
        generation_plan = classifier.classify(package)
        
        # Parse response
        if result.parsed:
            response: AnalysisResponse = result.parsed
            analysis = self._convert_response(response, package_id, result.extra)
            analysis.generation_plan = generation_plan
            return analysis
        
        # Fallback if parsing failed
        return PackageAnalysis(
            package_id=package_id,
            complexity="unknown",
            analysis_summary="Analysis failed to parse LLM response",
            generation_plan=generation_plan,
            analyzed_at=datetime.now(timezone.utc),
        )
    
    def _build_analysis_prompt(
        self,
        package: SSISPackage,
        profile: dict[str, Any],
        target_technology: str,
        project_context: dict[str, Any] | None,
    ) -> ChatPrompt[AnalysisResponse]:
        """Build the analysis prompt."""
        
        # Format package summary for LLM
        package_summary = self._format_package_summary(package)
        
        # Format profile patterns
        patterns_section = self._format_patterns(profile)
        
        # Format context
        context_section = ""
        if project_context:
            context_section = self._format_context(project_context)
        
        system_prompt = f"""You are an expert ETL migration analyst specializing in {profile.get('name', 'ETL')} migrations to {target_technology}.

Your task is to analyze an ETL package and identify:
1. Patterns from the technology profile (structural and execution patterns)
2. Potential blockers that could impede migration
3. Business rules embedded in the code
4. Migration complexity and effort estimation
5. Recommended target structure

{patterns_section}

{context_section}

Respond with a structured analysis. Be specific about pattern evidence and blocker details.
For blockers, include a decision_type if the blocker could be auto-resolved by looking up prior decisions."""
        
        user_message = f"""Analyze this ETL package:

{package_summary}

Provide a comprehensive migration analysis focusing on patterns, blockers, and recommendations."""
        
        return ChatPrompt(
            system=system_prompt,
            messages=[ChatMessage(role="user", content=user_message)],
            response_schema=AnalysisResponse,
            temperature=0.2,  # Low temperature for consistent analysis
        )
    
    def _format_package_summary(self, package: SSISPackage) -> str:
        """Format package details for LLM consumption."""
        lines = [
            f"# Package: {package.name}",
            "",
        ]
        
        if package.description:
            lines.append(f"Description: {package.description}")
            lines.append("")
        
        # Connection managers
        if package.connection_managers:
            lines.append("## Connection Managers")
            for cm in package.connection_managers:
                lines.append(f"- {cm.name} ({cm.connection_type})")
                if cm.database:
                    lines.append(f"  Database: {cm.database}")
            lines.append("")
        
        # Control flow
        if package.tasks:
            lines.append("## Control Flow Tasks")
            for task in package.tasks:
                status = " [DISABLED]" if task.disabled else ""
                lines.append(f"- {task.name} ({task.task_type.value}){status}")
                if task.sql_statement:
                    # Truncate long SQL
                    sql = task.sql_statement[:200]
                    if len(task.sql_statement) > 200:
                        sql += "..."
                    lines.append(f"  SQL: {sql}")
            lines.append("")
        
        # Precedence constraints
        if package.precedence_constraints:
            lines.append("## Task Dependencies")
            for pc in package.precedence_constraints:
                lines.append(f"- {pc.from_task} → {pc.to_task} ({pc.constraint_type})")
            lines.append("")
        
        # Data flows
        if package.data_flows:
            lines.append("## Data Flows")
            for df in package.data_flows:
                lines.append(f"### {df.name}")
                
                if df.sources:
                    lines.append("Sources:")
                    for src in df.sources:
                        table = src.table_name or src.sql_command or "dynamic"
                        lines.append(f"  - {src.name} ({src.component_type}): {table}")
                
                if df.transformations:
                    lines.append("Transformations:")
                    for t in df.transformations:
                        lines.append(f"  - {t.name} ({t.component_type})")
                
                if df.destinations:
                    lines.append("Destinations:")
                    for dest in df.destinations:
                        lines.append(f"  - {dest.name} ({dest.component_type}): {dest.table_name or 'dynamic'}")
                
                lines.append("")
        
        # Variables
        if package.variables:
            user_vars = [v for v in package.variables if v.namespace == "User"]
            if user_vars:
                lines.append("## User Variables")
                for var in user_vars[:20]:  # Limit to first 20
                    expr = " (expression)" if var.is_expression else ""
                    lines.append(f"- {var.name}{expr}")
                if len(user_vars) > 20:
                    lines.append(f"  ... and {len(user_vars) - 20} more")
                lines.append("")
        
        # Parameters
        if package.parameters:
            lines.append("## Parameters")
            for param in package.parameters:
                req = " (required)" if param.required else ""
                sens = " (sensitive)" if param.sensitive else ""
                lines.append(f"- {param.name}{req}{sens}")
            lines.append("")
        
        # Parse warnings
        if package.parse_warnings:
            lines.append("## Parse Warnings")
            for warn in package.parse_warnings[:10]:
                lines.append(f"- {warn}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_patterns(self, profile: dict[str, Any]) -> str:
        """Format profile patterns for system prompt."""
        lines = ["## Technology Profile Patterns to Detect"]
        
        # Structural patterns
        structural = profile.get("patterns", {}).get("structural", [])
        if structural:
            lines.append("\n### Structural Patterns")
            for p in structural:
                lines.append(f"- **{p['id']}**: {p['name']}")
                if p.get("description"):
                    lines.append(f"  {p['description']}")
        
        # Execution patterns
        execution = profile.get("patterns", {}).get("execution", [])
        if execution:
            lines.append("\n### Execution Patterns")
            for p in execution:
                lines.append(f"- **{p['id']}**: {p['name']}")
                if p.get("description"):
                    lines.append(f"  {p['description']}")
        
        return "\n".join(lines)
    
    def _format_context(self, context: dict[str, Any]) -> str:
        """Format project context for prompt."""
        lines = ["## Project Context"]
        
        # Resolved decisions
        decisions = context.get("resolved_decisions", [])
        if decisions:
            lines.append("\n### Previously Resolved Decisions")
            for d in decisions[:10]:
                lines.append(f"- {d['decision_type']}: {d['resolution']}")
        
        # Business rules
        rules = context.get("business_rules", [])
        if rules:
            lines.append("\n### Known Business Rules")
            for r in rules[:10]:
                lines.append(f"- {r['name']}: {r['description']}")
        
        return "\n".join(lines)
    
    def _convert_response(
        self,
        response: AnalysisResponse,
        package_id: uuid.UUID,
        extra: dict[str, Any] | None,
    ) -> PackageAnalysis:
        """Convert LLM response to PackageAnalysis."""
        
        # Convert patterns
        patterns = [
            DetectedPattern(
                pattern_id=p.pattern_id,
                pattern_name=p.pattern_id,  # Could look up from profile
                confidence=p.confidence,
                evidence=p.evidence,
                migration_implication=p.migration_implication,
            )
            for p in response.patterns
        ]
        
        # Convert blockers
        blockers = [
            BlockerItem(
                blocker_type=BlockerType(b.blocker_type) if b.blocker_type in BlockerType.__members__.values() else BlockerType.TECHNICAL,
                title=b.title,
                description=b.description,
                severity=BlockerSeverity(b.severity) if b.severity in BlockerSeverity.__members__.values() else BlockerSeverity.MEDIUM,
                affected_components=b.affected_components,
                suggested_action=b.suggested_action,
                decision_type=b.decision_type,
            )
            for b in response.blockers
        ]
        
        # Convert business rules
        business_rules = [
            BusinessRuleDiscovery(
                rule_id=f"rule_{i}",
                rule_name=r.rule_name,
                description=r.description,
                source_code=r.source_code,
                category=r.category,
                applies_to_tables=r.applies_to_tables,
            )
            for i, r in enumerate(response.business_rules)
        ]
        
        # Build decisions needed from unresolved blockers
        decisions_needed = [
            DecisionItem(
                decision_type=b.decision_type or "unknown",
                question=f"How to handle: {b.title}",
                context=b.description,
                suggested_action=b.suggested_action,
            )
            for b in response.blockers
            if b.decision_type and not b.suggested_action
        ]
        
        return PackageAnalysis(
            package_id=package_id,
            complexity=response.complexity,
            domain=response.domain,
            estimated_effort=response.estimated_effort,
            detected_patterns=patterns,
            business_rules=business_rules,
            blockers=blockers,
            decisions_needed=decisions_needed,
            analysis_summary=response.analysis_summary,
            target_notebook_structure=response.target_notebook_structure,
            migration_notes=response.migration_notes,
            analyzed_at=datetime.now(timezone.utc),
            llm_run_id=extra.get("run_id") if extra else None,
        )


def create_analyzer(llm_service: LLMService) -> PackageAnalyzer:
    """Create a package analyzer with the given LLM service.
    
    Args:
        llm_service: LLM service for running analysis
        
    Returns:
        Configured PackageAnalyzer
    """
    return PackageAnalyzer(llm_service)
