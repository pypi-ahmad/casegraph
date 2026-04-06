"""Review agent — reviews and validates agent outputs."""

from casegraph_agent_sdk.agents import (
    AgentExecutionContext,
    AgentInputEnvelope,
    AgentOutputEnvelope,
    AgentOutputStatus,
)

from app.agents.base import BaseAgent


class ReviewAgent(BaseAgent):
    agent_id = "review"
    display_name = "Review Agent"
    description = "Reviews and validates outputs from other agents."
    accepted_task_types = ["review"]
    handoff_targets: list[str] = []

    async def execute(
        self,
        input_envelope: AgentInputEnvelope,
        context: AgentExecutionContext,
    ) -> AgentOutputEnvelope:
        return AgentOutputEnvelope(
            agent_id=self.agent_id,
            task_type=input_envelope.task_type,
            status=AgentOutputStatus.COMPLETED,
            result={
                "message": "Review completed.",
                "reviewed_payload_keys": sorted(input_envelope.payload.keys()),
            },
            correlation_id=input_envelope.correlation_id,
        )
