"""Persistence models for automation runs, executed steps, artifacts, and events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class AutomationRunModel(SQLModel, table=True):
    __tablename__ = "automation_runs"

    run_id: str = Field(primary_key=True, index=True)
    draft_id: str = Field(foreign_key="submission_drafts.draft_id", index=True)
    plan_id: str = Field(foreign_key="submission_automation_plans.plan_id", index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    source_mode: str = Field(default="live_case_state", index=True)
    source_reviewed_snapshot_id: str = Field(default="", index=True)
    status: str = Field(default="created", index=True)
    operator_id: str = ""
    dry_run: bool = False
    guardrails_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    session_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    paused_run_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    summary_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    notes_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExecutedStepModel(SQLModel, table=True):
    __tablename__ = "automation_executed_steps"

    executed_step_id: str = Field(primary_key=True, index=True)
    run_id: str = Field(foreign_key="automation_runs.run_id", index=True)
    plan_step_id: str = Field(index=True)
    step_index: int = Field(index=True)
    step_type: str = Field(index=True)
    title: str
    description: str = ""
    target_reference: str = ""
    tool_id: str | None = Field(default=None, index=True)
    backend_id: str | None = Field(default=None, index=True)
    status: str = Field(default="pending", index=True)
    outcome_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    notes_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)


class RunArtifactModel(SQLModel, table=True):
    __tablename__ = "automation_run_artifacts"

    artifact_id: str = Field(primary_key=True, index=True)
    run_id: str = Field(foreign_key="automation_runs.run_id", index=True)
    executed_step_id: str | None = Field(default=None, index=True)
    artifact_type: str = Field(index=True)
    display_name: str = ""
    content_text: str | None = None
    content_url: str | None = None
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    notes_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    captured_at: datetime = Field(default_factory=utcnow, index=True)


class RunEventModel(SQLModel, table=True):
    __tablename__ = "automation_run_events"

    event_id: str = Field(primary_key=True, index=True)
    run_id: str = Field(foreign_key="automation_runs.run_id", index=True)
    event_type: str = Field(index=True)
    executed_step_id: str | None = Field(default=None, index=True)
    artifact_id: str | None = Field(default=None, index=True)
    message: str = ""
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    timestamp: datetime = Field(default_factory=utcnow, index=True)


class AutomationCheckpointModel(SQLModel, table=True):
    __tablename__ = "automation_run_checkpoints"

    checkpoint_id: str = Field(primary_key=True, index=True)
    run_id: str = Field(foreign_key="automation_runs.run_id", index=True)
    plan_step_id: str = Field(index=True)
    executed_step_id: str | None = Field(default=None, index=True)
    step_index: int = Field(index=True)
    step_type: str = Field(index=True)
    step_title: str = ""
    status: str = Field(default="pending_operator_review", index=True)
    decision_type: str | None = Field(default=None, index=True)
    operator_id: str = ""
    decision_note: str = ""
    skip_reason: str = ""
    block_reason: str = ""
    execution_mode: str = Field(default="blocked", index=True)
    checkpoint_reason: str = ""
    fallback_hint_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    notes_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)
    decided_at: datetime | None = None
    resolved_at: datetime | None = None


class AutomationCheckpointOverrideModel(SQLModel, table=True):
    __tablename__ = "automation_checkpoint_overrides"

    override_id: str = Field(primary_key=True, index=True)
    checkpoint_id: str = Field(index=True)
    run_id: str = Field(foreign_key="automation_runs.run_id", index=True)
    operator_id: str = ""
    decision_type: str = Field(index=True)
    decision_note: str = ""
    skip_reason: str = ""
    block_reason: str = ""
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)
