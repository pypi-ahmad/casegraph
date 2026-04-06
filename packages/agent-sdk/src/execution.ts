/**
 * Shared automation execution contracts — TypeScript mirror.
 *
 * Typed models for approval-gated automation runs, step execution journals,
 * artifact capture, and session boundaries.
 */

import type {
  SubmissionDraftId,
  AutomationPlanId,
  ExecutionGuardrailMetadata,
  NormalizedOperationResult,
  SubmissionDraftSummary,
  AutomationExecutionMode,
  AutomationFallbackRoutingHint,
} from "./submissions";
import type { DownstreamSourceMode } from "./reviewed-handoff";

// ---------------------------------------------------------------------------
// Identity aliases
// ---------------------------------------------------------------------------

export type AutomationRunId = string;
export type ExecutedStepId = string;
export type RunArtifactId = string;
export type RunEventId = string;
export type AutomationCheckpointId = string;
export type AutomationOverrideId = string;
export type PendingStepDecision = string;
export type OperatorDecisionNote = string;
export type SkipReason = string;
export type BlockReason = string;

// ---------------------------------------------------------------------------
// Status literals
// ---------------------------------------------------------------------------

export type AutomationRunStatus =
  | "created"
  | "awaiting_operator_review"
  | "running"
  | "completed_partial"
  | "completed"
  | "blocked"
  | "failed";

export type ExecutedStepStatus =
  | "pending"
  | "running"
  | "awaiting_operator_review"
  | "completed"
  | "skipped"
  | "blocked"
  | "failed";

export type RunArtifactType =
  | "text_log"
  | "page_metadata"
  | "screenshot"
  | "step_trace";

export type RunEventType =
  | "run_started"
  | "session_initialized"
  | "step_started"
  | "step_completed"
  | "step_skipped"
  | "step_blocked"
  | "step_failed"
  | "artifact_captured"
  | "checkpoint_created"
  | "checkpoint_approved"
  | "checkpoint_skipped"
  | "checkpoint_blocked"
  | "run_paused"
  | "run_resumed"
  | "run_completed"
  | "run_failed"
  | "run_blocked";

export type AutomationCheckpointStatus =
  | "pending_operator_review"
  | "approved"
  | "skipped"
  | "blocked"
  | "resolved";

export type OperatorDecisionType =
  | "approve_continue"
  | "skip_step"
  | "block_run";

// ---------------------------------------------------------------------------
// Execution request
// ---------------------------------------------------------------------------

export interface AutomationExecutionRequest {
  draft_id: string;
  plan_id: string;
  operator_id?: string;
  dry_run?: boolean;
  notes?: string[];
}

// ---------------------------------------------------------------------------
// Session metadata
// ---------------------------------------------------------------------------

export interface AutomationSessionMetadata {
  session_id: string | null;
  backend_id: string | null;
  mcp_server_url: string | null;
  browser_type: string | null;
  headless: boolean;
  status: "not_started" | "active" | "closed" | "error";
  notes: string[];
}

export interface AutomationCheckpointEventMetadata {
  checkpoint_id: AutomationCheckpointId;
  plan_step_id: string;
  executed_step_id: ExecutedStepId | null;
  execution_mode: AutomationExecutionMode;
  decision_type: OperatorDecisionType | null;
  notes: string[];
}

export interface PausedAutomationRunMetadata {
  checkpoint_id: AutomationCheckpointId;
  plan_step_id: string;
  executed_step_id: ExecutedStepId | null;
  step_index: number;
  step_title: string;
  execution_mode: AutomationExecutionMode;
  checkpoint_status: AutomationCheckpointStatus;
  paused_at: string;
  session_resume_supported: boolean;
  notes: string[];
}

// ---------------------------------------------------------------------------
// Executed step
// ---------------------------------------------------------------------------

export interface StepExecutionOutcome {
  status: ExecutedStepStatus;
  output: Record<string, unknown> | null;
  error_code: string | null;
  error_message: string | null;
  duration_ms: number | null;
  notes: string[];
}

export interface AutomationOperatorOverrideRecord {
  override_id: AutomationOverrideId;
  checkpoint_id: AutomationCheckpointId;
  run_id: AutomationRunId;
  operator_id: string;
  decision_type: OperatorDecisionType;
  decision_note: OperatorDecisionNote;
  skip_reason: SkipReason;
  block_reason: BlockReason;
  created_at: string;
}

export interface AutomationCheckpointRecord {
  checkpoint_id: AutomationCheckpointId;
  run_id: AutomationRunId;
  plan_step_id: string;
  executed_step_id: ExecutedStepId | null;
  step_index: number;
  step_type: string;
  step_title: string;
  status: AutomationCheckpointStatus;
  decision_type: OperatorDecisionType | null;
  operator_id: string;
  decision_note: OperatorDecisionNote;
  skip_reason: SkipReason;
  block_reason: BlockReason;
  execution_mode: AutomationExecutionMode;
  checkpoint_reason: string;
  fallback_hint: AutomationFallbackRoutingHint | null;
  created_at: string;
  decided_at: string;
  resolved_at: string;
  notes: string[];
}

