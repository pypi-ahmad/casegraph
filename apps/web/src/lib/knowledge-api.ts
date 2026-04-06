import type {
  IndexResult,
  KnowledgeCapabilitiesResponse,
  NormalizedExtractionOutput,
  SearchRequest,
  SearchResult,
} from "@casegraph/agent-sdk";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

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

/* ------------------------------------------------------------------ */
/* API calls                                                           */
/* ------------------------------------------------------------------ */

export async function fetchKnowledgeCapabilities(): Promise<KnowledgeCapabilitiesResponse> {
  const response = await fetch(`${API_BASE_URL}/knowledge/capabilities`, {
    method: "GET",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load knowledge capabilities."),
    );
  }

  return (await response.json()) as KnowledgeCapabilitiesResponse;
}

export async function indexDocument(
  payload: NormalizedExtractionOutput,
): Promise<IndexResult> {
  const response = await fetch(`${API_BASE_URL}/knowledge/index`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to index document."));
  }

  return (await response.json()) as IndexResult;
}

export async function searchKnowledge(
  request: SearchRequest,
): Promise<SearchResult> {
  const response = await fetch(`${API_BASE_URL}/knowledge/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to search knowledge."));
  }

  return (await response.json()) as SearchResult;
}
