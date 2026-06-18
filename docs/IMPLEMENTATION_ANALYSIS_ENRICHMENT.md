# Implementation Analysis: Artifact Enrichment & Human Feedback System

**Status**: Proposal  
**Date**: 2026-05-14  
**Scope**: Add enriched analysis generation and human feedback workflow to artifact processing

---

## 1. Overview

### What We're Building

An **enrichment layer** that sits between raw artifact extraction and card generation:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CURRENT FLOW                                                               │
│                                                                             │
│  Upload .dtsx → Extract XML → Store content_md → Cards reference raw content│
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  PROPOSED FLOW                                                              │
│                                                                             │
│  Upload .dtsx → Extract XML → Store content_md                              │
│                                    ↓                                        │
│                          AI Enrichment (async)                              │
│                                    ↓                                        │
│                          Generate analysis_md + feedback_items              │
│                                    ↓                                        │
│                          Human resolves feedback (if any)                   │
│                                    ↓                                        │
│                          Cards reference BOTH raw + enriched                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Deliverables

1. **Database schema** for `artifact_analyses` and `analysis_feedback_items`
2. **Dramatiq job** for async analysis generation
3. **LLM prompt** for generating enriched analysis
4. **API endpoints** for analysis CRUD and feedback resolution
5. **Web UI** for viewing analysis and resolving feedback
6. **Template integration** so cards can reference analyses

---

## 2. Database Schema Changes

### New Tables

```sql
-- Alembic migration: add_artifact_analysis_tables

CREATE TABLE artifact_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES project_artifacts(id) ON DELETE CASCADE,
    
    -- Analysis type (allows multiple analyses per artifact in future)
    analysis_type TEXT NOT NULL DEFAULT 'technical_assessment',
    
    -- Content (rendered from template)
    analysis_md TEXT NOT NULL,
    summary_md TEXT,  -- One-paragraph executive summary
    
    -- Structured data (JSON for querying)
    extracted_metadata JSONB,  -- Full ArtifactAnalysis schema as JSON
    
    -- Status workflow
    status TEXT NOT NULL DEFAULT 'draft' 
        CHECK (status IN ('draft', 'human_review', 'approved')),
    
    -- Human review tracking
    reviewed_by_user_id UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    
    -- Readiness
    readiness_score NUMERIC(2,1),  -- 1.0 - 5.0
    has_blocking_feedback BOOLEAN NOT NULL DEFAULT false,
    
    -- Audit
    llm_run_id UUID REFERENCES llm_runs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    UNIQUE (artifact_id, analysis_type)
);

CREATE TABLE analysis_feedback_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES artifact_analyses(id) ON DELETE CASCADE,
    
    -- Identity
    item_number INTEGER NOT NULL,  -- Sequential within analysis
    topic TEXT NOT NULL,
    category TEXT NOT NULL 
        CHECK (category IN ('business_rule', 'technical_decision', 'data_quality', 
                            'security', 'compliance', 'architecture', 'ownership')),
    priority TEXT NOT NULL 
        CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    
    -- Context
    context_md TEXT NOT NULL,
    why_it_matters_md TEXT NOT NULL,
    source_location TEXT,
    source_evidence TEXT,
    
    -- Options (JSONB array of FeedbackOption objects)
    options JSONB NOT NULL DEFAULT '[]',
    
    -- Resolution
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_review', 'resolved', 'wont_fix', 'deferred')),
    selected_option_id TEXT,
    custom_response TEXT,
    supporting_documentation TEXT,
    decided_by_user_id UUID REFERENCES users(id),
    decided_at TIMESTAMPTZ,
    
    -- Workflow
    suggested_owner TEXT,
    blocking_phase TEXT,
    deadline DATE,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    UNIQUE (analysis_id, item_number)
);

-- Indexes
CREATE INDEX ix_artifact_analyses_artifact ON artifact_analyses(artifact_id);
CREATE INDEX ix_artifact_analyses_status ON artifact_analyses(status);
CREATE INDEX ix_feedback_items_analysis ON analysis_feedback_items(analysis_id);
CREATE INDEX ix_feedback_items_status ON analysis_feedback_items(status);
CREATE INDEX ix_feedback_items_priority ON analysis_feedback_items(priority) 
    WHERE status = 'pending';
```

