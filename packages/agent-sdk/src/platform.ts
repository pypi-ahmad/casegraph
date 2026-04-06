/**
 * Platform status types — module maturity tracking.
 */

// ---------------------------------------------------------------------------
// Maturity labels
// ---------------------------------------------------------------------------

/**
 * - **stable**: Regression-gated, cross-layer tested, hardened.
 * - **implemented**: Working logic + endpoints + tests, not yet hardened.
 * - **scaffolded**: Router exists, logic is thin / proxy / stub.
 * - **planned**: Directory or placeholder only.
 */
export type ModuleMaturity =
  | "stable"
  | "implemented"
  | "scaffolded"
  | "planned";

// ---------------------------------------------------------------------------
// Module status entry
// ---------------------------------------------------------------------------

export interface ModuleStatusEntry {
  module_id: string;
  display_name: string;
  maturity: ModuleMaturity;
  route_count: number;
  has_db_models: boolean;
  has_tests: boolean;
  has_regression_gate: boolean;
  notes: string;
}

// ---------------------------------------------------------------------------
// Platform status response
// ---------------------------------------------------------------------------

export interface PlatformStatusResponse {
  modules: ModuleStatusEntry[];
  total_modules: number;
  stable_count: number;
  implemented_count: number;
  scaffolded_count: number;
  planned_count: number;
}
