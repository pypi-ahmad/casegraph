/**
 * Shared document ingestion contracts for the CaseGraph platform.
 *
 * These types define normalized document artifacts for readable PDF and OCR
 * extraction paths without introducing domain-specific business semantics.
 */

export type DocumentId = string;

export type FileTypeClassification = "pdf" | "image" | "unsupported";

export type IngestionMode =
  | "readable_pdf"
  | "scanned_pdf"
  | "image"
  | "unsupported";

export type IngestionModePreference =
  | "auto"
  | "readable_pdf"
  | "scanned_pdf"
  | "image";

export type DocumentProcessingStatus =
  | "pending"
  | "completed"
  | "failed"
  | "unsupported";

export type CoordinateSpace = "pdf_points" | "pixels" | "normalized";

export type GeometrySource = "pdf_text" | "ocr";

export interface SourceFileMetadata {
  filename: string;
  content_type: string | null;
  extension: string | null;
  size_bytes: number | null;
  sha256: string | null;
  classification: FileTypeClassification;
}

export interface IngestionRequest {
  requested_mode: IngestionModePreference;
  ocr_enabled: boolean;
}

export interface IngestionError {
  code: string;
  message: string;
  recoverable: boolean;
}

export interface PolygonPoint {
  x: number;
  y: number;
}

export interface BoundingBoxArtifact {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  coordinate_space: CoordinateSpace;
}

export interface PolygonArtifact {
  points: PolygonPoint[];
  coordinate_space: CoordinateSpace;
}

export interface TextBlockArtifact {
  block_id: string;
  page_number: number;
  text: string;
  bbox: BoundingBoxArtifact | null;
  polygon: PolygonArtifact | null;
  confidence: number | null;
  geometry_source: GeometrySource;
}

export interface PageArtifact {
  page_number: number;
  width: number | null;
  height: number | null;
  coordinate_space: CoordinateSpace | null;
  text: string;
  text_blocks: TextBlockArtifact[];
  geometry_source: GeometrySource | null;
}

export interface NormalizedExtractionOutput {
  document_id: DocumentId;
  source_file: SourceFileMetadata;
  requested_mode: IngestionModePreference;
  resolved_mode: IngestionMode;
  status: DocumentProcessingStatus;
  extractor_name: string | null;
  extracted_text: string;
  pages: PageArtifact[];
}

export interface IngestionResultSummary {
  document_id: DocumentId;
  source_file: SourceFileMetadata;
  status: DocumentProcessingStatus;
  requested_mode: IngestionModePreference;
  resolved_mode: IngestionMode;
  extractor_name: string | null;
  page_count: number;
  text_block_count: number;
  geometry_present: boolean;
  geometry_sources: GeometrySource[];
}

export interface IngestionResult {
  summary: IngestionResultSummary;
  output: NormalizedExtractionOutput | null;
  errors: IngestionError[];
}

// ---------------------------------------------------------------------------
// Capability / registry responses shared between API and frontend
// ---------------------------------------------------------------------------

export interface IngestionModeCapability {
  mode: IngestionMode;
  supported: boolean;
  requires_ocr: boolean;
  extractor_name: string | null;
  notes: string[];
}

export interface DocumentsCapabilitiesResponse {
  modes: IngestionModeCapability[];
  limitations: string[];
}

export interface DocumentRegistryListResponse {
  documents: IngestionResultSummary[];
}