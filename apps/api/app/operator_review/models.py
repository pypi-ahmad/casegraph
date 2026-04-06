"""Persistence models for operator lifecycle, action items, and review notes."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class StageTransitionModel(SQLModel, table=True):
    __tablename__ = "case_stage_transitions"

    transition_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    from_stage: str = Field(index=True)
    to_stage: str = Field(index=True)
    transition_type: str = Field(default="manual")
    reason: str = ""
    note: str = ""
    created_at: datetime = Field(default_factory=utcnow, index=True)


class ActionItemModel(SQLModel, table=True):
    __tablename__ = "case_action_items"
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "fingerprint",
            name="uq_case_action_items_case_fingerprint",
        ),
    )

    action_item_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    fingerprint: str = Field(index=True)
    category: str = Field(index=True)
    source: str = Field(index=True)
    priority: str = Field(default="normal")
    status: str = Field(default="open", index=True)
    title: str
    description: str = ""
    source_reason: str = ""
    checklist_item_id: str | None = Field(default=None, index=True)
    document_id: str | None = Field(default=None, index=True)
    extraction_id: str | None = Field(default=None, index=True)
    run_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)
    resolved_at: datetime | None = None


class ReviewNoteModel(SQLModel, table=True):
    __tablename__ = "case_review_notes"

    note_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    body: str
    decision: str = Field(default="note_only", index=True)
    related_action_item_id: str | None = Field(default=None, index=True)
    stage_snapshot: str = Field(default="intake", index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)