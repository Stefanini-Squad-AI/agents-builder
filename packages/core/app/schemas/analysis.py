"""Pydantic schemas for artifact analysis and human feedback.

These schemas define the data structures used to:
1. Generate enriched analysis documents from artifacts
2. Track human feedback items that require resolution
3. Validate analysis completeness and readiness
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------

class FeedbackPriority(str, Enum):
    CRITICAL = "critical"  # Blocks migration, must resolve before any work
    HIGH = "high"          # Blocks specific phase, must resolve before that phase
    MEDIUM = "medium"      # Should resolve, but can proceed with assumptions
    LOW = "low"            # Nice to have, document assumption if not resolved


class FeedbackCategory(str, Enum):
    BUSINESS_RULE = "business_rule"
    TECHNICAL_DECISION = "technical_decision"
    DATA_QUALITY = "data_quality"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    ARCHITECTURE = "architecture"
    OWNERSHIP = "ownership"


class FeedbackStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"
    DEFERRED = "deferred"


class ConnectionDirection(str, Enum):
    SOURCE = "source"
    TARGET = "target"
    BOTH = "both"
    CONTROL = "control"


class ReadinessLevel(str, Enum):
    READY = "ready"                    # 5/5 - No blockers
    READY_WITH_CAVEATS = "ready_caveats"  # 4/5 - Minor items
    NEEDS_WORK = "needs_work"          # 3/5 - Some blockers
    SIGNIFICANT_GAPS = "significant"   # 2/5 - Major blockers
    NOT_READY = "not_ready"            # 1/5 - Critical blockers


# -----------------------------------------------------------------------------
# Sub-models for Analysis Sections
# -----------------------------------------------------------------------------

class Consumer(BaseModel):
    """A downstream consumer of the artifact's output."""
    name: str
    usage: str


class ExecutiveSummary(BaseModel):
    """High-level business context for non-technical stakeholders."""
    what_it_does: str
    business_process: str
    consumers: list[Consumer]
    failure_impact: str


class UserJourney(BaseModel):
    """The story of how data flows through the business process."""
    narrative: str
    diagram: str  # ASCII diagram


class BusinessRule(BaseModel):
    """A business rule identified in the artifact."""
    id: str
    name: str
    description: str
    implementation: str
    source: str | None = None  # Where the rule was documented
    risk: str | None = None
    migration_note: str | None = None
    needs_confirmation: bool = False
    feedback_id: str | None = None  # Links to feedback item if needs_confirmation


class Connection(BaseModel):
    """A connection manager / data source or target."""
    name: str
    connection_type: str  # OLEDB, FlatFile, FTP, etc.
    system: str
    server: str | None = None
    database: str | None = None
    direction: ConnectionDirection
    business_role: str
    data_owned: str | None = None  # For sources
    consumers: str | None = None   # For targets
    purpose: str | None = None     # For control connections
    auth_method: str | None = None
    is_blocker: bool = False
    blocker_reason: str | None = None


class ConnectionLandscape(BaseModel):
    """Complete connection landscape for the artifact."""
    sources: list[Connection]
    targets: list[Connection]
    control: list[Connection] = []
    landscape_diagram: str  # ASCII diagram


class Metric(BaseModel):
    """A success metric."""
    name: str
    sla: str | None = None
    actual: str | None = None
    target: str | None = None


class Objective(BaseModel):
    """Package/artifact objective and success criteria."""
    primary: str
    current_metrics: list[Metric] = []
    migration_targets: list[Metric] = []


class ExecutionMode(BaseModel):
    """An execution mode (e.g., Full vs Incremental)."""
    name: str
    when_used: str
    behavior: str
    duration: str | None = None
    business_trigger: str


class TaskCensus(BaseModel):
    """Count of task types in the artifact."""
    type: str
    count: int
    enabled: int
    notes: str | None = None


class Variable(BaseModel):
    """A variable/parameter in the artifact."""
    name: str
    type: str
    is_expression: bool = False
    expression: str | None = None
    business_meaning: str


class DisabledTask(BaseModel):
    """A disabled task requiring decision."""
    name: str
    task_type: str
    disabled_since: str | None = None
    likely_reason: str
    recommendation: str
    feedback_id: str | None = None


class Assumption(BaseModel):
    """An assumption made during analysis."""
    id: str
    statement: str
    risk: str
    verification: str


class InformationGap(BaseModel):
    """Information not found in the source."""
    id: str
    what: str
    why_needed: str
    suggested_source: str


class ReadinessCategory(BaseModel):
    """A category in the readiness assessment."""
    name: str
    score: int  # 1-5
    notes: str


class Blocker(BaseModel):
    """A migration blocker."""
    id: str
    title: str
    description: str
    severity: Literal["critical", "high", "medium", "low"]
    severity_emoji: str = "⚠️"
    feedback_id: str | None = None


class ReadinessAssessment(BaseModel):
    """Overall migration readiness assessment."""
    score: float  # 1.0 - 5.0
    label: str
    emoji: str
    categories: list[ReadinessCategory]


class SourceReference(BaseModel):
    """Reference to source location."""
    section: str
    location: str
    lines: str


class CompletenessAspect(BaseModel):
    """Completeness tracking for an aspect of extraction."""
    name: str
    extracted: str  # e.g., "12/12" or "8/10"
    confidence: Literal["High", "Medium", "Low"]
    needs_verification: str | None = None