### Modifications to Existing Tables

```sql
-- Add analysis status to project_artifacts for quick filtering
ALTER TABLE project_artifacts ADD COLUMN analysis_status TEXT 
    DEFAULT 'pending'
    CHECK (analysis_status IN ('pending', 'analyzing', 'analyzed', 'needs_feedback', 'approved', 'skipped'));

-- Add index for filtering
CREATE INDEX ix_project_artifacts_analysis_status 
    ON project_artifacts(project_id, analysis_status);
```

---

## 3. Domain Models

### File: `app/domain/analysis.py`

```python
"""Analysis domain models for artifact enrichment."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, UuidPkMixin

if TYPE_CHECKING:
    from app.domain.identity import User
    from app.domain.llm import LlmRun
    from app.domain.projects import ProjectArtifact


class ArtifactAnalysis(UuidPkMixin, Base):
    __tablename__ = "artifact_analyses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'human_review', 'approved')",
            name="analysis_status_valid"
        ),
        UniqueConstraint("artifact_id", "analysis_type", name="unique_analysis_per_type"),
        Index("ix_artifact_analyses_artifact", "artifact_id"),
        Index("ix_artifact_analyses_status", "status"),
    )

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_artifacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_type: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="technical_assessment"
    )
    
    analysis_md: Mapped[str] = mapped_column(Text, nullable=False)
    summary_md: Mapped[str | None] = mapped_column(Text)
    extracted_metadata: Mapped[dict | None] = mapped_column(JSONB)
    
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="draft"
    )
    
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    
    readiness_score: Mapped[float | None] = mapped_column(Numeric(2, 1))
    has_blocking_feedback: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    
    llm_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("llm_runs.id")
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    artifact: Mapped[ProjectArtifact] = relationship(back_populates="analyses")
    feedback_items: Mapped[list[AnalysisFeedbackItem]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    llm_run: Mapped[LlmRun | None] = relationship()
    reviewed_by: Mapped[User | None] = relationship()


class AnalysisFeedbackItem(UuidPkMixin, Base):
    __tablename__ = "analysis_feedback_items"
    __table_args__ = (
        CheckConstraint(
            "category IN ('business_rule', 'technical_decision', 'data_quality', "
            "'security', 'compliance', 'architecture', 'ownership')",
            name="feedback_category_valid"
        ),
        CheckConstraint(
            "priority IN ('critical', 'high', 'medium', 'low')",
            name="feedback_priority_valid"
        ),
        CheckConstraint(
            "status IN ('pending', 'in_review', 'resolved', 'wont_fix', 'deferred')",
            name="feedback_status_valid"
        ),
        UniqueConstraint("analysis_id", "item_number", name="unique_item_number"),
        Index("ix_feedback_items_analysis", "analysis_id"),
        Index("ix_feedback_items_status", "status"),
    )

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifact_analyses.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    item_number: Mapped[int] = mapped_column(Integer, nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    
    context_md: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_matters_md: Mapped[str] = mapped_column(Text, nullable=False)
    source_location: Mapped[str | None] = mapped_column(Text)
    source_evidence: Mapped[str | None] = mapped_column(Text)
    
    options: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="pending"
    )
    selected_option_id: Mapped[str | None] = mapped_column(String(64))
    custom_response: Mapped[str | None] = mapped_column(Text)
    supporting_documentation: Mapped[str | None] = mapped_column(Text)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    suggested_owner: Mapped[str | None] = mapped_column(Text)
    blocking_phase: Mapped[str | None] = mapped_column(String(64))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    analysis: Mapped[ArtifactAnalysis] = relationship(back_populates="feedback_items")
    decided_by: Mapped[User | None] = relationship()
```

