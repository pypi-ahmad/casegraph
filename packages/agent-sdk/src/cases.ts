/**
 * Shared case/workspace contracts for the CaseGraph platform.
 *
 * These types define generic case records, case-document references,
 * workflow run tracking, and normalized request/response shapes for the
 * case-centric foundation layer.
 */

import type {
  DocumentId,
  DocumentProcessingStatus,
  IngestionMode,
  IngestionModePreference,
  SourceFileMetadata,
} from "./ingestion";
import type {
  CaseDomainContext,
  CaseTypeTemplateId,
  DomainPackId,
} from "./domains";
import type { CaseTargetPackSelection } from "./target-packs";

export type CaseId = string;
export type CaseTitle = string;
export type CaseCategory = string;
export type WorkflowRunId = string;

export type CaseStatus =
  | "open"
  | "active"
  | "on_hold"
  | "closed"
  | "archived";

export type CaseRunStatus =
  | "created"
  | "running"
  | "completed"
  | "failed"
  | "queued_placeholder"
  | "not_started"
  | "failed_validation"
  | "completed_placeholder";

export type RunInputReferenceType =
  | "case_document"
  | "document"
  | "case"
  | "custom";

export type CaseMetadata = Record<string, unknown>;

export interface TimestampMetadata {
  created_at: string;
  updated_at: string;
}

export interface NormalizedOperationError {
  error_code: string;
  message: string;
  recoverable: boolean;
}

export interface CaseWorkflowBindingMetadata {
  workflow_id: string;
  bound_at: string;
}

export interface CaseRecord {
  case_id: CaseId;
  title: CaseTitle;
  category: CaseCategory | null;
  status: CaseStatus;
  summary: string | null;
  metadata: CaseMetadata;
  domain_context: CaseDomainContext | null;
  workflow_binding: CaseWorkflowBindingMetadata | null;
  target_pack_selection: CaseTargetPackSelection | null;
  timestamps: TimestampMetadata;
}

export interface CaseDocumentReference {
  link_id: string;
  case_id: CaseId;
  document_id: DocumentId;
  source_file: SourceFileMetadata;
  requested_mode: IngestionModePreference | null;
  resolved_mode: IngestionMode | null;
  document_status: DocumentProcessingStatus | null;
  linked_at: string;
}

export interface RunInputReference {
  reference_type: RunInputReferenceType;
  reference_id: string;
  label: string | null;
  metadata: Record<string, unknown>;
}

export interface WorkflowRunOutputPlaceholderMetadata {
  output_available: boolean;
  summary: string | null;
  artifact_refs: string[];
  task_execution_id: string | null;
  task_execution: import("./tasks").TaskExecutionResult | null;
  rag_task_execution: import("./rag").RagTaskExecutionResult | null;
  events: import("./tasks").TaskExecutionEvent[];
}

export interface WorkflowRunRequest {
  workflow_id: string;
  input_references: RunInputReference[];
  linked_document_ids: DocumentId[];
  notes: string | null;
  task_execution?: import("./tasks").TaskExecutionRequest | null;
  rag_task_execution?: import("./rag").RagTaskExecutionRequest | null;
}

export interface WorkflowRunRecord {
  run_id: WorkflowRunId;
  case_id: CaseId;
  workflow_id: string;
  status: CaseRunStatus;
  input_references: RunInputReference[];
  linked_document_ids: DocumentId[];
  output: WorkflowRunOutputPlaceholderMetadata | null;
  events: import("./tasks").TaskExecutionEvent[];
  error: NormalizedOperationError | null;
  notes: string | null;
  timestamps: TimestampMetadata;
}

export interface CreateCaseRequest {
  title: CaseTitle;
  category: CaseCategory | null;
  summary: string | null;
  metadata: CaseMetadata;
  workflow_id: string | null;
  domain_pack_id?: DomainPackId | null;
  case_type_id?: CaseTypeTemplateId | null;
}

export interface UpdateCaseRequest {
  title?: CaseTitle;
  category?: CaseCategory | null;
  status?: CaseStatus;
  summary?: string | null;
  metadata?: CaseMetadata;
  workflow_id?: string | null;
}

export interface LinkCaseDocumentRequest {
  document_id: DocumentId;
}

export interface CaseListResponse {
  cases: CaseRecord[];
}

export interface CaseDocumentListResponse {
  documents: CaseDocumentReference[];
}

export interface WorkflowRunListResponse {
  runs: WorkflowRunRecord[];
}

export interface CaseDetailResponse {
  case: CaseRecord;
  documents: CaseDocumentReference[];
  runs: WorkflowRunRecord[];
}