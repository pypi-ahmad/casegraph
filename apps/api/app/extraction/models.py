"""Persistence models for extraction results."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class ExtractionRunModel(SQLModel, table=True):
    """Persisted extraction run record."""

    __tablename__ = "extraction_runs"

    extraction_id: str = Field(primary_key=True, index=True)
    document_id: str = Field(index=True)
    template_id: str = Field(index=True)
    case_id: str | None = Field(default=None, index=True)
    strategy_used: str
    provider: str | None = None
    model_id: str | None = None
    status: str
    duration_ms: int | None = None
    field_count: int = 0
    fields_extracted: int = 0
    grounding_available: bool = False
    fields_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    errors_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    events_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)
