"""Approval gating enforcement for automation execution.

Validates that a submission draft and its automation plan are in the
correct state before execution can proceed. Returns typed blocked
responses when requirements are not met.
"""

from __future__ import annotations

from casegraph_agent_sdk.execution import BlockedActionRecord
from casegraph_agent_sdk.submissions import (
    ApprovalRequirementMetadata,
    AutomationPlan,
    AutomationPlanStep,
)

from app.submissions.models import SubmissionDraftModel


# Step types that are safe to execute with read-only browser actions
EXECUTABLE_STEP_TYPES = frozenset({
    "open_target",
    "navigate_section",
    "review_before_submit",
})

# Step types that must remain blocked in this build
BLOCKED_STEP_TYPES = frozenset({
    "populate_field_placeholder",
    "attach_document_placeholder",
    "submit_blocked_placeholder",
})


class ApprovalGateResult:
    """Result of an approval gate check."""

    def __init__(
        self,
        *,
        allowed: bool,
        reason: str = "",
        blocked_actions: list[BlockedActionRecord] | None = None,
    ) -> None:
        self.allowed = allowed
        self.reason = reason
        self.blocked_actions = blocked_actions or []


def check_execution_approval(
    draft: SubmissionDraftModel,
    plan: AutomationPlan,
    approval: ApprovalRequirementMetadata,
) -> ApprovalGateResult:
    """Validate that execution can proceed for the given draft and plan.

    Returns an ApprovalGateResult with allowed=False if any gate fails.
    """

    if draft.status == "superseded_placeholder":
        return ApprovalGateResult(
            allowed=False,
            reason="Superseded drafts cannot be executed.",
        )

    if draft.status == "blocked":
        return ApprovalGateResult(
            allowed=False,
            reason="Draft is blocked and cannot be executed.",
        )

    if draft.approval_status != "approved_for_future_execution":
        return ApprovalGateResult(
            allowed=False,
            reason=(
                f"Draft approval status is '{draft.approval_status}'. "
                "Execution requires 'approved_for_future_execution'."
            ),
        )

    if approval.approval_status != "approved_for_future_execution":
        return ApprovalGateResult(
            allowed=False,
            reason="Plan approval metadata does not indicate approval for execution.",
        )

    if plan.status == "blocked":
        return ApprovalGateResult(
            allowed=False,
            reason="Automation plan is blocked.",
        )

    blocked_actions = classify_blocked_steps(plan.steps)

    return ApprovalGateResult(
        allowed=True,
        reason="Execution approved.",
        blocked_actions=blocked_actions,
    )


def classify_blocked_steps(
    steps: list[AutomationPlanStep],
) -> list[BlockedActionRecord]:
    """Identify plan steps that must be blocked during execution."""

    blocked: list[BlockedActionRecord] = []
    for step in steps:
        if step.step_type in BLOCKED_STEP_TYPES:
            blocked.append(
                BlockedActionRecord(
                    step_type=step.step_type,
                    step_title=step.title,
                    reason=_block_reason(step.step_type),
                    guardrail_code=f"blocked_{step.step_type}",
                    plan_step_id=step.step_id,
                )
            )
        elif step.status == "blocked":
            blocked.append(
                BlockedActionRecord(
                    step_type=step.step_type,
                    step_title=step.title,
                    reason="Step has blocked status in the automation plan.",
                    guardrail_code="plan_step_blocked",
                    plan_step_id=step.step_id,
                )
            )
    return blocked


def is_step_executable(step: AutomationPlanStep) -> bool:
    """Return True if a step type is in the safe executable set."""

    if step.step_type not in EXECUTABLE_STEP_TYPES:
        return False
    if step.status == "blocked":
        return False
    return True


def _block_reason(step_type: str) -> str:
    reasons = {
        "populate_field_placeholder": (
            "Field population requires write actions which are blocked in this build."
        ),
        "attach_document_placeholder": (
            "Document attachment upload is not implemented in this execution layer."
        ),
        "submit_blocked_placeholder": (
            "Final submission actions are explicitly blocked by execution guardrails."
        ),
    }
    return reasons.get(step_type, "Step type is not in the allowed execution set.")
