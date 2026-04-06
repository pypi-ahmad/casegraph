"""Shared document review contracts for the CaseGraph platform.

These types define the review surface for inspecting ingested document artifacts,
including page metadata, text block geometry, bounding box overlays, and honest
capability reporting for what artifacts are genuinely available.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.ingestion import (
    CoordinateSpace,
    DocumentId,
    DocumentProcessingStatus,
    GeometrySource,
    IngestionMode,
    SourceFileMetadata,
    TextBlockArtifact,
)


OverlaySourceType = Literal["readable_pdf_extraction", "ocr_extraction"]

_GEOMETRY_TO_OVERLAY: dict[GeometrySource, OverlaySourceType] = {
    GeometrySource.PDF_TEXT: "readable_pdf_extraction",
    GeometrySource.OCR: "ocr_extraction",
}


def geometry_source_to_overlay_type(source: GeometrySource) -> OverlaySourceType:
    """Map a geometry source to its overlay source type label."""
    return _GEOMETRY_TO_OVERLAY[source]


class PageDimensions(BaseModel):
    """Page physical dimensions in the extractor's coordinate space."""

    width: float | None = None
    height: float | None = None
    coordinate_space: CoordinateSpace | None = None


class PageReviewSummary(BaseModel):
    """Lightweight page metadata for document-level page lists."""

    page_number: int
    dimensions: PageDimensions
    geometry_source: GeometrySource | None = None
    text_block_count: int = 0
    has_geometry: bool = False
    has_page_image: bool = False
    text_preview: str = ""


class PageReviewDetail(BaseModel):
    """Full page artifact data for the review viewer."""

    page_number: int
    dimensions: PageDimensions
    text: str = ""
    geometry_source: GeometrySource | None = None
    text_blocks: list[TextBlockArtifact] = Field(default_factory=list)
    has_page_image: bool = False


class DocumentReviewSummary(BaseModel):
    """Document-level review metadata."""

    document_id: DocumentId
    source_file: SourceFileMetadata
    status: DocumentProcessingStatus
    ingestion_mode: IngestionMode
    extractor_name: str | None = None
    page_count: int = 0
    text_block_count: int = 0
    geometry_available: bool = False
    geometry_sources: list[GeometrySource] = Field(default_factory=list)
    page_images_available: bool = False
    linked_case_ids: list[str] = Field(default_factory=list)


class DocumentReviewCapability(BaseModel):
    """Honest capability reporting for the document review surface."""

    can_show_pages: bool = False
    can_show_geometry: bool = False
    can_show_page_images: bool = False
    overlay_source_types: list[OverlaySourceType] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DocumentReviewResponse(BaseModel):
    """Full document review response with page summaries and capabilities."""

    document: DocumentReviewSummary
    pages: list[PageReviewSummary] = Field(default_factory=list)
    capabilities: DocumentReviewCapability


class DocumentPageListResponse(BaseModel):
    """Page-list response for document page navigation."""

    document_id: DocumentId
    pages: list[PageReviewSummary] = Field(default_factory=list)
