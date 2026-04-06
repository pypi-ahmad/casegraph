import type {
  CaseTargetPackResponse,
  CaseTargetPackUpdateResponse,
  TargetPackCategory,
  TargetPackDetailResponse,
  TargetPackListResponse,
  TargetPackStatus,
  UpdateCaseTargetPackRequest,
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

export async function fetchTargetPacks(filters?: {
  domain_pack_id?: string | null;
  case_type_id?: string | null;
  category?: TargetPackCategory | null;
  status?: TargetPackStatus | null;
}): Promise<TargetPackListResponse> {
  const params = new URLSearchParams();
  if (filters?.domain_pack_id) params.set("domain_pack_id", filters.domain_pack_id);
  if (filters?.case_type_id) params.set("case_type_id", filters.case_type_id);
  if (filters?.category) params.set("category", filters.category);
  if (filters?.status) params.set("status", filters.status);
  const query = params.size > 0 ? `?${params.toString()}` : "";

  const response = await fetch(`${API_BASE_URL}/target-packs${query}`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load target packs."));
  }
  return (await response.json()) as TargetPackListResponse;
}

export async function fetchTargetPackDetail(
  packId: string,
): Promise<TargetPackDetailResponse> {
  const response = await fetch(`${API_BASE_URL}/target-packs/${packId}`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load target-pack detail."),
    );
  }
  return (await response.json()) as TargetPackDetailResponse;
}

export async function fetchCaseTargetPack(
  caseId: string,
): Promise<CaseTargetPackResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/target-pack`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load case target-pack selection."),
    );
  }
  return (await response.json()) as CaseTargetPackResponse;
}

export async function updateCaseTargetPack(
  caseId: string,
  payload: UpdateCaseTargetPackRequest,
): Promise<CaseTargetPackUpdateResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/target-pack`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to update case target-pack selection."),
    );
  }
  return (await response.json()) as CaseTargetPackUpdateResponse;
}