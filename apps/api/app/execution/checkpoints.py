"""Typed supervision policy for automation execution checkpoints.

Determines when a plan step should pause for operator review before the
execution service continues. This is intentionally explicit and minimal.
"""

from __future__ import annotations

from dataclasses import dataclass

from casegraph_agent_sdk.submissions import (
    AutomationFallbackRoutingHint,
    AutomationPlanStep,
)


CHECKPOINT_REQUIRED_STEP_TYPES = frozenset({
    "review_before_submit",
})


@dataclass(slots=True)
class StepCheckpointPolicy:
    required: bool
    execution_mode: str
    reason: str
    fallback_hint: AutomationFallbackRoutingHint | None = None


def determine_step_checkpoint_policy(step: AutomationPlanStep) -> StepCheckpointPolicy:
    execution_mode = step.execution_mode or "blocked"
    fallback_hint = step.fallback_hint

    if step.status == "blocked":
        return StepCheckpointPolicy(
            required=False,
            execution_mode=execution_mode,
            reason="Blocked plan steps are not eligible for operator-continue checkpoints.",
            fallback_hint=fallback_hint,
        )

    if step.checkpoint_required:
        return StepCheckpointPolicy(
            required=True,
            execution_mode=execution_mode,
            reason=step.checkpoint_reason or "Operator review is required before this step can continue.",
            fallback_hint=fallback_hint,
        )

    if step.step_type in CHECKPOINT_REQUIRED_STEP_TYPES:
        return StepCheckpointPolicy(
            required=True,
            execution_mode=execution_mode,
            reason="Step type requires an operator review checkpoint.",
            fallback_hint=fallback_hint,
        )

    if execution_mode in {"computer_use_fallback", "manual_only"}:
        return StepCheckpointPolicy(
            required=True,
            execution_mode=execution_mode,
            reason=(
                step.checkpoint_reason
                or "Operator review is required before continuing past a non-deterministic or manual-only step."
            ),
            fallback_hint=fallback_hint,
        )

    return StepCheckpointPolicy(
        required=False,
        execution_mode=execution_mode,
        reason="No checkpoint required for this step.",
        fallback_hint=fallback_hint,
    )