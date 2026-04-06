import type {
  AutomationPlanGenerateResponse,
  AutomationPlanResponse,
  CreateSubmissionDraftRequest,
  GenerateAutomationPlanRequest,
  SubmissionApprovalUpdateResponse,
  SubmissionDraftCreateResponse,
  SubmissionDraftDetailResponse,
  SubmissionDraftListResponse,
  SubmissionTargetListResponse,
  UpdateSubmissionApprovalRequest,
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

export async function fetchSubmissionTargets(): Promise<SubmissionTargetListResponse> {
  const response = await fetch(`${API_BASE_URL}/submission/targets`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load submission targets."));
  }
  return (await response.json()) as SubmissionTargetListResponse;
}

export async function createSubmissionDraft(
  caseId: string,
  payload: CreateSubmissionDraftRequest,
): Promise<SubmissionDraftCreateResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/submission-drafts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to create submission draft."));
  }
  return (await response.json()) as SubmissionDraftCreateResponse;
}

export async function fetchSubmissionDrafts(
  caseId: string,
): Promise<SubmissionDraftListResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/submission-drafts`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load submission drafts."));
  }
  return (await response.json()) as SubmissionDraftListResponse;
}

export async function fetchSubmissionDraftDetail(
  draftId: string,
): Promise<SubmissionDraftDetailResponse> {
  const response = await fetch(`${API_BASE_URL}/submission-drafts/${draftId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load submission draft detail."));
  }
  return (await response.json()) as SubmissionDraftDetailResponse;
}

export async function generateSubmissionPlan(
  draftId: string,
  payload: GenerateAutomationPlanRequest = { dry_run: true },
): Promise<AutomationPlanGenerateResponse> {
  const response = await fetch(`${API_BASE_URL}/submission-drafts/${draftId}/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to generate automation plan."));
  }
  return (await response.json()) as AutomationPlanGenerateResponse;
}

export async function fetchSubmissionPlan(
  draftId: string,
): Promise<AutomationPlanResponse> {
  const response = await fetch(`${API_BASE_URL}/submission-drafts/${draftId}/plan`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load automation plan."));
  }
  return (await response.json()) as AutomationPlanResponse;
}

export async function updateSubmissionApproval(
  draftId: string,
  payload: UpdateSubmissionApprovalRequest,
): Promise<SubmissionApprovalUpdateResponse> {
  const response = await fetch(`${API_BASE_URL}/submission-drafts/${draftId}/approval`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to update approval metadata."));
  }
  return (await response.json()) as SubmissionApprovalUpdateResponse;
}