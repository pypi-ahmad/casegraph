"""Topology service — derives a visual graph from runtime metadata."""

from __future__ import annotations

from casegraph_agent_sdk.agents import AgentMetadata
from casegraph_workflows.schemas import WorkflowDefinition

from app.topology.schemas import (
    TopologyEdge,
    TopologyNode,
    TopologyResponse,
)


def build_topology(
    agents: list[AgentMetadata],
    workflows: list[WorkflowDefinition],
) -> TopologyResponse:
    """Convert agent + workflow metadata into a flat node/edge graph."""

    nodes: list[TopologyNode] = []
    edges: list[TopologyEdge] = []

    # --- Agent nodes -------------------------------------------------------
    for agent in agents:
        node_id = f"agent:{agent.id}"
        nodes.append(
            TopologyNode(
                id=node_id,
                label=agent.display_name,
                category="agent",
                description=agent.description,
                meta={
                    "accepted_task_types": agent.accepted_task_types,
                    "capability_count": len(agent.capabilities),
                },
            )
        )

    # --- Agent handoff edges -----------------------------------------------
    for agent in agents:
        src = f"agent:{agent.id}"
        for target_id in agent.handoff_targets:
            tgt = f"agent:{target_id}"
            edges.append(
                TopologyEdge(
                    id=f"handoff:{agent.id}->{target_id}",
                    source=src,
                    target=tgt,
                    type="handoff",
                    label="handoff",
                )
            )

    # --- Workflow nodes + step edges ---------------------------------------
    for wf in workflows:
        wf_node_id = f"workflow:{wf.id}"
        nodes.append(
            TopologyNode(
                id=wf_node_id,
                label=wf.display_name,
                category="workflow",
                description=wf.description,
                meta={
                    "step_count": len(wf.steps),
                },
            )
        )

        step_id_map: dict[str, str] = {}
        for step in wf.steps:
            step_agent_node = f"agent:{step.agent_id}"
            step_id_map[step.id] = step_agent_node

            # Membership edge: workflow → agent
            edges.append(
                TopologyEdge(
                    id=f"membership:{wf.id}->{step.agent_id}:{step.id}",
                    source=wf_node_id,
                    target=step_agent_node,
                    type="membership",
                    label=step.display_name,
                )
            )

        # Step dependency edges (between agent nodes within workflow)
        for step in wf.steps:
            current = step_id_map[step.id]
            for dep_id in step.depends_on:
                dep_node = step_id_map.get(dep_id)
                if dep_node:
                    edges.append(
                        TopologyEdge(
                            id=f"step:{wf.id}:{dep_id}->{step.id}",
                            source=dep_node,
                            target=current,
                            type="step",
                            label=f"{dep_id} → {step.id}",
                        )
                    )

    return TopologyResponse(nodes=nodes, edges=edges)
