/**
 * Audit, decision-ledger, and artifact-lineage contracts.
 *
 * These types describe local-first operational traceability. They do not
 * claim formal compliance archiving, WORM storage, notarization, or
 * cryptographic immutability guarantees.
 */

export type AuditEventId = string;
export type DecisionLedgerEntryId = string;
export type LineageRecordId = string;
export type LineageEdgeId = string;

export type AuditEventCategory =
  | "case"
  | "work_management"
  | "checklist"
  | "review"
  | "extraction"
  | "packet"
  | "submission_draft"
  | "automation"
  | "workflow_run"
  | "communication"
  | "human_validation"
  | "reviewed_handoff"
  | "reviewed_release";

export type AuditEventType =
  | "case_created"
  | "case_updated"
  | "case_assignment_updated"
  | "case_sla_updated"
  | "case_document_linked"
  | "case_stage_transitioned"
  | "checklist_generated"
  | "checklist_evaluated"
  | "review_note_added"
  | "extraction_completed"
  | "packet_generated"
  | "submission_draft_created"
  | "submission_approval_updated"
  | "automation_plan_generated"
  | "automation_run_created"
  | "automation_checkpoint_decided"
  | "communication_draft_generated"
  | "communication_draft_review_updated"
  | "workflow_pack_run_completed"
  | "field_validation_recorded"
  | "requirement_review_recorded"
  | "reviewed_snapshot_created"
  | "reviewed_snapshot_signed_off"
  | "reviewed_snapshot_selected_for_handoff"
  | "release_bundle_created";

export type AuditActorType =
  | "operator"
  | "service"
  | "system"
  | "workflow_pack"
  | "automation";

export type DecisionType =
  | "stage_transition"
  | "review_note_added"
  | "case_assignment_updated"
  | "case_sla_updated"
  | "checklist_evaluated"
  | "packet_generated"
  | "draft_approval_updated"
  | "checkpoint_approved"
  | "checkpoint_skipped"
  | "checkpoint_blocked"
  | "workflow_pack_completed"
  | "communication_draft_generated"
  | "communication_draft_review_updated"
  | "automation_plan_generated"
  | "field_validated"
  | "requirement_reviewed"
  | "reviewed_snapshot_signed_off"
  | "release_bundle_created";

export type ArtifactType =
  | "case"
  | "document"
  | "checklist"
  | "workflow_run"
  | "workflow_pack_run"
  | "extraction_run"
  | "packet"
  | "submission_draft"
  | "automation_plan"
  | "automation_run"
  | "communication_draft"
  | "reviewed_snapshot"
  | "release_bundle";

export type LineageRelationshipType =
  | "case_context"
  | "document_source"
  | "checklist_reference"
  | "workflow_reference"
  | "workflow_pack_reference"
  | "extraction_source"
  | "packet_source"
  | "snapshot_source"
  | "draft_source"
  | "plan_source"
  | "run_source"
  | "release_bundle_source";

export interface AuditActorMetadata {
  actor_type: AuditActorType;
  actor_id: string;
  display_name: string;
  metadata: Record<string, unknown>;
}

export interface AuditableEntityReference {
  entity_type: string;
  entity_id: string;
  case_id: string;
  display_label: string;
  source_path: string;
}

export interface FieldChangeRecord {
  field_path: string;
  old_value: unknown;
  new_value: unknown;
}

export interface ChangeSummary {
  message: string;
  field_changes: FieldChangeRecord[];
}

export interface SourceArtifactReference {
  artifact_type: ArtifactType;
  artifact_id: string;
  case_id: string;
  display_label: string;
  source_path: string;
}

export interface DerivedArtifactReference {
  artifact_type: ArtifactType;
  artifact_id: string;
  case_id: string;
  display_label: string;
}

export interface AuditEventRecord {
  event_id: AuditEventId;
  case_id: string;
  category: AuditEventCategory;
  event_type: AuditEventType;
  actor: AuditActorMetadata;
  entity: AuditableEntityReference;
  change_summary: ChangeSummary;
  decision_ids: DecisionLedgerEntryId[];
  related_entities: AuditableEntityReference[];
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface DecisionLedgerEntry {
  decision_id: DecisionLedgerEntryId;
  case_id: string;
  decision_type: DecisionType;
  actor: AuditActorMetadata;
  source_entity: AuditableEntityReference;
  outcome: string;
  reason: string;
  note: string;
  related_event_id: AuditEventId;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface LineageEdge {
  edge_id: LineageEdgeId;
  relationship_type: LineageRelationshipType;
  source: SourceArtifactReference;
  derived: DerivedArtifactReference;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface LineageRecord {
  record_id: LineageRecordId;
  case_id: string;
  artifact: DerivedArtifactReference;
  edges: LineageEdge[];
  notes: string[];
  created_at: string;
  updated_at: string;
}

export interface AuditFilterMetadata {
  categories: AuditEventCategory[];
  event_types: AuditEventType[];
  actor_types: AuditActorType[];
}

export interface AuditErrorInfo {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface AuditOperationResult {
  success: boolean;
  message: string;
  error: AuditErrorInfo | null;
}

export interface AuditTimelineResponse {
  case_id: string;
  events: AuditEventRecord[];
  filters: AuditFilterMetadata;
}

export interface DecisionLedgerResponse {
  case_id: string;
  decisions: DecisionLedgerEntry[];
}

export interface LineageResponse {
  case_id: string;
  records: LineageRecord[];
}

export interface ArtifactLineageResponse {
  artifact_type: ArtifactType;
  artifact_id: string;
  record: LineageRecord | null;
}