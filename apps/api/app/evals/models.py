"""Persistence models for eval suite runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class EvalRunModel(SQLModel, table=True):
    __tablename__ = "eval_runs"

    run_id: str = Field(primary_key=True, index=True)
    suite_id: str = Field(index=True)
    status: str = Field(default="created", index=True)
    case_results_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    error_cases: int = 0
    skipped_cases: int = 0
    notes_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float = 0.0
