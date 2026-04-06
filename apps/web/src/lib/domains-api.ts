import type {
  CaseTypeDetailResponse,
  CaseTypeTemplateMetadata,
  DocumentRequirementDefinition,
  DomainPackDetailResponse,
  DomainPackListResponse,
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

export async function fetchDomainPacks(): Promise<DomainPackListResponse> {
  const response = await fetch(`${API_BASE_URL}/domain-packs`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load domain packs."),
    );
  }
  return (await response.json()) as DomainPackListResponse;
}

export async function fetchDomainPackDetail(
  packId: string,
): Promise<DomainPackDetailResponse> {
  const response = await fetch(`${API_BASE_URL}/domain-packs/${packId}`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load domain pack detail."),
    );
  }
  return (await response.json()) as DomainPackDetailResponse;
}

export async function fetchPackCaseTypes(
  packId: string,
): Promise<CaseTypeTemplateMetadata[]> {
  const response = await fetch(
    `${API_BASE_URL}/domain-packs/${packId}/case-types`,
    { method: "GET", cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load case types."),
    );
  }
  return (await response.json()) as CaseTypeTemplateMetadata[];
}

export async function fetchCaseTypeDetail(
  caseTypeId: string,
): Promise<CaseTypeDetailResponse> {
  const response = await fetch(
    `${API_BASE_URL}/case-types/${caseTypeId}`,
    { method: "GET", cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load case type detail."),
    );
  }
  return (await response.json()) as CaseTypeDetailResponse;
}

export async function fetchCaseTypeRequirements(
  caseTypeId: string,
): Promise<DocumentRequirementDefinition[]> {
  const response = await fetch(
    `${API_BASE_URL}/case-types/${caseTypeId}/requirements`,
    { method: "GET", cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load document requirements."),
    );
  }
  return (await response.json()) as DocumentRequirementDefinition[];
}
