"""Automation execution service — approval-gated, checkpoint-aware runs.

Extends the existing execution foundation with explicit operator review
checkpoints, auditable override decisions, resumable continuation, and
metadata-only computer-use fallback routing.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from sqlmodel import Session, desc, select

from casegraph_agent_sdk.audit import ChangeSummary, FieldChangeRecord
from casegraph_agent_sdk.automation import AutomationCapabilitiesResponse
from casegraph_agent_sdk.execution import (
    ApproveCheckpointRequest,
    AutomationCheckpointEventMetadata,
    AutomationCheckpointRecord,
    AutomationCheckpointResponse,
    AutomationCheckpointStatus,
    AutomationExecutionRequest,
    AutomationOperatorOverrideRecord,
    AutomationResumeRequest,
    AutomationRunArtifactsResponse,
    AutomationRunCheckpointsResponse,
    AutomationRunDetailResponse,
    AutomationRunEventsResponse,
    AutomationRunListResponse,
    AutomationRunRecord,
    AutomationRunResponse,
    AutomationRunStepsResponse,
    AutomationRunSummary,
    AutomationSessionMetadata,
    BlockCheckpointRequest,
    BlockedActionRecord,
    ExecutedStepRecord,
    PausedAutomationRunMetadata,
    RunArtifactRecord,
    RunEventRecord,
    SkipCheckpointRequest,
    StepExecutionOutcome,
)
from casegraph_agent_sdk.submissions import (
    ApprovalRequirementMetadata,
    AutomationFallbackRoutingHint,
    AutomationPlan,
    AutomationPlanStep,
    ExecutionGuardrailMetadata,
    NormalizedOperationResult,
    NormalizedResultIssue,
)

from app.execution.checkpoints import determine_step_checkpoint_policy
from app.execution.errors import AutomationExecutionError
from app.execution.gating import (
    ApprovalGateResult,
    check_execution_approval,
    classify_blocked_steps,
    is_step_executable,
)
from app.execution.models import (
    AutomationCheckpointModel,
    AutomationCheckpointOverrideModel,
    AutomationRunModel,
    ExecutedStepModel,
    RunArtifactModel,
    RunEventModel,
)
from app.audit.service import AuditTrailService, audit_actor, derived_ref, entity_ref, source_ref
from app.persistence.database import isoformat_utc, utcnow
from app.submissions.models import (
    AutomationPlanModel,
    AutomationPlanStepModel,
    SubmissionDraftModel,
)

logger = logging.getLogger(__name__)

_FINAL_STEP_STATUSES = {"completed", "skipped", "blocked", "failed"}


async def _empty_capabilities() -> AutomationCapabilitiesResponse:
    return AutomationCapabilitiesResponse()


class AutomationExecutionService:
    """Orchestrates approval-gated automation runs with operator checkpoints."""

    def __init__(
        self,
        session: Session,
        *,
        playwright_mcp_url: str = "http://localhost:3100",
        automation_capabilities_loader: Callable[[], Awaitable[AutomationCapabilitiesResponse]] | None = None,
    ) -> None:
        self._session = session
        self._mcp_url = playwright_mcp_url.rstrip("/")
        self._capabilities_loader = automation_capabilities_loader or _empty_capabilities

    async def execute(self, request: AutomationExecutionRequest) -> AutomationRunResponse:
        draft = self._require_draft(request.draft_id)
        plan = self._load_plan(request.plan_id, draft.draft_id)
        approval = self._to_approval(draft)

        gate = check_execution_approval(draft, plan, approval)
        if not gate.allowed:
            return self._blocked_response(draft, plan, gate)

        now = utcnow()
        run = self._create_run(draft, plan, request, gate.blocked_actions, now)
        audit = AuditTrailService(self._session)
        audit.append_event(
            case_id=draft.case_id,
            category="automation",
            event_type="automation_run_created",
            actor=audit_actor(
                "operator",
                actor_id=run.operator_id,
                display_name=run.operator_id,
            ) if run.operator_id else audit_actor("service", actor_id="execution.service", display_name="Automation Execution Service"),
            entity=entity_ref("automation_run", run.run_id, case_id=draft.case_id, display_label=plan.plan_id),
            change_summary=ChangeSummary(
                message="Automation run created from approved submission draft and automation plan.",
                field_changes=[
                    FieldChangeRecord(field_path="status", new_value=run.status),
                    FieldChangeRecord(field_path="dry_run", new_value=run.dry_run),
                ],
            ),
            metadata={"draft_id": draft.draft_id, "plan_id": plan.plan_id},
        )
        audit.record_lineage(
            case_id=draft.case_id,
            artifact=derived_ref("automation_run", run.run_id, case_id=draft.case_id, display_label=plan.plan_id),
            edges=[
                (
                    "case_context",
                    source_ref("case", draft.case_id, case_id=draft.case_id, display_label=draft.case_title, source_path="case"),
                    None,
                ),
                (
                    "draft_source",
                    source_ref("submission_draft", draft.draft_id, case_id=draft.case_id, display_label=draft.submission_target_id, source_path="submission_draft"),
                    None,
                ),
                (
                    "plan_source",
                    source_ref("automation_plan", plan.plan_id, case_id=draft.case_id, display_label=plan.plan_id, source_path="automation.plan"),
                    None,
                ),
                (
                    "packet_source",
                    source_ref("packet", draft.packet_id, case_id=draft.case_id, display_label=draft.case_title, source_path="packet"),
                    None,
                ),
                *(
                    [
                        (
                            "snapshot_source",
                            source_ref(
                                "reviewed_snapshot",
                                plan.source_reviewed_snapshot_id,
                                case_id=draft.case_id,
                                display_label=plan.source_reviewed_snapshot_id,
                                source_path="reviewed_snapshot",
                            ),
                            None,
                        )
                    ]
                    if plan.source_mode == "reviewed_snapshot" and plan.source_reviewed_snapshot_id
                    else []
                ),
            ],
            notes=["Automation run lineage is anchored to the submission draft and approved automation plan used to start the run."],
            metadata={"dry_run": run.dry_run, "source_mode": plan.source_mode},
        )
        capabilities = await self._capabilities_loader()
        self._activate_session(run, capabilities, note="Initial execution session boundary opened.")
        self._emit_event(run.run_id, "run_started", "Automation run started.", now)
        if self._session_meta(run).status == "active":
            self._emit_event(
                run.run_id,
                "session_initialized",
                f"Playwright MCP session boundary established ({self._mcp_url}).",
                now,
            )

        self._session.add(run)
        self._session.commit()

        resumed_run = await self._continue_run(run, plan, capabilities, start_step_index=1)
        return AutomationRunResponse(
            result=NormalizedOperationResult(
                success=True,
                message=self._run_result_message(resumed_run.status),
                issues=[],
            ),
            run=self._to_run_record(resumed_run),
            draft=None,
        )

    async def resume(self, run_id: str, request: AutomationResumeRequest) -> AutomationRunResponse:
        run = self._require_run(run_id)
        plan = self._load_plan_by_id(run.plan_id)
        if plan is None:
            raise AutomationExecutionError(
                f"Automation plan '{run.plan_id}' not found for run '{run_id}'.",
                status_code=404,
            )
        if run.status != "awaiting_operator_review" or run.paused_run_json is None:
            raise AutomationExecutionError(
                "Run is not currently paused for operator review.",
                status_code=400,
            )

        paused = PausedAutomationRunMetadata.model_validate(run.paused_run_json)
        checkpoint = self._require_checkpoint(run_id, paused.checkpoint_id)
        if checkpoint.status == "pending_operator_review":
            raise AutomationExecutionError(
                "Checkpoint still requires an operator decision before resume.",
                status_code=400,
            )
        if checkpoint.status == "blocked":
            raise AutomationExecutionError(
                "Blocked checkpoints cannot be resumed.",
                status_code=400,
            )

        resume_operator_id = request.operator_id.strip()
        capabilities = await self._capabilities_loader()
        self._activate_session(run, capabilities, note="Continuation opened a fresh session boundary.")
        run.status = "running"
        if resume_operator_id:
            run.operator_id = resume_operator_id
            run.notes_json.append(f"Resumed by operator: {resume_operator_id}")
        if request.note.strip():
            run.notes_json.append(f"Resume note: {request.note.strip()}")
        run.paused_run_json = None
        resumed_at = utcnow()
        resumed_message = "Automation run resumed after operator review."
        if resume_operator_id:
            resumed_message = f"Automation run resumed after operator review by {resume_operator_id}."
        self._emit_event(run.run_id, "run_resumed", resumed_message, resumed_at)

        step = self._require_plan_step(plan.plan_id, checkpoint.plan_step_id)
        step_record = self._require_step_model(run.run_id, checkpoint.plan_step_id)

        next_step_index = checkpoint.step_index + 1
        if checkpoint.status == "approved":
            await self._apply_approved_checkpoint(run, checkpoint, step, step_record, capabilities)
        elif checkpoint.status == "skipped":
            next_step_index = checkpoint.step_index + 1
        else:
            raise AutomationExecutionError(
                f"Checkpoint status '{checkpoint.status}' cannot be resumed.",
                status_code=400,
            )

        self._session.add(run)
        self._session.commit()

        updated_run = await self._continue_run(run, plan, capabilities, start_step_index=next_step_index)
        return AutomationRunResponse(
            result=NormalizedOperationResult(
                success=True,
                message=self._run_result_message(updated_run.status),
                issues=[],
            ),
            run=self._to_run_record(updated_run),
            draft=None,
        )

    def get_run(self, run_id: str) -> AutomationRunResponse:
        run = self._require_run(run_id)
        self._refresh_run_summary(run)
        return AutomationRunResponse(
            result=NormalizedOperationResult(success=True, message=""),
            run=self._to_run_record(run),
        )

    def list_runs_for_case(self, case_id: str) -> AutomationRunListResponse:
        rows = list(self._session.exec(
            select(AutomationRunModel)
            .where(AutomationRunModel.case_id == case_id)
            .order_by(desc(AutomationRunModel.created_at), desc(AutomationRunModel.run_id))
        ).all())
        runs: list[AutomationRunRecord] = []
        for row in rows:
            self._refresh_run_summary(row)
            runs.append(self._to_run_record(row))
        return AutomationRunListResponse(runs=runs)

    def get_run_detail(self, run_id: str) -> AutomationRunDetailResponse:
        run = self._require_run(run_id)
        self._refresh_run_summary(run)
        plan = self._load_plan_by_id(run.plan_id)
        blocked_actions = classify_blocked_steps(plan.steps) if plan else []
        return AutomationRunDetailResponse(
            run=self._to_run_record(run),
            steps=self._load_executed_steps(run_id),
            artifacts=self._load_artifacts(run_id),
            events=self._load_events(run_id),
            blocked_actions=blocked_actions,
            checkpoints=self._load_checkpoints(run_id),
            overrides=self._load_overrides(run_id),
        )

    def get_run_steps(self, run_id: str) -> AutomationRunStepsResponse:
        self._require_run(run_id)
        return AutomationRunStepsResponse(steps=self._load_executed_steps(run_id))

    def get_run_artifacts(self, run_id: str) -> AutomationRunArtifactsResponse:
        self._require_run(run_id)
        return AutomationRunArtifactsResponse(artifacts=self._load_artifacts(run_id))

    def get_run_events(self, run_id: str) -> AutomationRunEventsResponse:
        self._require_run(run_id)
        return AutomationRunEventsResponse(events=self._load_events(run_id))

    def get_run_checkpoints(self, run_id: str) -> AutomationRunCheckpointsResponse:
        self._require_run(run_id)
        return AutomationRunCheckpointsResponse(
            checkpoints=self._load_checkpoints(run_id),
            overrides=self._load_overrides(run_id),
        )

    def approve_checkpoint(
        self,
        run_id: str,
        checkpoint_id: str,
        request: ApproveCheckpointRequest,
    ) -> AutomationCheckpointResponse:
        run = self._require_run(run_id)
        checkpoint = self._require_checkpoint(run_id, checkpoint_id)
        if checkpoint.status != "pending_operator_review":
            raise AutomationExecutionError("Checkpoint is not pending operator review.", status_code=400)

        previous_status = checkpoint.status
        override = self._record_override(
            run_id,
            checkpoint_id,
            operator_id=request.operator_id.strip(),
            decision_type="approve_continue",
            decision_note=request.decision_note.strip(),
        )
        now = utcnow()
        checkpoint.status = "approved"
        checkpoint.decision_type = "approve_continue"
        checkpoint.operator_id = request.operator_id.strip()
        checkpoint.decision_note = request.decision_note.strip()
        checkpoint.decided_at = now
        self._emit_event(
            run.run_id,
            "checkpoint_approved",
            f"Checkpoint approved for continuation: {checkpoint.step_title}",
            now,
            checkpoint.executed_step_id,
            metadata=self._checkpoint_event_metadata(checkpoint, "approve_continue").model_dump(mode="json"),
        )
        self._update_paused_run_checkpoint_status(run, checkpoint.status)
        self._refresh_run_summary(run)
        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=run.case_id,
            category="automation",
            event_type="automation_checkpoint_decided",
            actor=audit_actor("operator", actor_id=request.operator_id.strip(), display_name=request.operator_id.strip()),
            entity=entity_ref("automation_checkpoint", checkpoint.checkpoint_id, case_id=run.case_id, display_label=checkpoint.step_title),
            change_summary=ChangeSummary(
                message="Automation checkpoint approved for continuation.",
                field_changes=[
                    FieldChangeRecord(field_path="status", old_value=previous_status, new_value=checkpoint.status),
                ],
            ),
            metadata={"run_id": run.run_id, "plan_step_id": checkpoint.plan_step_id},
        )
        decision = audit.append_decision(
            case_id=run.case_id,
            decision_type="checkpoint_approved",
            actor=audit_actor("operator", actor_id=request.operator_id.strip(), display_name=request.operator_id.strip()),
            source_entity=entity_ref("automation_checkpoint", checkpoint.checkpoint_id, case_id=run.case_id, display_label=checkpoint.step_title),
            outcome=checkpoint.status,
            note=request.decision_note.strip(),
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)
        self._session.add(checkpoint)
        self._session.add(run)
        self._session.commit()
        return AutomationCheckpointResponse(
            result=NormalizedOperationResult(success=True, message="Checkpoint approved for continuation."),
            run=self._to_run_record(run),
            checkpoint=self._to_checkpoint_record(checkpoint),
            override=self._to_override_record(override),
        )

    def skip_checkpoint(
        self,
        run_id: str,
        checkpoint_id: str,
        request: SkipCheckpointRequest,
    ) -> AutomationCheckpointResponse:
        run = self._require_run(run_id)
        checkpoint = self._require_checkpoint(run_id, checkpoint_id)
        if checkpoint.status != "pending_operator_review":
            raise AutomationExecutionError("Checkpoint is not pending operator review.", status_code=400)

        step_model = self._require_step_model(run_id, checkpoint.plan_step_id)
        previous_status = checkpoint.status
        override = self._record_override(
            run_id,
            checkpoint_id,
            operator_id=request.operator_id.strip(),
            decision_type="skip_step",
            decision_note=request.decision_note.strip(),
            skip_reason=request.skip_reason.strip(),
        )
        now = utcnow()
        checkpoint.status = "skipped"
        checkpoint.decision_type = "skip_step"
        checkpoint.operator_id = request.operator_id.strip()
        checkpoint.decision_note = request.decision_note.strip()
        checkpoint.skip_reason = request.skip_reason.strip()
        checkpoint.decided_at = now
        checkpoint.resolved_at = now

        step_model.status = "skipped"
        step_model.outcome_json = StepExecutionOutcome(
            status="skipped",
            notes=[
                "Step skipped by explicit operator decision.",
                *([f"Skip reason: {request.skip_reason.strip()}"] if request.skip_reason.strip() else []),
                *([f"Operator note: {request.decision_note.strip()}"] if request.decision_note.strip() else []),
            ],
        ).model_dump(mode="json")
        step_model.completed_at = now

        self._emit_event(
            run.run_id,
            "checkpoint_skipped",
            f"Checkpoint skipped by operator: {checkpoint.step_title}",
            now,
            checkpoint.executed_step_id,
            metadata=self._checkpoint_event_metadata(checkpoint, "skip_step").model_dump(mode="json"),
        )
        self._emit_event(run.run_id, "step_skipped", f"Step skipped by operator: {checkpoint.step_title}", now, checkpoint.executed_step_id)
        self._update_paused_run_checkpoint_status(run, checkpoint.status)
        self._refresh_run_summary(run)
        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=run.case_id,
            category="automation",
            event_type="automation_checkpoint_decided",
            actor=audit_actor("operator", actor_id=request.operator_id.strip(), display_name=request.operator_id.strip()),
            entity=entity_ref("automation_checkpoint", checkpoint.checkpoint_id, case_id=run.case_id, display_label=checkpoint.step_title),
            change_summary=ChangeSummary(
                message="Automation checkpoint marked to skip the step.",
                field_changes=[
                    FieldChangeRecord(field_path="status", old_value=previous_status, new_value=checkpoint.status),
                ],
            ),
            metadata={"run_id": run.run_id, "plan_step_id": checkpoint.plan_step_id},
        )
        decision = audit.append_decision(
            case_id=run.case_id,
            decision_type="checkpoint_skipped",
            actor=audit_actor("operator", actor_id=request.operator_id.strip(), display_name=request.operator_id.strip()),
            source_entity=entity_ref("automation_checkpoint", checkpoint.checkpoint_id, case_id=run.case_id, display_label=checkpoint.step_title),
            outcome=checkpoint.status,
            reason=request.skip_reason.strip(),
            note=request.decision_note.strip(),
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)
        self._session.add(step_model)
        self._session.add(checkpoint)
        self._session.add(run)
        self._session.commit()
        return AutomationCheckpointResponse(
            result=NormalizedOperationResult(success=True, message="Checkpoint marked to skip the step."),
            run=self._to_run_record(run),
            checkpoint=self._to_checkpoint_record(checkpoint),
            override=self._to_override_record(override),
        )

    def block_checkpoint(
        self,
        run_id: str,
        checkpoint_id: str,
        request: BlockCheckpointRequest,
    ) -> AutomationCheckpointResponse:
        run = self._require_run(run_id)
        checkpoint = self._require_checkpoint(run_id, checkpoint_id)
        if checkpoint.status != "pending_operator_review":
            raise AutomationExecutionError("Checkpoint is not pending operator review.", status_code=400)

        step_model = self._require_step_model(run_id, checkpoint.plan_step_id)
        previous_status = checkpoint.status
        override = self._record_override(
            run_id,
            checkpoint_id,
            operator_id=request.operator_id.strip(),
            decision_type="block_run",
            decision_note=request.decision_note.strip(),
            block_reason=request.block_reason.strip(),
        )
        now = utcnow()
        checkpoint.status = "blocked"
        checkpoint.decision_type = "block_run"
        checkpoint.operator_id = request.operator_id.strip()
        checkpoint.decision_note = request.decision_note.strip()
        checkpoint.block_reason = request.block_reason.strip()
        checkpoint.decided_at = now
        checkpoint.resolved_at = now

        step_model.status = "blocked"
        step_model.outcome_json = StepExecutionOutcome(
            status="blocked",
            error_code="operator_blocked",
            error_message=request.block_reason.strip() or "Run blocked by operator decision.",
            notes=[
                "Step blocked by explicit operator decision.",
                *([f"Operator note: {request.decision_note.strip()}"] if request.decision_note.strip() else []),
            ],
        ).model_dump(mode="json")
        step_model.completed_at = now

        run.status = "blocked"
        run.completed_at = now
        run.paused_run_json = None
        self._close_session(run, note="Run blocked by operator decision.")

        self._emit_event(
            run.run_id,
            "checkpoint_blocked",
            f"Checkpoint blocked the run: {checkpoint.step_title}",
            now,
            checkpoint.executed_step_id,
            metadata=self._checkpoint_event_metadata(checkpoint, "block_run").model_dump(mode="json"),
        )
        self._emit_event(run.run_id, "step_blocked", f"Step blocked by operator: {checkpoint.step_title}", now, checkpoint.executed_step_id)
        self._emit_event(run.run_id, "run_blocked", "Automation run blocked by operator decision.", now)
        self._refresh_run_summary(run)
        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=run.case_id,
            category="automation",
            event_type="automation_checkpoint_decided",
            actor=audit_actor("operator", actor_id=request.operator_id.strip(), display_name=request.operator_id.strip()),
            entity=entity_ref("automation_checkpoint", checkpoint.checkpoint_id, case_id=run.case_id, display_label=checkpoint.step_title),
            change_summary=ChangeSummary(
                message="Automation checkpoint blocked the run.",
                field_changes=[
                    FieldChangeRecord(field_path="status", old_value=previous_status, new_value=checkpoint.status),
                ],
            ),
            metadata={"run_id": run.run_id, "plan_step_id": checkpoint.plan_step_id},
        )
        decision = audit.append_decision(
            case_id=run.case_id,
            decision_type="checkpoint_blocked",
            actor=audit_actor("operator", actor_id=request.operator_id.strip(), display_name=request.operator_id.strip()),
            source_entity=entity_ref("automation_checkpoint", checkpoint.checkpoint_id, case_id=run.case_id, display_label=checkpoint.step_title),
            outcome=checkpoint.status,
            reason=request.block_reason.strip(),
            note=request.decision_note.strip(),
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)
        self._session.add(step_model)
        self._session.add(checkpoint)
        self._session.add(run)
        self._session.commit()
        return AutomationCheckpointResponse(
            result=NormalizedOperationResult(success=True, message="Checkpoint blocked the run."),
            run=self._to_run_record(run),
            checkpoint=self._to_checkpoint_record(checkpoint),
            override=self._to_override_record(override),
        )

    async def _continue_run(
        self,
        run: AutomationRunModel,
        plan: AutomationPlan,
        capabilities: AutomationCapabilitiesResponse,
        *,
        start_step_index: int,
    ) -> AutomationRunModel:
        for step in sorted(plan.steps, key=lambda value: (value.step_index, value.step_id)):
            if step.step_index < start_step_index:
                continue

            existing_step = self._find_step_model(run.run_id, step.step_id)
            if existing_step is not None and existing_step.status in _FINAL_STEP_STATUSES:
                continue

            if existing_step is not None and existing_step.status == "awaiting_operator_review":
                checkpoint = self._require_pending_checkpoint_for_step(run.run_id, step.step_id)
                self._pause_run(run, checkpoint, checkpoint.checkpoint_reason)
                self._refresh_run_summary(run)
                self._session.add(run)
                self._session.commit()
                return run

            policy = determine_step_checkpoint_policy(step)
            if policy.required:
                step_model = self._create_pending_step(run, step)
                checkpoint = self._create_checkpoint(run, step, step_model, policy.reason)
                self._emit_event(
                    run.run_id,
                    "checkpoint_created",
                    f"Checkpoint created for step {step.step_index}: {step.title}",
                    utcnow(),
                    step_model.executed_step_id,
                    metadata=self._checkpoint_event_metadata(checkpoint).model_dump(mode="json"),
                )
                self._pause_run(run, checkpoint, policy.reason)
                self._refresh_run_summary(run)
                self._session.add(run)
                self._session.commit()
                return run

            await self._execute_step(run, step, capabilities, existing_step=existing_step)

        self._close_session(run, note="Run completed or reached a terminal state.")
        final_status = self._determine_final_status(run.plan_id, run.run_id)
        run.status = final_status
        run.completed_at = utcnow()
        run.paused_run_json = None
        self._emit_event(
            run.run_id,
            "run_completed" if final_status == "completed" else "run_failed" if final_status == "failed" else "run_blocked" if final_status == "blocked" else "run_completed",
            f"Automation run finished with status: {final_status}.",
            run.completed_at,
        )
        self._refresh_run_summary(run)
        self._session.add(run)
        self._session.commit()
        return run

    async def _apply_approved_checkpoint(
        self,
        run: AutomationRunModel,
        checkpoint: AutomationCheckpointModel,
        step: AutomationPlanStep,
        step_model: ExecutedStepModel,
        capabilities: AutomationCapabilitiesResponse,
    ) -> None:
        if step.execution_mode == "playwright_mcp" and is_step_executable(step):
            await self._execute_step(run, step, capabilities, existing_step=step_model)
        elif step.execution_mode == "manual_only" or step.step_type == "review_before_submit":
            now = utcnow()
            step_model.status = "completed"
            step_model.outcome_json = StepExecutionOutcome(
                status="completed",
                notes=[
                    "Operator approved continuation at a manual-only checkpoint.",
                    "No automated browser action was executed for this step.",
                ],
            ).model_dump(mode="json")
            step_model.completed_at = now
            self._emit_event(run.run_id, "step_completed", f"Manual checkpoint resolved: {step.title}", now, step_model.executed_step_id)
            self._session.add(step_model)
        else:
            now = utcnow()
            step_model.status = "skipped"
            step_model.outcome_json = StepExecutionOutcome(
                status="skipped",
                notes=[
                    "Operator approved continuation past a non-deterministic or manual-only step.",
                    "No computer-use execution was performed in this build.",
                ],
            ).model_dump(mode="json")
            step_model.completed_at = now
            self._emit_event(run.run_id, "step_skipped", f"Fallback step skipped after approval: {step.title}", now, step_model.executed_step_id)
            self._session.add(step_model)

        checkpoint.status = "resolved"
        checkpoint.resolved_at = utcnow()
        self._session.add(checkpoint)

    async def _execute_step(
        self,
        run: AutomationRunModel,
        step: AutomationPlanStep,
        capabilities: AutomationCapabilitiesResponse,
        *,
        existing_step: ExecutedStepModel | None = None,
    ) -> ExecutedStepModel:
        step_model = existing_step or ExecutedStepModel(
            executed_step_id=str(uuid4()),
            run_id=run.run_id,
            plan_step_id=step.step_id,
            step_index=step.step_index,
            step_type=step.step_type,
            title=step.title,
            description=step.description,
            target_reference=step.target_reference,
            tool_id=step.tool_id,
            backend_id=step.backend_id,
            status="pending",
            started_at=utcnow(),
            created_at=utcnow(),
        )
        if existing_step is None:
            self._emit_event(run.run_id, "step_started", f"Step {step.step_index}: {step.title}", step_model.started_at or utcnow(), step_model.executed_step_id)

        artifacts: list[RunArtifactModel] = []
        has_playwright = self._has_backend(capabilities, "playwright_mcp")

        if not is_step_executable(step):
            step_model.status = "blocked"
            step_model.outcome_json = StepExecutionOutcome(
                status="blocked",
                error_code="step_blocked",
                error_message=f"Step type '{step.step_type}' is not in the executable set.",
                notes=["This step is blocked by execution guardrails."],
            ).model_dump(mode="json")
            step_model.completed_at = utcnow()
            self._emit_event(run.run_id, "step_blocked", f"Step blocked: {step.title}", step_model.completed_at, step_model.executed_step_id)
        elif step.step_type == "open_target" and step.execution_mode == "playwright_mcp":
            if has_playwright:
                step_model, artifacts = await self._execute_navigate_step(run, step_model, step)
            else:
                step_model.status = "skipped"
                step_model.outcome_json = StepExecutionOutcome(
                    status="skipped",
                    notes=[
                        "No Playwright MCP backend is currently available.",
                        "Step skipped — deterministic browser execution was not possible.",
                    ],
                ).model_dump(mode="json")
                step_model.completed_at = utcnow()
                self._emit_event(run.run_id, "step_skipped", f"Step skipped: {step.title}", step_model.completed_at, step_model.executed_step_id)
        elif step.step_type == "navigate_section":
            step_model.status = "skipped"
            step_model.outcome_json = StepExecutionOutcome(
                status="skipped",
                notes=[
                    "Section navigation requires page selectors not defined in this build.",
                    "Computer-use fallback remains metadata-only in this build.",
                ],
            ).model_dump(mode="json")
            step_model.completed_at = utcnow()
            self._emit_event(run.run_id, "step_skipped", f"Step skipped: {step.title}", step_model.completed_at, step_model.executed_step_id)
        elif step.step_type == "review_before_submit":
            step_model.status = "completed"
            step_model.outcome_json = StepExecutionOutcome(
                status="completed",
                notes=["Review checkpoint reached. No execution action required."],
            ).model_dump(mode="json")
            step_model.completed_at = utcnow()
            self._emit_event(run.run_id, "step_completed", f"Step completed: {step.title}", step_model.completed_at, step_model.executed_step_id)
        else:
            step_model.status = "skipped"
            step_model.outcome_json = StepExecutionOutcome(
                status="skipped",
                notes=[f"Step type '{step.step_type}' has no execution handler in this build."],
            ).model_dump(mode="json")
            step_model.completed_at = utcnow()
            self._emit_event(run.run_id, "step_skipped", f"Step skipped: {step.title}", step_model.completed_at, step_model.executed_step_id)

        self._session.add(step_model)
        for artifact in artifacts:
            self._session.add(artifact)
        self._session.flush()
        return step_model

    async def _execute_navigate_step(
        self,
        run: AutomationRunModel,
        step_model: ExecutedStepModel,
        step: AutomationPlanStep,
    ) -> tuple[ExecutedStepModel, list[RunArtifactModel]]:
        artifacts: list[RunArtifactModel] = []
        target_url = step.target_reference or ""
        start_ms = time.monotonic()

        if not target_url.startswith(("http://", "https://")):
            step_model.status = "skipped"
            step_model.outcome_json = StepExecutionOutcome(
                status="skipped",
                notes=[
                    f"Target reference '{target_url}' is not a valid HTTP/HTTPS URL.",
                    "Navigate step skipped — only http:// and https:// URLs are supported.",
                ],
            ).model_dump(mode="json")
            step_model.completed_at = utcnow()
            self._emit_event(
                run.run_id,
                "step_skipped",
                f"Navigate step skipped (invalid URL): {step.title}",
                step_model.completed_at,
                step_model.executed_step_id,
            )
            return step_model, artifacts

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                resp = await client.post(
                    f"{self._mcp_url}/tools/call",
                    json={
                        "name": "browser_navigate",
                        "arguments": {"url": target_url},
                    },
                )
                duration_ms = (time.monotonic() - start_ms) * 1000
                if resp.status_code == 200:
                    body = resp.json()
                    step_model.status = "completed"
                    step_model.outcome_json = StepExecutionOutcome(
                        status="completed",
                        output={"mcp_response": body},
                        duration_ms=round(duration_ms, 1),
                        notes=["Playwright MCP navigate call returned successfully."],
                    ).model_dump(mode="json")

                    page_title = ""
                    page_url = ""
                    if isinstance(body, dict):
                        content = body.get("content", [])
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    text = item.get("text", "")
                                    for line in text.split("\n"):
                                        stripped = line.strip()
                                        if stripped.startswith("Title:"):
                                            page_title = stripped.removeprefix("Title:").strip()
                                        if stripped.startswith("URL:"):
                                            page_url = stripped.removeprefix("URL:").strip()

                    if page_title or page_url:
                        artifact = RunArtifactModel(
                            artifact_id=str(uuid4()),
                            run_id=run.run_id,
                            executed_step_id=step_model.executed_step_id,
                            artifact_type="page_metadata",
                            display_name=f"Page: {page_title or page_url or 'unknown'}",
                            content_text=f"Title: {page_title}\nURL: {page_url}",
                            metadata_json={"page_title": page_title, "page_url": page_url},
                            captured_at=utcnow(),
                        )
                        artifacts.append(artifact)
                        self._emit_event(
                            run.run_id,
                            "artifact_captured",
                            f"Captured page metadata: {page_title or page_url}",
                            utcnow(),
                            step_model.executed_step_id,
                            artifact.artifact_id,
                        )

                    log_artifact = RunArtifactModel(
                        artifact_id=str(uuid4()),
                        run_id=run.run_id,
                        executed_step_id=step_model.executed_step_id,
                        artifact_type="text_log",
                        display_name=f"Navigate step log ({step.step_index})",
                        content_text=f"MCP call to browser_navigate completed in {round(duration_ms, 1)}ms.",
                        metadata_json={"duration_ms": round(duration_ms, 1), "status_code": resp.status_code},
                        captured_at=utcnow(),
                    )
                    artifacts.append(log_artifact)
                else:
                    step_model.status = "failed"
                    step_model.outcome_json = StepExecutionOutcome(
                        status="failed",
                        error_code="mcp_error",
                        error_message=f"Playwright MCP returned status {resp.status_code}.",
                        duration_ms=round(duration_ms, 1),
                        notes=[f"HTTP {resp.status_code} from MCP server."],
                    ).model_dump(mode="json")
        except httpx.TimeoutException:
            duration_ms = (time.monotonic() - start_ms) * 1000
            step_model.status = "failed"
            step_model.outcome_json = StepExecutionOutcome(
                status="failed",
                error_code="mcp_timeout",
                error_message="Playwright MCP call timed out.",
                duration_ms=round(duration_ms, 1),
                notes=["The MCP server did not respond within the timeout."],
            ).model_dump(mode="json")
        except httpx.ConnectError:
            step_model.status = "failed"
            step_model.outcome_json = StepExecutionOutcome(
                status="failed",
                error_code="mcp_connection_error",
                error_message=f"Could not connect to Playwright MCP server at {self._mcp_url}.",
                notes=[
                    "The MCP server may not be running.",
                    "This is expected in local development without a Playwright MCP server.",
                ],
            ).model_dump(mode="json")
        except Exception as exc:
            logger.warning("Unexpected error during MCP navigate step.", exc_info=True)
            step_model.status = "failed"
            step_model.outcome_json = StepExecutionOutcome(
                status="failed",
                error_code="unexpected_error",
                error_message=str(exc)[:500],
                notes=["An unexpected error occurred during step execution."],
            ).model_dump(mode="json")

        step_model.completed_at = utcnow()
        event_type = "step_completed" if step_model.status == "completed" else "step_failed"
        self._emit_event(
            run.run_id,
            event_type,
            f"Navigate step {step_model.status}: {step.title}",
            step_model.completed_at,
            step_model.executed_step_id,
        )
        return step_model, artifacts

    def _create_run(
        self,
        draft: SubmissionDraftModel,
        plan: AutomationPlan,
        request: AutomationExecutionRequest,
        blocked_actions: list[BlockedActionRecord],
        now: datetime,
    ) -> AutomationRunModel:
        run = AutomationRunModel(
            run_id=str(uuid4()),
            draft_id=draft.draft_id,
            plan_id=plan.plan_id,
            case_id=draft.case_id,
            source_mode=plan.source_mode,
            source_reviewed_snapshot_id=plan.source_reviewed_snapshot_id,
            status="running",
            operator_id=request.operator_id.strip() if request.operator_id else draft.approved_by,
            dry_run=request.dry_run,
            guardrails_json=plan.guardrails.model_dump(mode="json"),
            session_json=AutomationSessionMetadata().model_dump(mode="json"),
            paused_run_json=None,
            summary_json=AutomationRunSummary().model_dump(mode="json"),
            notes_json=list(request.notes) + [
                f"Executing plan {plan.plan_id} for draft {draft.draft_id}.",
                f"{len(blocked_actions)} step(s) remain blocked by guardrails.",
            ],
            created_at=now,
            started_at=now,
        )
        self._session.add(run)
        self._session.flush()
        return run

    def _create_pending_step(self, run: AutomationRunModel, step: AutomationPlanStep) -> ExecutedStepModel:
        now = utcnow()
        step_model = ExecutedStepModel(
            executed_step_id=str(uuid4()),
            run_id=run.run_id,
            plan_step_id=step.step_id,
            step_index=step.step_index,
            step_type=step.step_type,
            title=step.title,
            description=step.description,
            target_reference=step.target_reference,
            tool_id=step.tool_id,
            backend_id=step.backend_id,
            status="awaiting_operator_review",
            outcome_json=StepExecutionOutcome(
                status="awaiting_operator_review",
                notes=["Execution paused pending operator review for this step."],
            ).model_dump(mode="json"),
            started_at=now,
            created_at=now,
        )
        self._session.add(step_model)
        self._emit_event(run.run_id, "step_started", f"Step {step.step_index}: {step.title}", now, step_model.executed_step_id)
        self._session.flush()
        return step_model

    def _create_checkpoint(
        self,
        run: AutomationRunModel,
        step: AutomationPlanStep,
        step_model: ExecutedStepModel,
        reason: str,
    ) -> AutomationCheckpointModel:
        existing = self._find_checkpoint(run.run_id, step.step_id)
        if existing is not None:
            return existing
        checkpoint = AutomationCheckpointModel(
            checkpoint_id=str(uuid4()),
            run_id=run.run_id,
            plan_step_id=step.step_id,
            executed_step_id=step_model.executed_step_id,
            step_index=step.step_index,
            step_type=step.step_type,
            step_title=step.title,
            status="pending_operator_review",
            execution_mode=step.execution_mode,
            checkpoint_reason=reason,
            fallback_hint_json=step.fallback_hint.model_dump(mode="json") if step.fallback_hint else {},
            notes_json=list(step.notes),
            created_at=utcnow(),
        )
        self._session.add(checkpoint)
        self._session.flush()
        return checkpoint

    def _pause_run(self, run: AutomationRunModel, checkpoint: AutomationCheckpointModel, reason: str) -> None:
        now = utcnow()
        run.status = "awaiting_operator_review"
        run.paused_run_json = PausedAutomationRunMetadata(
            checkpoint_id=checkpoint.checkpoint_id,
            plan_step_id=checkpoint.plan_step_id,
            executed_step_id=checkpoint.executed_step_id,
            step_index=checkpoint.step_index,
            step_title=checkpoint.step_title,
            execution_mode=checkpoint.execution_mode,
            checkpoint_status=checkpoint.status,
            paused_at=isoformat_utc(now),
            session_resume_supported=False,
            notes=[
                reason,
                "True browser session resumption is not implemented in this build.",
                "Resume continues from persisted run and checkpoint state only.",
            ],
        ).model_dump(mode="json")
        self._close_session(run, note="Checkpoint pause closed the current session boundary.")
        self._emit_event(
            run.run_id,
            "run_paused",
            f"Automation run paused for operator review at step {checkpoint.step_index}: {checkpoint.step_title}",
            now,
            checkpoint.executed_step_id,
            metadata=self._checkpoint_event_metadata(checkpoint).model_dump(mode="json"),
        )

    def _update_paused_run_checkpoint_status(self, run: AutomationRunModel, status: AutomationCheckpointStatus) -> None:
        if run.paused_run_json is None:
            return
        paused = PausedAutomationRunMetadata.model_validate(run.paused_run_json)
        paused.checkpoint_status = status
        run.paused_run_json = paused.model_dump(mode="json")

    def _activate_session(
        self,
        run: AutomationRunModel,
        capabilities: AutomationCapabilitiesResponse,
        *,
        note: str,
    ) -> None:
        if not self._has_backend(capabilities, "playwright_mcp"):
            session = self._session_meta(run)
            session.status = "not_started"
            session.notes.append("No Playwright MCP backend metadata available.")
            run.session_json = session.model_dump(mode="json")
            return
        session = AutomationSessionMetadata(
            session_id=str(uuid4()),
            backend_id="playwright_mcp",
            mcp_server_url=self._mcp_url,
            headless=True,
            status="active",
            notes=[note],
        )
        run.session_json = session.model_dump(mode="json")

    def _close_session(self, run: AutomationRunModel, *, note: str) -> None:
        session = self._session_meta(run)
        if session.status == "active":
            session.status = "closed"
            session.notes.append(note)
            run.session_json = session.model_dump(mode="json")

    def _record_override(
        self,
        run_id: str,
        checkpoint_id: str,
        *,
        operator_id: str,
        decision_type: str,
        decision_note: str = "",
        skip_reason: str = "",
        block_reason: str = "",
    ) -> AutomationCheckpointOverrideModel:
        override = AutomationCheckpointOverrideModel(
            override_id=str(uuid4()),
            checkpoint_id=checkpoint_id,
            run_id=run_id,
            operator_id=operator_id,
            decision_type=decision_type,
            decision_note=decision_note,
            skip_reason=skip_reason,
            block_reason=block_reason,
            metadata_json={},
            created_at=utcnow(),
        )
        self._session.add(override)
        self._session.flush()
        return override

    def _emit_event(
        self,
        run_id: str,
        event_type: str,
        message: str,
        timestamp: datetime,
        step_id: str | None = None,
        artifact_id: str | None = None,
        metadata: dict | None = None,
    ) -> RunEventModel:
        event = RunEventModel(
            event_id=str(uuid4()),
            run_id=run_id,
            event_type=event_type,
            executed_step_id=step_id,
            artifact_id=artifact_id,
            message=message,
            metadata_json=metadata or {},
            timestamp=timestamp,
        )
        self._session.add(event)
        return event

    def _blocked_response(
        self,
        draft: SubmissionDraftModel,
        plan: AutomationPlan,
        gate: ApprovalGateResult,
    ) -> AutomationRunResponse:
        return AutomationRunResponse(
            result=NormalizedOperationResult(
                success=False,
                message=gate.reason,
                issues=[
                    NormalizedResultIssue(
                        severity="error",
                        code="execution_blocked",
                        message=gate.reason,
                        related_entity_type="submission_draft",
                        related_entity_id=draft.draft_id,
                    ),
                ],
            ),
            run=AutomationRunRecord(
                run_id="",
                draft_id=draft.draft_id,
                plan_id=plan.plan_id,
                case_id=draft.case_id,
                source_mode=plan.source_mode,
                source_reviewed_snapshot_id=plan.source_reviewed_snapshot_id,
                status="blocked",
            ),
        )

    def _determine_final_status(self, plan_id: str, run_id: str) -> str:
        plan = self._load_plan_by_id(plan_id)
        total = len(plan.steps) if plan else 0
        steps = self._load_executed_steps(run_id)
        completed = sum(1 for step in steps if step.status == "completed")
        skipped = sum(1 for step in steps if step.status == "skipped")
        blocked = sum(1 for step in steps if step.status == "blocked")
        failed = sum(1 for step in steps if step.status == "failed")

        if failed > 0:
            return "failed"
        if blocked > 0 and completed == 0 and skipped == 0:
            return "blocked"
        if blocked > 0:
            return "completed_partial"
        if skipped > 0 and completed > 0:
            return "completed_partial"
        if skipped == total and total > 0:
            return "completed"
        if completed == total and total > 0:
            return "completed"
        return "completed_partial"

    def _run_result_message(self, status: str) -> str:
        messages = {
            "awaiting_operator_review": "Automation run paused for operator review.",
            "running": "Automation run is in progress.",
            "completed": "Automation run completed.",
            "completed_partial": "Automation run completed partially.",
            "blocked": "Automation run is blocked.",
            "failed": "Automation run failed.",
        }
        return messages.get(status, f"Automation run status: {status}.")

    def _has_backend(self, capabilities: AutomationCapabilitiesResponse, backend_id: str) -> bool:
        return any(backend.id == backend_id for backend in capabilities.backends)

    def _session_meta(self, run: AutomationRunModel) -> AutomationSessionMetadata:
        return AutomationSessionMetadata.model_validate(run.session_json)

    def _refresh_run_summary(self, run: AutomationRunModel) -> None:
        plan = self._load_plan_by_id(run.plan_id)
        total_steps = len(plan.steps) if plan else 0
        steps = self._load_executed_steps(run.run_id)
        checkpoints = self._load_checkpoints(run.run_id)
        summary = AutomationRunSummary(
            total_steps=total_steps,
            completed_steps=sum(1 for step in steps if step.status == "completed"),
            skipped_steps=sum(1 for step in steps if step.status == "skipped"),
            blocked_steps=sum(1 for step in steps if step.status == "blocked"),
            failed_steps=sum(1 for step in steps if step.status == "failed"),
            artifact_count=len(self._load_artifacts(run.run_id)),
            event_count=len(self._load_events(run.run_id)),
            checkpoint_count=len(checkpoints),
            pending_checkpoint_count=sum(1 for checkpoint in checkpoints if checkpoint.status == "pending_operator_review"),
            notes=self._summary_notes(run.status, checkpoints),
        )
        run.summary_json = summary.model_dump(mode="json")

    def _summary_notes(
        self,
        status: str,
        checkpoints: list[AutomationCheckpointRecord],
    ) -> list[str]:
        notes: list[str] = []
        if status == "awaiting_operator_review" and checkpoints:
            pending = next((checkpoint for checkpoint in checkpoints if checkpoint.status == "pending_operator_review"), None)
            if pending is not None:
                notes.append(f"Awaiting operator review at step {pending.step_index}: {pending.step_title}.")
        if any(checkpoint.execution_mode == "computer_use_fallback" for checkpoint in checkpoints):
            notes.append("Computer-use fallback remains metadata-only in this build.")
        if status == "completed_partial":
            notes.append("Run completed partially — some steps were skipped or blocked by design.")
        return notes

    def _checkpoint_event_metadata(
        self,
        checkpoint: AutomationCheckpointModel,
        decision_type: str | None = None,
    ) -> AutomationCheckpointEventMetadata:
        return AutomationCheckpointEventMetadata(
            checkpoint_id=checkpoint.checkpoint_id,
            plan_step_id=checkpoint.plan_step_id,
            executed_step_id=checkpoint.executed_step_id,
            execution_mode=checkpoint.execution_mode,
            decision_type=decision_type,
            notes=list(checkpoint.notes_json),
        )

    def _require_draft(self, draft_id: str) -> SubmissionDraftModel:
        draft = self._session.get(SubmissionDraftModel, draft_id)
        if draft is None:
            raise AutomationExecutionError(f"Submission draft '{draft_id}' not found.", status_code=404)
        return draft

    def _require_run(self, run_id: str) -> AutomationRunModel:
        run = self._session.get(AutomationRunModel, run_id)
        if run is None:
            raise AutomationExecutionError(f"Automation run '{run_id}' not found.", status_code=404)
        return run

    def _require_checkpoint(self, run_id: str, checkpoint_id: str) -> AutomationCheckpointModel:
        checkpoint = self._session.get(AutomationCheckpointModel, checkpoint_id)
        if checkpoint is None or checkpoint.run_id != run_id:
            raise AutomationExecutionError(
                f"Automation checkpoint '{checkpoint_id}' not found for run '{run_id}'.",
                status_code=404,
            )
        return checkpoint

    def _require_plan_step(self, plan_id: str, plan_step_id: str) -> AutomationPlanStep:
        record = self._session.exec(
            select(AutomationPlanStepModel)
            .where(AutomationPlanStepModel.plan_id == plan_id)
            .where(AutomationPlanStepModel.step_id == plan_step_id)
        ).first()
        if record is None:
            raise AutomationExecutionError(
                f"Automation plan step '{plan_step_id}' not found for plan '{plan_id}'.",
                status_code=404,
            )
        return self._step_from_model(record)

    def _require_step_model(self, run_id: str, plan_step_id: str) -> ExecutedStepModel:
        step_model = self._find_step_model(run_id, plan_step_id)
        if step_model is None:
            raise AutomationExecutionError(
                f"Executed step for plan step '{plan_step_id}' not found in run '{run_id}'.",
                status_code=404,
            )
        return step_model

    def _find_step_model(self, run_id: str, plan_step_id: str) -> ExecutedStepModel | None:
        return self._session.exec(
            select(ExecutedStepModel)
            .where(ExecutedStepModel.run_id == run_id)
            .where(ExecutedStepModel.plan_step_id == plan_step_id)
            .order_by(desc(ExecutedStepModel.created_at), desc(ExecutedStepModel.executed_step_id))
        ).first()

    def _find_checkpoint(self, run_id: str, plan_step_id: str) -> AutomationCheckpointModel | None:
        return self._session.exec(
            select(AutomationCheckpointModel)
            .where(AutomationCheckpointModel.run_id == run_id)
            .where(AutomationCheckpointModel.plan_step_id == plan_step_id)
            .order_by(desc(AutomationCheckpointModel.created_at), desc(AutomationCheckpointModel.checkpoint_id))
        ).first()

    def _require_pending_checkpoint_for_step(self, run_id: str, plan_step_id: str) -> AutomationCheckpointModel:
        checkpoint = self._find_checkpoint(run_id, plan_step_id)
        if checkpoint is None:
            raise AutomationExecutionError(
                f"Checkpoint not found for plan step '{plan_step_id}' in run '{run_id}'.",
                status_code=404,
            )
        return checkpoint

    def _load_plan(self, plan_id: str, draft_id: str) -> AutomationPlan:
        record = self._session.get(AutomationPlanModel, plan_id)
        if record is None or record.draft_id != draft_id:
            raise AutomationExecutionError(
                f"Automation plan '{plan_id}' not found for draft '{draft_id}'.",
                status_code=404,
            )
        steps = list(self._session.exec(
            select(AutomationPlanStepModel)
            .where(AutomationPlanStepModel.plan_id == plan_id)
            .order_by(AutomationPlanStepModel.step_index, AutomationPlanStepModel.step_id)
        ).all())
        return AutomationPlan(
            plan_id=record.plan_id,
            draft_id=record.draft_id,
            target_id=record.target_id,
            status=record.status,
            dry_run=record.dry_run,
            generated_at=isoformat_utc(record.created_at),
            guardrails=ExecutionGuardrailMetadata.model_validate(record.guardrails_json),
            dry_run_summary=record.dry_run_summary_json,
            steps=[self._step_from_model(row) for row in steps],
        )

    def _load_plan_by_id(self, plan_id: str) -> AutomationPlan | None:
        record = self._session.get(AutomationPlanModel, plan_id)
        if record is None:
            return None
        steps = list(self._session.exec(
            select(AutomationPlanStepModel)
            .where(AutomationPlanStepModel.plan_id == plan_id)
            .order_by(AutomationPlanStepModel.step_index, AutomationPlanStepModel.step_id)
        ).all())
        return AutomationPlan(
            plan_id=record.plan_id,
            draft_id=record.draft_id,
            target_id=record.target_id,
            status=record.status,
            dry_run=record.dry_run,
            generated_at=isoformat_utc(record.created_at),
            guardrails=ExecutionGuardrailMetadata.model_validate(record.guardrails_json),
            dry_run_summary=record.dry_run_summary_json,
            steps=[self._step_from_model(row) for row in steps],
        )

    def _step_from_model(self, row: AutomationPlanStepModel) -> AutomationPlanStep:
        return AutomationPlanStep(
            step_id=row.step_id,
            step_index=row.step_index,
            step_type=row.step_type,
            status=row.status,
            title=row.title,
            description=row.description,
            target_reference=row.target_reference,
            tool_id=row.tool_id,
            backend_id=row.backend_id,
            execution_mode=row.execution_mode,
            checkpoint_required=row.checkpoint_required,
            checkpoint_reason=row.checkpoint_reason,
            fallback_hint=(
                AutomationFallbackRoutingHint.model_validate(row.fallback_hint_json)
                if row.fallback_hint_json else None
            ),
            mapping_id=row.mapping_id,
            related_document_id=row.related_document_id,
            notes=list(row.notes_json),
        )

    def _load_executed_steps(self, run_id: str) -> list[ExecutedStepRecord]:
        rows = list(self._session.exec(
            select(ExecutedStepModel)
            .where(ExecutedStepModel.run_id == run_id)
            .order_by(ExecutedStepModel.step_index, ExecutedStepModel.executed_step_id)
        ).all())
        return [self._executed_step_to_record(row) for row in rows]

    def _load_artifacts(self, run_id: str) -> list[RunArtifactRecord]:
        rows = list(self._session.exec(
            select(RunArtifactModel)
            .where(RunArtifactModel.run_id == run_id)
            .order_by(RunArtifactModel.captured_at, RunArtifactModel.artifact_id)
        ).all())
        return [self._artifact_to_record(row) for row in rows]

    def _load_events(self, run_id: str) -> list[RunEventRecord]:
        rows = list(self._session.exec(
            select(RunEventModel)
            .where(RunEventModel.run_id == run_id)
            .order_by(RunEventModel.timestamp, RunEventModel.event_id)
        ).all())
        return [self._event_to_record(row) for row in rows]

    def _load_checkpoints(self, run_id: str) -> list[AutomationCheckpointRecord]:
        rows = list(self._session.exec(
            select(AutomationCheckpointModel)
            .where(AutomationCheckpointModel.run_id == run_id)
            .order_by(AutomationCheckpointModel.step_index, AutomationCheckpointModel.created_at)
        ).all())
        return [self._to_checkpoint_record(row) for row in rows]

    def _load_overrides(self, run_id: str) -> list[AutomationOperatorOverrideRecord]:
        rows = list(self._session.exec(
            select(AutomationCheckpointOverrideModel)
            .where(AutomationCheckpointOverrideModel.run_id == run_id)
            .order_by(AutomationCheckpointOverrideModel.created_at, AutomationCheckpointOverrideModel.override_id)
        ).all())
        return [self._to_override_record(row) for row in rows]

    def _to_approval(self, draft: SubmissionDraftModel) -> ApprovalRequirementMetadata:
        return ApprovalRequirementMetadata(
            requires_operator_approval=draft.requires_operator_approval,
            approval_status=draft.approval_status,
            approved_by=draft.approved_by,
            approved_at=isoformat_utc(draft.approved_at) if draft.approved_at else "",
            approval_note=draft.approval_note,
            scope="future_execution",
        )

    def _to_run_record(self, row: AutomationRunModel) -> AutomationRunRecord:
        return AutomationRunRecord(
            run_id=row.run_id,
            draft_id=row.draft_id,
            plan_id=row.plan_id,
            case_id=row.case_id,
            source_mode=row.source_mode,
            source_reviewed_snapshot_id=row.source_reviewed_snapshot_id,
            status=row.status,
            operator_id=row.operator_id,
            dry_run=row.dry_run,
            guardrails=ExecutionGuardrailMetadata.model_validate(row.guardrails_json),
            session=AutomationSessionMetadata.model_validate(row.session_json),
            paused_run=(PausedAutomationRunMetadata.model_validate(row.paused_run_json) if row.paused_run_json else None),
            summary=AutomationRunSummary.model_validate(row.summary_json),
            created_at=isoformat_utc(row.created_at),
            started_at=isoformat_utc(row.started_at) if row.started_at else "",
            completed_at=isoformat_utc(row.completed_at) if row.completed_at else "",
            notes=list(row.notes_json),
        )

    def _executed_step_to_record(self, row: ExecutedStepModel) -> ExecutedStepRecord:
        return ExecutedStepRecord(
            executed_step_id=row.executed_step_id,
            run_id=row.run_id,
            plan_step_id=row.plan_step_id,
            step_index=row.step_index,
            step_type=row.step_type,
            title=row.title,
            description=row.description,
            target_reference=row.target_reference,
            tool_id=row.tool_id,
            backend_id=row.backend_id,
            status=row.status,
            outcome=StepExecutionOutcome.model_validate(row.outcome_json) if row.outcome_json else StepExecutionOutcome(),
            started_at=isoformat_utc(row.started_at) if row.started_at else "",
            completed_at=isoformat_utc(row.completed_at) if row.completed_at else "",
            notes=list(row.notes_json),
        )

    def _artifact_to_record(self, row: RunArtifactModel) -> RunArtifactRecord:
        return RunArtifactRecord(
            artifact_id=row.artifact_id,
            run_id=row.run_id,
            executed_step_id=row.executed_step_id,
            artifact_type=row.artifact_type,
            display_name=row.display_name,
            content_text=row.content_text,
            content_url=row.content_url,
            metadata=row.metadata_json,
            captured_at=isoformat_utc(row.captured_at),
            notes=list(row.notes_json),
        )

    def _event_to_record(self, row: RunEventModel) -> RunEventRecord:
        return RunEventRecord(
            event_id=row.event_id,
            run_id=row.run_id,
            event_type=row.event_type,
            executed_step_id=row.executed_step_id,
            artifact_id=row.artifact_id,
            message=row.message,
            timestamp=isoformat_utc(row.timestamp),
            metadata=row.metadata_json,
        )

    def _to_checkpoint_record(self, row: AutomationCheckpointModel) -> AutomationCheckpointRecord:
        return AutomationCheckpointRecord(
            checkpoint_id=row.checkpoint_id,
            run_id=row.run_id,
            plan_step_id=row.plan_step_id,
            executed_step_id=row.executed_step_id,
            step_index=row.step_index,
            step_type=row.step_type,
            step_title=row.step_title,
            status=row.status,
            decision_type=row.decision_type,
            operator_id=row.operator_id,
            decision_note=row.decision_note,
            skip_reason=row.skip_reason,
            block_reason=row.block_reason,
            execution_mode=row.execution_mode,
            checkpoint_reason=row.checkpoint_reason,
            fallback_hint=(AutomationFallbackRoutingHint.model_validate(row.fallback_hint_json) if row.fallback_hint_json else None),
            created_at=isoformat_utc(row.created_at),
            decided_at=isoformat_utc(row.decided_at) if row.decided_at else "",
            resolved_at=isoformat_utc(row.resolved_at) if row.resolved_at else "",
            notes=list(row.notes_json),
        )

    def _to_override_record(self, row: AutomationCheckpointOverrideModel) -> AutomationOperatorOverrideRecord:
        return AutomationOperatorOverrideRecord(
            override_id=row.override_id,
            checkpoint_id=row.checkpoint_id,
            run_id=row.run_id,
            operator_id=row.operator_id,
            decision_type=row.decision_type,
            decision_note=row.decision_note,
            skip_reason=row.skip_reason,
            block_reason=row.block_reason,
            created_at=isoformat_utc(row.created_at),
        )