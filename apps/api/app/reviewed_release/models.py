"""Persistence models for reviewed release bundles and artifact entries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class ReleaseBundleModel(SQLModel, table=True):
    __tablename__ = "release_bundles"

    release_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    snapshot_id: str = Field(foreign_key="reviewed_snapshots.snapshot_id", index=True)
    signoff_id: str = Field(default="", foreign_key="reviewed_snapshot_signoffs.signoff_id", index=True)
    status: str = Field(default="created", index=True)
    note: str = ""
    created_by: str = Field(default="", index=True)
    created_by_display_name: str = ""
    source_metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    summary_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    artifacts_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)
