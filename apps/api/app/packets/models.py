"""Persistence models for case packets and export artifacts."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class PacketRecordModel(SQLModel, table=True):
    __tablename__ = "case_packets"

    packet_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    source_mode: str = Field(default="live_case_state", index=True)
    source_reviewed_snapshot_id: str = Field(default="", index=True)
    case_title: str = ""
    current_stage: str = Field(default="intake", index=True)
    readiness_status: str | None = None
    section_count: int = 0
    artifact_count: int = 0
    manifest_json: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    note: str = ""
    generated_at: datetime = Field(default_factory=utcnow, index=True)


class ExportArtifactModel(SQLModel, table=True):
    __tablename__ = "export_artifacts"

    artifact_id: str = Field(primary_key=True, index=True)
    packet_id: str = Field(foreign_key="case_packets.packet_id", index=True)
    format: str = Field(index=True)
    filename: str
    size_bytes: int = 0
    content_type: str = ""
    content_text: str | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)
