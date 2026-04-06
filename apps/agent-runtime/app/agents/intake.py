"""Intake agent — receives and validates incoming task requests."""

from casegraph_agent_sdk.agents import (
    AgentExecutionContext,
    AgentInputEnvelope,
    AgentOutputEnvelope,
    AgentOutputStatus,
)

from app.agents.base import BaseAgent


class IntakeAgent(BaseAgent):
    agent_id = "intake"
    display_name = "Intake Agent"
    description = "Receives and validates incoming task requests."
    accepted_task_types = ["intake"]
    handoff_targets = ["router", "review"]

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
                "message": "Intake processed.",
                "received_payload_keys": sorted(input_envelope.payload.keys()),
            },
            correlation_id=input_envelope.correlation_id,
        )
