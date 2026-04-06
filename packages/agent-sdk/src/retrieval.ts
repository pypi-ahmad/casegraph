/**
 * Shared retrieval / knowledge contracts for the CaseGraph platform.
 *
 * These types mirror the Python Pydantic models in casegraph_agent_sdk/retrieval.py
 * and define normalized structures for chunking, vector indexing, and search.
 */

export type ChunkId = string;
export type KnowledgeItemId = string;

/* ------------------------------------------------------------------ */
/* Source references                                                    */
/* ------------------------------------------------------------------ */

export interface SourceReference {
  document_id: string;
  page_number: number | null;
  block_ids: string[];
  geometry_source: string | null;
}

/* ------------------------------------------------------------------ */
/* Chunk                                                               */
/* ------------------------------------------------------------------ */

export interface ChunkMetadata {
  document_id: string;
  page_number: number | null;
  block_ids: string[];
  source_filename: string | null;
  chunk_index: number;
  total_chunks: number;
}

export interface ChunkContent {
  chunk_id: ChunkId;
  text: string;
  metadata: ChunkMetadata;
  source_reference: SourceReference;
}

/* ------------------------------------------------------------------ */
/* Embedding model metadata                                            */
/* ------------------------------------------------------------------ */

export interface EmbeddingModelInfo {
  model_name: string;
  dimension: number;
  provider: string;
  notes: string[];
}

/* ------------------------------------------------------------------ */
/* Index request / result                                              */
/* ------------------------------------------------------------------ */

export interface IndexRequest {
  document_id: string;
  chunks: ChunkContent[];
}

export interface IndexResultSummary {
  document_id: string;
  chunks_indexed: number;
  embedding_model: string | null;
  vector_store: string | null;
}

export interface RetrievalError {
  code: string;
  message: string;
  recoverable: boolean;
}

export interface IndexResult {
  summary: IndexResultSummary;
  errors: RetrievalError[];
}

/* ------------------------------------------------------------------ */
/* Search request / result                                             */
/* ------------------------------------------------------------------ */

export interface MetadataFilter {
  field: string;
  value: string;
}

export interface SearchRequest {
  query: string;
  top_k: number;
  filters: MetadataFilter[];
}

export interface SearchScoreMetadata {
  raw_score: number;
  normalized_score: number | null;
  scoring_method: string;
}

export interface SearchResultItem {
  chunk_id: ChunkId;
  text: string;
  score: SearchScoreMetadata;
  metadata: ChunkMetadata;
  source_reference: SourceReference;
}

export interface SearchResult {
  query: string;
  items: SearchResultItem[];
  total_results: number;
  embedding_model: string | null;
  vector_store: string | null;
}

/* ------------------------------------------------------------------ */
/* Knowledge capability / status                                       */
/* ------------------------------------------------------------------ */

export interface KnowledgeCapabilityStatus {
  component: string;
  available: boolean;
  name: string | null;
  notes: string[];
}

export interface KnowledgeCapabilitiesResponse {
  embedding: KnowledgeCapabilityStatus;
  vector_store: KnowledgeCapabilityStatus;
  embedding_model: EmbeddingModelInfo | null;
  indexed_chunks: number;
  limitations: string[];
}
