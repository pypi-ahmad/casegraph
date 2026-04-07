import type {
  AssignmentHistoryResponse,
  CaseAssignmentResponse,
  CaseSLAResponse,
  CaseWorkStatusResponse,
  UpdateCaseAssignmentRequest,
  UpdateCaseSLARequest,
  WorkQueueFilters,
  WorkQueueResponse,
  WorkSummaryResponse,
} from "@casegraph/agent-sdk";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

async function getErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (typeof payload.detail === "string" && payload.detail) {
      return payload.detail;
    }
  } catch {
    /* ignore */
  }
  return fallback;
}

function toQuery(filters?: Partial<WorkQueueFilters>): string {
  if (!filters) return "";

  const params = new URLSearchParams();
  if (filters.assignee_id) params.set("assignee_id", filters.assignee_id);
  if (filters.assignment_status) {
    params.set("assignment_status", filters.assignment_status);
  }
  if (filters.sla_state) params.set("sla_state", filters.sla_state);
  if (filters.escalation_state) {
    params.set("escalation_state", filters.escalation_state);
  }
  if (filters.domain_pack_id) params.set("domain_pack_id", filters.domain_pack_id);
  if (filters.case_type_id) params.set("case_type_id", filters.case_type_id);
  if (typeof filters.limit === "number") params.set("limit", String(filters.limit));

  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function fetchWorkQueue(
  filters?: Partial<WorkQueueFilters>,
): Promise<WorkQueueResponse> {
  const response = await fetch(`${API_BASE_URL}/work/queue${toQuery(filters)}`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load work queue. Try refreshing the page."));
  }
  return (await response.json()) as WorkQueueResponse;
}

export async function fetchWorkSummary(
  filters?: Partial<WorkQueueFilters>,
): Promise<WorkSummaryResponse> {
  const response = await fetch(`${API_BASE_URL}/work/summary${toQuery(filters)}`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load work summary. Try refreshing the page."));
  }
  return (await response.json()) as WorkSummaryResponse;
}

export async function fetchCaseWorkStatus(
  caseId: string,
): Promise<CaseWorkStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/work-status`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load case work status. Try refreshing the page."));
  }
  return (await response.json()) as CaseWorkStatusResponse;
}

export async function fetchAssignmentHistory(
  caseId: string,
): Promise<AssignmentHistoryResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/assignment-history`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load assignment history. Try refreshing the page."));
  }
  return (await response.json()) as AssignmentHistoryResponse;
}

export async function updateCaseAssignment(
  caseId: string,
  payload: UpdateCaseAssignmentRequest,
): Promise<CaseAssignmentResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/assignment`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to update assignment. Verify the selected operator and try again."));
  }
  return (await response.json()) as CaseAssignmentResponse;
}

export async function updateCaseSLA(
  caseId: string,
  payload: UpdateCaseSLARequest,
): Promise<CaseSLAResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/sla`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to update deadline. Confirm that the due date is valid and try again."));
  }
  return (await response.json()) as CaseSLAResponse;
}