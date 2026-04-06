import type {
  ArtifactLineageResponse,
  AuditTimelineResponse,
  DecisionLedgerResponse,
  LineageResponse,
} from "@casegraph/agent-sdk";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
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

export async function fetchCaseAudit(
  caseId: string,
  filters?: { category?: string; eventType?: string },
): Promise<AuditTimelineResponse> {
  const query = new URLSearchParams();
  if (filters?.category) query.set("category", filters.category);
  if (filters?.eventType) query.set("event_type", filters.eventType);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetch<AuditTimelineResponse>(`/cases/${encodeURIComponent(caseId)}/audit${suffix}`);
}

export async function fetchCaseDecisions(caseId: string): Promise<DecisionLedgerResponse> {
  return apiFetch<DecisionLedgerResponse>(`/cases/${encodeURIComponent(caseId)}/decisions`);
}

export async function fetchCaseLineage(caseId: string): Promise<LineageResponse> {
  return apiFetch<LineageResponse>(`/cases/${encodeURIComponent(caseId)}/lineage`);
}

export async function fetchArtifactLineage(
  artifactType: string,
  artifactId: string,
): Promise<ArtifactLineageResponse> {
  return apiFetch<ArtifactLineageResponse>(
    `/artifacts/${encodeURIComponent(artifactType)}/${encodeURIComponent(artifactId)}/lineage`,
  );
}