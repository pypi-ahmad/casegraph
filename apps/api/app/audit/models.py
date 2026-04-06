"""Persistence models for audit events, decision ledger entries, and lineage."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class AuditEventModel(SQLModel, table=True):
    __tablename__ = "audit_events"

    event_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    category: str = Field(index=True)
    event_type: str = Field(index=True)
    actor_type: str = Field(index=True)
    actor_id: str = Field(default="", index=True)
    actor_display_name: str = ""
    actor_metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    entity_type: str = Field(index=True)
    entity_id: str = Field(index=True)
    entity_label: str = ""
    change_summary_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    decision_ids_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    related_entities_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)


class DecisionLedgerEntryModel(SQLModel, table=True):
    __tablename__ = "decision_ledger_entries"

    decision_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    decision_type: str = Field(index=True)
    actor_type: str = Field(index=True)
    actor_id: str = Field(default="", index=True)
    actor_display_name: str = ""
    actor_metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    source_entity_type: str = Field(index=True)
    source_entity_id: str = Field(index=True)
    source_entity_label: str = ""
    related_event_id: str = Field(default="", index=True)
    outcome: str = ""
    reason: str = ""
    note: str = ""
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)


class ArtifactLineageRecordModel(SQLModel, table=True):
    __tablename__ = "artifact_lineage_records"
    __table_args__ = (
        UniqueConstraint(
            "artifact_type",
            "artifact_id",
            name="uq_artifact_lineage_records_type_id",
        ),
    )

    record_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    artifact_type: str = Field(index=True)
    artifact_id: str = Field(index=True)
    artifact_label: str = ""
    notes_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)


class ArtifactLineageEdgeModel(SQLModel, table=True):
    __tablename__ = "artifact_lineage_edges"

    edge_id: str = Field(primary_key=True, index=True)
    record_id: str = Field(foreign_key="artifact_lineage_records.record_id", index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    relationship_type: str = Field(index=True)
    source_artifact_type: str = Field(index=True)
    source_artifact_id: str = Field(index=True)
    source_label: str = ""
    source_path: str = ""
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)