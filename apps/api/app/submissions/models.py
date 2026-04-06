"""Persistence models for submission drafts, mappings, and automation plans."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class SubmissionDraftModel(SQLModel, table=True):
    __tablename__ = "submission_drafts"

    draft_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    packet_id: str = Field(foreign_key="case_packets.packet_id", index=True)
    source_mode: str = Field(default="live_case_state", index=True)
    source_reviewed_snapshot_id: str = Field(default="", index=True)
    case_title: str = ""
    submission_target_id: str = Field(index=True)
    submission_target_category: str = Field(index=True)
    status: str = Field(default="draft_created", index=True)
    domain_pack_id: str | None = Field(default=None, index=True)
    case_type_id: str | None = Field(default=None, index=True)
    mapping_count: int = 0
    unresolved_mapping_count: int = 0
    source_metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    note: str = ""
    requires_operator_approval: bool = True
    approval_status: str = Field(default="not_requested", index=True)
    approved_by: str = ""
    approved_at: datetime | None = None
    approval_note: str = ""
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)


class SubmissionMappingModel(SQLModel, table=True):
    __tablename__ = "submission_mappings"

    mapping_id: str = Field(primary_key=True, index=True)
    draft_id: str = Field(foreign_key="submission_drafts.draft_id", index=True)
    target_field_name: str = Field(index=True)
    target_section: str = Field(index=True)
    target_label: str = ""
    target_field_type: str = "text"
    target_required: bool = False
    status: str = Field(default="unresolved", index=True)
    source_entity_type: str | None = Field(default=None, index=True)
    source_entity_id: str | None = Field(default=None, index=True)
    source_path: str | None = None
    source_label: str | None = None
    preview_text: str | None = None
    preview_json: Any = Field(default=None, sa_column=Column(JSON, nullable=True))
    notes_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)


class AutomationPlanModel(SQLModel, table=True):
    __tablename__ = "submission_automation_plans"

    plan_id: str = Field(primary_key=True, index=True)
    draft_id: str = Field(foreign_key="submission_drafts.draft_id", index=True)
    target_id: str = Field(index=True)
    source_mode: str = Field(default="live_case_state", index=True)
    source_reviewed_snapshot_id: str = Field(default="", index=True)
    status: str = Field(default="draft", index=True)
    dry_run: bool = True
    guardrails_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    dry_run_summary_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)


class AutomationPlanStepModel(SQLModel, table=True):
    __tablename__ = "submission_automation_plan_steps"

    step_id: str = Field(primary_key=True, index=True)
    plan_id: str = Field(foreign_key="submission_automation_plans.plan_id", index=True)
    step_index: int = Field(index=True)
    step_type: str = Field(index=True)
    status: str = Field(default="informational", index=True)
    title: str
    description: str = ""
    target_reference: str = ""
    tool_id: str | None = Field(default=None, index=True)
    backend_id: str | None = Field(default=None, index=True)
    execution_mode: str = Field(default="blocked", index=True)
    checkpoint_required: bool = False
    checkpoint_reason: str = ""
    fallback_hint_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    mapping_id: str | None = Field(default=None, index=True)
    related_document_id: str | None = Field(default=None, index=True)
    notes_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)