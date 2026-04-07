"""Shared automation execution contracts.

Typed models for approval-gated automation runs, step execution journals,
artifact capture, and session boundaries. Used by the API backend and
consumed by the frontend via the TypeScript mirror.

This layer sits between the existing submission draft / automation plan
foundation and the actual Playwright MCP execution boundary.
No fake portal data, screenshots, or successful submissions are modelled.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.submissions import (
    AutomationExecutionMode,
    AutomationFallbackRoutingHint,
    AutomationPlanId,
    ExecutionGuardrailMetadata,
    NormalizedOperationResult,
    SubmissionDraftId,
    SubmissionDraftSummary,
)
from casegraph_agent_sdk.reviewed_handoff import DownstreamSourceMode

# ---------------------------------------------------------------------------
# Identity aliases
# ---------------------------------------------------------------------------

AutomationRunId = str
ExecutedStepId = str
RunArtifactId = str
RunEventId = str
AutomationCheckpointId = str
AutomationOverrideId = str
PendingStepDecision = str
OperatorDecisionNote = str
SkipReason = str
BlockReason = str

# ---------------------------------------------------------------------------
# Status literals
# ---------------------------------------------------------------------------

AutomationRunStatus = Literal[
    "created",
    "awaiting_operator_review",
    "running",
    "completed_partial",
    "completed",
    "blocked",
    "failed",
]

ExecutedStepStatus = Literal[
    "pending",
    "running",
    "awaiting_operator_review",
    "completed",
    "skipped",
    "blocked",
    "failed",
]

RunArtifactType = Literal[
    "text_log",
    "page_metadata",
    "screenshot",
    "step_trace",
]

RunEventType = Literal[
    "run_started",
    "session_initialized",
    "step_started",
    "step_completed",
    "step_skipped",
    "step_blocked",
    "step_failed",
    "artifact_captured",
    "checkpoint_created",
    "checkpoint_approved",
    "checkpoint_skipped",
    "checkpoint_blocked",
    "run_paused",
    "run_resumed",
    "run_completed",
    "run_failed",
    "run_blocked",
]

AutomationCheckpointStatus = Literal[
    "pending_operator_review",
    "approved",
    "skipped",
    "blocked",
    "resolved",
]

OperatorDecisionType = Literal[
    "approve_continue",
    "skip_step",
    "block_run",
]

# ---------------------------------------------------------------------------
# Execution request
# ---------------------------------------------------------------------------


class AutomationExecutionRequest(BaseModel):
    """Request to begin executing an approved automation plan."""

    draft_id: SubmissionDraftId
    plan_id: AutomationPlanId
    operator_id: str = ""
    dry_run: bool = False
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Session metadata
# ---------------------------------------------------------------------------


class AutomationSessionMetadata(BaseModel):
    """Tracks the browser / MCP session boundary during a run."""

    session_id: str | None = None
    backend_id: str | None = None
    mcp_server_url: str | None = None
    browser_type: str | None = None
    headless: bool = True
    status: Literal["not_started", "active", "closed", "error"] = "not_started"
    notes: list[str] = Field(default_factory=list)


class AutomationCheckpointEventMetadata(BaseModel):
    checkpoint_id: AutomationCheckpointId
    plan_step_id: str
    executed_step_id: ExecutedStepId | None = None
    execution_mode: AutomationExecutionMode = "blocked"
    decision_type: OperatorDecisionType | None = None
    notes: list[str] = Field(default_factory=list)


class PausedAutomationRunMetadata(BaseModel):
    checkpoint_id: AutomationCheckpointId
    plan_step_id: str
    executed_step_id: ExecutedStepId | None = None
    step_index: int = 0
    step_title: str = ""
    execution_mode: AutomationExecutionMode = "blocked"
    checkpoint_status: AutomationCheckpointStatus = "pending_operator_review"
    paused_at: str = ""
    session_resume_supported: bool = False
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Executed step record
# ---------------------------------------------------------------------------


class StepExecutionOutcome(BaseModel):
    """The result of attempting to execute a single plan step."""

    status: ExecutedStepStatus = "pending"
    output: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    duration_ms: float | None = None
    notes: list[str] = Field(default_factory=list)


class AutomationOperatorOverrideRecord(BaseModel):
    override_id: AutomationOverrideId
    checkpoint_id: AutomationCheckpointId
    run_id: AutomationRunId
    operator_id: str = ""
    decision_type: OperatorDecisionType
    decision_note: OperatorDecisionNote = ""
    skip_reason: SkipReason = ""
    block_reason: BlockReason = ""
    created_at: str = ""


class AutomationCheckpointRecord(BaseModel):
    checkpoint_id: AutomationCheckpointId
    run_id: AutomationRunId
    plan_step_id: str
    executed_step_id: ExecutedStepId | None = None
    step_index: int = 0
    step_type: str
    step_title: str
    status: AutomationCheckpointStatus = "pending_operator_review"
    decision_type: OperatorDecisionType | None = None
    operator_id: str = ""
    decision_note: OperatorDecisionNote = ""
    skip_reason: SkipReason = ""
    block_reason: BlockReason = ""
    execution_mode: AutomationExecutionMode = "blocked"
    checkpoint_reason: str = ""
    fallback_hint: AutomationFallbackRoutingHint | None = None
    created_at: str = ""
    decided_at: str = ""
    resolved_at: str = ""
    notes: list[str] = Field(default_factory=list)


class ExecutedStepRecord(BaseModel):
    """Persisted record of a step that was attempted during a run."""

    executed_step_id: ExecutedStepId
    run_id: AutomationRunId
    plan_step_id: str
    step_index: int = 0
    step_type: str
    title: str
    description: str = ""
    target_reference: str = ""
    tool_id: str | None = None
    backend_id: str | None = None
    status: ExecutedStepStatus = "pending"
    outcome: StepExecutionOutcome = Field(default_factory=StepExecutionOutcome)
    started_at: str = ""
    completed_at: str = ""
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Artifact record
# ---------------------------------------------------------------------------


class RunArtifactRecord(BaseModel):
    """Metadata about an artifact captured during a run."""

    artifact_id: RunArtifactId
    run_id: AutomationRunId
    executed_step_id: ExecutedStepId | None = None
    artifact_type: RunArtifactType
    display_name: str = ""
    content_text: str | None = None
    content_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    captured_at: str = ""
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Blocked action record
# ---------------------------------------------------------------------------


class BlockedActionRecord(BaseModel):
    """Record of an action that was blocked by guardrails."""

    step_type: str
    step_title: str
    reason: str
    guardrail_code: str = ""
    plan_step_id: str | None = None


# ---------------------------------------------------------------------------
# Run summary
# ---------------------------------------------------------------------------


class AutomationRunSummary(BaseModel):
    """Summary statistics for a completed or in-progress run."""

    total_steps: int = 0
    completed_steps: int = 0
    skipped_steps: int = 0
    blocked_steps: int = 0
    failed_steps: int = 0
    artifact_count: int = 0
    event_count: int = 0
    checkpoint_count: int = 0
    pending_checkpoint_count: int = 0
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Run event (journal entry)
# ---------------------------------------------------------------------------


class RunEventRecord(BaseModel):
    """A single journal entry in the execution timeline."""

    event_id: RunEventId
    run_id: AutomationRunId
    event_type: RunEventType
    executed_step_id: ExecutedStepId | None = None
    artifact_id: RunArtifactId | None = None
    message: str = ""
    timestamp: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Automation run record
# ---------------------------------------------------------------------------


class AutomationRunRecord(BaseModel):
    """Full automation run record."""

    run_id: AutomationRunId
    draft_id: SubmissionDraftId
    plan_id: AutomationPlanId
    case_id: str
    source_mode: DownstreamSourceMode = "live_case_state"
    source_reviewed_snapshot_id: str = ""
    status: AutomationRunStatus = "created"
    operator_id: str = ""
    dry_run: bool = False
    guardrails: ExecutionGuardrailMetadata = Field(
        default_factory=ExecutionGuardrailMetadata
    )
    session: AutomationSessionMetadata = Field(
        default_factory=AutomationSessionMetadata
    )
    paused_run: PausedAutomationRunMetadata | None = None
    summary: AutomationRunSummary = Field(default_factory=AutomationRunSummary)
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API responses
# ---------------------------------------------------------------------------


class AutomationRunResponse(BaseModel):
    """Response after creating or fetching a run."""

    result: NormalizedOperationResult
    run: AutomationRunRecord
    draft: SubmissionDraftSummary | None = None


class ApproveCheckpointRequest(BaseModel):
    operator_id: str
    decision_note: OperatorDecisionNote = ""


class SkipCheckpointRequest(BaseModel):
    operator_id: str
    decision_note: OperatorDecisionNote = ""
    skip_reason: SkipReason = ""


class BlockCheckpointRequest(BaseModel):
    operator_id: str
    decision_note: OperatorDecisionNote = ""
    block_reason: BlockReason = ""


class AutomationResumeRequest(BaseModel):
    operator_id: str = ""
    note: str = ""


class AutomationRunDetailResponse(BaseModel):
    """Full run detail including steps and events."""

    run: AutomationRunRecord
    steps: list[ExecutedStepRecord] = Field(default_factory=list)
    artifacts: list[RunArtifactRecord] = Field(default_factory=list)
    events: list[RunEventRecord] = Field(default_factory=list)
    blocked_actions: list[BlockedActionRecord] = Field(default_factory=list)
    checkpoints: list[AutomationCheckpointRecord] = Field(default_factory=list)
    overrides: list[AutomationOperatorOverrideRecord] = Field(default_factory=list)


class AutomationRunListResponse(BaseModel):
    runs: list[AutomationRunRecord] = Field(default_factory=list)


class AutomationRunCheckpointsResponse(BaseModel):
    checkpoints: list[AutomationCheckpointRecord] = Field(default_factory=list)
    overrides: list[AutomationOperatorOverrideRecord] = Field(default_factory=list)


class AutomationCheckpointResponse(BaseModel):
    result: NormalizedOperationResult
    run: AutomationRunRecord
    checkpoint: AutomationCheckpointRecord
    override: AutomationOperatorOverrideRecord | None = None


class AutomationRunStepsResponse(BaseModel):
    steps: list[ExecutedStepRecord] = Field(default_factory=list)


class AutomationRunArtifactsResponse(BaseModel):
    artifacts: list[RunArtifactRecord] = Field(default_factory=list)


class AutomationRunEventsResponse(BaseModel):
    events: list[RunEventRecord] = Field(default_factory=list)
