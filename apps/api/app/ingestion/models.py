"""Persistence models for ingested document summaries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class DocumentRecord(SQLModel, table=True):
    __tablename__ = "documents"

    document_id: str = Field(primary_key=True, index=True)
    filename: str
    content_type: str | None = None
    extension: str | None = None
    size_bytes: int | None = None
    sha256: str | None = Field(default=None, index=True)
    classification: str
    requested_mode: str
    resolved_mode: str
    processing_status: str
    extractor_name: str | None = None
    page_count: int = 0
    text_block_count: int = 0
    geometry_present: bool = False
    geometry_sources_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    source_file_path: str | None = None
    extraction_output_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)