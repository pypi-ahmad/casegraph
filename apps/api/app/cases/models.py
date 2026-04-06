"""SQLModel persistence models for cases and workflow run tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class CaseRecordModel(SQLModel, table=True):
    __tablename__ = "cases"

    case_id: str = Field(primary_key=True, index=True)
    title: str = Field(index=True)
    category: str | None = None
    status: str = Field(default="open", index=True)
    summary: str | None = None
    case_metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    selected_workflow_id: str | None = Field(default=None, index=True)
    workflow_bound_at: datetime | None = None
    current_stage: str = Field(default="intake", index=True)
    domain_pack_id: str | None = Field(default=None, index=True)
    jurisdiction: str | None = None
    case_type_id: str | None = Field(default=None, index=True)
    domain_category: str | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)


class CaseDocumentLinkModel(SQLModel, table=True):
    __tablename__ = "case_document_links"
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "document_id",
            name="uq_case_document_links_case_document",
        ),
    )

    link_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    document_id: str = Field(foreign_key="documents.document_id", index=True)
    linked_at: datetime = Field(default_factory=utcnow, index=True)


class WorkflowRunRecordModel(SQLModel, table=True):
    __tablename__ = "workflow_runs"

    run_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    workflow_id: str = Field(index=True)
    status: str = Field(default="created", index=True)
    input_references_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    linked_document_ids_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    output_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    error_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    notes: str | None = None
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)