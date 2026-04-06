import type { AgentsResponse } from "@casegraph/agent-sdk";
import type { WorkflowsResponse } from "@casegraph/workflows";

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

export async function fetchAgents(): Promise<AgentsResponse> {
  const response = await fetch(`${API_BASE_URL}/agents`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load agents."));
  }
  return (await response.json()) as AgentsResponse;
}

export async function fetchWorkflows(): Promise<WorkflowsResponse> {
  const response = await fetch(`${API_BASE_URL}/workflows`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load workflows."),
    );
  }
  return (await response.json()) as WorkflowsResponse;
}
