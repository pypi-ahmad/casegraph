"""Persistence models for reviewed snapshots and explicit sign-off records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class ReviewedSnapshotModel(SQLModel, table=True):
    __tablename__ = "reviewed_snapshots"

    snapshot_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    status: str = Field(default="created", index=True)
    note: str = ""
    created_by: str = Field(default="", index=True)
    created_by_display_name: str = ""
    created_by_metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    source_metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    summary_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    field_entries_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    requirement_entries_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    unresolved_items_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)
    selected_at: datetime | None = None


class ReviewedSnapshotSignOffModel(SQLModel, table=True):
    __tablename__ = "reviewed_snapshot_signoffs"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            name="uq_reviewed_snapshot_signoffs_snapshot",
        ),
    )

    signoff_id: str = Field(primary_key=True, index=True)
    snapshot_id: str = Field(foreign_key="reviewed_snapshots.snapshot_id", index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    status: str = Field(default="signed_off", index=True)
    actor_id: str = Field(default="", index=True)
    actor_display_name: str = ""
    actor_metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    note: str = ""
    created_at: datetime = Field(default_factory=utcnow, index=True)