"""Shared agent contracts for the CaseGraph platform.

Defines envelopes, metadata, handoff structures, and result/error
normalization used across all agents and workflows.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Agent capability
# ---------------------------------------------------------------------------


class AgentCapabilityStatus(str, Enum):
    IMPLEMENTED = "implemented"
    PLACEHOLDER = "placeholder"
    NOT_MODELED = "not_modeled"


class AgentCapability(BaseModel):
    id: str
    display_name: str
    status: AgentCapabilityStatus


# ---------------------------------------------------------------------------
# Agent metadata
# ---------------------------------------------------------------------------


class AgentMetadata(BaseModel):
    id: str
    display_name: str
    description: str
    capabilities: list[AgentCapability] = Field(default_factory=list)
    accepted_task_types: list[str] = Field(default_factory=list)
    handoff_targets: list[str] = Field(default_factory=list)


class AgentsResponse(BaseModel):
    agents: list[AgentMetadata]


# ---------------------------------------------------------------------------
# Execution context
# ---------------------------------------------------------------------------


class AgentExecutionContext(BaseModel):
    workflow_run_id: str | None = None
    step_index: int | None = None
    caller_agent_id: str | None = None
    correlation_id: str | None = None


# ---------------------------------------------------------------------------
# Agent input / output envelopes
# ---------------------------------------------------------------------------


class AgentInputEnvelope(BaseModel):
    task_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    context: AgentExecutionContext | None = None
    correlation_id: str | None = None


class AgentOutputStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    HANDED_OFF = "handed_off"


class AgentError(BaseModel):
    agent_id: str
    error_code: str
    message: str


class HandoffRequest(BaseModel):
    source_agent_id: str
    target_agent_id: str
    task_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    context: AgentExecutionContext | None = None


class AgentOutputEnvelope(BaseModel):
    agent_id: str
    task_type: str
    status: AgentOutputStatus
    result: dict[str, Any] | None = None
    error: AgentError | None = None
    handoff: HandoffRequest | None = None
    correlation_id: str | None = None


# ---------------------------------------------------------------------------
# Handoff
# ---------------------------------------------------------------------------


class HandoffResult(BaseModel):
    source_agent_id: str
    target_agent_id: str
    accepted: bool
    result: AgentOutputEnvelope | None = None
    error: AgentError | None = None


# ---------------------------------------------------------------------------
# Workflow execution
# ---------------------------------------------------------------------------


class WorkflowRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStepResult(BaseModel):
    step_id: str
    agent_id: str
    status: AgentOutputStatus
    result: dict[str, Any] | None = None
    error: AgentError | None = None
    started_at: str | None = None
    completed_at: str | None = None
