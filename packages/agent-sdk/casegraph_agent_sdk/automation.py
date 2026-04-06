"""Shared automation and tool contracts for the CaseGraph platform.

Foundation-level types for tool metadata, execution envelopes, browser
session metadata, computer-use provider capability metadata, and automation
capability discovery.

Domain-specific tool definitions, full execution engines, and session replay
are intentionally not included in this step.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Tool identity & categorisation
# ---------------------------------------------------------------------------

ToolCategory = Literal[
    "browser_automation",
    "computer_use",
    "file_system",
    "data_retrieval",
    "custom",
]

ToolImplementationStatus = Literal["implemented", "adapter_only", "planned"]

ToolSafetyLevel = Literal["read_only", "approval_required", "unrestricted"]

# ---------------------------------------------------------------------------
# Tool metadata
# ---------------------------------------------------------------------------


class ToolCapabilityFlags(BaseModel):
    read_only: bool = True
    requires_approval: bool = False
    requires_browser_session: bool = False
    requires_computer_use_provider: bool = False


class ToolMetadata(BaseModel):
    id: str
    version: str = "0.1.0"
    display_name: str
    description: str
    category: ToolCategory
    safety_level: ToolSafetyLevel = "read_only"
    implementation_status: ToolImplementationStatus = "planned"
    capability_flags: ToolCapabilityFlags = Field(default_factory=ToolCapabilityFlags)


# ---------------------------------------------------------------------------
# Tool execution request / result
# ---------------------------------------------------------------------------

ToolExecutionStatus = Literal["success", "error", "approval_required", "not_implemented"]


class ToolExecutionRequest(BaseModel):
    tool_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    dry_run: bool = False


class ToolExecutionError(BaseModel):
    error_code: str
    message: str
    recoverable: bool = False


class ToolExecutionResult(BaseModel):
    tool_id: str
    status: ToolExecutionStatus
    output: dict[str, Any] | None = None
    error: ToolExecutionError | None = None
    duration_ms: float | None = None
    correlation_id: str | None = None


# ---------------------------------------------------------------------------
# Browser session metadata (Playwright MCP)
# ---------------------------------------------------------------------------

BrowserSessionStatus = Literal["not_started", "active", "closed", "error"]


class BrowserSessionMetadata(BaseModel):
    session_id: str | None = None
    status: BrowserSessionStatus = "not_started"
    mcp_server_url: str | None = None
    browser_type: str | None = None
    headless: bool = True


# ---------------------------------------------------------------------------
# Computer-use provider capability metadata
# ---------------------------------------------------------------------------

ComputerUseSupport = Literal["supported", "not_supported", "unknown"]


class ComputerUseProviderMeta(BaseModel):
    provider_id: str
    display_name: str
    computer_use_support: ComputerUseSupport = "unknown"
    notes: list[str] = Field(default_factory=list)


def default_computer_use_providers() -> list[ComputerUseProviderMeta]:
    """Return the default computer-use capability metadata set.

    This is intentionally provider-agnostic metadata shared by the API and
    agent-runtime so both surfaces describe the same current support state.
    """

    return [
        ComputerUseProviderMeta(
            provider_id="anthropic",
            display_name="Anthropic",
            computer_use_support="supported",
            notes=[
                "Anthropic Claude models support computer-use via the beta API.",
                "CaseGraph has not wired execution in this foundation step.",
            ],
        ),
        ComputerUseProviderMeta(
            provider_id="openai",
            display_name="OpenAI",
            computer_use_support="unknown",
            notes=[
                "OpenAI has announced computer-use research capabilities.",
                "No stable public API is integrated in CaseGraph yet.",
            ],
        ),
        ComputerUseProviderMeta(
            provider_id="gemini",
            display_name="Gemini",
            computer_use_support="unknown",
            notes=[
                "Google has demonstrated computer-use capabilities in research.",
                "No stable public API is integrated in CaseGraph yet.",
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Automation run metadata
# ---------------------------------------------------------------------------

AutomationRunStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


class AutomationRunMeta(BaseModel):
    run_id: str
    tool_id: str
    status: AutomationRunStatus = "pending"
    started_at: str | None = None
    completed_at: str | None = None


# ---------------------------------------------------------------------------
# Automation backends & capabilities response
# ---------------------------------------------------------------------------


class AutomationBackend(BaseModel):
    id: str
    display_name: str
    status: ToolImplementationStatus = "planned"
    notes: list[str] = Field(default_factory=list)


class AutomationCapabilitiesResponse(BaseModel):
    tools: list[ToolMetadata] = Field(default_factory=list)
    backends: list[AutomationBackend] = Field(default_factory=list)
    computer_use_providers: list[ComputerUseProviderMeta] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
