"""Persistence models for human validation records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.persistence.database import utcnow


class FieldValidationModel(SQLModel, table=True):
    __tablename__ = "field_validations"
    __table_args__ = (
        UniqueConstraint(
            "extraction_id",
            "field_id",
            name="uq_field_validations_extraction_field",
        ),
    )

    validation_id: str = Field(primary_key=True, index=True)
    extraction_id: str = Field(index=True)
    field_id: str = Field(index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    status: str = Field(default="unreviewed", index=True)
    original_value_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    reviewed_value_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    reviewer_id: str = Field(default="", index=True)
    reviewer_display_name: str = ""
    reviewer_metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    note: str = ""
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)


class RequirementReviewModel(SQLModel, table=True):
    __tablename__ = "requirement_reviews"
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "checklist_id",
            "item_id",
            name="uq_requirement_reviews_case_checklist_item",
        ),
    )

    review_id: str = Field(primary_key=True, index=True)
    case_id: str = Field(foreign_key="cases.case_id", index=True)
    checklist_id: str = Field(index=True)
    item_id: str = Field(index=True)
    status: str = Field(default="unreviewed", index=True)
    original_machine_status: str = ""
    reviewer_id: str = Field(default="", index=True)
    reviewer_display_name: str = ""
    reviewer_metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    note: str = ""
    linked_document_ids_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    linked_extraction_ids_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    linked_evidence_notes_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)
