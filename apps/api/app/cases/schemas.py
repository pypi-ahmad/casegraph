"""Router-level query and response helpers for the case module."""

from __future__ import annotations

from pydantic import BaseModel, Field

from casegraph_agent_sdk.cases import CaseStatus


class CaseListFilters(BaseModel):
    status: CaseStatus | None = None
    limit: int = Field(default=100, ge=1, le=250)
