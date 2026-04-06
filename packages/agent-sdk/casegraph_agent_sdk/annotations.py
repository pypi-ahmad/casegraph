"""Document annotation types for the CaseGraph review surface.

Annotations anchor to document pages via bounding-box regions, allowing
operators and automated processes to mark, comment, flag, and correct
text blocks.  Each annotation carries the coordinate-space of its anchor
so the frontend can render overlays accurately regardless of whether the
source was a readable-PDF or OCR extraction.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.ingestion import (
    BoundingBoxArtifact,
    CoordinateSpace,
    DocumentId,
)

# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------

AnnotationId = str
"""Opaque annotation identifier."""

AnnotationType = Literal[
    "highlight",
    "comment",
    "correction",
    "flag",
    "redaction",
]
"""
Annotation categories:

- **highlight** — visual emphasis on a text region.
- **comment** — free-text note anchored to a region.
- **correction** — operator override of extracted text.
- **flag** — marks a region for later review (e.g. low-confidence OCR).
- **redaction** — marks a region that should be excluded from downstream use.
"""

AnnotationStatus = Literal["active", "resolved", "deleted"]


class AnnotationAnchor(BaseModel):
    """Spatial anchor tying an annotation to a page region."""

    page_number: int
    bbox: BoundingBoxArtifact
    block_id: str | None = None
    """Optional reference to the TextBlockArtifact.block_id this annotation targets."""


class AnnotationBody(BaseModel):
    """Content payload of an annotation."""

    text: str = ""
    """Free-text content (comment body, corrected text, flag reason, etc.)."""

    original_text: str | None = None
    """For 'correction' type — the original extracted text being overridden."""


# ---------------------------------------------------------------------------
# Request / Response types
# ---------------------------------------------------------------------------


class CreateAnnotationRequest(BaseModel):
    """Request to create a new annotation on a document page."""

    document_id: DocumentId
    annotation_type: AnnotationType
    anchor: AnnotationAnchor
    body: AnnotationBody = Field(default_factory=AnnotationBody)
    created_by: str = "operator"


class UpdateAnnotationRequest(BaseModel):
    """Request to update an existing annotation."""

    annotation_type: AnnotationType | None = None
    body: AnnotationBody | None = None
    status: AnnotationStatus | None = None


class AnnotationRecord(BaseModel):
    """Full annotation record as returned by the API."""

    annotation_id: AnnotationId
    document_id: DocumentId
    annotation_type: AnnotationType
    status: AnnotationStatus = "active"
    anchor: AnnotationAnchor
    body: AnnotationBody
    created_by: str = "operator"
    created_at: str = ""
    updated_at: str | None = None


class AnnotationListResponse(BaseModel):
    """Response for listing annotations on a document."""

    document_id: DocumentId
    annotations: list[AnnotationRecord] = Field(default_factory=list)
    total_count: int = 0


class PageAnnotationListResponse(BaseModel):
    """Response for listing annotations on a specific page."""

    document_id: DocumentId
    page_number: int
    annotations: list[AnnotationRecord] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Word-level extraction types
# ---------------------------------------------------------------------------


class WordArtifact(BaseModel):
    """A single word with its bounding box, extracted at word granularity."""

    text: str
    bbox: BoundingBoxArtifact
    block_number: int | None = None
    line_number: int | None = None
    word_number: int | None = None
    confidence: float | None = None


class PageWordsResponse(BaseModel):
    """Word-level extraction for a single page."""

    document_id: DocumentId
    page_number: int
    coordinate_space: CoordinateSpace | None = None
    words: list[WordArtifact] = Field(default_factory=list)
    word_count: int = 0