---

## 4. Async Job: Analysis Generation

### File: `app/jobs/analyze_artifact.py`

```python
"""Dramatiq actor for generating enriched artifact analyses."""

import dramatiq
from uuid import UUID

from app.db import get_sync_session
from app.domain.projects import ProjectArtifact
from app.domain.analysis import ArtifactAnalysis, AnalysisFeedbackItem
from app.llm.service import LLMService
from app.prompts.analyze_artifact import AnalyzeArtifactPrompt
from app.services.analysis import AnalysisRenderer


@dramatiq.actor(max_retries=2, time_limit=300_000)  # 5 min timeout
def analyze_artifact(artifact_id: str, analysis_type: str = "technical_assessment"):
    """Generate enriched analysis for an artifact.
    
    This job:
    1. Loads the artifact and its extracted content
    2. Calls LLM to generate structured analysis
    3. Renders analysis to markdown using templates
    4. Creates feedback items for anything needing human input
    5. Stores analysis and feedback items in database
    """
    artifact_uuid = UUID(artifact_id)
    
    with get_sync_session() as session:
        # Load artifact
        artifact = session.get(ProjectArtifact, artifact_uuid)
        if not artifact:
            raise ValueError(f"Artifact {artifact_id} not found")
        
        if artifact.extraction_status != "extracted":
            raise ValueError(f"Artifact {artifact_id} not yet extracted")
        
        # Update status
        artifact.analysis_status = "analyzing"
        session.commit()
        
        try:
            # Get project context
            project = artifact.project
            
            # Build prompt
            prompt = AnalyzeArtifactPrompt.build(
                artifact=artifact,
                project=project,
                analysis_type=analysis_type,
            )
            
            # Call LLM
            llm_service = LLMService(
                provider=project.llm_provider,
                model=project.llm_model,
                temperature=project.llm_temperature,
            )
            
            result = llm_service.run(
                prompt=prompt,
                project_id=project.id,
                kind="analyze_artifact",
            )
            
            # Parse structured response
            analysis_data = result.parsed  # ArtifactAnalysis schema
            
            # Render to markdown
            renderer = AnalysisRenderer()
            analysis_md = renderer.render_analysis(analysis_data)
            feedback_md = renderer.render_feedback_request(analysis_data) if analysis_data.feedback_items else None
            
            # Create database records
            analysis = ArtifactAnalysis(
                artifact_id=artifact_uuid,
                analysis_type=analysis_type,
                analysis_md=analysis_md,
                summary_md=analysis_data.executive_summary.what_it_does,
                extracted_metadata=analysis_data.model_dump(),
                status="draft" if not analysis_data.feedback_items else "human_review",
                readiness_score=analysis_data.readiness.score,
                has_blocking_feedback=bool(analysis_data.get_blocking_feedback()),
                llm_run_id=result.llm_run_id,
            )
            session.add(analysis)
            session.flush()  # Get analysis.id
            
            # Create feedback items
            for i, item in enumerate(analysis_data.feedback_items, start=1):
                feedback = AnalysisFeedbackItem(
                    analysis_id=analysis.id,
                    item_number=i,
                    topic=item.topic,
                    category=item.category.value,
                    priority=item.priority.value,
                    context_md=item.context,
                    why_it_matters_md=item.why_it_matters,
                    source_location=item.source_location,
                    source_evidence=item.source_evidence,
                    options=[opt.model_dump() for opt in item.options],
                    suggested_owner=item.suggested_owner,
                    blocking_phase=item.blocking_phase,
                )
                session.add(feedback)
            
            # Update artifact status
            artifact.analysis_status = "needs_feedback" if analysis_data.feedback_items else "analyzed"
            
            session.commit()
            
        except Exception as e:
            artifact.analysis_status = "pending"  # Allow retry
            session.commit()
            raise
```

