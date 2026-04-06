import type {
  EvalCapabilitiesResponse,
  EvalSuiteListResponse,
  EvalSuiteDetailResponse,
  EvalRunResponse,
  EvalRunDetailResponse,
  EvalRunRecord,
} from "@casegraph/agent-sdk";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    ...init,
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

export async function fetchEvalCapabilities(): Promise<EvalCapabilitiesResponse> {
  return apiFetch<EvalCapabilitiesResponse>("/evals/capabilities");
}

export async function fetchEvalSuites(): Promise<EvalSuiteListResponse> {
  return apiFetch<EvalSuiteListResponse>("/evals/suites");
}

export async function fetchEvalSuite(suiteId: string): Promise<EvalSuiteDetailResponse> {
  return apiFetch<EvalSuiteDetailResponse>(`/evals/suites/${encodeURIComponent(suiteId)}`);
}

export async function runEvalSuite(suiteId: string): Promise<EvalRunResponse> {
  return apiFetch<EvalRunResponse>(`/evals/suites/${encodeURIComponent(suiteId)}/run`, {
    method: "POST",
  });
}

export async function fetchEvalRun(runId: string): Promise<EvalRunDetailResponse> {
  return apiFetch<EvalRunDetailResponse>(`/evals/runs/${encodeURIComponent(runId)}`);
}

export async function fetchEvalRuns(suiteId?: string): Promise<EvalRunRecord[]> {
  const query = suiteId ? `?suite_id=${encodeURIComponent(suiteId)}` : "";
  return apiFetch<EvalRunRecord[]>(`/evals/runs${query}`);
}
