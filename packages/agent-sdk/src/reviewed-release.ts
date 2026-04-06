import type {
  DownstreamSourceMode,
  ReviewedSnapshotId,
  SignOffRecordId,
  SignOffStatus,
} from "./reviewed-handoff";
import type { CaseTargetPackSelection } from "./target-packs";

export type ReleaseBundleId = string;
export type ReleaseArtifactId = string;

export type ReleaseBundleStatus =
  | "created"
  | "incomplete"
  | "superseded_placeholder"
  | "archived_placeholder";

export type ReleaseArtifactType =
  | "reviewed_packet"
  | "reviewed_submission_draft"
  | "reviewed_communication_draft"
  | "reviewed_automation_plan";

export type ReleaseArtifactStatus =
  | "generated"
  | "skipped_missing_data"
  | "blocked"
  | "failed";

export type ReleaseBlockingReasonCode =
  | "no_reviewed_snapshot"
  | "missing_signoff"
  | "unresolved_review_items"
  | "required_requirement_reviews_incomplete";

export type ReleaseIssueSeverity = "info" | "warning" | "error";

export interface ReleaseBundleSourceMetadata {
  case_id: string;
  snapshot_id: ReviewedSnapshotId;
  signoff_id: SignOffRecordId;
  signoff_status: SignOffStatus;
  signed_off_by: string;
  signed_off_at: string;
  snapshot_created_at: string;
  snapshot_included_fields: number;
  snapshot_corrected_fields: number;
  snapshot_reviewed_requirements: number;
  snapshot_unresolved_item_count: number;
  target_pack_selection: CaseTargetPackSelection | null;
}

export interface ReleaseArtifactEntry {
  artifact_ref_id: ReleaseArtifactId;
  artifact_type: ReleaseArtifactType;
  downstream_artifact_id: string;
  status: ReleaseArtifactStatus;
  display_label: string;
  source_mode: DownstreamSourceMode;
  source_snapshot_id: ReviewedSnapshotId;
  release_bundle_id: ReleaseBundleId;
  notes: string[];
  created_at: string;
}

export interface ReleaseBundleSummary {
  total_artifacts: number;
  generated_artifacts: number;
  skipped_artifacts: number;
  blocked_artifacts: number;
  failed_artifacts: number;
}

export interface ReleaseBlockingReason {
  code: ReleaseBlockingReasonCode;
  message: string;
  blocking: boolean;
}

export interface ReleaseEligibilitySummary {
  case_id: string;
  snapshot_id: string;
  signoff_status: SignOffStatus;
  eligible: boolean;
  reasons: ReleaseBlockingReason[];
}

export interface ReleaseIssue {
  severity: ReleaseIssueSeverity;
  code: string;
  message: string;
  related_artifact_type: ReleaseArtifactType | null;
  related_artifact_id: string | null;
}

export interface ReleaseOperationResult {
  success: boolean;
  message: string;
  issues: ReleaseIssue[];
}

export interface ReleaseBundleRecord {
  release_id: ReleaseBundleId;
  case_id: string;
  status: ReleaseBundleStatus;
  source: ReleaseBundleSourceMetadata;
  summary: ReleaseBundleSummary;
  artifacts: ReleaseArtifactEntry[];
  note: string;
  created_by: string;
  created_at: string;
}

export interface CreateReleaseBundleRequest {
  snapshot_id?: ReviewedSnapshotId;
  note?: string;
  operator_id?: string;
  operator_display_name?: string;
  generate_packet?: boolean;
  generate_submission_draft?: boolean;
  generate_communication_draft?: boolean;
  include_automation_plan_metadata?: boolean;
}

export interface ReleaseBundleCreateResponse {
  result: ReleaseOperationResult;
  release: ReleaseBundleRecord;
}

export interface ReleaseBundleResponse {
  release: ReleaseBundleRecord;
}

export interface ReleaseBundleListResponse {
  case_id: string;
  releases: ReleaseBundleRecord[];
}

export interface ReleaseArtifactListResponse {
  release_id: ReleaseBundleId;
  artifacts: ReleaseArtifactEntry[];
}

export interface ReleaseEligibilityResponse {
  eligibility: ReleaseEligibilitySummary;
}
