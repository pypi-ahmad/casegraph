/**
 * Shared extraction contracts for the CaseGraph platform.
 *
 * These types define schema-driven extraction: templates, field definitions,
 * extraction strategies, results with per-field grounding, and geometry-aware
 * source references.
 */

import type {
  BoundingBoxArtifact,
  CoordinateSpace,
  DocumentId,
  GeometrySource,
  PolygonArtifact,
} from "./ingestion";

// ---------------------------------------------------------------------------
// Identifiers
// ---------------------------------------------------------------------------

export type ExtractionTemplateId = string;
export type ExtractionId = string;

// ---------------------------------------------------------------------------
// Enums and literals
// ---------------------------------------------------------------------------

export type ExtractionFieldType =
  | "string"
  | "integer"
  | "number"
  | "boolean"
  | "date"
  | "list"
  | "object";

export type ExtractionStrategy =
  | "provider_structured"
  | "langextract_grounded"
  | "auto";

export type ExtractionStatus =
  | "pending"
  | "running"
  | "completed"
  | "partial"
  | "failed";

export type ExtractionEventKind =
  | "extraction_started"
  | "extraction_strategy_selected"
  | "provider_resolved"
  | "langextract_selected"
  | "extraction_completed"
  | "grounding_attached"
  | "extraction_failed";

// ---------------------------------------------------------------------------
// Field and schema definitions
// ---------------------------------------------------------------------------

export interface ExtractionFieldDefinition {
  field_id: string;
  display_name: string;
  field_type: ExtractionFieldType;
  description: string;
  required: boolean;
  item_type: ExtractionFieldType | null;
  nested_fields: ExtractionFieldDefinition[] | null;
}

export interface ExtractionSchemaDefinition {
  fields: ExtractionFieldDefinition[];
}

// ---------------------------------------------------------------------------
// Template metadata
// ---------------------------------------------------------------------------

export interface ExtractionTemplateMetadata {
  template_id: ExtractionTemplateId;
  display_name: string;
  description: string;
  category: string;
  preferred_strategy: ExtractionStrategy;
  field_count: number;
}

export interface ExtractionTemplateDetail {
  metadata: ExtractionTemplateMetadata;
  schema_definition: ExtractionSchemaDefinition;
  system_prompt: string;
  user_prompt_template: string;
}

// ---------------------------------------------------------------------------
// Grounding and source references
// ---------------------------------------------------------------------------

export interface GroundingReference {
  document_id: DocumentId | null;
  page_number: number | null;
  block_id: string | null;
  chunk_id: string | null;
  text_span: string | null;
  geometry_source: GeometrySource | null;
  coordinate_space: CoordinateSpace | null;
  bbox: BoundingBoxArtifact | null;
  polygon: PolygonArtifact | null;
  grounding_method: string | null;
}

// ---------------------------------------------------------------------------
// Extraction request
// ---------------------------------------------------------------------------

export interface ExtractionRequest {
  template_id: ExtractionTemplateId;
  document_id: DocumentId;
  case_id: string | null;
  strategy: ExtractionStrategy;
  provider: string | null;
  model_id: string | null;
  api_key: string | null;
  max_tokens: number | null;
  temperature: number | null;
}

// ---------------------------------------------------------------------------
// Extraction results
// ---------------------------------------------------------------------------

export interface ExtractedFieldResult {
  field_id: string;
  field_type: ExtractionFieldType;
  value: unknown;
  raw_value: string | null;
  is_present: boolean;
  grounding: GroundingReference[];
}

export interface ExtractionError {
  code: string;
  message: string;
  recoverable: boolean;
}

export interface ExtractionEvent {
  kind: ExtractionEventKind;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface ExtractionRunMetadata {
  extraction_id: ExtractionId;
  document_id: DocumentId;
  template_id: ExtractionTemplateId;
  case_id: string | null;
  strategy_used: ExtractionStrategy;
  provider: string | null;
  model_id: string | null;
  status: ExtractionStatus;
  duration_ms: number | null;
  field_count: number;
  fields_extracted: number;
  grounding_available: boolean;
}

export interface ExtractionResult {
  run: ExtractionRunMetadata;
  fields: ExtractedFieldResult[];
  errors: ExtractionError[];
  events: ExtractionEvent[];
}

// ---------------------------------------------------------------------------
// API response models
// ---------------------------------------------------------------------------

export interface ExtractionTemplateListResponse {
  templates: ExtractionTemplateMetadata[];
  available_strategies: ExtractionStrategy[];
  limitations: string[];
}

export interface DocumentExtractionListResponse {
  document_id: DocumentId;
  extractions: ExtractionRunMetadata[];
}
