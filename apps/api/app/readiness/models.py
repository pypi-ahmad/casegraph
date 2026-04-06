"""Persistence models for case checklists and readiness evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class ChecklistModel(SQLModel, table=True):
    """A checklist instance derived from a domain pack case type template."""

    __tablename__ = "checklists"

    checklist_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    domain_pack_id: str = Field(index=True)
    case_type_id: str = Field(index=True)
    requirement_count: int = 0
    generated_at: datetime = Field(default_factory=utcnow, index=True)


class ChecklistItemModel(SQLModel, table=True):
    """A single requirement item within a checklist."""

    __tablename__ = "checklist_items"
    __table_args__ = (
        UniqueConstraint(
            "checklist_id",
            "requirement_id",
            name="uq_checklist_items_checklist_requirement",
        ),
    )

    item_id: str = Field(primary_key=True, index=True)
    checklist_id: str = Field(foreign_key="checklists.checklist_id", index=True)
    requirement_id: str = Field(index=True)
    display_name: str
    description: str = ""
    document_category: str
    priority: str  # required | recommended | optional
    status: str = "missing"
    operator_notes: str = ""
    last_evaluated_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ChecklistItemDocumentLinkModel(SQLModel, table=True):
    """Links a checklist item to a case document."""

    __tablename__ = "checklist_item_document_links"
    __table_args__ = (
        UniqueConstraint(
            "item_id",
            "document_id",
            name="uq_checklist_item_doc_link",
        ),
    )

    link_id: str = Field(primary_key=True, index=True)
    item_id: str = Field(foreign_key="checklist_items.item_id", index=True)
    document_id: str = Field(index=True)
    filename: str = ""
    content_type: str = ""
    linked_at: datetime = Field(default_factory=utcnow)


class ChecklistItemExtractionLinkModel(SQLModel, table=True):
    """Links a checklist item to an extraction run result."""

    __tablename__ = "checklist_item_extraction_links"
    __table_args__ = (
        UniqueConstraint(
            "item_id",
            "extraction_id",
            name="uq_checklist_item_extract_link",
        ),
    )

    link_id: str = Field(primary_key=True, index=True)
    item_id: str = Field(foreign_key="checklist_items.item_id", index=True)
    extraction_id: str = Field(index=True)
    template_id: str = ""
    document_id: str = ""
    field_count: int = 0
    grounding_available: bool = False
    linked_at: datetime = Field(default_factory=utcnow)