export interface ExecutedStepRecord {
  executed_step_id: ExecutedStepId;
  run_id: AutomationRunId;
  plan_step_id: string;
  step_index: number;
  step_type: string;
  title: string;
  description: string;
  target_reference: string;
  tool_id: string | null;
  backend_id: string | null;
  status: ExecutedStepStatus;
  outcome: StepExecutionOutcome;
  started_at: string;
  completed_at: string;
  notes: string[];
}

// ---------------------------------------------------------------------------
// Artifact
// ---------------------------------------------------------------------------

export interface RunArtifactRecord {
  artifact_id: RunArtifactId;
  run_id: AutomationRunId;
  executed_step_id: ExecutedStepId | null;
  artifact_type: RunArtifactType;
  display_name: string;
  content_text: string | null;
  content_url: string | null;
  metadata: Record<string, unknown>;
  captured_at: string;
  notes: string[];
}

// ---------------------------------------------------------------------------
// Blocked action
// ---------------------------------------------------------------------------

export interface BlockedActionRecord {
  step_type: string;
  step_title: string;
  reason: string;
  guardrail_code: string;
  plan_step_id: string | null;
}

// ---------------------------------------------------------------------------
// Run summary
// ---------------------------------------------------------------------------

export interface AutomationRunSummary {
  total_steps: number;
  completed_steps: number;
  skipped_steps: number;
  blocked_steps: number;
  failed_steps: number;
  artifact_count: number;
  event_count: number;
  checkpoint_count: number;
  pending_checkpoint_count: number;
  notes: string[];
}

// ---------------------------------------------------------------------------
// Run event (journal)
// ---------------------------------------------------------------------------

export interface RunEventRecord {
  event_id: RunEventId;
  run_id: AutomationRunId;
  event_type: RunEventType;
  executed_step_id: ExecutedStepId | null;
  artifact_id: RunArtifactId | null;
  message: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Run record
// ---------------------------------------------------------------------------

export interface AutomationRunRecord {
  run_id: AutomationRunId;
  draft_id: SubmissionDraftId;
  plan_id: AutomationPlanId;
  case_id: string;
  source_mode: DownstreamSourceMode;
  source_reviewed_snapshot_id: string;
  status: AutomationRunStatus;
  operator_id: string;
  dry_run: boolean;
  guardrails: ExecutionGuardrailMetadata;
  session: AutomationSessionMetadata;
  paused_run: PausedAutomationRunMetadata | null;
  summary: AutomationRunSummary;
  created_at: string;
  started_at: string;
  completed_at: string;
  notes: string[];
}

// ---------------------------------------------------------------------------
// API responses
// ---------------------------------------------------------------------------

export interface AutomationRunResponse {
  result: NormalizedOperationResult;
  run: AutomationRunRecord;
  draft: SubmissionDraftSummary | null;
}

export interface ApproveCheckpointRequest {
  operator_id: string;
  decision_note?: OperatorDecisionNote;
}

export interface SkipCheckpointRequest {
  operator_id: string;
  decision_note?: OperatorDecisionNote;
  skip_reason?: SkipReason;
}

export interface BlockCheckpointRequest {
  operator_id: string;
  decision_note?: OperatorDecisionNote;
  block_reason?: BlockReason;
}

export interface AutomationResumeRequest {
  operator_id?: string;
  note?: string;
}

export interface AutomationRunDetailResponse {
  run: AutomationRunRecord;
  steps: ExecutedStepRecord[];
  artifacts: RunArtifactRecord[];
  events: RunEventRecord[];
  blocked_actions: BlockedActionRecord[];
  checkpoints: AutomationCheckpointRecord[];
  overrides: AutomationOperatorOverrideRecord[];
}

export interface AutomationRunListResponse {
  runs: AutomationRunRecord[];
}

export interface AutomationRunCheckpointsResponse {
  checkpoints: AutomationCheckpointRecord[];
  overrides: AutomationOperatorOverrideRecord[];
}

export interface AutomationCheckpointResponse {
  result: NormalizedOperationResult;
  run: AutomationRunRecord;
  checkpoint: AutomationCheckpointRecord;
  override: AutomationOperatorOverrideRecord | null;
}

export interface AutomationRunStepsResponse {
  steps: ExecutedStepRecord[];
}

export interface AutomationRunArtifactsResponse {
  artifacts: RunArtifactRecord[];
}

export interface AutomationRunEventsResponse {
  events: RunEventRecord[];
}