---

## 5. LLM Prompt for Analysis

### File: `app/prompts/analyze_artifact.py`

```python
"""LLM prompt for generating enriched artifact analysis."""

from app.llm.base import ChatMessage, ChatPrompt
from app.schemas.analysis import ArtifactAnalysis
from app.domain.projects import Project, ProjectArtifact


class AnalyzeArtifactPrompt:
    """Builds prompts for artifact analysis generation."""
    
    SYSTEM_PROMPT = """You are an expert data engineer and migration specialist. Your task is to analyze legacy ETL artifacts (SSIS packages, Airflow DAGs, Talend jobs, etc.) and produce a comprehensive enrichment document.

**Your Goals:**
1. Understand the BUSINESS PURPOSE, not just the technical implementation
2. Document the USER JOURNEY of data through the system
3. Extract BUSINESS RULES encoded in the code
4. Map the SYSTEM LANDSCAPE and connections
5. Identify what NEEDS HUMAN INPUT and provide OPTIONS

**Output Structure:**
You must return a structured JSON matching the ArtifactAnalysis schema with ALL sections populated.

**Critical Guidelines:**
- Write for three audiences: Business stakeholders, Architects, Engineers
- Distinguish FACTS (found in source) from INFERENCES (your interpretation)
- When uncertain, create a feedback_item with options instead of guessing
- Include source line references for all claims
- Rate confidence honestly in completeness tracking

**Feedback Items:**
When you encounter something that needs human decision, create a feedback_item with:
- Clear context explaining what you found
- Why it matters for migration
- 2-4 concrete options with pros/cons
- Suggested owner (role, not person name)

**Example Feedback Item:**
```json
{
  "id": "FB-001",
  "topic": "7-Hour Deduplication Tie-Breaker Rule",
  "category": "business_rule",
  "priority": "high",
  "context": "Found ROW_NUMBER with 7-hour partition, but tie-breaker logic prioritizes Company A without documented justification.",
  "why_it_matters": "Incorrect tie-breaker could cause duplicate billing or missed records.",
  "source_location": "Execute SQL Task 'ESQL_Dedup', lines 45-67",
  "source_evidence": "ORDER BY CASE WHEN company = 'MRS' THEN 0 ELSE 1 END",
  "options": [
    {
      "id": "OPT-1",
      "title": "Keep MRS Priority (Document as Business Rule)",
      "description": "Maintain current behavior, document as intentional business decision.",
      "pros": ["No code change", "Preserves current behavior"],
      "cons": ["May perpetuate undocumented assumption"],
      "effort": "Low",
      "recommended": false
    },
    {
      "id": "OPT-2", 
      "title": "Use Timestamp as Tie-Breaker",
      "description": "Change to pure timestamp-based ordering, most recent wins.",
      "pros": ["More transparent logic", "No company bias"],
      "cons": ["Changes behavior", "Needs parallel testing"],
      "effort": "Medium",
      "recommended": false
    },
    {
      "id": "OPT-3",
      "title": "Escalate to Business SME",
      "description": "Pause migration of this logic until business confirms intent.",
      "pros": ["Correct decision", "Documented approval"],
      "cons": ["Delays timeline", "Requires SME availability"],
      "effort": "Low",
      "recommended": true
    }
  ],
  "suggested_owner": "Business Analyst / Data Steward",
  "blocking_phase": "phase-3-refactoring"
}
```
"""

    @classmethod
    def build(
        cls,
        artifact: ProjectArtifact,
        project: Project,
        analysis_type: str,
    ) -> ChatPrompt[ArtifactAnalysis]:
        """Build the analysis prompt."""
        
        # Determine artifact type label
        type_labels = {
            ".dtsx": "SSIS Package",
            ".py": "Python Script (likely Airflow DAG)",
            ".sql": "SQL Script",
            ".xml": "XML Configuration",
        }
        ext = "." + artifact.filename.rsplit(".", 1)[-1].lower() if "." in artifact.filename else ""
        artifact_type_label = type_labels.get(ext, "Data Artifact")
        
        user_message = f"""Analyze the following artifact and generate a comprehensive enrichment document.

**Project Context:**
- Project: {project.name}
- Objective: {project.objective}
- Target Platform: Databricks (assume unless stated otherwise)

**Artifact Details:**
- Filename: {artifact.filename}
- Type: {artifact_type_label}
- Kind: {artifact.kind}

**Raw Content:**
```
{artifact.content_md}
```

Generate the ArtifactAnalysis JSON with all sections populated. For any uncertainty, create feedback_items."""

        return ChatPrompt(
            system=cls.SYSTEM_PROMPT,
            messages=[ChatMessage(role="user", content=user_message)],
            response_schema=ArtifactAnalysis,
        )
```

