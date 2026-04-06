import type {
  ChecklistItem,
  ChecklistResponse,
  ReadinessResponse,
  UpdateChecklistItemRequest,
} from "@casegraph/agent-sdk";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export class ReadinessApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ReadinessApiError";
    this.status = status;
  }
}

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

export async function fetchChecklist(
  caseId: string,
): Promise<ChecklistResponse> {
  const res = await fetch(`${API_BASE_URL}/cases/${caseId}/checklist`);
  if (!res.ok) {
    throw new ReadinessApiError(
      res.status,
      await getErrorMessage(res, "Failed to fetch checklist"),
    );
  }
  return res.json();
}

export async function generateChecklist(
  caseId: string,
  force = false,
): Promise<ChecklistResponse> {
  const res = await fetch(
    `${API_BASE_URL}/cases/${caseId}/checklist/generate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force }),
    },
  );
  if (!res.ok) {
    throw new ReadinessApiError(
      res.status,
      await getErrorMessage(res, "Failed to generate checklist"),
    );
  }
  return res.json();
}

export async function evaluateChecklist(
  caseId: string,
): Promise<ReadinessResponse> {
  const res = await fetch(
    `${API_BASE_URL}/cases/${caseId}/checklist/evaluate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
  if (!res.ok) {
    throw new ReadinessApiError(
      res.status,
      await getErrorMessage(res, "Failed to evaluate checklist"),
    );
  }
  return res.json();
}

export async function fetchReadiness(
  caseId: string,
): Promise<ReadinessResponse> {
  const res = await fetch(`${API_BASE_URL}/cases/${caseId}/readiness`);
  if (!res.ok) {
    throw new ReadinessApiError(
      res.status,
      await getErrorMessage(res, "Failed to fetch readiness"),
    );
  }
  return res.json();
}

export async function updateChecklistItem(
  caseId: string,
  itemId: string,
  body: UpdateChecklistItemRequest,
): Promise<ChecklistItem> {
  const res = await fetch(
    `${API_BASE_URL}/cases/${caseId}/checklist/items/${itemId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!res.ok) {
    throw new ReadinessApiError(
      res.status,
      await getErrorMessage(res, "Failed to update checklist item"),
    );
  }
  return res.json();
}
