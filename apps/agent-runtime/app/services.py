"""Runtime service — exposes agent and workflow metadata."""

from __future__ import annotations

from casegraph_agent_sdk.agents import AgentMetadata, AgentsResponse

from casegraph_workflows.schemas import WorkflowDefinition, WorkflowsResponse

from app.registry import agent_registry
from casegraph_workflows.registry import workflow_registry


class RuntimeService:
    def list_agents(self) -> AgentsResponse:
        return AgentsResponse(agents=agent_registry.list_metadata())

    def get_agent(self, agent_id: str) -> AgentMetadata | None:
        agent = agent_registry.get(agent_id)
        return agent.metadata() if agent else None

    def list_workflows(self) -> WorkflowsResponse:
        return WorkflowsResponse(workflows=workflow_registry.list_definitions())

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        return workflow_registry.get(workflow_id)
