/**
 * Shared evaluation and observability contracts for the CaseGraph platform.
 *
 * These types describe:
 *   - eval/observability capabilities endpoint (existing)
 *   - workflow evaluation suites, cases, assertions, and runs (new)
 *   - fixture metadata and provider comparison metadata
 *
 * These contracts describe evaluation infrastructure — not benchmark
 * results, scorecards, or production quality claims.
 */

import type { WorkflowPackId } from "./workflow-packs";

// ---------------------------------------------------------------------------
// Integration status (existing)
// ---------------------------------------------------------------------------

export type IntegrationStatus = "configured" | "available" | "not_configured";

export interface IntegrationInfo {
  id: string;
  display_name: string;
  status: IntegrationStatus;
  notes: string[];
}

// ---------------------------------------------------------------------------
// Benchmark suite metadata (existing)
// ---------------------------------------------------------------------------

export type BenchmarkCategory =
  | "provider_comparison"
  | "retrieval"
  | "agent_workflow"
  | "custom";

export interface BenchmarkSuiteMeta {
  id: string;
  display_name: string;
  category: BenchmarkCategory;
  description: string;
  /** Relative path to the Promptfoo config file from the repo root. */
  config_path: string;
}

// ---------------------------------------------------------------------------
// Capabilities response (existing)
// ---------------------------------------------------------------------------

export interface EvalCapabilitiesResponse {
  integrations: IntegrationInfo[];
  benchmark_suites: BenchmarkSuiteMeta[];
  limitations: string[];
}

// ---------------------------------------------------------------------------
// Eval identifiers
// ---------------------------------------------------------------------------

export type EvalSuiteId = string;
export type EvalCaseId = string;
export type EvalRunId = string;

// ---------------------------------------------------------------------------
// Eval target and assertion type literals
// ---------------------------------------------------------------------------

export type EvalTargetType =
  | "workflow_pack"
  | "extraction_template"
  | "communication_draft_template"
  | "provider_task"
  | "readiness_evaluation";

export type EvalSuiteCategory =
  | "workflow_regression"
  | "extraction_quality"
  | "provider_comparison"
  | "readiness_assertion"
  | "communication_draft"
  | "packet_assertion"
  | "composite";

export type AssertionType =
  | "status_equals"
  | "field_present"
  | "field_absent"
  | "minimum_item_count"
  | "required_reference_present"
  | "requirement_status_expected"
  | "section_generated"
  | "blocked_state_expected";

export type AssertionResultStatus = "pass" | "fail" | "error" | "skipped";

export type EvalRunStatus =
  | "created"
  | "running"
  | "completed"
  | "completed_partial"
  | "failed";

// ---------------------------------------------------------------------------
// Assertions
// ---------------------------------------------------------------------------

export interface EvalAssertion {
  assertion_id: string;
  assertion_type: AssertionType;
  target_path: string;
  expected_value: unknown;
  description: string;
}

export interface EvalAssertionResult {
  assertion_id: string;
  assertion_type: AssertionType;
  status: AssertionResultStatus;
  actual_value: unknown;
  expected_value: unknown;
  message: string;
}

// ---------------------------------------------------------------------------
// Fixture metadata
// ---------------------------------------------------------------------------

export interface EvalFixtureMeta {
  fixture_id: string;
  display_name: string;
  description: string;
  domain_pack_id: string;
  case_type_id: string;
  document_filenames: string[];
  notes: string[];
}

// ---------------------------------------------------------------------------
// Eval case and suite
// ---------------------------------------------------------------------------

export interface EvalCaseDefinition {
  case_id: EvalCaseId;
  display_name: string;
  description: string;
  fixture: EvalFixtureMeta;
  assertions: EvalAssertion[];
}

export interface EvalSuiteDefinition {
  suite_id: EvalSuiteId;
  display_name: string;
  description: string;
  category: EvalSuiteCategory;
  target_type: EvalTargetType;
  target_ids: string[];
  cases: EvalCaseDefinition[];
  limitations: string[];
}

// ---------------------------------------------------------------------------
// Eval run results
// ---------------------------------------------------------------------------

export interface EvalCaseResult {
  case_id: EvalCaseId;
  display_name: string;
  status: AssertionResultStatus;
  assertion_results: EvalAssertionResult[];
  duration_ms: number;
  error_message: string;
  notes: string[];
}

export interface EvalRunRecord {
  run_id: EvalRunId;
  suite_id: EvalSuiteId;
  status: EvalRunStatus;
  case_results: EvalCaseResult[];
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  error_cases: number;
  skipped_cases: number;
  started_at: string;
  completed_at: string;
  duration_ms: number;
  notes: string[];
}

// ---------------------------------------------------------------------------
// Provider comparison
// ---------------------------------------------------------------------------

export interface ProviderComparisonEntry {
  provider_id: string;
  model_id: string;
  completed: boolean;
  error_message: string;
  latency_ms: number;
  output_summary: string;
  notes: string[];
}

export interface ProviderComparisonResult {
  task_description: string;
  entries: ProviderComparisonEntry[];
  notes: string[];
}

// ---------------------------------------------------------------------------
// Domain-scoped eval summaries
// ---------------------------------------------------------------------------

export interface WorkflowEvalSummary {
  workflow_pack_id: string;
  total_assertions: number;
  passed: number;
  failed: number;
  errors: number;
  notes: string[];
}

export interface ExtractionEvalSummary {
  template_id: string;
  total_assertions: number;
  passed: number;
  failed: number;
  notes: string[];
}

export interface ReadinessEvalSummary {
  total_assertions: number;
  passed: number;
  failed: number;
  notes: string[];
}

export interface CommunicationDraftEvalSummary {
  total_assertions: number;
  passed: number;
  failed: number;
  notes: string[];
}

export interface PacketEvalSummary {
  total_assertions: number;
  passed: number;
  failed: number;
  notes: string[];
}

// ---------------------------------------------------------------------------
// API responses
// ---------------------------------------------------------------------------

export interface EvalSuiteListResponse {
  suites: EvalSuiteDefinition[];
}

export interface EvalSuiteDetailResponse {
  definition: EvalSuiteDefinition;
}

export interface EvalRunResponse {
  success: boolean;
  message: string;
  run: EvalRunRecord;
}

export interface EvalRunDetailResponse {
  run: EvalRunRecord;
  suite_display_name: string;
}
