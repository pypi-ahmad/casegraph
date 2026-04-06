import type {
  CreateReviewedSnapshotRequest,
  HandoffEligibilityResponse,
  ReviewedSnapshotCreateResponse,
  ReviewedSnapshotListResponse,
  ReviewedSnapshotResponse,
  ReviewedSnapshotSelectResponse,
  ReviewedSnapshotSignOffResponse,
  SignOffReviewedSnapshotRequest,
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

export async function fetchReviewedSnapshots(
  caseId: string,
): Promise<ReviewedSnapshotListResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/reviewed-snapshots`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load reviewed snapshots."));
  }
  return (await response.json()) as ReviewedSnapshotListResponse;
}

export async function createReviewedSnapshot(
  caseId: string,
  payload: CreateReviewedSnapshotRequest = {},
): Promise<ReviewedSnapshotCreateResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/reviewed-snapshots`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to create reviewed snapshot."));
  }
  return (await response.json()) as ReviewedSnapshotCreateResponse;
}

export async function fetchReviewedSnapshot(
  snapshotId: string,
): Promise<ReviewedSnapshotResponse> {
  const response = await fetch(`${API_BASE_URL}/reviewed-snapshots/${snapshotId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load reviewed snapshot."));
  }
  return (await response.json()) as ReviewedSnapshotResponse;
}

export async function signoffReviewedSnapshot(
  snapshotId: string,
  payload: SignOffReviewedSnapshotRequest,
): Promise<ReviewedSnapshotSignOffResponse> {
  const response = await fetch(`${API_BASE_URL}/reviewed-snapshots/${snapshotId}/signoff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to sign off reviewed snapshot."));
  }
  return (await response.json()) as ReviewedSnapshotSignOffResponse;
}

export async function fetchHandoffEligibility(
  caseId: string,
): Promise<HandoffEligibilityResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/handoff-eligibility`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load handoff eligibility."));
  }
  return (await response.json()) as HandoffEligibilityResponse;
}

export async function selectReviewedSnapshotForHandoff(
  caseId: string,
  snapshotId: string,
): Promise<ReviewedSnapshotSelectResponse> {
  const response = await fetch(
    `${API_BASE_URL}/cases/${caseId}/reviewed-snapshots/${snapshotId}/select-for-handoff`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to select reviewed snapshot for handoff."));
  }
  return (await response.json()) as ReviewedSnapshotSelectResponse;
}