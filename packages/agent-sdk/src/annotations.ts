/**
 * Document annotation types for the CaseGraph review surface.
 */

import type {
  BoundingBoxArtifact,
  CoordinateSpace,
  DocumentId,
} from "./ingestion";

export type AnnotationId = string;

export type AnnotationType =
  | "highlight"
  | "comment"
  | "correction"
  | "flag"
  | "redaction";

export type AnnotationStatus = "active" | "resolved" | "deleted";

export interface AnnotationAnchor {
  page_number: number;
  bbox: BoundingBoxArtifact;
  block_id: string | null;
}

export interface AnnotationBody {
  text: string;
  original_text: string | null;
}

export interface CreateAnnotationRequest {
  document_id: DocumentId;
  annotation_type: AnnotationType;
  anchor: AnnotationAnchor;
  body?: AnnotationBody;
  created_by?: string;
}

export interface UpdateAnnotationRequest {
  annotation_type?: AnnotationType;
  body?: AnnotationBody;
  status?: AnnotationStatus;
}

export interface AnnotationRecord {
  annotation_id: AnnotationId;
  document_id: DocumentId;
  annotation_type: AnnotationType;
  status: AnnotationStatus;
  anchor: AnnotationAnchor;
  body: AnnotationBody;
  created_by: string;
  created_at: string;
  updated_at: string | null;
}

export interface AnnotationListResponse {
  document_id: DocumentId;
  annotations: AnnotationRecord[];
  total_count: number;
}

export interface PageAnnotationListResponse {
  document_id: DocumentId;
  page_number: number;
  annotations: AnnotationRecord[];
}

export interface WordArtifact {
  text: string;
  bbox: BoundingBoxArtifact;
  block_number: number | null;
  line_number: number | null;
  word_number: number | null;
  confidence: number | null;
}

export interface PageWordsResponse {
  document_id: DocumentId;
  page_number: number;
  coordinate_space: CoordinateSpace | null;
  words: WordArtifact[];
  word_count: number;
}
