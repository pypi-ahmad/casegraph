"""Minimal supervisor graph that routes tasks to registered agents.

The graph follows the supervisor pattern:
1. ``supervisor`` node reads ``task_type`` (or a handoff-set ``next_agent``)
   and decides which agent to invoke next.
2. Each agent wrapper node calls ``BaseAgent.execute()``, appends its
   output to ``agent_outputs``, and either signals completion or sets a
   handoff target.
3. After each agent, routing returns to the supervisor for re-evaluation
   or terminates the graph.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from casegraph_agent_sdk.agents import (
    AgentExecutionContext,
    AgentInputEnvelope,
)

from app.agents.base import BaseAgent
from app.state import RuntimeState


# ---------------------------------------------------------------------------
# Node factories
# ---------------------------------------------------------------------------


def _make_agent_node(agent: BaseAgent):
    """Return a graph-node function that wraps *agent*.execute()."""

    async def node(state: RuntimeState) -> dict[str, Any]:
        envelope = AgentInputEnvelope(
            task_type=state["task_type"],
            payload=state.get("payload", {}),
            correlation_id=state.get("correlation_id"),
        )
        context = AgentExecutionContext(
            correlation_id=state.get("correlation_id"),
        )

        output = await agent.execute(envelope, context)

        next_agent = "__end__"
        if output.handoff is not None:
            next_agent = output.handoff.target_agent_id

        return {
            "agent_outputs": [output.model_dump()],
            "next_agent": next_agent,
            "status": output.status.value,
        }

    node.__name__ = f"agent_{agent.agent_id}"
    return node


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------


def _supervisor_route(state: RuntimeState) -> str:
    return state.get("next_agent", "__end__")


def _after_agent(state: RuntimeState) -> str:
    """After an agent node: end the graph or loop back to supervisor."""
    next_agent = state.get("next_agent", "__end__")
    if next_agent == "__end__":
        return "__end__"
    return "supervisor"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_supervisor_graph(agents: list[BaseAgent]) -> CompiledStateGraph:
    """Compile a supervisor StateGraph with the given *agents*.

    The resulting graph routes an initial ``task_type`` to the first
    matching agent, supports inter-agent handoffs, and terminates when
    an agent returns ``status="completed"`` or ``status="failed"``
    without a handoff.
    """

    agent_map = {a.agent_id: a for a in agents}
    agent_ids = list(agent_map.keys())

    builder: StateGraph = StateGraph(RuntimeState)

    # -- supervisor ---------------------------------------------------------

    async def supervisor(state: RuntimeState) -> dict[str, Any]:
        next_agent = state.get("next_agent", "")

        # A previous agent set a handoff target — validate & proceed.
        if next_agent and next_agent != "__end__":
            if next_agent in agent_map:
                return {"status": "running"}
            return {"next_agent": "__end__", "status": "failed"}

        # Initial routing: match task_type to first accepting agent.
        task_type = state.get("task_type", "")
        for agent in agents:
            if task_type in agent.accepted_task_types:
                return {"next_agent": agent.agent_id, "status": "running"}

        return {"next_agent": "__end__", "status": "failed"}

    builder.add_node("supervisor", supervisor)

    # -- agent nodes --------------------------------------------------------

    for agent in agents:
        builder.add_node(agent.agent_id, _make_agent_node(agent))

    # -- edges --------------------------------------------------------------

    builder.set_entry_point("supervisor")

    # Supervisor → agent or END
    sup_route_map: dict[str, str] = {aid: aid for aid in agent_ids}
    sup_route_map["__end__"] = END
    builder.add_conditional_edges("supervisor", _supervisor_route, sup_route_map)

    # Each agent → supervisor (handoff) or END
    for aid in agent_ids:
        builder.add_conditional_edges(
            aid,
            _after_agent,
            {"supervisor": "supervisor", "__end__": END},
        )

    return builder.compile()
