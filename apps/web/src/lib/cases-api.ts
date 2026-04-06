import type {
  CaseDetailResponse,
  CaseListResponse,
  CaseRecord,
  CreateCaseRequest,
  DocumentRegistryListResponse,
  LinkCaseDocumentRequest,
  UpdateCaseRequest,
  WorkflowRunRecord,
  WorkflowRunRequest,
  IngestionResultSummary,
  DocumentProcessingStatus,
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
    return fallback;
  }
  return fallback;
}

export async function fetchCases(): Promise<CaseListResponse> {
  const response = await fetch(`${API_BASE_URL}/cases`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load cases."));
  }
  return (await response.json()) as CaseListResponse;
}

export async function createCase(payload: CreateCaseRequest): Promise<CaseRecord> {
  const response = await fetch(`${API_BASE_URL}/cases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to create case."));
  }
  return (await response.json()) as CaseRecord;
}

export async function fetchCaseDetail(caseId: string): Promise<CaseDetailResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load case detail."));
  }
  return (await response.json()) as CaseDetailResponse;
}

export async function updateCase(
  caseId: string,
  payload: UpdateCaseRequest,
): Promise<CaseRecord> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to update case."));
  }
  return (await response.json()) as CaseRecord;
}

export async function fetchPersistedDocuments(options?: {
  status?: DocumentProcessingStatus;
  limit?: number;
}): Promise<DocumentRegistryListResponse> {
  const params = new URLSearchParams();
  if (options?.status) params.set("status", options.status);
  if (typeof options?.limit === "number") params.set("limit", String(options.limit));
  const query = params.size > 0 ? `?${params.toString()}` : "";

  const response = await fetch(`${API_BASE_URL}/documents${query}`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load documents."));
  }
  return (await response.json()) as DocumentRegistryListResponse;
}

export async function linkCaseDocument(
  caseId: string,
  payload: LinkCaseDocumentRequest,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to link document."));
  }
}

export async function createWorkflowRunRecord(
  caseId: string,
  payload: WorkflowRunRequest,
): Promise<WorkflowRunRecord> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to create run record."));
  }
  return (await response.json()) as WorkflowRunRecord;
}