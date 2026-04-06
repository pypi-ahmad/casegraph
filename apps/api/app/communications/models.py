"""Persistence models for case-scoped communication drafts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class CommunicationDraftModel(SQLModel, table=True):
    __tablename__ = "communication_drafts"

    draft_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    template_id: str = Field(index=True)
    draft_type: str = Field(index=True)
    audience_type: str = Field(index=True)
    status: str = Field(default="needs_human_review", index=True)
    strategy: str = Field(default="deterministic_template_only", index=True)
    packet_id: str | None = Field(default=None, foreign_key="case_packets.packet_id", index=True)
    workflow_run_id: str | None = Field(default=None, index=True)
    workflow_pack_run_id: str | None = Field(default=None, index=True)
    title: str = ""
    subject: str = ""
    sections_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    source_metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    source_entities_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    evidence_references_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    review_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    generation_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)