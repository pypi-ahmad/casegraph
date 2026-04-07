import type {
  ActionGenerationResponse,
  CaseActionListResponse,
  CaseStageResponse,
  CreateReviewNoteRequest,
  QueueFilterMetadata,
  QueueSummaryResponse,
  ReviewNoteListResponse,
  ReviewNoteResponse,
  ReviewQueueResponse,
  StageHistoryResponse,
  StageTransitionResponse,
  UpdateCaseStageRequest,
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

function toQuery(filters?: Partial<QueueFilterMetadata>): string {
  if (!filters) return "";
  const params = new URLSearchParams();
  if (filters.stage) params.set("stage", filters.stage);
  if (typeof filters.has_missing_items === "boolean") {
    params.set("has_missing_items", String(filters.has_missing_items));
  }
  if (typeof filters.has_open_actions === "boolean") {
    params.set("has_open_actions", String(filters.has_open_actions));
  }
  if (filters.domain_pack_id) params.set("domain_pack_id", filters.domain_pack_id);
  if (filters.case_type_id) params.set("case_type_id", filters.case_type_id);
  if (typeof filters.limit === "number") params.set("limit", String(filters.limit));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function fetchOperatorQueue(
  filters?: Partial<QueueFilterMetadata>,
): Promise<ReviewQueueResponse> {
  const response = await fetch(`${API_BASE_URL}/queue${toQuery(filters)}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load operator queue. Try refreshing the page."));
  }
  return (await response.json()) as ReviewQueueResponse;
}

export async function fetchOperatorQueueSummary(
  filters?: Partial<QueueFilterMetadata>,
): Promise<QueueSummaryResponse> {
  const response = await fetch(`${API_BASE_URL}/queue/summary${toQuery(filters)}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load queue summary. Try refreshing the page."));
  }
  return (await response.json()) as QueueSummaryResponse;
}

export async function fetchCaseStage(caseId: string): Promise<CaseStageResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/stage`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load case stage."));
  }
  return (await response.json()) as CaseStageResponse;
}

export async function transitionCaseStage(
  caseId: string,
  payload: UpdateCaseStageRequest,
): Promise<StageTransitionResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/stage`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to update case stage. Verify the transition is allowed and try again."));
  }
  return (await response.json()) as StageTransitionResponse;
}

export async function fetchStageHistory(caseId: string): Promise<StageHistoryResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/stage-history`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load stage history."));
  }
  return (await response.json()) as StageHistoryResponse;
}

export async function fetchCaseActions(caseId: string): Promise<CaseActionListResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/actions`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load action items."));
  }
  return (await response.json()) as CaseActionListResponse;
}

export async function generateCaseActions(caseId: string): Promise<ActionGenerationResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/actions/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to generate action items. Ensure documents are linked to this case."));
  }
  return (await response.json()) as ActionGenerationResponse;
}

export async function fetchReviewNotes(caseId: string): Promise<ReviewNoteListResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/review-notes`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load review notes."));
  }
  return (await response.json()) as ReviewNoteListResponse;
}

export async function createReviewNote(
  caseId: string,
  payload: CreateReviewNoteRequest,
): Promise<ReviewNoteResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/review-notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to create review note. Check your note content and try again."));
  }
  return (await response.json()) as ReviewNoteResponse;
}