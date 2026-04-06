import type {
  DocumentRegistryListResponse,
  DocumentReviewResponse,
  IngestionResultSummary,
  PageReviewDetail,
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

export async function fetchDocumentsList(options?: {
  limit?: number;
}): Promise<DocumentRegistryListResponse> {
  const params = new URLSearchParams();
  if (typeof options?.limit === "number")
    params.set("limit", String(options.limit));
  const query = params.size > 0 ? `?${params.toString()}` : "";

  const response = await fetch(`${API_BASE_URL}/documents${query}`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load documents."),
    );
  }
  return (await response.json()) as DocumentRegistryListResponse;
}

export async function fetchDocumentReview(
  documentId: string,
): Promise<DocumentReviewResponse> {
  const response = await fetch(
    `${API_BASE_URL}/documents/${documentId}`,
    { method: "GET", cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load document review."),
    );
  }
  return (await response.json()) as DocumentReviewResponse;
}

export async function fetchPageDetail(
  documentId: string,
  pageNumber: number,
): Promise<PageReviewDetail> {
  const response = await fetch(
    `${API_BASE_URL}/documents/${documentId}/pages/${pageNumber}`,
    { method: "GET", cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load page detail."),
    );
  }
  return (await response.json()) as PageReviewDetail;
}

export function getPageImageUrl(
  documentId: string,
  pageNumber: number,
): string {
  return `${API_BASE_URL}/documents/${documentId}/pages/${pageNumber}/image`;
}