---

## 6. API Endpoints

### File: `app/api/analyses.py`

```python
"""API endpoints for artifact analyses and feedback."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.domain.analysis import ArtifactAnalysis, AnalysisFeedbackItem
from app.domain.projects import ProjectArtifact
from app.jobs.analyze_artifact import analyze_artifact
from app.schemas.analysis import (
    ArtifactAnalysisCreate, ArtifactAnalysisUpdate,
    FeedbackItemResolve,
)

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("/artifacts/{artifact_id}/analyze")
async def trigger_analysis(
    artifact_id: UUID,
    analysis_type: str = "technical_assessment",
    session: AsyncSession = Depends(get_session),
):
    """Trigger async analysis generation for an artifact."""
    artifact = await session.get(ProjectArtifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    if artifact.extraction_status != "extracted":
        raise HTTPException(
            status_code=400, 
            detail=f"Artifact must be extracted first. Current status: {artifact.extraction_status}"
        )
    
    # Enqueue async job
    analyze_artifact.send(str(artifact_id), analysis_type)
    
    artifact.analysis_status = "analyzing"
    await session.commit()
    
    return {"status": "analyzing", "message": "Analysis job enqueued"}


@router.get("/artifacts/{artifact_id}")
async def get_analysis(
    artifact_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get the analysis for an artifact."""
    result = await session.execute(
        select(ArtifactAnalysis)
        .where(ArtifactAnalysis.artifact_id == artifact_id)
        .options(selectinload(ArtifactAnalysis.feedback_items))
    )
    analysis = result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return {
        "id": analysis.id,
        "artifact_id": analysis.artifact_id,
        "status": analysis.status,
        "readiness_score": float(analysis.readiness_score) if analysis.readiness_score else None,
        "has_blocking_feedback": analysis.has_blocking_feedback,
        "analysis_md": analysis.analysis_md,
        "summary_md": analysis.summary_md,
        "feedback_items": [
            {
                "id": item.id,
                "item_number": item.item_number,
                "topic": item.topic,
                "category": item.category,
                "priority": item.priority,
                "status": item.status,
                "context_md": item.context_md,
                "options": item.options,
            }
            for item in analysis.feedback_items
        ],
        "created_at": analysis.created_at,
        "updated_at": analysis.updated_at,
    }


@router.patch("/artifacts/{artifact_id}/approve")
async def approve_analysis(
    artifact_id: UUID,
    user_id: UUID,  # In real app, get from auth
    review_notes: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Approve an analysis after human review."""
    result = await session.execute(
        select(ArtifactAnalysis)
        .where(ArtifactAnalysis.artifact_id == artifact_id)
        .options(selectinload(ArtifactAnalysis.feedback_items))
    )
    analysis = result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Check for unresolved blocking feedback
    blocking = [
        item for item in analysis.feedback_items
        if item.status == "pending" and item.priority in ("critical", "high")
    ]
    if blocking:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve: {len(blocking)} blocking feedback items unresolved"
        )
    
    analysis.status = "approved"
    analysis.reviewed_by_user_id = user_id
    analysis.reviewed_at = func.now()
    analysis.review_notes = review_notes
    analysis.has_blocking_feedback = False
    
    # Update artifact status
    artifact = await session.get(ProjectArtifact, artifact_id)
    artifact.analysis_status = "approved"
    
    await session.commit()
    
    return {"status": "approved"}


@router.patch("/feedback/{feedback_id}/resolve")
async def resolve_feedback(
    feedback_id: UUID,
    resolution: FeedbackItemResolve,
    session: AsyncSession = Depends(get_session),
):
    """Resolve a feedback item."""
    item = await session.get(AnalysisFeedbackItem, feedback_id)
    if not item:
        raise HTTPException(status_code=404, detail="Feedback item not found")
    
    item.status = "resolved"
    item.selected_option_id = resolution.selected_option_id
    item.custom_response = resolution.custom_response
    item.supporting_documentation = resolution.supporting_documentation
    item.decided_by_user_id = resolution.decided_by  # In real app, get from auth
    item.decided_at = func.now()
    
    # Check if all blocking items are resolved
    analysis = await session.get(
        ArtifactAnalysis, item.analysis_id,
        options=[selectinload(ArtifactAnalysis.feedback_items)]
    )
    blocking = [
        i for i in analysis.feedback_items
        if i.status == "pending" and i.priority in ("critical", "high")
    ]
    analysis.has_blocking_feedback = bool(blocking)
    
    await session.commit()
    
    return {"status": "resolved", "remaining_blocking": len(blocking)}
```

