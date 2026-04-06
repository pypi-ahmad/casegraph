import type {
  CommunicationDraftDetailResponse,
  CommunicationDraftGenerateRequest,
  CommunicationDraftGenerateResponse,
  CommunicationDraftListResponse,
  CommunicationDraftReviewUpdateRequest,
  CommunicationDraftReviewUpdateResponse,
  CommunicationDraftSourceResponse,
  CommunicationTemplateListResponse,
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

export async function fetchCommunicationTemplates(): Promise<CommunicationTemplateListResponse> {
  const response = await fetch(`${API_BASE_URL}/communication/templates`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load communication templates."));
  }
  return (await response.json()) as CommunicationTemplateListResponse;
}

export async function createCommunicationDraft(
  caseId: string,
  payload: CommunicationDraftGenerateRequest,
): Promise<CommunicationDraftGenerateResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/communication-drafts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to create communication draft."));
  }
  return (await response.json()) as CommunicationDraftGenerateResponse;
}

export async function fetchCommunicationDrafts(
  caseId: string,
): Promise<CommunicationDraftListResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/communication-drafts`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load communication drafts."));
  }
  return (await response.json()) as CommunicationDraftListResponse;
}

export async function fetchCommunicationDraftDetail(
  draftId: string,
): Promise<CommunicationDraftDetailResponse> {
  const response = await fetch(`${API_BASE_URL}/communication-drafts/${draftId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load communication draft detail."));
  }
  return (await response.json()) as CommunicationDraftDetailResponse;
}

export async function fetchCommunicationDraftSources(
  draftId: string,
): Promise<CommunicationDraftSourceResponse> {
  const response = await fetch(`${API_BASE_URL}/communication-drafts/${draftId}/sources`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load communication draft sources."));
  }
  return (await response.json()) as CommunicationDraftSourceResponse;
}

export async function updateCommunicationDraftReview(
  draftId: string,
  payload: CommunicationDraftReviewUpdateRequest,
): Promise<CommunicationDraftReviewUpdateResponse> {
  const response = await fetch(`${API_BASE_URL}/communication-drafts/${draftId}/review`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to update communication draft review metadata."));
  }
  return (await response.json()) as CommunicationDraftReviewUpdateResponse;
}