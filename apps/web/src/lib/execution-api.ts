import type {
  ApproveCheckpointRequest,
  AutomationCheckpointResponse,
  AutomationExecutionRequest,
  AutomationResumeRequest,
  AutomationRunArtifactsResponse,
  AutomationRunCheckpointsResponse,
  AutomationRunDetailResponse,
  AutomationRunEventsResponse,
  AutomationRunListResponse,
  AutomationRunResponse,
  AutomationRunStepsResponse,
  BlockCheckpointRequest,
  SkipCheckpointRequest,
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

export async function executeAutomationPlan(
  draftId: string,
  payload: AutomationExecutionRequest,
): Promise<AutomationRunResponse> {
  const response = await fetch(`${API_BASE_URL}/submission-drafts/${draftId}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, draft_id: draftId }),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to execute automation plan."));
  }
  return (await response.json()) as AutomationRunResponse;
}

export async function fetchCaseAutomationRuns(
  caseId: string,
): Promise<AutomationRunListResponse> {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/automation-runs`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load automation runs."));
  }
  return (await response.json()) as AutomationRunListResponse;
}

export async function fetchAutomationRun(
  runId: string,
): Promise<AutomationRunResponse> {
  const response = await fetch(`${API_BASE_URL}/automation-runs/${runId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load automation run."));
  }
  return (await response.json()) as AutomationRunResponse;
}

export async function fetchAutomationRunDetail(
  runId: string,
): Promise<AutomationRunDetailResponse> {
  const response = await fetch(`${API_BASE_URL}/automation-runs/${runId}/detail`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load automation run detail."));
  }
  return (await response.json()) as AutomationRunDetailResponse;
}

export async function fetchAutomationRunSteps(
  runId: string,
): Promise<AutomationRunStepsResponse> {
  const response = await fetch(`${API_BASE_URL}/automation-runs/${runId}/steps`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load execution steps."));
  }
  return (await response.json()) as AutomationRunStepsResponse;
}

export async function fetchAutomationRunArtifacts(
  runId: string,
): Promise<AutomationRunArtifactsResponse> {
  const response = await fetch(`${API_BASE_URL}/automation-runs/${runId}/artifacts`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load run artifacts."));
  }
  return (await response.json()) as AutomationRunArtifactsResponse;
}

export async function fetchAutomationRunEvents(
  runId: string,
): Promise<AutomationRunEventsResponse> {
  const response = await fetch(`${API_BASE_URL}/automation-runs/${runId}/events`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load run events."));
  }
  return (await response.json()) as AutomationRunEventsResponse;
}

export async function fetchAutomationRunCheckpoints(
  runId: string,
): Promise<AutomationRunCheckpointsResponse> {
  const response = await fetch(`${API_BASE_URL}/automation-runs/${runId}/checkpoints`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load automation checkpoints."));
  }
  return (await response.json()) as AutomationRunCheckpointsResponse;
}

export async function approveAutomationCheckpoint(
  runId: string,
  checkpointId: string,
  payload: ApproveCheckpointRequest,
): Promise<AutomationCheckpointResponse> {
  const response = await fetch(`${API_BASE_URL}/automation-runs/${runId}/checkpoints/${checkpointId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to approve checkpoint."));
  }
  return (await response.json()) as AutomationCheckpointResponse;
}

export async function skipAutomationCheckpoint(
  runId: string,
  checkpointId: string,
  payload: SkipCheckpointRequest,
): Promise<AutomationCheckpointResponse> {
  const response = await fetch(`${API_BASE_URL}/automation-runs/${runId}/checkpoints/${checkpointId}/skip`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to skip checkpoint."));
  }
  return (await response.json()) as AutomationCheckpointResponse;
}

export async function blockAutomationCheckpoint(
  runId: string,
  checkpointId: string,
  payload: BlockCheckpointRequest,
): Promise<AutomationCheckpointResponse> {
  const response = await fetch(`${API_BASE_URL}/automation-runs/${runId}/checkpoints/${checkpointId}/block`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to block checkpoint."));
  }
  return (await response.json()) as AutomationCheckpointResponse;
}

export async function resumeAutomationRun(
  runId: string,
  payload: AutomationResumeRequest,
): Promise<AutomationRunResponse> {
  const response = await fetch(`${API_BASE_URL}/automation-runs/${runId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to resume automation run."));
  }
  return (await response.json()) as AutomationRunResponse;
}