---

## 7. Web UI Components

### Required UI Elements

1. **Analysis Panel** (in artifact detail view)
   - Shows analysis status (pending/analyzing/needs_feedback/approved)
   - Renders analysis_md with sections collapsible
   - Shows readiness score as badge

2. **Feedback Resolution Modal**
   - Lists pending feedback items by priority
   - For each item: context, options as radio buttons, custom response textarea
   - Submit resolves and updates analysis

3. **Analysis Dashboard** (project-level)
   - Table of all artifacts with analysis status
   - Filter by status: needs_feedback, approved
   - Bulk approve action

### File: `packages/web/src/components/analysis/AnalysisPanel.tsx`

```tsx
// Key component structure (simplified)

interface AnalysisPanelProps {
  artifactId: string;
}

export function AnalysisPanel({ artifactId }: AnalysisPanelProps) {
  const { data: analysis, isLoading } = useQuery({
    queryKey: ['analysis', artifactId],
    queryFn: () => api.get(`/analyses/artifacts/${artifactId}`),
  });

  if (!analysis) {
    return <TriggerAnalysisButton artifactId={artifactId} />;
  }

  return (
    <div className="space-y-4">
      {/* Status Badge */}
      <div className="flex items-center gap-2">
        <StatusBadge status={analysis.status} />
        <ReadinessScore score={analysis.readiness_score} />
        {analysis.has_blocking_feedback && (
          <Badge variant="destructive">Feedback Required</Badge>
        )}
      </div>

      {/* Feedback Items (if any) */}
      {analysis.feedback_items.length > 0 && (
        <FeedbackItemsList 
          items={analysis.feedback_items}
          onResolve={handleResolve}
        />
      )}

      {/* Analysis Content */}
      <Tabs defaultValue="summary">
        <TabsList>
          <TabsTrigger value="summary">Summary</TabsTrigger>
          <TabsTrigger value="full">Full Analysis</TabsTrigger>
          <TabsTrigger value="raw">Raw Source</TabsTrigger>
        </TabsList>
        <TabsContent value="summary">
          <Markdown>{analysis.summary_md}</Markdown>
        </TabsContent>
        <TabsContent value="full">
          <Markdown>{analysis.analysis_md}</Markdown>
        </TabsContent>
        <TabsContent value="raw">
          <CodeBlock>{artifact.content_md}</CodeBlock>
        </TabsContent>
      </Tabs>

      {/* Approval Action */}
      {analysis.status === 'human_review' && !analysis.has_blocking_feedback && (
        <ApproveButton analysisId={analysis.id} />
      )}
    </div>
  );
}
```

