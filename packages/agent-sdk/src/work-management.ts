import type { UserRole } from "./auth";
import type { CaseStatus, NormalizedOperationError } from "./cases";
import type { CaseTypeTemplateId, DomainPackId } from "./domains";
import type { CaseStage } from "./operator-review";
import type { ReadinessStatus } from "./readiness";

export type AssignmentRecordId = string;
export type SLAPolicyId = string;

export type AssignmentStatus =
  | "unassigned"
  | "assigned"
  | "reassigned"
  | "released_placeholder";

export type AssignmentReasonPlaceholder =
  | "manual_assignment"
  | "manual_reassignment"
  | "manual_clear"
  | "workload_balancing_placeholder";

export type WorkloadSegment =
  | "assigned"
  | "unassigned"
  | "attention_needed"
  | "due_soon"
  | "overdue"
  | "escalation_ready";

export type SLAState =
  | "no_deadline"
  | "on_track"
  | "due_soon"
  | "overdue";

export type EscalationReadinessState =
  | "not_applicable"
  | "attention_needed"
  | "escalation_ready";

export type EscalationReason =
  | "overdue_case"
  | "unresolved_review_items"
  | "release_blocked"
  | "submission_planning_blocked"
  | "open_actions_lingering"
  | "assignment_missing";

export interface AssigneeReference {
  user_id: string;
  display_name: string;
  email: string;
  role: UserRole;
}

export interface AssignmentHistoryEntry {
  record_id: AssignmentRecordId;
  case_id: string;
  status: AssignmentStatus;
  assignee: AssigneeReference | null;
  reason: AssignmentReasonPlaceholder;
  note: string;
  changed_by_id: string;
  changed_by_display_name: string;
  created_at: string;
}

export interface OwnershipSummary {
  case_id: string;
  assignment_status: AssignmentStatus;
  current_assignee: AssigneeReference | null;
  assigned_at: string;
  changed_by_id: string;
  changed_by_display_name: string;
  note: string;
  reason: AssignmentReasonPlaceholder | null;
}

export interface DueDateMetadata {
  due_at: string;
  due_soon_window_hours: number;
  note: string;
  updated_by_id: string;
  updated_by_display_name: string;
  updated_at: string;
}

export interface SLATargetMetadata {
  policy_id: SLAPolicyId;
  due_date: DueDateMetadata | null;
}

export interface EscalationAssessment {
  state: EscalationReadinessState;
  reasons: EscalationReason[];
  note: string;
}

export interface WorkStatusSummary {
  case_id: string;
  title: string;
  case_status: CaseStatus;
  current_stage: CaseStage;
  domain_pack_id: DomainPackId | null;
  case_type_id: CaseTypeTemplateId | null;
  readiness_status: ReadinessStatus | null;
  ownership: OwnershipSummary;
  assignment_expected: boolean;
  sla_target: SLATargetMetadata;
  sla_state: SLAState;
  workload_segment: WorkloadSegment;
  escalation: EscalationAssessment;
  open_action_count: number;
  unresolved_review_item_count: number;
  release_blocked: boolean;
  submission_planning_blocked: boolean;
  updated_at: string;
}

export interface WorkloadSummary {
  total_cases: number;
  assigned_cases: number;
  unassigned_cases: number;
  due_soon_cases: number;
  overdue_cases: number;
  attention_needed_cases: number;
  escalation_ready_cases: number;
}

export interface WorkManagementOperationResult {
  success: boolean;
  message: string;
  error: NormalizedOperationError | null;
}

export interface WorkQueueFilters {
  assignee_id?: string | null;
  assignment_status?: AssignmentStatus | null;
  sla_state?: SLAState | null;
  escalation_state?: EscalationReadinessState | null;
  domain_pack_id?: DomainPackId | null;
  case_type_id?: CaseTypeTemplateId | null;
  limit?: number;
}

export interface UpdateCaseAssignmentRequest {
  assignee_id?: string | null;
  clear_assignment?: boolean;
  reason?: AssignmentReasonPlaceholder | null;
  note?: string | null;
  actor_id?: string;
  actor_display_name?: string;
}

export interface UpdateCaseSLARequest {
  due_at?: string | null;
  clear_due_date?: boolean;
  policy_id?: SLAPolicyId | null;
  due_soon_window_hours?: number | null;
  note?: string | null;
  actor_id?: string;
  actor_display_name?: string;
}

export interface WorkQueueResponse {
  filters: WorkQueueFilters;
  items: WorkStatusSummary[];
}

export interface WorkSummaryResponse {
  filters: WorkQueueFilters;
  summary: WorkloadSummary;
  available_assignees: AssigneeReference[];
}

export interface CaseAssignmentResponse {
  result: WorkManagementOperationResult;
  ownership: OwnershipSummary;
  history_entry: AssignmentHistoryEntry | null;
}

export interface AssignmentHistoryResponse {
  case_id: string;
  history: AssignmentHistoryEntry[];
}

export interface CaseSLAResponse {
  result: WorkManagementOperationResult;
  sla_target: SLATargetMetadata;
  sla_state: SLAState;
}

export interface CaseWorkStatusResponse {
  work_status: WorkStatusSummary;
  available_assignees: AssigneeReference[];
}