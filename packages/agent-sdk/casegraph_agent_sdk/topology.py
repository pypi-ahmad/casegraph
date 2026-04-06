"""Visual topology contracts for the CaseGraph platform.

These types describe the normalized graph structure used to render
agent/workflow topology in the frontend.  The backend derives this
from the existing agent and workflow registries.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


TopologyNodeCategory = Literal["agent", "workflow", "service"]
TopologyEdgeType = Literal["handoff", "step", "membership"]


class TopologyNode(BaseModel):
    id: str
    label: str
    category: TopologyNodeCategory
    description: str | None = None
    meta: dict[str, object] = Field(default_factory=dict)


class TopologyEdge(BaseModel):
    id: str
    source: str
    target: str
    type: TopologyEdgeType
    label: str | None = None


class TopologyResponse(BaseModel):
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]


__all__ = [
    "TopologyEdge",
    "TopologyEdgeType",
    "TopologyNode",
    "TopologyNodeCategory",
    "TopologyResponse",
]
