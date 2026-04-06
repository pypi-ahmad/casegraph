"""Persistence models for case work-management state and assignment history."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class CaseWorkStateModel(SQLModel, table=True):
    __tablename__ = "case_work_state"

    case_id: str = Field(primary_key=True, foreign_key="cases.case_id", index=True)
    assignment_status: str = Field(default="unassigned", index=True)
    assignee_id: str = Field(default="", index=True)
    assignee_display_name: str = ""
    assignee_email: str = ""
    assignee_role: str = Field(default="member", index=True)
    assignment_reason: str = ""
    assignment_note: str = ""
    assigned_at: datetime | None = Field(default=None, index=True)
    assignment_changed_by_id: str = Field(default="", index=True)
    assignment_changed_by_display_name: str = ""
    sla_policy_id: str = Field(default="", index=True)
    due_at: datetime | None = Field(default=None, index=True)
    due_soon_window_hours: int = 24
    sla_note: str = ""
    sla_updated_by_id: str = Field(default="", index=True)
    sla_updated_by_display_name: str = ""
    sla_updated_at: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)


class CaseAssignmentHistoryModel(SQLModel, table=True):
    __tablename__ = "case_assignment_history"

    record_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    status: str = Field(default="unassigned", index=True)
    assignee_id: str = Field(default="", index=True)
    assignee_display_name: str = ""
    assignee_email: str = ""
    assignee_role: str = Field(default="member", index=True)
    reason: str = Field(default="manual_assignment", index=True)
    note: str = ""
    changed_by_id: str = Field(default="", index=True)
    changed_by_display_name: str = ""
    created_at: datetime = Field(default_factory=utcnow, index=True)