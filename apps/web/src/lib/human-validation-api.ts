import type {
  ExtractionValidationsResponse,
  FieldValidationResponse,
  RequirementReviewResponse,
  RequirementReviewsResponse,
  ReviewedCaseStateResponse,
  ValidateFieldRequest,
  ReviewRequirementRequest,
} from "@casegraph/agent-sdk";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    ...init,
  });
  if (!response.ok) {
    let message = `Request failed: ${path}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (typeof payload.detail === "string" && payload.detail) {
        message = payload.detail;
      }
    } catch {
      // ignore parse errors
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function fetchReviewedCaseState(
  caseId: string,
): Promise<ReviewedCaseStateResponse> {
  return apiFetch<ReviewedCaseStateResponse>(
    `/cases/${encodeURIComponent(caseId)}/review-state`,
  );
}

export async function fetchExtractionValidations(
  caseId: string,
): Promise<ExtractionValidationsResponse> {
  return apiFetch<ExtractionValidationsResponse>(
    `/cases/${encodeURIComponent(caseId)}/extraction-validations`,
  );
}

export async function fetchRequirementReviews(
  caseId: string,
): Promise<RequirementReviewsResponse> {
  return apiFetch<RequirementReviewsResponse>(
    `/cases/${encodeURIComponent(caseId)}/requirement-reviews`,
  );
}

export async function validateField(
  extractionId: string,
  fieldId: string,
  request: ValidateFieldRequest,
): Promise<FieldValidationResponse> {
  return apiFetch<FieldValidationResponse>(
    `/extractions/${encodeURIComponent(extractionId)}/fields/${encodeURIComponent(fieldId)}/validate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
  );
}

export async function reviewRequirement(
  caseId: string,
  itemId: string,
  request: ReviewRequirementRequest,
): Promise<RequirementReviewResponse> {
  return apiFetch<RequirementReviewResponse>(
    `/cases/${encodeURIComponent(caseId)}/checklist/items/${encodeURIComponent(itemId)}/review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
  );
}
