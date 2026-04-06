"""Base agent abstraction for the CaseGraph runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod

from casegraph_agent_sdk.agents import (
    AgentCapability,
    AgentExecutionContext,
    AgentInputEnvelope,
    AgentMetadata,
    AgentOutputEnvelope,
)


class BaseAgent(ABC):
    """Abstract base class that every agent in the runtime must implement.

    Subclasses declare their identity, accepted task types, and the set
    of agents they may hand work off to.  The ``execute`` method is the
    single entry-point invoked by the supervisor graph.
    """

    agent_id: str
    display_name: str
    description: str
    accepted_task_types: list[str]
    handoff_targets: list[str]

    def capabilities(self) -> list[AgentCapability]:
        """Override to declare agent-level capabilities."""
        return []

    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            id=self.agent_id,
            display_name=self.display_name,
            description=self.description,
            capabilities=self.capabilities(),
            accepted_task_types=list(self.accepted_task_types),
            handoff_targets=list(self.handoff_targets),
        )

    @abstractmethod
    async def execute(
        self,
        input_envelope: AgentInputEnvelope,
        context: AgentExecutionContext,
    ) -> AgentOutputEnvelope:
        """Process a single task and return a typed output envelope."""
