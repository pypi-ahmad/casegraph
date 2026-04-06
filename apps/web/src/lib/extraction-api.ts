import type {
  DocumentExtractionListResponse,
  ExtractionResult,
  ExtractionRequest,
  ExtractionTemplateDetail,
  ExtractionTemplateListResponse,
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

export async function fetchExtractionTemplates(): Promise<ExtractionTemplateListResponse> {
  const response = await fetch(`${API_BASE_URL}/extraction/templates`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load extraction templates."),
    );
  }
  return (await response.json()) as ExtractionTemplateListResponse;
}

export async function fetchExtractionTemplateDetail(
  templateId: string,
): Promise<ExtractionTemplateDetail> {
  const response = await fetch(
    `${API_BASE_URL}/extraction/templates/${templateId}`,
    { method: "GET", cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load template detail."),
    );
  }
  return (await response.json()) as ExtractionTemplateDetail;
}

export async function executeExtraction(params: {
  template_id: string;
  document_id: string;
  case_id?: string | null;
  strategy: string;
  provider?: string | null;
  model_id?: string | null;
  api_key?: string | null;
}): Promise<{ result: ExtractionResult }> {
  const response = await fetch(`${API_BASE_URL}/extraction/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Extraction failed."),
    );
  }
  return (await response.json()) as { result: ExtractionResult };
}

export async function fetchDocumentExtractions(
  documentId: string,
): Promise<DocumentExtractionListResponse> {
  const response = await fetch(
    `${API_BASE_URL}/documents/${documentId}/extractions`,
    { method: "GET", cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load document extractions."),
    );
  }
  return (await response.json()) as DocumentExtractionListResponse;
}

export async function fetchExtractionResult(
  extractionId: string,
): Promise<ExtractionResult> {
  const response = await fetch(
    `${API_BASE_URL}/extractions/${extractionId}`,
    { method: "GET", cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load extraction result."),
    );
  }
  return (await response.json()) as ExtractionResult;
}
