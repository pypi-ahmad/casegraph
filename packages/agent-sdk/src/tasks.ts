/**
 * Shared contracts for provider-backed LLM task execution.
 */

// ---------------------------------------------------------------------------
// Task identity & classification
// ---------------------------------------------------------------------------

export type TaskId = string;

export type TaskCategory =
  | "text_generation"
  | "classification"
  | "extraction"
  | "summarization"
  | "custom";

export interface TaskDefinitionMeta {
  task_id: TaskId;
  display_name: string;
  category: TaskCategory;
  description: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  supports_structured_output: boolean;
}

// ---------------------------------------------------------------------------
// Task input / output envelopes
// ---------------------------------------------------------------------------

export interface TaskInput {
  text: string;
  parameters: Record<string, unknown>;
}

export interface StructuredOutputSchema {
  json_schema: Record<string, unknown>;
  strict: boolean;
}

// ---------------------------------------------------------------------------
// Provider / model selection
// ---------------------------------------------------------------------------

export interface ProviderSelection {
  provider: string;
  model_id: string;
  api_key: string;
}

// ---------------------------------------------------------------------------
// Execution request
// ---------------------------------------------------------------------------

export interface TaskExecutionRequest {
  task_id: TaskId;
  input: TaskInput;
  provider_selection: ProviderSelection;
  structured_output: StructuredOutputSchema | null;
  max_tokens: number | null;
  temperature: number | null;
}

// ---------------------------------------------------------------------------
// Finish / usage / error normalization
// ---------------------------------------------------------------------------

export type FinishReason =
  | "completed"
  | "max_tokens"
  | "content_filter"
  | "error"
  | "unknown";

export interface UsageMetadata {
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
}

export interface TaskExecutionError {
  error_code: string;
  message: string;
  provider: string | null;
  model_id: string | null;
  recoverable: boolean;
  upstream_status_code: number | null;
}

// ---------------------------------------------------------------------------
// Structured output result
// ---------------------------------------------------------------------------

export interface StructuredOutputResult {
  parsed: Record<string, unknown> | null;
  raw_text: string | null;
  schema_valid: boolean;
  validation_errors: string[];
}

// ---------------------------------------------------------------------------
// Execution result
// ---------------------------------------------------------------------------

export interface TaskExecutionResult {
  task_id: TaskId;
  provider: string;
  model_id: string;
  finish_reason: FinishReason;
  output_text: string | null;
  structured_output: StructuredOutputResult | null;
  usage: UsageMetadata | null;
  error: TaskExecutionError | null;
  duration_ms: number | null;
  provider_request_id: string | null;
}

// ---------------------------------------------------------------------------
// Task registry response
// ---------------------------------------------------------------------------

export interface TaskRegistryResponse {
  tasks: TaskDefinitionMeta[];
}

// ---------------------------------------------------------------------------
// Task execution event types
// ---------------------------------------------------------------------------

export type TaskExecutionEventKind =
  | "task_selected"
  | "provider_resolved"
  | "model_invoked"
  | "model_completed"
  | "structured_output_validated"
  | "model_failed"
  // RAG-specific event kinds
  | "retrieval_started"
  | "retrieval_completed"
  | "retrieval_failed"
  | "evidence_selected"
  | "context_assembled"
  | "citations_attached";

export interface TaskExecutionEvent {
  kind: TaskExecutionEventKind;
  timestamp: string;
  metadata: Record<string, unknown>;
}
