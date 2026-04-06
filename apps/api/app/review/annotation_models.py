"""Persistence models for document annotations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class AnnotationModel(SQLModel, table=True):
    __tablename__ = "document_annotations"

    annotation_id: str = Field(primary_key=True, index=True)
    document_id: str = Field(foreign_key="documents.document_id", index=True)
    page_number: int = Field(index=True)
    annotation_type: str  # highlight | comment | correction | flag | redaction
    status: str = "active"  # active | resolved | deleted
    anchor_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    body_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = "operator"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime | None = None
