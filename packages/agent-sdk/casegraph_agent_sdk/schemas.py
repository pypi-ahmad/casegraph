"""Backward-compatible re-exports — prefer importing from agents module directly."""

from casegraph_agent_sdk.agents import AgentInputEnvelope as AgentRequest
from casegraph_agent_sdk.agents import AgentOutputEnvelope as AgentResponse

__all__ = ["AgentRequest", "AgentResponse"]
