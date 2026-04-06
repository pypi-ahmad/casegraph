"""Inter-agent handoff execution."""

from __future__ import annotations

from casegraph_agent_sdk.agents import (
    AgentError,
    AgentExecutionContext,
    AgentInputEnvelope,
    HandoffRequest,
    HandoffResult,
)

from app.agents.base import BaseAgent


async def execute_handoff(
    request: HandoffRequest,
    target_agent: BaseAgent,
) -> HandoffResult:
    """Execute a handoff from one agent to another.

    Wraps the target agent's ``execute`` call and normalises the result
    into a :class:`HandoffResult`.
    """
    if request.target_agent_id != target_agent.agent_id:
        return HandoffResult(
            source_agent_id=request.source_agent_id,
            target_agent_id=request.target_agent_id,
            accepted=False,
            error=AgentError(
                agent_id=request.target_agent_id,
                error_code="handoff_target_mismatch",
                message="Handoff target does not match the provided agent.",
            ),
        )

    context = AgentExecutionContext(
        caller_agent_id=request.source_agent_id,
        workflow_run_id=request.context.workflow_run_id if request.context else None,
        step_index=request.context.step_index if request.context else None,
        correlation_id=request.context.correlation_id if request.context else None,
    )

    envelope = AgentInputEnvelope(
        task_type=request.task_type,
        payload=request.payload,
        context=context,
        correlation_id=context.correlation_id,
    )

    try:
        output = await target_agent.execute(envelope, context)
        return HandoffResult(
            source_agent_id=request.source_agent_id,
            target_agent_id=request.target_agent_id,
            accepted=True,
            result=output,
        )
    except Exception as exc:
        return HandoffResult(
            source_agent_id=request.source_agent_id,
            target_agent_id=request.target_agent_id,
            accepted=False,
            error=AgentError(
                agent_id=request.target_agent_id,
                error_code="handoff_failed",
                message=str(exc),
            ),
        )
