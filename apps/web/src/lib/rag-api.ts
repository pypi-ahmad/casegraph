import type {
  RagTaskRegistryResponse,
  RagTaskExecutionResult,
} from "@casegraph/agent-sdk";
import type { TaskExecutionEvent } from "@casegraph/agent-sdk";

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
    // ignore parse errors
  }
  return fallback;
}

export async function fetchRagTasks(): Promise<RagTaskRegistryResponse> {
  const response = await fetch(`${API_BASE_URL}/rag/tasks`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load RAG tasks."));
  }
  return (await response.json()) as RagTaskRegistryResponse;
}

export interface RagExecutePayload {
  task_id: string;
  query: string;
  parameters: Record<string, unknown>;
  provider: string;
  model_id: string;
  api_key: string;
  retrieval_scope: {
    kind: "global" | "case" | "document";
    case_id: string | null;
    document_ids: string[];
  };
  top_k: number;
  max_tokens: number | null;
  temperature: number | null;
  use_structured_output: boolean;
}

export interface RagExecuteResponse {
  result: RagTaskExecutionResult;
  events: TaskExecutionEvent[];
}

export async function executeRagTask(
  payload: RagExecutePayload,
): Promise<RagExecuteResponse> {
  const response = await fetch(`${API_BASE_URL}/rag/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "RAG task execution failed."));
  }
  return (await response.json()) as RagExecuteResponse;
}
