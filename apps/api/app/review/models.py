"""Persistence models for document review page artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class PageRecord(SQLModel, table=True):
    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "page_number",
            name="uq_document_pages_doc_page",
        ),
    )

    page_id: str = Field(primary_key=True, index=True)
    document_id: str = Field(foreign_key="documents.document_id", index=True)
    page_number: int
    width: float | None = None
    height: float | None = None
    coordinate_space: str | None = None
    geometry_source: str | None = None
    text: str = ""
    text_blocks_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    has_page_image: bool = False
    page_image_path: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
