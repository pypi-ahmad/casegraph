"""Tool registry — singleton that tracks all registered automation tools."""

from __future__ import annotations

from casegraph_agent_sdk.automation import ToolMetadata

from app.tools.base import BaseTool


class ToolRegistry:
    """Central registry for automation tools.

    Tools register themselves at startup (typically during the lifespan
    hook).  The registry is read by the automation capabilities service
    and the API metadata endpoints.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        meta = tool.metadata()
        self._tools[meta.id] = tool

    def get(self, tool_id: str) -> BaseTool | None:
        return self._tools.get(tool_id)

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def list_metadata(self) -> list[ToolMetadata]:
        return [t.metadata() for t in self._tools.values()]

    def list_ids(self) -> list[str]:
        return list(self._tools.keys())


tool_registry = ToolRegistry()
