/**
 * Shared document review contracts for the CaseGraph platform.
 *
 * These types define the review surface for inspecting ingested document artifacts,
 * including page metadata, text block geometry, bounding box overlays, and honest
 * capability reporting for what artifacts are genuinely available.
 */

import type {
  CoordinateSpace,
  DocumentId,
  DocumentProcessingStatus,
  GeometrySource,
  IngestionMode,
  SourceFileMetadata,
  TextBlockArtifact,
} from "./ingestion";

export type OverlaySourceType = "readable_pdf_extraction" | "ocr_extraction";

export interface PageDimensions {
  width: number | null;
  height: number | null;
  coordinate_space: CoordinateSpace | null;
}

export interface PageReviewSummary {
  page_number: number;
  dimensions: PageDimensions;
  geometry_source: GeometrySource | null;
  text_block_count: number;
  has_geometry: boolean;
  has_page_image: boolean;
  text_preview: string;
}

export interface PageReviewDetail {
  page_number: number;
  dimensions: PageDimensions;
  text: string;
  geometry_source: GeometrySource | null;
  text_blocks: TextBlockArtifact[];
  has_page_image: boolean;
}

export interface DocumentReviewSummary {
  document_id: DocumentId;
  source_file: SourceFileMetadata;
  status: DocumentProcessingStatus;
  ingestion_mode: IngestionMode;
  extractor_name: string | null;
  page_count: number;
  text_block_count: number;
  geometry_available: boolean;
  geometry_sources: GeometrySource[];
  page_images_available: boolean;
  linked_case_ids: string[];
}

export interface DocumentReviewCapability {
  can_show_pages: boolean;
  can_show_geometry: boolean;
  can_show_page_images: boolean;
  overlay_source_types: OverlaySourceType[];
  limitations: string[];
}

export interface DocumentReviewResponse {
  document: DocumentReviewSummary;
  pages: PageReviewSummary[];
  capabilities: DocumentReviewCapability;
}

export interface DocumentPageListResponse {
  document_id: DocumentId;
  pages: PageReviewSummary[];
}
