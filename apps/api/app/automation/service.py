"""Automation capability metadata service.

Aggregates tool metadata from the agent-runtime, Playwright MCP
configuration status, and computer-use provider capability metadata
into a single ``AutomationCapabilitiesResponse``.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlsplit

import httpx

from casegraph_agent_sdk.automation import (
    AutomationBackend,
    AutomationCapabilitiesResponse,
    ComputerUseProviderMeta,
    ToolMetadata,
    default_computer_use_providers,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Playwright MCP config helpers (mirror from agent-runtime)
# ---------------------------------------------------------------------------

def playwright_mcp_url() -> str:
    return os.getenv("CASEGRAPH_PLAYWRIGHT_MCP_URL", "http://localhost:3100")


def playwright_mcp_origin() -> str:
    try:
        parsed = urlsplit(playwright_mcp_url())
        if parsed.scheme and parsed.hostname:
            origin = f"{parsed.scheme}://{parsed.hostname}"
            if parsed.port is not None:
                origin = f"{origin}:{parsed.port}"
            return origin
    except ValueError:
        pass

    return "[configured]" if playwright_mcp_configured() else "http://localhost:3100"


def playwright_mcp_configured() -> bool:
    return bool(os.getenv("CASEGRAPH_PLAYWRIGHT_MCP_URL"))


# ---------------------------------------------------------------------------
# Computer-use provider metadata (static)
# ---------------------------------------------------------------------------

_COMPUTER_USE_PROVIDERS: list[ComputerUseProviderMeta] = default_computer_use_providers()


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

def _build_backends() -> list[AutomationBackend]:
    return [
        AutomationBackend(
            id="playwright_mcp",
            display_name="Playwright MCP",
            status="implemented",
            notes=[
                "Approval-gated execution can perform real read-only browser_navigate calls through the execution service.",
                f"Configured MCP origin: {playwright_mcp_origin()}",
                "Explicitly configured: " + ("yes" if playwright_mcp_configured() else "no"),
                "Browser writes, uploads, and final submission remain blocked by execution guardrails.",
            ],
        ),
        AutomationBackend(
            id="computer_use",
            display_name="Computer Use (Provider)",
            status="planned",
            notes=[
                "Provider abstraction and capability metadata defined.",
                "No provider-specific execution adapters are wired yet.",
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Limitations
# ---------------------------------------------------------------------------

_LIMITATIONS: list[str] = [
    "Read-only navigate execution exists only through the approval-gated automation run flow, not through the capability inspector.",
    "Only deterministic Playwright navigate steps execute real browser actions in this build.",
    "Computer-use provider execution is not implemented — only capability metadata exists.",
    "Step-level operator approval checkpoints exist for supervised runs, but there is no broader multi-party approval workflow yet.",
    "No browser preview, screenshot stream, session replay, or generic tool runner is exposed.",
    "No domain-specific automation tools (medical, insurance, tax).",
    "The automation inspector page is a capability inspector only — not the supervised run workspace.",
]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AutomationService:
    """Builds automation capabilities by combining local metadata with
    tool metadata fetched from the agent-runtime."""

    def __init__(self, runtime_base_url: str, timeout_seconds: float) -> None:
        self._runtime_url = runtime_base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds)

    async def get_capabilities(self) -> AutomationCapabilitiesResponse:
        tools = await self._fetch_tools()
        return AutomationCapabilitiesResponse(
            tools=tools,
            backends=_build_backends(),
            computer_use_providers=list(_COMPUTER_USE_PROVIDERS),
            limitations=list(_LIMITATIONS),
        )

    async def get_tools(self) -> list[ToolMetadata]:
        return await self._fetch_tools()

    async def _fetch_tools(self) -> list[ToolMetadata]:
        """Fetch tool metadata from the agent-runtime /tools endpoint."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(f"{self._runtime_url}/tools")
                resp.raise_for_status()
                data = resp.json()
                return [ToolMetadata(**t) for t in data.get("tools", [])]
        except Exception:
            logger.warning("Could not fetch tools from agent-runtime.", exc_info=True)
            return []
