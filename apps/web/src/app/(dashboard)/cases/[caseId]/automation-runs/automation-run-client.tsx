"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import type {
  AutomationCheckpointRecord,
  AutomationOperatorOverrideRecord,
  AutomationRunDetailResponse,
  AutomationRunRecord,
  BlockedActionRecord,
  ExecutedStepRecord,
  RunArtifactRecord,
  RunEventRecord,
  SubmissionDraftSummary,
} from "@casegraph/agent-sdk";

import { fetchCaseDetail } from "@/lib/cases-api";
import {
  approveAutomationCheckpoint,
  blockAutomationCheckpoint,
  executeAutomationPlan,
  fetchAutomationRunDetail,
  fetchCaseAutomationRuns,
  resumeAutomationRun,
  skipAutomationCheckpoint,
} from "@/lib/execution-api";
import {
  fetchSubmissionDraftDetail,
  fetchSubmissionDrafts,
} from "@/lib/submissions-api";

type DecisionDraftState = {
  decisionNote: string;
  skipReason: string;
  blockReason: string;
};

export default function AutomationRunClient({ caseId }: { caseId: string }) {
  const [caseTitle, setCaseTitle] = useState("");
  const [drafts, setDrafts] = useState<SubmissionDraftSummary[]>([]);
  const [runs, setRuns] = useState<AutomationRunRecord[]>([]);
  const [selectedDraftId, setSelectedDraftId] = useState("");
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [operatorId, setOperatorId] = useState("");
  const [resumeNote, setResumeNote] = useState("");
  const [decisionDrafts, setDecisionDrafts] = useState<Record<string, DecisionDraftState>>({});
  const [runDetail, setRunDetail] = useState<AutomationRunDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load(preferredRunId?: string, preferredDraftId?: string) {
    setLoading(true);
    setError(null);
    try {
      const [caseDetail, draftResponse, runResponse] = await Promise.all([
        fetchCaseDetail(caseId),
        fetchSubmissionDrafts(caseId),
        fetchCaseAutomationRuns(caseId),
      ]);

      setCaseTitle(caseDetail.case.title);
      const approvedDrafts = draftResponse.drafts.filter(
        (draft) => draft.approval_status === "approved_for_future_execution"
          && draft.status !== "superseded_placeholder",
      );
      setDrafts(approvedDrafts);

      const nextDraftId = preferredDraftId ?? selectedDraftId ?? approvedDrafts[0]?.draft_id ?? "";
      setSelectedDraftId(nextDraftId);

      setRuns(runResponse.runs);
      const nextRunId = preferredRunId ?? selectedRunId ?? runResponse.runs[0]?.run_id ?? "";
      setSelectedRunId(nextRunId);

      if (nextRunId) {
        setRunDetail(await fetchAutomationRunDetail(nextRunId));
      } else {
        setRunDetail(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load automation run workspace.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [caseId]);

  useEffect(() => {
    if (!selectedDraftId) {
      setSelectedPlanId("");
      return;
    }
    fetchSubmissionDraftDetail(selectedDraftId)
      .then((detail) => setSelectedPlanId(detail.plan?.plan_id ?? ""))
      .catch(() => setSelectedPlanId(""));
  }, [selectedDraftId]);

  useEffect(() => {
    if (!selectedRunId) {
      setRunDetail(null);
      return;
    }
    setWorking(true);
    fetchAutomationRunDetail(selectedRunId)
      .then((detail) => setRunDetail(detail))
      .catch((err: unknown) => {
        setMessage(err instanceof Error ? err.message : "Unable to load automation run detail.");
      })
      .finally(() => setWorking(false));
  }, [selectedRunId]);

  function updateDecisionDraft(checkpointId: string, patch: Partial<DecisionDraftState>) {
    setDecisionDrafts((current) => ({
      ...current,
      [checkpointId]: {
        decisionNote: current[checkpointId]?.decisionNote ?? "",
        skipReason: current[checkpointId]?.skipReason ?? "",
        blockReason: current[checkpointId]?.blockReason ?? "",
        ...patch,
      },
    }));
  }

  function decisionDraft(checkpointId: string): DecisionDraftState {
    return decisionDrafts[checkpointId] ?? { decisionNote: "", skipReason: "", blockReason: "" };
  }

  async function refreshRun(runId: string) {
    const detail = await fetchAutomationRunDetail(runId);
    setRunDetail(detail);
    setSelectedRunId(runId);
    const runResponse = await fetchCaseAutomationRuns(caseId);
    setRuns(runResponse.runs);
  }

  async function handleExecute(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDraftId || !selectedPlanId) {
      return;
    }
    setWorking(true);
    setMessage(null);
    try {
      const response = await executeAutomationPlan(selectedDraftId, {
        draft_id: selectedDraftId,
        plan_id: selectedPlanId,
        operator_id: operatorId.trim(),
      });
      setMessage(response.result.message || "Automation run created.");
      if (response.run.run_id) {
        await load(response.run.run_id, selectedDraftId);
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to execute automation plan.");
    } finally {
      setWorking(false);
    }
  }

  async function handleApprove(checkpoint: AutomationCheckpointRecord) {
    const resolvedOperatorId = operatorId.trim() || runDetail?.run.operator_id || "";
    if (!resolvedOperatorId) {
      setMessage("Operator identifier is required before approving a checkpoint.");
      return;
    }
    const draft = decisionDraft(checkpoint.checkpoint_id);
    setWorking(true);
    setMessage(null);
    try {
      const response = await approveAutomationCheckpoint(checkpoint.run_id, checkpoint.checkpoint_id, {
        operator_id: resolvedOperatorId,
        decision_note: draft.decisionNote,
      });
      setMessage(response.result.message || "Checkpoint approved.");
      await refreshRun(checkpoint.run_id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to approve checkpoint.");
    } finally {
      setWorking(false);
    }
  }

  async function handleSkip(checkpoint: AutomationCheckpointRecord) {
    const resolvedOperatorId = operatorId.trim() || runDetail?.run.operator_id || "";
    if (!resolvedOperatorId) {
      setMessage("Operator identifier is required before skipping a checkpoint.");
      return;
    }
    const draft = decisionDraft(checkpoint.checkpoint_id);
    setWorking(true);
    setMessage(null);
    try {
      const response = await skipAutomationCheckpoint(checkpoint.run_id, checkpoint.checkpoint_id, {
        operator_id: resolvedOperatorId,
        decision_note: draft.decisionNote,
        skip_reason: draft.skipReason,
      });
      setMessage(response.result.message || "Checkpoint skipped.");
      await refreshRun(checkpoint.run_id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to skip checkpoint.");
    } finally {
      setWorking(false);
    }
  }

  async function handleBlock(checkpoint: AutomationCheckpointRecord) {
    const resolvedOperatorId = operatorId.trim() || runDetail?.run.operator_id || "";
    if (!resolvedOperatorId) {
      setMessage("Operator identifier is required before blocking a run.");
      return;
    }
    const draft = decisionDraft(checkpoint.checkpoint_id);
    setWorking(true);
    setMessage(null);
    try {
      const response = await blockAutomationCheckpoint(checkpoint.run_id, checkpoint.checkpoint_id, {
        operator_id: resolvedOperatorId,
        decision_note: draft.decisionNote,
        block_reason: draft.blockReason,
      });
      setMessage(response.result.message || "Checkpoint blocked the run.");
      await refreshRun(checkpoint.run_id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to block checkpoint.");
    } finally {
      setWorking(false);
    }
  }

  async function handleResume() {
    if (!runDetail) {
      return;
    }
    setWorking(true);
    setMessage(null);
    try {
      const response = await resumeAutomationRun(runDetail.run.run_id, {
        operator_id: operatorId.trim(),
        note: resumeNote.trim(),
      });
      setMessage(response.result.message || "Automation run resumed.");
      setResumeNote("");
      await refreshRun(response.run.run_id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to resume automation run.");
    } finally {
      setWorking(false);
    }
  }

  const actionableCheckpoint = runDetail?.checkpoints.find((checkpoint) => checkpoint.status === "pending_operator_review")
    ?? null;
  const resumableCheckpoint = runDetail?.run.status === "awaiting_operator_review"
    ? runDetail.checkpoints.find((checkpoint) => checkpoint.checkpoint_id === runDetail.run.paused_run?.checkpoint_id)
    : null;

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <div style={linkRowStyle}>
          <Link href={`/cases/${caseId}`} style={secondaryLinkStyle}>Case workspace</Link>
          <Link href={`/cases/${caseId}/handoff`} style={secondaryLinkStyle}>Reviewed handoff</Link>
          <Link href={`/cases/${caseId}/communication-drafts`} style={secondaryLinkStyle}>Communication drafts</Link>
          <Link href={`/cases/${caseId}/submission-drafts`} style={secondaryLinkStyle}>Submission drafts</Link>
          <Link href={`/cases/${caseId}/packets`} style={secondaryLinkStyle}>Packets</Link>
        </div>

        <header style={headerStyle}>
          <p style={breadcrumbStyle}>Automation Runs</p>
          <h1 style={titleStyle}>{caseTitle || "Automation Checkpoint Workspace"}</h1>
          <p style={subtitleStyle}>
            Human-supervised automation execution with explicit operator checkpoints, auditable
            decisions, resumable continuation, and metadata-only computer-use fallback hints.
            Dangerous write actions and final submission remain blocked.
          </p>
        </header>

        {message && <div style={panelStyle}>{message}</div>}

        {loading ? (
          <div style={panelStyle}>Loading…</div>
        ) : error ? (
          <div style={errorPanelStyle}>{error}</div>
        ) : (
          <>
            <section style={sectionCardStyle}>
              <h2 style={sectionTitleStyle}>Execute Approved Plan</h2>
              {drafts.length === 0 ? (
                <div style={subtlePanelStyle}>
                  No approved submission drafts are ready for supervised execution.
                </div>
              ) : (
                <form onSubmit={handleExecute} style={formStyle}>
                  <label style={fieldStyle}>
                    <span style={labelStyle}>Approved Draft</span>
                    <select value={selectedDraftId} onChange={(event) => setSelectedDraftId(event.target.value)} style={inputStyle}>
                      <option value="">Select approved draft</option>
                      {drafts.map((draft) => (
                        <option key={draft.draft_id} value={draft.draft_id}>
                            {draft.submission_target_id.replace(/_/g, " ")} • {draft.draft_id.slice(0, 12)}… • {describeSourceMode(draft.source_mode)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label style={fieldStyle}>
                    <span style={labelStyle}>Operator</span>
                    <input
                      value={operatorId}
                      onChange={(event) => setOperatorId(event.target.value)}
                      style={inputStyle}
                      placeholder="Operator identifier"
                    />
                  </label>
                  <button type="submit" style={primaryButtonStyle} disabled={working || !selectedDraftId || !selectedPlanId}>
                    {working ? "Working…" : "Start Supervised Run"}
                  </button>
                </form>
              )}
              {!selectedPlanId && selectedDraftId && (
                <div style={subtlePanelStyle}>No automation plan is available for this draft yet.</div>
              )}
            </section>

            <section style={sectionCardStyle}>
              <h2 style={sectionTitleStyle}>Case Automation Runs</h2>
              {runs.length === 0 ? (
                <div style={subtlePanelStyle}>No automation runs have been created for this case yet.</div>
              ) : (
                <div style={stackStyle}>
                  {runs.map((run) => (
                    <article
                      key={run.run_id}
                      style={{
                        ...itemCardStyle,
                        cursor: "pointer",
                        borderColor: selectedRunId === run.run_id ? "#0d6efd" : "#d7dee8",
                      }}
                      onClick={() => setSelectedRunId(run.run_id)}
                    >
                      <div style={itemHeaderStyle}>
                        <strong>{run.run_id.slice(0, 12)}…</strong>
                        <span style={{ ...badgeStyle, backgroundColor: statusColor(run.status) }}>
                          {run.status.replace(/_/g, " ")}
                        </span>
                      </div>
                      <div style={metaGridStyle}>
                        <span>Draft</span><span style={monoStyle}>{run.draft_id.slice(0, 12)}…</span>
                        <span>Plan</span><span style={monoStyle}>{run.plan_id.slice(0, 12)}…</span>
                        <span>Source mode</span><span>{describeSourceMode(run.source_mode)}</span>
                        <span>Reviewed snapshot</span><span style={monoStyle}>{run.source_reviewed_snapshot_id ? `${run.source_reviewed_snapshot_id.slice(0, 12)}…` : "None"}</span>
                        <span>Operator</span><span>{run.operator_id || "—"}</span>
                        <span>Checkpoints</span><span>{run.summary.checkpoint_count}</span>
                        <span>Pending review</span><span>{run.summary.pending_checkpoint_count}</span>
                        <span>Completed</span><span>{run.summary.completed_steps}</span>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>

            {runDetail && (
              <>
                <RunOverviewPanel run={runDetail.run} resumeNote={resumeNote} onResumeNoteChange={setResumeNote} onResume={handleResume} canResume={Boolean(resumableCheckpoint && ["approved", "skipped"].includes(resumableCheckpoint.status) && runDetail.run.status === "awaiting_operator_review")} working={working} />
                <CheckpointsPanel
                  checkpoints={runDetail.checkpoints}
                  overrides={runDetail.overrides}
                  actionableCheckpoint={actionableCheckpoint}
                  decisionDraft={decisionDraft}
                  onDraftChange={updateDecisionDraft}
                  onApprove={handleApprove}
                  onSkip={handleSkip}
                  onBlock={handleBlock}
                  working={working}
                />
                <StepsPanel steps={runDetail.steps} />
                <BlockedPanel blocked={runDetail.blocked_actions} />
                <ArtifactsPanel artifacts={runDetail.artifacts} />
                <EventsPanel events={runDetail.events} />
              </>
            )}
          </>
        )}
      </section>
    </main>
  );
}

function RunOverviewPanel({
  run,
  resumeNote,
  onResumeNoteChange,
  onResume,
  canResume,
  working,
}: {
  run: AutomationRunRecord;
  resumeNote: string;
  onResumeNoteChange: (value: string) => void;
  onResume: () => void;
  canResume: boolean;
  working: boolean;
}) {
  return (
    <section style={sectionCardStyle}>
      <div style={sectionHeaderStyle}>
        <h2 style={sectionTitleStyle}>Run Overview</h2>
        {run.status === "awaiting_operator_review" && (
          <button type="button" style={primaryButtonStyle} onClick={onResume} disabled={!canResume || working}>
            {working ? "Working…" : "Resume Run"}
          </button>
        )}
      </div>
      <div style={metaGridStyle}>
        <span>Run ID</span><span style={monoStyle}>{run.run_id}</span>
        <span>Status</span><span style={{ ...badgeStyle, backgroundColor: statusColor(run.status), width: "fit-content" }}>{run.status.replace(/_/g, " ")}</span>
        <span>Draft</span><span style={monoStyle}>{run.draft_id}</span>
        <span>Plan</span><span style={monoStyle}>{run.plan_id}</span>
        <span>Source mode</span><span>{describeSourceMode(run.source_mode)}</span>
        <span>Reviewed snapshot</span><span style={monoStyle}>{run.source_reviewed_snapshot_id || "None"}</span>
        <span>Operator</span><span>{run.operator_id || "—"}</span>
        <span>Dry run</span><span>{run.dry_run ? "Yes" : "No"}</span>
        <span>Started</span><span>{formatTs(run.started_at)}</span>
        <span>Completed</span><span>{formatTs(run.completed_at)}</span>
      </div>
      <div style={{ ...subtlePanelStyle, marginTop: "0.75rem" }}>
        <div style={metaGridStyle}>
          <span>Total steps</span><span>{run.summary.total_steps}</span>
          <span>Completed</span><span>{run.summary.completed_steps}</span>
          <span>Skipped</span><span>{run.summary.skipped_steps}</span>
          <span>Blocked</span><span>{run.summary.blocked_steps}</span>
          <span>Failed</span><span>{run.summary.failed_steps}</span>
          <span>Checkpoints</span><span>{run.summary.checkpoint_count}</span>
          <span>Pending review</span><span>{run.summary.pending_checkpoint_count}</span>
          <span>Artifacts</span><span>{run.summary.artifact_count}</span>
        </div>
        {run.summary.notes.map((note) => (
          <p key={note} style={metaTextStyle}>{note}</p>
        ))}
      </div>
      {run.paused_run && (
        <div style={{ ...subtlePanelStyle, marginTop: "0.75rem" }}>
          <strong>Paused Checkpoint</strong>
          <div style={metaGridStyle}>
            <span>Step</span><span>{run.paused_run.step_index}. {run.paused_run.step_title}</span>
            <span>Execution mode</span><span>{run.paused_run.execution_mode.replace(/_/g, " ")}</span>
            <span>Checkpoint status</span><span>{run.paused_run.checkpoint_status.replace(/_/g, " ")}</span>
            <span>Paused at</span><span>{formatTs(run.paused_run.paused_at)}</span>
            <span>Session resume</span><span>{run.paused_run.session_resume_supported ? "Supported" : "Not supported"}</span>
          </div>
          {run.paused_run.notes.map((note) => (
            <p key={note} style={metaTextStyle}>{note}</p>
          ))}
          <label style={{ ...fieldStyle, marginTop: "0.75rem" }}>
            <span style={labelStyle}>Resume Note</span>
            <input value={resumeNote} onChange={(event) => onResumeNoteChange(event.target.value)} style={inputStyle} placeholder="Optional resume context" />
          </label>
        </div>
      )}
      {run.session.status !== "not_started" && (
        <div style={{ ...subtlePanelStyle, marginTop: "0.75rem" }}>
          <strong>Session Boundary</strong>
          <div style={metaGridStyle}>
            <span>Backend</span><span>{run.session.backend_id || "—"}</span>
            <span>Status</span><span>{run.session.status}</span>
            <span>MCP URL</span><span style={monoStyle}>{run.session.mcp_server_url || "—"}</span>
          </div>
        </div>
      )}
    </section>
  );
}

function CheckpointsPanel({
  checkpoints,
  overrides,
  actionableCheckpoint,
  decisionDraft,
  onDraftChange,
  onApprove,
  onSkip,
  onBlock,
  working,
}: {
  checkpoints: AutomationCheckpointRecord[];
  overrides: AutomationOperatorOverrideRecord[];
  actionableCheckpoint: AutomationCheckpointRecord | null;
  decisionDraft: (checkpointId: string) => DecisionDraftState;
  onDraftChange: (checkpointId: string, patch: Partial<DecisionDraftState>) => void;
  onApprove: (checkpoint: AutomationCheckpointRecord) => void;
  onSkip: (checkpoint: AutomationCheckpointRecord) => void;
  onBlock: (checkpoint: AutomationCheckpointRecord) => void;
  working: boolean;
}) {
  if (checkpoints.length === 0) {
    return null;
  }

  return (
    <section style={sectionCardStyle}>
      <h2 style={sectionTitleStyle}>Approval Checkpoints</h2>
      <div style={stackStyle}>
        {checkpoints.map((checkpoint) => {
          const draft = decisionDraft(checkpoint.checkpoint_id);
          const checkpointOverrides = overrides.filter((override) => override.checkpoint_id === checkpoint.checkpoint_id);
          const isActionable = actionableCheckpoint?.checkpoint_id === checkpoint.checkpoint_id;
          return (
            <article key={checkpoint.checkpoint_id} style={itemCardStyle}>
              <div style={itemHeaderStyle}>
                <strong>{checkpoint.step_index}. {checkpoint.step_title}</strong>
                <span style={{ ...badgeStyle, backgroundColor: statusColor(checkpoint.status) }}>
                  {checkpoint.status.replace(/_/g, " ")}
                </span>
              </div>
              <div style={metaGridStyle}>
                <span>Step type</span><span>{checkpoint.step_type.replace(/_/g, " ")}</span>
                <span>Execution mode</span><span>{checkpoint.execution_mode.replace(/_/g, " ")}</span>
                <span>Operator</span><span>{checkpoint.operator_id || "—"}</span>
                <span>Decision</span><span>{checkpoint.decision_type ? checkpoint.decision_type.replace(/_/g, " ") : "Pending"}</span>
                <span>Created</span><span>{formatTs(checkpoint.created_at)}</span>
                <span>Resolved</span><span>{formatTs(checkpoint.resolved_at)}</span>
              </div>
              <p style={metaTextStyle}>{checkpoint.checkpoint_reason}</p>
              {checkpoint.fallback_hint && (
                <div style={{ ...subtlePanelStyle, marginTop: "0.5rem" }}>
                  <strong>Fallback Hint</strong>
                  <div style={metaGridStyle}>
                    <span>Recommended mode</span><span>{checkpoint.fallback_hint.recommended_mode.replace(/_/g, " ")}</span>
                    <span>Supported providers</span><span>{checkpoint.fallback_hint.supported_provider_ids.join(", ") || "None"}</span>
                  </div>
                  <p style={metaTextStyle}>{checkpoint.fallback_hint.reason}</p>
                  {checkpoint.fallback_hint.notes.map((note) => (
                    <p key={note} style={metaTextStyle}>{note}</p>
                  ))}
                </div>
              )}
              {checkpoint.decision_note && <p style={metaTextStyle}>Decision note: {checkpoint.decision_note}</p>}
              {checkpoint.skip_reason && <p style={metaTextStyle}>Skip reason: {checkpoint.skip_reason}</p>}
              {checkpoint.block_reason && <p style={metaTextStyle}>Block reason: {checkpoint.block_reason}</p>}

              {isActionable && (
                <div style={{ ...subtlePanelStyle, marginTop: "0.75rem" }}>
                  <label style={fieldStyle}>
                    <span style={labelStyle}>Operator Note</span>
                    <input value={draft.decisionNote} onChange={(event) => onDraftChange(checkpoint.checkpoint_id, { decisionNote: event.target.value })} style={inputStyle} placeholder="Optional operator note" />
                  </label>
                  <label style={{ ...fieldStyle, marginTop: "0.5rem" }}>
                    <span style={labelStyle}>Skip Reason</span>
                    <input value={draft.skipReason} onChange={(event) => onDraftChange(checkpoint.checkpoint_id, { skipReason: event.target.value })} style={inputStyle} placeholder="Why skip this step" />
                  </label>
                  <label style={{ ...fieldStyle, marginTop: "0.5rem" }}>
                    <span style={labelStyle}>Block Reason</span>
                    <input value={draft.blockReason} onChange={(event) => onDraftChange(checkpoint.checkpoint_id, { blockReason: event.target.value })} style={inputStyle} placeholder="Why block the run" />
                  </label>
                  <div style={buttonRowStyle}>
                    <button type="button" style={primaryButtonStyle} onClick={() => onApprove(checkpoint)} disabled={working}>Approve / Continue</button>
                    <button type="button" style={secondaryButtonStyle} onClick={() => onSkip(checkpoint)} disabled={working}>Skip Step</button>
                    <button type="button" style={dangerButtonStyle} onClick={() => onBlock(checkpoint)} disabled={working}>Block Run</button>
                  </div>
                </div>
              )}

              {checkpointOverrides.length > 0 && (
                <div style={{ ...subtlePanelStyle, marginTop: "0.75rem" }}>
                  <strong>Decision History</strong>
                  <div style={stackStyle}>
                    {checkpointOverrides.map((override) => (
                      <div key={override.override_id} style={miniCardStyle}>
                        <div style={metaGridStyle}>
                          <span>Decision</span><span>{override.decision_type.replace(/_/g, " ")}</span>
                          <span>Operator</span><span>{override.operator_id || "—"}</span>
                          <span>Created</span><span>{formatTs(override.created_at)}</span>
                        </div>
                        {override.decision_note && <p style={metaTextStyle}>Note: {override.decision_note}</p>}
                        {override.skip_reason && <p style={metaTextStyle}>Skip reason: {override.skip_reason}</p>}
                        {override.block_reason && <p style={metaTextStyle}>Block reason: {override.block_reason}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function StepsPanel({ steps }: { steps: ExecutedStepRecord[] }) {
  if (steps.length === 0) {
    return null;
  }
  return (
    <section style={sectionCardStyle}>
      <h2 style={sectionTitleStyle}>Executed Steps</h2>
      <div style={stackStyle}>
        {steps.map((step) => (
          <article key={step.executed_step_id} style={itemCardStyle}>
            <div style={itemHeaderStyle}>
              <strong>{step.step_index}. {step.title}</strong>
              <span style={{ ...badgeStyle, backgroundColor: statusColor(step.status) }}>{step.status}</span>
            </div>
            <div style={metaGridStyle}>
              <span>Type</span><span>{step.step_type.replace(/_/g, " ")}</span>
              <span>Tool</span><span>{step.tool_id ?? "—"}</span>
              <span>Backend</span><span>{step.backend_id ?? "—"}</span>
              <span>Duration</span><span>{step.outcome.duration_ms != null ? `${step.outcome.duration_ms}ms` : "—"}</span>
            </div>
            {step.outcome.error_message && <p style={{ ...metaTextStyle, color: "#b91c1c" }}>{step.outcome.error_message}</p>}
            {step.outcome.notes.map((note) => <p key={note} style={metaTextStyle}>{note}</p>)}
          </article>
        ))}
      </div>
    </section>
  );
}

function BlockedPanel({ blocked }: { blocked: BlockedActionRecord[] }) {
  if (blocked.length === 0) {
    return null;
  }
  return (
    <section style={sectionCardStyle}>
      <h2 style={sectionTitleStyle}>Guardrail-Blocked Steps</h2>
      <div style={stackStyle}>
        {blocked.map((blockedItem) => (
          <article key={`${blockedItem.plan_step_id ?? "none"}-${blockedItem.guardrail_code}`} style={itemCardStyle}>
            <div style={itemHeaderStyle}>
              <strong>{blockedItem.step_title}</strong>
              <span style={{ ...badgeStyle, backgroundColor: "#b91c1c" }}>blocked</span>
            </div>
            <p style={metaTextStyle}>{blockedItem.reason}</p>
            <p style={metaTextStyle}>Guardrail: {blockedItem.guardrail_code}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function ArtifactsPanel({ artifacts }: { artifacts: RunArtifactRecord[] }) {
  if (artifacts.length === 0) {
    return null;
  }
  return (
    <section style={sectionCardStyle}>
      <h2 style={sectionTitleStyle}>Captured Artifacts</h2>
      <div style={stackStyle}>
        {artifacts.map((artifact) => (
          <article key={artifact.artifact_id} style={itemCardStyle}>
            <div style={itemHeaderStyle}>
              <strong>{artifact.display_name}</strong>
              <span style={{ ...badgeStyle, backgroundColor: "#0d6efd" }}>{artifact.artifact_type.replace(/_/g, " ")}</span>
            </div>
            {artifact.content_text && <pre style={preStyle}>{artifact.content_text}</pre>}
            <p style={metaTextStyle}>Captured: {formatTs(artifact.captured_at)}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function EventsPanel({ events }: { events: RunEventRecord[] }) {
  if (events.length === 0) {
    return null;
  }
  return (
    <section style={sectionCardStyle}>
      <h2 style={sectionTitleStyle}>Event Journal</h2>
      <div style={stackStyle}>
        {events.map((event) => (
          <div key={event.event_id} style={eventRowStyle}>
            <span style={{ ...badgeStyle, backgroundColor: eventColor(event.event_type), fontSize: "0.7rem" }}>
              {event.event_type.replace(/_/g, " ")}
            </span>
            <span style={{ flex: 1 }}>{event.message}</span>
            <span style={eventTimestampStyle}>{formatTs(event.timestamp)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function formatTs(value: string): string {
  if (!value) {
    return "—";
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function describeSourceMode(value: string): string {
  return value === "reviewed_snapshot" ? "Reviewed snapshot" : "Live case state";
}

function statusColor(status: string): string {
  switch (status) {
    case "completed":
    case "approved":
    case "resolved":
      return "#15803d";
    case "running":
    case "pending_operator_review":
    case "awaiting_operator_review":
      return "#0d6efd";
    case "completed_partial":
    case "skipped":
      return "#b45309";
    case "blocked":
    case "failed":
      return "#b91c1c";
    default:
      return "#64748b";
  }
}

function eventColor(eventType: string): string {
  if (eventType.includes("completed") || eventType === "artifact_captured" || eventType.includes("approved")) return "#15803d";
  if (eventType.includes("failed") || eventType.includes("blocked")) return "#b91c1c";
  if (eventType.includes("started") || eventType.includes("paused") || eventType.includes("resumed") || eventType.includes("checkpoint")) return "#0d6efd";
  if (eventType.includes("skipped")) return "#b45309";
  return "#475569";
}

const pageStyle: CSSProperties = { minHeight: "100vh", padding: "2.5rem 1.25rem 3rem", backgroundColor: "#f5f7fa" };
const containerStyle: CSSProperties = { maxWidth: "1180px", margin: "0 auto" };
const linkRowStyle: CSSProperties = { display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1rem" };
const headerStyle: CSSProperties = { marginBottom: "1.5rem" };
const breadcrumbStyle: CSSProperties = { margin: 0, textTransform: "uppercase", letterSpacing: "0.08em", fontSize: "0.8rem", color: "#64748b" };
const titleStyle: CSSProperties = { fontSize: "1.65rem", fontWeight: 700, margin: "0.25rem 0 0.5rem" };
const subtitleStyle: CSSProperties = { color: "#64748b", fontSize: "0.92rem", margin: 0, maxWidth: "840px", lineHeight: 1.55 };
const sectionCardStyle: CSSProperties = { backgroundColor: "white", borderRadius: "0.75rem", padding: "1.25rem 1.5rem", marginBottom: "1.25rem", border: "1px solid #e2e8f0" };
const sectionHeaderStyle: CSSProperties = { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" };
const sectionTitleStyle: CSSProperties = { fontSize: "1.1rem", fontWeight: 600, margin: "0 0 0.75rem" };
const formStyle: CSSProperties = { display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "flex-end" };
const fieldStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: "0.25rem", minWidth: "220px" };
const labelStyle: CSSProperties = { fontSize: "0.8rem", fontWeight: 600, color: "#334155" };
const inputStyle: CSSProperties = { padding: "0.5rem 0.75rem", borderRadius: "0.375rem", border: "1px solid #cbd5e1", fontSize: "0.875rem", width: "100%" };
const primaryButtonStyle: CSSProperties = { padding: "0.5rem 1.25rem", borderRadius: "0.375rem", backgroundColor: "#0d6efd", color: "white", border: "none", fontWeight: 600, cursor: "pointer", fontSize: "0.875rem" };
const secondaryButtonStyle: CSSProperties = { ...primaryButtonStyle, backgroundColor: "#475569" };
const dangerButtonStyle: CSSProperties = { ...primaryButtonStyle, backgroundColor: "#b91c1c" };
const buttonRowStyle: CSSProperties = { display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.75rem" };
const panelStyle: CSSProperties = { padding: "0.75rem 1rem", backgroundColor: "#e0f2fe", borderRadius: "0.5rem", marginBottom: "1rem", fontSize: "0.88rem" };
const errorPanelStyle: CSSProperties = { ...panelStyle, backgroundColor: "#fee2e2", color: "#b91c1c" };
const subtlePanelStyle: CSSProperties = { padding: "0.75rem 1rem", backgroundColor: "#f8fafc", borderRadius: "0.5rem", border: "1px solid #e2e8f0" };
const stackStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: "0.75rem" };
const itemCardStyle: CSSProperties = { padding: "0.85rem 1rem", backgroundColor: "#f8fafc", borderRadius: "0.5rem", border: "1px solid #d7dee8" };
const miniCardStyle: CSSProperties = { padding: "0.6rem 0.75rem", borderRadius: "0.4rem", border: "1px solid #d7dee8", backgroundColor: "white" };
const itemHeaderStyle: CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem", gap: "0.75rem", flexWrap: "wrap" };
const metaGridStyle: CSSProperties = { display: "grid", gridTemplateColumns: "140px 1fr", gap: "0.25rem 0.75rem", fontSize: "0.82rem" };
const metaTextStyle: CSSProperties = { margin: "0.25rem 0 0", fontSize: "0.8rem", color: "#64748b" };
const monoStyle: CSSProperties = { fontFamily: "monospace", fontSize: "0.78rem" };
const preStyle: CSSProperties = { backgroundColor: "#f1f5f9", padding: "0.5rem", borderRadius: "0.25rem", fontSize: "0.78rem", whiteSpace: "pre-wrap", margin: "0.5rem 0" };
const badgeStyle: CSSProperties = { fontSize: "0.72rem", fontWeight: 600, color: "white", padding: "0.15rem 0.5rem", borderRadius: "0.25rem", textTransform: "uppercase" };
const secondaryLinkStyle: CSSProperties = { fontSize: "0.82rem", color: "#475569", textDecoration: "underline" };
const eventRowStyle: CSSProperties = { display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.4rem 0", borderBottom: "1px solid #f1f5f9", fontSize: "0.82rem" };
const eventTimestampStyle: CSSProperties = { fontSize: "0.75rem", color: "#94a3b8" };
