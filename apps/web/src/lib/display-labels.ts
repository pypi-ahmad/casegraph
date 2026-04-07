/**
 * Shared display-label maps for enum values across the UI.
 * Keeps operator-facing text consistent and professional.
 */

/* ---- Case status ---- */
const CASE_STATUS_LABELS: Record<string, string> = {
  open: "Open",
  active: "Active",
  on_hold: "On Hold",
  closed: "Closed",
  archived: "Archived",
};

export function caseStatusLabel(status: string): string {
  return CASE_STATUS_LABELS[status] ?? titleCase(status);
}

/* ---- Case stage ---- */
const STAGE_LABELS: Record<string, string> = {
  intake: "Intake",
  document_review: "Document Review",
  readiness_review: "Readiness Review",
  awaiting_documents: "Awaiting Documents",
  ready_for_next_step: "Ready",
  closed_placeholder: "Closed",
};

export function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? titleCase(stage);
}

/* ---- Readiness status ---- */
const READINESS_LABELS: Record<string, string> = {
  not_started: "Not Started",
  in_progress: "In Progress",
  ready: "Ready",
  blocked: "Blocked",
  awaiting_operator_review: "Pending Review",
  escalation_ready: "Needs Escalation",
};

export function readinessLabel(status: string): string {
  return READINESS_LABELS[status] ?? titleCase(status);
}

/* ---- Downstream source mode ---- */
const SOURCE_MODE_LABELS: Record<string, string> = {
  live_case_state: "Current case data",
  reviewed_snapshot: "Approved review version",
};

export function sourceModeLabel(mode: string): string {
  return SOURCE_MODE_LABELS[mode] ?? titleCase(mode);
}

/* ---- Action item categories ---- */
const ACTION_CATEGORY_LABELS: Record<string, string> = {
  missing_document: "Missing Document",
  needs_review: "Needs Review",
  extraction_followup: "Extraction Follow-up",
  workflow_next_step: "Next Step",
  compliance_gap: "Compliance Gap",
  general: "General",
};

export function actionCategoryLabel(category: string): string {
  return ACTION_CATEGORY_LABELS[category] ?? titleCase(category);
}

/* ---- Generic title-case fallback ---- */
export function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/* ---- Short reference for internal IDs ---- */
/**
 * Truncates a long technical ID (e.g. UUID) to a short reference.
 * Returns the first 8 characters followed by "…".
 * Short values and blanks are returned as-is.
 */
export function shortRef(id: string | null | undefined): string {
  if (!id) return "—";
  return id.length > 12 ? id.slice(0, 8) + "…" : id;
}
