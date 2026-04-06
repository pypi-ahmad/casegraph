"""Typed workflow definition schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkflowStepDefinition(BaseModel):
    id: str
    display_name: str
    agent_id: str
    description: str | None = None
    depends_on: list[str] = Field(default_factory=list)


class WorkflowDefinition(BaseModel):
    id: str
    display_name: str
    description: str
    steps: list[WorkflowStepDefinition] = Field(default_factory=list)


class WorkflowsResponse(BaseModel):
    workflows: list[WorkflowDefinition]
