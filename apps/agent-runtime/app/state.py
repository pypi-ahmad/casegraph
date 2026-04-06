"""Runtime state for the LangGraph supervisor graph."""

from __future__ import annotations

from typing import Annotated, Any

from typing_extensions import TypedDict


def _append_list(existing: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reducer that appends new items to the existing list."""
    return existing + new


class RuntimeState(TypedDict):
    """State flowing through the supervisor graph.

    Fields:
        task_type: The task type that initiated this run.
        payload: Arbitrary input data for the current task.
        next_agent: The agent id the supervisor should route to next, or
            ``"__end__"`` to terminate.
        agent_outputs: Accumulated outputs from each agent node (append-only).
        status: Current run status (pending | running | completed | failed).
        correlation_id: Optional correlation id for tracing.
    """

    task_type: str
    payload: dict[str, Any]
    next_agent: str
    agent_outputs: Annotated[list[dict[str, Any]], _append_list]
    status: str
    correlation_id: str
