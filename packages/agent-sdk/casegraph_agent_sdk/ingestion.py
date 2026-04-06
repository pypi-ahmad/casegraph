"""Shared document ingestion contracts for the CaseGraph platform."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


DocumentId = str


class FileTypeClassification(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    UNSUPPORTED = "unsupported"


class IngestionMode(str, Enum):
    READABLE_PDF = "readable_pdf"
    SCANNED_PDF = "scanned_pdf"
    IMAGE = "image"
    UNSUPPORTED = "unsupported"


class IngestionModePreference(str, Enum):
    AUTO = "auto"
    READABLE_PDF = "readable_pdf"
    SCANNED_PDF = "scanned_pdf"
    IMAGE = "image"


class DocumentProcessingStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class CoordinateSpace(str, Enum):
    PDF_POINTS = "pdf_points"
    PIXELS = "pixels"
    NORMALIZED = "normalized"


class GeometrySource(str, Enum):
    PDF_TEXT = "pdf_text"
    OCR = "ocr"


class SourceFileMetadata(BaseModel):
    filename: str
    content_type: str | None = None
    extension: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    classification: FileTypeClassification = FileTypeClassification.UNSUPPORTED


class IngestionRequest(BaseModel):
    requested_mode: IngestionModePreference = IngestionModePreference.AUTO
    ocr_enabled: bool = False


class IngestionError(BaseModel):
    code: str
    message: str
    recoverable: bool = False


class PolygonPoint(BaseModel):
    x: float
    y: float


class BoundingBoxArtifact(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float
    coordinate_space: CoordinateSpace


class PolygonArtifact(BaseModel):
    points: list[PolygonPoint] = Field(default_factory=list)
    coordinate_space: CoordinateSpace


class TextBlockArtifact(BaseModel):
    block_id: str
    page_number: int
    text: str
    bbox: BoundingBoxArtifact | None = None
    polygon: PolygonArtifact | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    geometry_source: GeometrySource


class PageArtifact(BaseModel):
    page_number: int
    width: float | None = None
    height: float | None = None
    coordinate_space: CoordinateSpace | None = None
    text: str = ""
    text_blocks: list[TextBlockArtifact] = Field(default_factory=list)
    geometry_source: GeometrySource | None = None


class NormalizedExtractionOutput(BaseModel):
    document_id: DocumentId
    source_file: SourceFileMetadata
    requested_mode: IngestionModePreference
    resolved_mode: IngestionMode
    status: DocumentProcessingStatus
    extractor_name: str | None = None
    extracted_text: str = ""
    pages: list[PageArtifact] = Field(default_factory=list)


class IngestionResultSummary(BaseModel):
    document_id: DocumentId
    source_file: SourceFileMetadata
    status: DocumentProcessingStatus
    requested_mode: IngestionModePreference
    resolved_mode: IngestionMode
    extractor_name: str | None = None
    page_count: int = 0
    text_block_count: int = 0
    geometry_present: bool = False
    geometry_sources: list[GeometrySource] = Field(default_factory=list)


class IngestionResult(BaseModel):
    summary: IngestionResultSummary
    output: NormalizedExtractionOutput | None = None
    errors: list[IngestionError] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Capability / registry responses shared between API and frontend
# ---------------------------------------------------------------------------


class IngestionModeCapability(BaseModel):
    mode: IngestionMode
    supported: bool
    requires_ocr: bool
    extractor_name: str | None = None
    notes: list[str] = Field(default_factory=list)


class DocumentsCapabilitiesResponse(BaseModel):
    modes: list[IngestionModeCapability] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DocumentRegistryListResponse(BaseModel):
    documents: list[IngestionResultSummary] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Document detail / page retrieval responses
# ---------------------------------------------------------------------------


class DocumentPageSummary(BaseModel):
    """Persisted page with text blocks (matches PageRecord schema)."""

    page_number: int
    width: float | None = None
    height: float | None = None
    coordinate_space: str | None = None
    geometry_source: str | None = None
    text: str = ""
    text_blocks: list[dict] = Field(default_factory=list)
    has_page_image: bool = False
    page_image_path: str | None = None


class DocumentDetailResponse(BaseModel):
    """Full document detail: summary, extraction output, source file path, and pages."""

    summary: IngestionResultSummary
    output: NormalizedExtractionOutput | None = None
    source_file_path: str | None = None
    pages: list[DocumentPageSummary] = Field(default_factory=list)


class DocumentPagesResponse(BaseModel):
    document_id: DocumentId
    pages: list[DocumentPageSummary] = Field(default_factory=list)