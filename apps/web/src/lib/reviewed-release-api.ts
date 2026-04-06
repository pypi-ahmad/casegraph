import type {
  CreateReleaseBundleRequest,
  ReleaseArtifactListResponse,
  ReleaseBundleCreateResponse,
  ReleaseBundleListResponse,
  ReleaseBundleResponse,
  ReleaseEligibilityResponse,
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

export async function fetchReleases(
  caseId: string,
): Promise<ReleaseBundleListResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/releases`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load release bundles."));
  }
  return (await response.json()) as ReleaseBundleListResponse;
}

export async function createRelease(
  caseId: string,
  payload: CreateReleaseBundleRequest = {},
): Promise<ReleaseBundleCreateResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/releases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to create release bundle."));
  }
  return (await response.json()) as ReleaseBundleCreateResponse;
}

export async function fetchRelease(
  releaseId: string,
): Promise<ReleaseBundleResponse> {
  const response = await fetch(`${API_BASE_URL}/releases/${releaseId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load release bundle."));
  }
  return (await response.json()) as ReleaseBundleResponse;
}

export async function fetchReleaseArtifacts(
  releaseId: string,
): Promise<ReleaseArtifactListResponse> {
  const response = await fetch(`${API_BASE_URL}/releases/${releaseId}/artifacts`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load release artifacts."));
  }
  return (await response.json()) as ReleaseArtifactListResponse;
}

export async function fetchReleaseEligibility(
  caseId: string,
  snapshotId?: string,
): Promise<ReleaseEligibilityResponse> {
  const params = snapshotId ? `?snapshot_id=${encodeURIComponent(snapshotId)}` : "";
  const response = await fetch(
    `${API_BASE_URL}/cases/${caseId}/release-eligibility${params}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load release eligibility."));
  }
  return (await response.json()) as ReleaseEligibilityResponse;
}
