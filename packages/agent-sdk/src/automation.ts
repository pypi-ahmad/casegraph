/**
 * Shared automation and tool contracts for the CaseGraph platform.
 *
 * These types define tool metadata, execution envelopes, browser session
 * metadata, computer-use provider capability metadata, and automation
 * capability discovery responses.
 *
 * This is a foundation-level contract set. Domain-specific tool definitions,
 * full execution engines, and session replay are intentionally not included.
 */

// ---------------------------------------------------------------------------
// Tool identity & categorisation
// ---------------------------------------------------------------------------

export type ToolCategory =
  | "browser_automation"
  | "computer_use"
  | "file_system"
  | "data_retrieval"
  | "custom";

export type ToolImplementationStatus = "implemented" | "adapter_only" | "planned";

export type ToolSafetyLevel = "read_only" | "approval_required" | "unrestricted";

export interface ToolId {
  id: string;
  version: string;
}

// ---------------------------------------------------------------------------
// Tool metadata
// ---------------------------------------------------------------------------

export interface ToolCapabilityFlags {
  /** Tool can be invoked without side-effects */
  read_only: boolean;
  /** Tool requires explicit approval before execution */
  requires_approval: boolean;
  /** Tool needs a live browser session (Playwright MCP) */
  requires_browser_session: boolean;
  /** Tool needs a computer-use capable provider */
  requires_computer_use_provider: boolean;
}

export interface ToolMetadata {
  id: string;
  version: string;
  display_name: string;
  description: string;
  category: ToolCategory;
  safety_level: ToolSafetyLevel;
  implementation_status: ToolImplementationStatus;
  capability_flags: ToolCapabilityFlags;
}

// ---------------------------------------------------------------------------
// Tool execution request / result
// ---------------------------------------------------------------------------

export type ToolExecutionStatus = "success" | "error" | "approval_required" | "not_implemented";

export interface ToolExecutionRequest {
  tool_id: string;
  parameters: Record<string, unknown>;
  correlation_id: string | null;
  /** If true, skip actual execution and return metadata only */
  dry_run: boolean;
}

export interface ToolExecutionError {
  error_code: string;
  message: string;
  recoverable: boolean;
}

export interface ToolExecutionResult {
  tool_id: string;
  status: ToolExecutionStatus;
  output: Record<string, unknown> | null;
  error: ToolExecutionError | null;
  duration_ms: number | null;
  correlation_id: string | null;
}

// ---------------------------------------------------------------------------
// Browser session metadata (Playwright MCP)
// ---------------------------------------------------------------------------

export type BrowserSessionStatus = "not_started" | "active" | "closed" | "error";

export interface BrowserSessionMetadata {
  session_id: string | null;
  status: BrowserSessionStatus;
  /** Which Playwright MCP config is driving this session */
  mcp_server_url: string | null;
  browser_type: string | null;
  headless: boolean;
}

// ---------------------------------------------------------------------------
// Computer-use provider capability metadata
// ---------------------------------------------------------------------------

export type ComputerUseSupport = "supported" | "not_supported" | "unknown";

export interface ComputerUseProviderMeta {
  provider_id: string;
  display_name: string;
  computer_use_support: ComputerUseSupport;
  notes: string[];
}

// ---------------------------------------------------------------------------
// Automation run metadata
// ---------------------------------------------------------------------------

export type AutomationRunStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export interface AutomationRunMeta {
  run_id: string;
  tool_id: string;
  status: AutomationRunStatus;
  started_at: string | null;
  completed_at: string | null;
}

// ---------------------------------------------------------------------------
// Automation capabilities response
// ---------------------------------------------------------------------------

export interface AutomationBackend {
  id: string;
  display_name: string;
  /** "implemented" | "adapter_only" | "planned" */
  status: ToolImplementationStatus;
  notes: string[];
}

export interface AutomationCapabilitiesResponse {
  tools: ToolMetadata[];
  backends: AutomationBackend[];
  computer_use_providers: ComputerUseProviderMeta[];
  limitations: string[];
}
