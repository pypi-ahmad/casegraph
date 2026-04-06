"""Router agent — analyses task context and routes to the appropriate agent."""

from casegraph_agent_sdk.agents import (
    AgentError,
    AgentExecutionContext,
    AgentInputEnvelope,
    AgentOutputEnvelope,
    AgentOutputStatus,
    HandoffRequest,
)

from app.agents.base import BaseAgent


class RouterAgent(BaseAgent):
    agent_id = "router"
    display_name = "Router Agent"
    description = "Analyses task context and routes to the appropriate downstream agent."
    accepted_task_types = ["route"]
    handoff_targets = ["intake", "review"]

    async def execute(
        self,
        input_envelope: AgentInputEnvelope,
        context: AgentExecutionContext,
    ) -> AgentOutputEnvelope:
        target = input_envelope.payload.get("route_to")

        if isinstance(target, str) and target and target in self.handoff_targets:
            return AgentOutputEnvelope(
                agent_id=self.agent_id,
                task_type=input_envelope.task_type,
                status=AgentOutputStatus.HANDED_OFF,
                result={"routed_to": target},
                handoff=HandoffRequest(
                    source_agent_id=self.agent_id,
                    target_agent_id=target,
                    task_type=str(input_envelope.payload.get("target_task_type", target)),
                    payload=input_envelope.payload,
                    context=context,
                ),
                correlation_id=input_envelope.correlation_id,
            )

        if isinstance(target, str) and target:
            return AgentOutputEnvelope(
                agent_id=self.agent_id,
                task_type=input_envelope.task_type,
                status=AgentOutputStatus.FAILED,
                error=AgentError(
                    agent_id=self.agent_id,
                    error_code="invalid_handoff_target",
                    message=f"Unsupported handoff target: {target}.",
                ),
                correlation_id=input_envelope.correlation_id,
            )

        return AgentOutputEnvelope(
            agent_id=self.agent_id,
            task_type=input_envelope.task_type,
            status=AgentOutputStatus.COMPLETED,
            result={"message": "No routing target specified."},
            correlation_id=input_envelope.correlation_id,
        )
