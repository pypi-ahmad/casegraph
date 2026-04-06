import type {
  TaskRegistryResponse,
  TaskExecutionResult,
  TaskExecutionEvent,
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
    // ignore parse errors
  }
  return fallback;
}

export async function fetchTasks(): Promise<TaskRegistryResponse> {
  const response = await fetch(`${API_BASE_URL}/tasks`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load tasks."));
  }
  return (await response.json()) as TaskRegistryResponse;
}

export interface ExecuteTaskPayload {
  task_id: string;
  input: { text: string; parameters: Record<string, unknown> };
  provider: string;
  model_id: string;
  api_key: string;
  max_tokens: number | null;
  temperature: number | null;
  use_structured_output: boolean;
}

export interface ExecuteTaskResponse {
  result: TaskExecutionResult;
  events: TaskExecutionEvent[];
}

export async function executeTask(
  payload: ExecuteTaskPayload,
): Promise<ExecuteTaskResponse> {
  const response = await fetch(`${API_BASE_URL}/tasks/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Task execution failed."));
  }
  return (await response.json()) as ExecuteTaskResponse;
}
