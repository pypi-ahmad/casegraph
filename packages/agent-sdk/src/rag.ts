/**
 * Shared contracts for retrieval-augmented task execution.
 *
 * These types mirror the Python Pydantic models in casegraph_agent_sdk/rag.py
 * and define normalized structures for evidence selection, citation references,
 * retrieval scope, and RAG-specific execution requests/results.
 */

import type { SearchScoreMetadata, SourceReference } from "./retrieval";
import type {
  FinishReason,
  ProviderSelection,
  StructuredOutputResult,
  StructuredOutputSchema,
  TaskExecutionError,
  TaskExecutionEvent,
  TaskId,
  UsageMetadata,
} from "./tasks";

// ---------------------------------------------------------------------------
// Evidence / citation references
// ---------------------------------------------------------------------------

export interface EvidenceChunkReference {
  chunk_id: string;
  text: string;
  score: SearchScoreMetadata;
  source_reference: SourceReference;
  source_filename: string | null;
  page_number: number | null;
}

export interface CitationReference {
  citation_index: number;
  chunk_id: string;
  document_id: string | null;
  page_number: number | null;
  source_filename: string | null;
}

// ---------------------------------------------------------------------------
// Evidence selection summary
// ---------------------------------------------------------------------------

export interface EvidenceSelectionSummary {
  query: string;
  total_retrieved: number;
  total_selected: number;
  embedding_model: string | null;
  vector_store: string | null;
}

// ---------------------------------------------------------------------------
// Retrieval scope
// ---------------------------------------------------------------------------

export type RetrievalScopeKind = "global" | "case" | "document";

export interface RetrievalScope {
  kind: RetrievalScopeKind;
  case_id: string | null;
  document_ids: string[];
}

// ---------------------------------------------------------------------------
// RAG execution request / result
// ---------------------------------------------------------------------------

export interface RagTaskExecutionRequest {
  task_id: TaskId;
  query: string;
  parameters: Record<string, unknown>;
  provider_selection: ProviderSelection;
  retrieval_scope: RetrievalScope;
  top_k: number;
  structured_output: StructuredOutputSchema | null;
  max_tokens: number | null;
  temperature: number | null;
}

export interface ResultGroundingMetadata {
  evidence_provided: boolean;
  evidence_chunk_count: number;
  citation_count: number;
  grounding_method: string;
}

export interface RagTaskExecutionResult {
  task_id: TaskId;
  provider: string;
  model_id: string;
  finish_reason: FinishReason;
  output_text: string | null;
  structured_output: StructuredOutputResult | null;
  citations: CitationReference[];
  evidence: EvidenceChunkReference[];
  evidence_summary: EvidenceSelectionSummary | null;
  grounding: ResultGroundingMetadata | null;
  usage: UsageMetadata | null;
  error: TaskExecutionError | null;
  duration_ms: number | null;
  provider_request_id: string | null;
}

// ---------------------------------------------------------------------------
// RAG task registry response
// ---------------------------------------------------------------------------

export interface RagTaskDefinitionMeta {
  task_id: TaskId;
  display_name: string;
  category: string;
  description: string;
  requires_evidence: boolean;
  returns_citations: boolean;
  supports_structured_output: boolean;
  output_schema: Record<string, unknown>;
}

export interface RagTaskRegistryResponse {
  tasks: RagTaskDefinitionMeta[];
}

// ---------------------------------------------------------------------------
// RAG-specific event kinds
// ---------------------------------------------------------------------------

export type RagEventKind =
  | "retrieval_started"
  | "retrieval_completed"
  | "evidence_selected"
  | "context_assembled"
  | "provider_resolved"
  | "model_invoked"
  | "model_completed"
  | "structured_output_validated"
  | "citations_attached"
  | "model_failed"
  | "retrieval_failed";
