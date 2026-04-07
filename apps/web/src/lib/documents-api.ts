import type {
  DocumentsCapabilitiesResponse,
  IngestionModePreference,
  IngestionResult,
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

export async function fetchDocumentCapabilities(): Promise<DocumentsCapabilitiesResponse> {
  const response = await fetch(`${API_BASE_URL}/documents/capabilities`, {
    method: "GET",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load document capabilities. Check that the API server is running."),
    );
  }

  return (await response.json()) as DocumentsCapabilitiesResponse;
}

export async function ingestDocument(
  file: File,
  options: { mode: IngestionModePreference; ocrEnabled: boolean },
): Promise<IngestionResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("mode", options.mode);
  formData.append("ocr_enabled", String(options.ocrEnabled));

  const response = await fetch(`${API_BASE_URL}/documents/ingest`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to process document. Check the file format and size, then try again."));
  }

  return (await response.json()) as IngestionResult;
}
