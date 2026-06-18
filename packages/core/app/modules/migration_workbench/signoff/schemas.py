"""Schemas for sign-off workflow module.

Sign-off manages approval checklists and formal sign-off requests
for migration milestones (parallel run approval, static analysis, cutover).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SignoffType(str, Enum):
    """Type of sign-off request."""
    
    STATIC_ANALYSIS = "static_analysis"      # Code review, security checks
    PARALLEL_RUN = "parallel_run"            # Source and target running in parallel
    CUTOVER = "cutover"                      # Production cutover approval
    POST_MIGRATION = "post_migration"        # Post-migration validation


class SignoffStatus(str, Enum):
    """Status of a sign-off request."""
    
    DRAFT = "draft"                # Not yet submitted
    PENDING = "pending"            # Awaiting approval
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ChecklistItemStatus(str, Enum):
    """Status of a checklist item."""
    
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "n/a"


class ChecklistItem(BaseModel):
    """A single checklist item in a sign-off."""
    
    id: str = Field(..., description="Unique ID within the checklist")
    title: str
    description: str | None = None
    category: str = Field("general", description="Category grouping")
    
    # Status
    status: ChecklistItemStatus = ChecklistItemStatus.NOT_STARTED
    required: bool = True
    
    # Evidence/notes
    evidence: str | None = Field(None, description="Link or description of evidence")
    notes: str | None = None
    
    # Completion info
    completed_by: str | None = None
    completed_at: datetime | None = None


class SignoffChecklist(BaseModel):
    """Complete checklist for a sign-off type."""
    
    signoff_type: SignoffType
    items: list[ChecklistItem] = Field(default_factory=list)
    
    @property
    def total_items(self) -> int:
        return len(self.items)
    
    @property
    def completed_items(self) -> int:
        return sum(
            1 for i in self.items
            if i.status in (ChecklistItemStatus.PASSED, ChecklistItemStatus.SKIPPED, ChecklistItemStatus.NOT_APPLICABLE)
        )
    
    @property
    def failed_items(self) -> int:
        return sum(1 for i in self.items if i.status == ChecklistItemStatus.FAILED)
    
    @property
    def required_incomplete(self) -> int:
        return sum(
            1 for i in self.items
            if i.required and i.status not in (
                ChecklistItemStatus.PASSED,
                ChecklistItemStatus.SKIPPED,
                ChecklistItemStatus.NOT_APPLICABLE,
            )
        )


class SignoffRequest(BaseModel):
    """A sign-off request for a package or set of packages."""
    
    id: uuid.UUID
    project_id: uuid.UUID
    signoff_type: SignoffType
    status: SignoffStatus = SignoffStatus.DRAFT
    
    # What's being signed off
    package_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="Packages included in this sign-off",
    )
    wave_number: int | None = Field(
        None, description="If signing off an entire wave"
    )
    
    # Title and description
    title: str
    description: str | None = None
    
    # Checklist
    checklist: SignoffChecklist
    
    # Requestor
    requested_by: str
    requested_at: datetime
    
    # Approver info
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    
    # Comments
    comments: list[str] = Field(default_factory=list)


class SignoffRequestView(BaseModel):
    """Summary view of a sign-off request for listings."""
    
    id: uuid.UUID
    project_id: uuid.UUID
    signoff_type: SignoffType
    status: SignoffStatus
    title: str
    
    package_count: int = 0
    wave_number: int | None = None
    
    checklist_total: int = 0
    checklist_completed: int = 0
    checklist_failed: int = 0
    
    requested_by: str
    requested_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None
    
    model_config = {"from_attributes": True}


class CreateSignoffRequest(BaseModel):
    """Request to create a new sign-off."""
    
    signoff_type: SignoffType
    title: str
    description: str | None = None
    
    package_ids: list[uuid.UUID] = Field(default_factory=list)
    wave_number: int | None = None
    
    requested_by: str = Field(..., description="User requesting the sign-off")


class UpdateChecklistItem(BaseModel):
    """Update a checklist item."""
    
    item_id: str
    status: ChecklistItemStatus | None = None
    evidence: str | None = None
    notes: str | None = None
    completed_by: str | None = None


class ApproveSignoffRequest(BaseModel):
    """Request to approve a sign-off."""
    
    approved_by: str
    comments: str | None = None


class RejectSignoffRequest(BaseModel):
    """Request to reject a sign-off."""
    
    rejected_by: str
    reason: str
