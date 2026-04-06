"""Agent registry — singleton that tracks all registered agents."""

from __future__ import annotations

from casegraph_agent_sdk.agents import AgentMetadata

from app.agents.base import BaseAgent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.agent_id] = agent

    def get(self, agent_id: str) -> BaseAgent | None:
        return self._agents.get(agent_id)

    def list_agents(self) -> list[BaseAgent]:
        return list(self._agents.values())

    def list_metadata(self) -> list[AgentMetadata]:
        return [a.metadata() for a in self._agents.values()]

    def list_ids(self) -> list[str]:
        return list(self._agents.keys())


agent_registry = AgentRegistry()
