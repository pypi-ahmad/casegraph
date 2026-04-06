"""Playwright MCP tool adapter — configuration and capability boundary.

This module provides the adapter layer between CaseGraph's tool registry
and a Playwright MCP server.  In this foundation step:

- Configuration resolution is real (reads from env / settings).
- The adapter registers as a tool with correct metadata and safety flags.
- Actual browser execution is gated behind implementation_status checks.
- No fake browser sessions or fake screenshots are produced.

When a Playwright MCP server is running locally, the adapter will report
``adapter_only`` status.  Full execution wiring is deferred to a later step.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

from casegraph_agent_sdk.automation import (
    ToolCapabilityFlags,
    ToolMetadata,
)
from app.tools.base import BaseTool, ToolExecutionException

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_MCP_URL = "http://localhost:3100"


def playwright_mcp_url() -> str:
    """Return the configured Playwright MCP server URL."""
    return os.getenv("CASEGRAPH_PLAYWRIGHT_MCP_URL", _DEFAULT_MCP_URL)


def playwright_mcp_origin() -> str:
    """Return a redacted origin for the configured Playwright MCP server."""
    try:
        parsed = urlsplit(playwright_mcp_url())
        if parsed.scheme and parsed.hostname:
            origin = f"{parsed.scheme}://{parsed.hostname}"
            if parsed.port is not None:
                origin = f"{origin}:{parsed.port}"
            return origin
    except ValueError:
        pass

    return "[configured]" if playwright_mcp_configured() else _DEFAULT_MCP_URL


def playwright_mcp_configured() -> bool:
    """Return True if a Playwright MCP URL is explicitly set."""
    return bool(os.getenv("CASEGRAPH_PLAYWRIGHT_MCP_URL"))


# ---------------------------------------------------------------------------
# Adapter tool
# ---------------------------------------------------------------------------


class PlaywrightNavigateTool(BaseTool):
    """Read-only browser navigation tool via Playwright MCP.

    This is the minimal foundational tool — it represents a
    ``browser_navigate`` action with read-only safety defaults.
    Full execution is deferred until the MCP client wiring is added.
    """

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="playwright.navigate",
            version="0.1.0",
            display_name="Playwright Navigate",
            description=(
                "Navigate a browser page to a URL via Playwright MCP. "
                "Read-only — does not perform clicks, form fills, or writes."
            ),
            category="browser_automation",
            safety_level="read_only",
            implementation_status="adapter_only",
            capability_flags=ToolCapabilityFlags(
                read_only=True,
                requires_approval=False,
                requires_browser_session=True,
                requires_computer_use_provider=False,
            ),
        )

    async def _execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        url = parameters.get("url")
        if not url or not isinstance(url, str):
            raise ToolExecutionException(
                "Missing or invalid 'url' parameter.",
                error_code="invalid_parameters",
                recoverable=True,
            )

        # Foundation: adapter boundary only — no actual MCP call yet
        raise ToolExecutionException(
            "Playwright MCP execution is not wired in this foundation step. "
            f"Configured MCP origin: {playwright_mcp_origin()}",
            error_code="not_wired",
            recoverable=False,
        )


class PlaywrightSnapshotTool(BaseTool):
    """Read-only page snapshot tool via Playwright MCP.

    Returns an accessibility snapshot of the current page.
    Full execution is deferred until the MCP client wiring is added.
    """

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="playwright.snapshot",
            version="0.1.0",
            display_name="Playwright Snapshot",
            description=(
                "Capture an accessibility snapshot of the current page "
                "via Playwright MCP. Read-only, no browser mutations."
            ),
            category="browser_automation",
            safety_level="read_only",
            implementation_status="adapter_only",
            capability_flags=ToolCapabilityFlags(
                read_only=True,
                requires_approval=False,
                requires_browser_session=True,
                requires_computer_use_provider=False,
            ),
        )

    async def _execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        raise ToolExecutionException(
            "Playwright MCP execution is not wired in this foundation step. "
            f"Configured MCP origin: {playwright_mcp_origin()}",
            error_code="not_wired",
            recoverable=False,
        )