---

## 8. Integration with Card Generation

### Cards Reference Both Raw and Enriched

When generating cards, the `DraftCardPrompt` should include:

```python
# In app/prompts/draft_card.py

def build_artifact_context(card: CardView, artifacts: list[ProjectArtifact]) -> str:
    """Build context from artifacts for card drafting."""
    parts = []
    
    for artifact in artifacts:
        # Include summary from analysis (if approved)
        if artifact.analysis_status == "approved":
            analysis = artifact.analyses[0]  # Get latest
            parts.append(f"""
**Artifact: {artifact.filename}**
Analysis Summary: {analysis.summary_md}
Readiness: {analysis.readiness_score}/5

Key Business Rules:
{extract_business_rules_summary(analysis.extracted_metadata)}

Resolved Decisions:
{extract_resolved_feedback(analysis.feedback_items)}
""")
        else:
            # Fallback to raw content if no approved analysis
            parts.append(f"""
**Artifact: {artifact.filename}** (raw, not analyzed)
Content preview: {artifact.content_md[:1000]}...
""")
    
    return "\n---\n".join(parts)
```

---

## 9. Migration & Rollout Plan

### Phase 1: Schema & Backend (Week 1)
1. Create Alembic migration for new tables
2. Add domain models
3. Create Dramatiq job skeleton
4. Add basic API endpoints

### Phase 2: LLM Integration (Week 2)
1. Build analysis prompt with few-shot examples
2. Create Jinja templates for rendering
3. Test with sample SSIS packages
4. Tune prompt based on output quality

### Phase 3: Web UI (Week 3)
1. Analysis panel component
2. Feedback resolution modal
3. Analysis dashboard
4. Status indicators throughout UI

### Phase 4: Integration & Testing (Week 4)
1. Integration tests for full workflow
2. E2E tests with Playwright
3. Performance testing with large artifacts
4. Documentation and user guide

---

## 10. Summary: Implementation Checklist

```markdown
### Schema & Database
- [ ] Alembic migration: artifact_analyses table
- [ ] Alembic migration: analysis_feedback_items table
- [ ] Add analysis_status to project_artifacts
- [ ] Domain models in app/domain/analysis.py

### Backend Services
- [ ] Pydantic schemas in app/schemas/analysis.py
- [ ] Dramatiq job: analyze_artifact
- [ ] Analysis renderer service
- [ ] LLM prompt: AnalyzeArtifactPrompt

### API Endpoints
- [ ] POST /analyses/artifacts/{id}/analyze
- [ ] GET /analyses/artifacts/{id}
- [ ] PATCH /analyses/artifacts/{id}/approve
- [ ] PATCH /analyses/feedback/{id}/resolve
- [ ] GET /projects/{id}/analyses (dashboard)

### Templates
- [ ] artifact_analysis.md.j2
- [ ] human_feedback_request.md.j2

### Web UI
- [ ] AnalysisPanel component
- [ ] FeedbackItemsList component
- [ ] FeedbackResolutionModal component
- [ ] AnalysisDashboard page
- [ ] Status badges and indicators

### Testing
- [ ] Unit tests for analysis service
- [ ] Integration tests for job
- [ ] E2E tests for UI workflow
- [ ] Load test with large artifacts
```

---

This implementation analysis provides a complete blueprint for adding artifact enrichment and human feedback to Agents Workshop. The key insight is that **analysis enriches but never replaces** the source, and **human feedback is structured with options** to guide decisions.
