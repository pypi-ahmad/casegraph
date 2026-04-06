"""Persistence models for task execution records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class TaskExecutionRecordModel(SQLModel, table=True):
    """Persisted record of a provider-backed task execution."""

    __tablename__ = "task_executions"

    execution_id: str = Field(primary_key=True, index=True)
    task_id: str = Field(index=True)
    provider: str = Field(index=True)
    model_id: str
    finish_reason: str
    output_text: str | None = None
    structured_output_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True),
    )
    usage_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True),
    )
    error_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True),
    )
    events_json: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False),
    )
    duration_ms: int | None = None
    provider_request_id: str | None = None
    # Optional link to a workflow run
    run_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
