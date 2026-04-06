/**
 * Shared agent contracts for the CaseGraph platform.
 *
 * These types define the envelopes, metadata, handoff structures,
 * and result/error normalization used across all agents and workflows.
 */

// ---------------------------------------------------------------------------
// Agent capability
// ---------------------------------------------------------------------------

export type AgentCapabilityStatus = "implemented" | "placeholder" | "not_modeled";

export interface AgentCapability {
  id: string;
  display_name: string;
  status: AgentCapabilityStatus;
}

// ---------------------------------------------------------------------------
// Agent metadata
// ---------------------------------------------------------------------------

export interface AgentMetadata {
  id: string;
  display_name: string;
  description: string;
  capabilities: AgentCapability[];
  accepted_task_types: string[];
  handoff_targets: string[];
}

export interface AgentsResponse {
  agents: AgentMetadata[];
}

// ---------------------------------------------------------------------------
// Execution context
// ---------------------------------------------------------------------------

export interface AgentExecutionContext {
  workflow_run_id: string | null;
  step_index: number | null;
  caller_agent_id: string | null;
  correlation_id: string | null;
}

// ---------------------------------------------------------------------------
// Agent input / output envelopes
// ---------------------------------------------------------------------------

export interface AgentInputEnvelope {
  task_type: string;
  payload: Record<string, unknown>;
  context: AgentExecutionContext | null;
  correlation_id: string | null;
}

export type AgentOutputStatus = "completed" | "failed" | "handed_off";

export interface AgentError {
  agent_id: string;
  error_code: string;
  message: string;
}

export interface AgentOutputEnvelope {
  agent_id: string;
  task_type: string;
  status: AgentOutputStatus;
  result: Record<string, unknown> | null;
  error: AgentError | null;
  handoff: HandoffRequest | null;
  correlation_id: string | null;
}

// ---------------------------------------------------------------------------
// Handoff
// ---------------------------------------------------------------------------

export interface HandoffRequest {
  source_agent_id: string;
  target_agent_id: string;
  task_type: string;
  payload: Record<string, unknown>;
  context: AgentExecutionContext | null;
}

export interface HandoffResult {
  source_agent_id: string;
  target_agent_id: string;
  accepted: boolean;
  result: AgentOutputEnvelope | null;
  error: AgentError | null;
}

// ---------------------------------------------------------------------------
// Workflow execution
// ---------------------------------------------------------------------------

export type WorkflowRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface WorkflowStepResult {
  step_id: string;
  agent_id: string;
  status: AgentOutputStatus;
  result: Record<string, unknown> | null;
  error: AgentError | null;
  started_at: string | null;
  completed_at: string | null;
}
