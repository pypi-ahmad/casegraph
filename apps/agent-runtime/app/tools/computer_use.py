"""Computer-use provider abstraction — capability metadata boundary.

This module provides the adapter layer for future computer-use support
across LLM providers (OpenAI, Anthropic, Gemini).  In this foundation step:

- Provider computer-use capability metadata is typed and queryable.
- No real computer-use execution is implemented.
- The metadata connects to the existing BYOK provider IDs.
- When providers ship stable computer-use APIs, concrete adapters
  will implement the ``execute`` method.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from casegraph_agent_sdk.automation import (
    ComputerUseProviderMeta,
    ToolCapabilityFlags,
    ToolMetadata,
    default_computer_use_providers,
)
from app.tools.base import BaseTool, ToolExecutionException

# ---------------------------------------------------------------------------
# Static provider capability metadata
# ---------------------------------------------------------------------------

# These represent which providers have announced or shipped computer-use
# capabilities.  "unknown" means the provider's API may support it
# but we have not integrated or verified it.

COMPUTER_USE_PROVIDERS: list[ComputerUseProviderMeta] = default_computer_use_providers()


def list_computer_use_providers() -> list[ComputerUseProviderMeta]:
    """Return metadata for all known computer-use providers."""
    return list(COMPUTER_USE_PROVIDERS)


# ---------------------------------------------------------------------------
# Base adapter
# ---------------------------------------------------------------------------


class BaseComputerUseAdapter(ABC):
    """Abstract base for provider-specific computer-use adapters.

    Concrete adapters will wrap provider APIs to execute screen-level
    actions (click, type, screenshot, etc.) through LLM-driven
    computer-use flows.
    """

    provider_id: str
    display_name: str

    @abstractmethod
    async def execute_action(
        self,
        action: str,
        parameters: dict[str, Any],
        *,
        api_key: str,
    ) -> dict[str, Any]:
        """Execute a computer-use action via the provider API."""


# ---------------------------------------------------------------------------
# Placeholder tool
# ---------------------------------------------------------------------------


class ComputerUseScreenshotTool(BaseTool):
    """Placeholder computer-use screenshot tool.

    Represents the future ability to take a screenshot via a
    computer-use capable provider.  Execution is not wired.
    """

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="computer_use.screenshot",
            version="0.1.0",
            display_name="Computer-Use Screenshot",
            description=(
                "Take a screenshot of the current desktop/browser viewport "
                "via a computer-use capable provider. Not wired in this step."
            ),
            category="computer_use",
            safety_level="read_only",
            implementation_status="planned",
            capability_flags=ToolCapabilityFlags(
                read_only=True,
                requires_approval=False,
                requires_browser_session=False,
                requires_computer_use_provider=True,
            ),
        )

    async def _execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        raise ToolExecutionException(
            "Computer-use execution is not implemented in this foundation step.",
            error_code="not_implemented",
            recoverable=False,
        )
