import type { CaseId, CaseStatus } from "./cases";
import type { CaseTypeTemplateId, DomainPackId } from "./domains";
import type { DocumentId } from "./ingestion";
import type {
  ActionItemCategory,
  ActionItemPriority,
  ActionItemStatus,
  CaseStage,
  ReviewDecision,
} from "./operator-review";
import type { ChecklistItemId, ChecklistItemStatus, ReadinessStatus } from "./readiness";
import type { DownstreamSourceMode, SignOffStatus } from "./reviewed-handoff";

export type PacketId = string;
export type ExportArtifactId = string;

export type PacketStatus = "generated" | "stale";

export type PacketSectionType =
  | "case_summary"
  | "domain_metadata"
  | "linked_documents"
  | "extraction_results"
  | "readiness_summary"
  | "open_actions"
  | "review_notes"
  | "run_history"
  | "human_review_state"
  | "reviewed_snapshot";

export type ExportArtifactFormat = "json_manifest" | "markdown_summary";

export interface PacketGenerateRequest {
  note?: string;
  source_mode?: DownstreamSourceMode;
  reviewed_snapshot_id?: string;
}

export interface PacketDocumentEntry {
  document_id: DocumentId;
  filename: string;
  content_type: string | null;
  page_count: number;
  linked_at: string;
}

export interface PacketExtractionEntry {
  extraction_id: string;
  document_id: DocumentId | null;
  template_id: string | null;
  strategy_used: string | null;
  status: string;
  field_count: number;
  fields_extracted: number;
  grounding_available: boolean;
  created_at: string;
}

export interface PacketReadinessEntry {
  checklist_item_id: ChecklistItemId;
  requirement_id: string;
  display_name: string;
  priority: string;
  status: ChecklistItemStatus;
  linked_document_count: number;
  linked_extraction_count: number;
}

export interface PacketActionEntry {
  action_item_id: string;
  category: ActionItemCategory;
  priority: ActionItemPriority;
  status: ActionItemStatus;
  title: string;
  source_reason: string;
}

export interface PacketReviewNoteEntry {
  note_id: string;
  body: string;
  decision: ReviewDecision;
  stage_snapshot: CaseStage;
  created_at: string;
}

export interface PacketRunSummaryEntry {
  run_id: string;
  workflow_id: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface PacketSection {
  section_type: PacketSectionType;
  title: string;
  item_count: number;
  data: Record<string, unknown>;
  empty: boolean;
}

export interface PacketManifest {
  packet_id: PacketId;
  case_id: CaseId;
  source_mode: DownstreamSourceMode;
  source_reviewed_snapshot_id: string;
  source_snapshot_signoff_status: SignOffStatus;
  source_snapshot_signed_off_at: string;
  source_snapshot_signed_off_by: string;
  case_title: string;
  case_status: CaseStatus;
  current_stage: CaseStage;
  domain_pack_id: DomainPackId | null;
  case_type_id: CaseTypeTemplateId | null;
  readiness_status: ReadinessStatus | null;
  linked_document_count: number;
  extraction_count: number;
  open_action_count: number;
  review_note_count: number;
  run_count: number;
  sections: PacketSection[];
  generated_at: string;
  note: string;
}

export interface ExportArtifact {
  artifact_id: ExportArtifactId;
  packet_id: PacketId;
  format: ExportArtifactFormat;
  filename: string;
  size_bytes: number;
  content_type: string;
  created_at: string;
}

export interface PacketSummary {
  packet_id: PacketId;
  case_id: CaseId;
  source_mode: DownstreamSourceMode;
  source_reviewed_snapshot_id: string;
  case_title: string;
  current_stage: CaseStage;
  readiness_status: ReadinessStatus | null;
  section_count: number;
  artifact_count: number;
  generated_at: string;
  note: string;
}

export interface PacketGenerationResult {
  success: boolean;
  message: string;
  packet: PacketSummary | null;
}

export interface PacketListResponse {
  packets: PacketSummary[];
}

export interface PacketDetailResponse {
  packet: PacketSummary;
  manifest: PacketManifest;
}

export interface PacketManifestResponse {
  manifest: PacketManifest;
}

export interface PacketArtifactListResponse {
  artifacts: ExportArtifact[];
}

export interface PacketGenerateResponse {
  result: PacketGenerationResult;
  packet: PacketSummary | null;
  artifacts: ExportArtifact[];
}
