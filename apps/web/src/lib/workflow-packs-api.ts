import type {
  WorkflowPackDetailResponse,
  WorkflowPackExecutionRequest,
  WorkflowPackListResponse,
  WorkflowPackRunResponse,
  WorkflowPackRunSummaryResponse,
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
    /* ignore */
  }
  return fallback;
}

export async function fetchWorkflowPacks(): Promise<WorkflowPackListResponse> {
  const response = await fetch(`${API_BASE_URL}/workflow-packs`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load workflow packs."));
  }
  return (await response.json()) as WorkflowPackListResponse;
}

export async function fetchWorkflowPackDetail(
  workflowPackId: string,
): Promise<WorkflowPackDetailResponse> {
  const response = await fetch(`${API_BASE_URL}/workflow-packs/${workflowPackId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load workflow pack detail."));
  }
  return (await response.json()) as WorkflowPackDetailResponse;
}

export async function executeWorkflowPack(
  caseId: string,
  workflowPackId: string,
  payload: WorkflowPackExecutionRequest,
): Promise<WorkflowPackRunResponse> {
  const response = await fetch(
    `${API_BASE_URL}/cases/${caseId}/workflow-packs/${workflowPackId}/execute`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...payload,
        case_id: caseId,
        workflow_pack_id: workflowPackId,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to execute workflow pack."));
  }
  return (await response.json()) as WorkflowPackRunResponse;
}

export async function fetchWorkflowPackRun(
  runId: string,
): Promise<WorkflowPackRunSummaryResponse> {
  const response = await fetch(`${API_BASE_URL}/workflow-pack-runs/${runId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load workflow pack run."));
  }
  return (await response.json()) as WorkflowPackRunSummaryResponse;
}

export async function fetchCaseWorkflowPackRuns(
  caseId: string,
): Promise<WorkflowPackRunResponse[]> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/workflow-pack-runs`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load workflow pack runs."));
  }
  return (await response.json()) as WorkflowPackRunResponse[];
}