class KnownOmission(BaseModel):
    """Something the AI explicitly didn't extract fully."""
    description: str
    location: str
    reason: str | None = None


# -----------------------------------------------------------------------------
# Feedback Item Model
# -----------------------------------------------------------------------------

class FeedbackOption(BaseModel):
    """An option for resolving a feedback item."""
    id: str
    title: str
    description: str
    pros: list[str] = []
    cons: list[str] = []
    effort: str | None = None
    risk: str | None = None
    recommended: bool = False


class FeedbackItem(BaseModel):
    """A single item requiring human feedback."""
    id: str
    topic: str
    category: FeedbackCategory
    priority: FeedbackPriority
    priority_emoji: str = "⚠️"
    status: FeedbackStatus = FeedbackStatus.PENDING
    
    # Context
    context: str
    why_it_matters: str
    source_location: str | None = None
    source_language: str | None = None
    source_evidence: str | None = None
    
    # Options
    options: list[FeedbackOption]
    
    # Resolution
    selected_option_id: str | None = None
    custom_response: str | None = None
    supporting_documentation: str | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    
    # Workflow
    suggested_owner: str | None = None
    blocking_phase: str | None = None
    deadline: str | None = None

    def get_priority_emoji(self) -> str:
        return {
            FeedbackPriority.CRITICAL: "🔴",
            FeedbackPriority.HIGH: "🟠",
            FeedbackPriority.MEDIUM: "🟡",
            FeedbackPriority.LOW: "🟢",
        }.get(self.priority, "⚠️")


# -----------------------------------------------------------------------------
# Main Analysis Model
# -----------------------------------------------------------------------------

class ArtifactAnalysis(BaseModel):
    """Complete enriched analysis of an artifact."""
    
    # Metadata
    artifact_id: UUID
    artifact_filename: str
    artifact_kind: str
    artifact_type_label: str  # "SSIS Package", "Airflow DAG", etc.
    target_platform: str  # "Databricks", "Glue", etc.
    
    generated_at: datetime = Field(default_factory=datetime.now)
    status: Literal["draft", "human_review", "approved"] = "draft"
    
    # Sections
    executive_summary: ExecutiveSummary
    user_journey: UserJourney
    business_rules: list[BusinessRule]
    connections: ConnectionLandscape
    objective: Objective
    execution_modes: list[ExecutionMode]
    mode_selection_logic: str | None = None
    mode_migration_note: str | None = None
    
    # Technical inventory
    task_census: list[TaskCensus]
    variables: list[Variable]
    disabled_tasks: list[DisabledTask] = []
    
    # Gaps and assumptions
    assumptions: list[Assumption]
    information_gaps: list[InformationGap]
    
    # Readiness
    readiness: ReadinessAssessment
    blockers: list[Blocker]
    
    # Completeness
    source_references: list[SourceReference]
    completeness: list[CompletenessAspect]
    known_omissions: list[KnownOmission] = []
    
    # Feedback
    feedback_items: list[FeedbackItem] = []
    feedback_document_path: str | None = None
    
    def has_pending_feedback(self) -> bool:
        """Check if there are unresolved feedback items."""
        return any(
            item.status == FeedbackStatus.PENDING 
            for item in self.feedback_items
        )
    
    def get_blocking_feedback(self) -> list[FeedbackItem]:
        """Get feedback items that block migration."""
        return [
            item for item in self.feedback_items
            if item.status == FeedbackStatus.PENDING
            and item.priority in (FeedbackPriority.CRITICAL, FeedbackPriority.HIGH)
        ]
    
    def calculate_readiness_score(self) -> float:
        """Calculate overall readiness score based on categories and blockers."""
        if not self.readiness.categories:
            return 0.0
        
        base_score = sum(c.score for c in self.readiness.categories) / len(self.readiness.categories)
        
        # Penalty for blockers
        critical_blockers = len([b for b in self.blockers if b.severity == "critical"])
        high_blockers = len([b for b in self.blockers if b.severity == "high"])
        
        penalty = (critical_blockers * 1.0) + (high_blockers * 0.5)
        
        return max(1.0, min(5.0, base_score - penalty))


# -----------------------------------------------------------------------------
# Database Model (for ORM mapping)
# -----------------------------------------------------------------------------

class ArtifactAnalysisCreate(BaseModel):
    """Schema for creating an analysis record."""
    artifact_id: UUID
    analysis_type: str = "technical_assessment"
    analysis_md: str
    summary_md: str | None = None
    extracted_metadata: dict | None = None  # JSON blob of ArtifactAnalysis
    llm_run_id: UUID | None = None


class ArtifactAnalysisUpdate(BaseModel):
    """Schema for updating an analysis record."""
    analysis_md: str | None = None
    summary_md: str | None = None
    extracted_metadata: dict | None = None
    status: Literal["draft", "human_reviewed", "approved"] | None = None
    reviewed_by_user_id: UUID | None = None


class FeedbackItemCreate(BaseModel):
    """Schema for creating a feedback item."""
    analysis_id: UUID
    topic: str
    category: FeedbackCategory
    priority: FeedbackPriority
    context: str
    why_it_matters: str
    options: list[FeedbackOption]
    source_location: str | None = None
    source_evidence: str | None = None
    suggested_owner: str | None = None
    blocking_phase: str | None = None


class FeedbackItemResolve(BaseModel):
    """Schema for resolving a feedback item."""
    selected_option_id: str | None = None
    custom_response: str | None = None
    supporting_documentation: str | None = None
    decided_by: str
