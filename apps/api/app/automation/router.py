"""Route handlers for automation/tool capability metadata."""

from __future__ import annotations

from fastapi import APIRouter

from casegraph_agent_sdk.automation import (
    AutomationCapabilitiesResponse,
    ToolMetadata,
)
from app.automation.service import AutomationService
from app.config import settings

router = APIRouter(prefix="/automation", tags=["automation"])

_service = AutomationService(
    runtime_base_url=settings.agent_runtime_url,
    timeout_seconds=settings.agent_runtime_timeout_seconds,
)


@router.get("/capabilities", response_model=AutomationCapabilitiesResponse)
async def automation_capabilities() -> AutomationCapabilitiesResponse:
    """Return metadata about registered tools, automation backends,
    computer-use provider support, and current limitations."""
    return await _service.get_capabilities()


@router.get("/tools", response_model=list[ToolMetadata])
async def automation_tools() -> list[ToolMetadata]:
    """Return metadata for all registered automation tools."""
    return await _service.get_tools()
