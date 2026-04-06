"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import type {
  WorkflowPackMetadata,
  WorkflowPackRunRecord,
  WorkflowPackRunResponse,
  WorkflowPackRunSummaryResponse,
  WorkflowPackStageResult,
} from "@casegraph/agent-sdk";

import { fetchCaseDetail } from "@/lib/cases-api";
import {
  executeWorkflowPack,
  fetchCaseWorkflowPackRuns,
  fetchWorkflowPackRun,
  fetchWorkflowPacks,
} from "@/lib/workflow-packs-api";

export default function WorkflowPackClient({ caseId }: { caseId: string }) {
  const [caseTitle, setCaseTitle] = useState("");
  const [caseTypeId, setCaseTypeId] = useState("");
  const [packs, setPacks] = useState<WorkflowPackMetadata[]>([]);
  const [runs, setRuns] = useState<WorkflowPackRunResponse[]>([]);
  const [selectedPackId, setSelectedPackId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [operatorId, setOperatorId] = useState("");
  const [skipOptional, setSkipOptional] = useState(false);
  const [runDetail, setRunDetail] = useState<WorkflowPackRunSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load(preferredRunId?: string) {
    setLoading(true);
    setError(null);
    try {
      const [caseDetail, packResponse, runResponse] = await Promise.all([
        fetchCaseDetail(caseId),
        fetchWorkflowPacks(),
        fetchCaseWorkflowPackRuns(caseId),
      ]);

      setCaseTitle(caseDetail.case.title);
      const resolvedCaseTypeId = caseDetail.case.domain_context?.case_type_id ?? "";
      setCaseTypeId(resolvedCaseTypeId);

      // Filter packs compatible with this case type
      const compatible = packResponse.packs.filter((pack) =>
        pack.compatible_case_type_ids.length === 0 ||
        pack.compatible_case_type_ids.includes(resolvedCaseTypeId),
      );
      setPacks(compatible);
      if (!selectedPackId && compatible.length > 0) {
        setSelectedPackId(compatible[0].workflow_pack_id);
      }

      setRuns(runResponse);
      const nextRunId = preferredRunId ?? selectedRunId ?? runResponse[0]?.run.run_id ?? "";
      setSelectedRunId(nextRunId);

      if (nextRunId) {
        setRunDetail(await fetchWorkflowPackRun(nextRunId));
      } else {
        setRunDetail(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load workflow pack workspace.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [caseId]);

  useEffect(() => {
    if (!selectedRunId) {
      setRunDetail(null);
      return;
    }
    setWorking(true);
    fetchWorkflowPackRun(selectedRunId)
      .then((detail) => setRunDetail(detail))
      .catch((err: unknown) => {
        setMessage(err instanceof Error ? err.message : "Unable to load workflow pack run detail.");
      })
      .finally(() => setWorking(false));
  }, [selectedRunId]);

  async function handleExecute(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPackId) {
      return;
    }
    setWorking(true);
    setMessage(null);
    try {
      const response = await executeWorkflowPack(caseId, selectedPackId, {
        case_id: caseId,
        workflow_pack_id: selectedPackId,
        operator_id: operatorId.trim(),
        skip_optional_stages: skipOptional,
      });
      setMessage(response.message || "Workflow pack run created.");
      if (response.run.run_id) {
        await load(response.run.run_id);
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to execute workflow pack.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <div style={linkRowStyle}>
          <Link href={`/cases/${caseId}`} style={secondaryLinkStyle}>Case workspace</Link>
          <Link href="/documents" style={secondaryLinkStyle}>Documents</Link>
          <Link href="/extraction" style={secondaryLinkStyle}>Extraction</Link>
          <Link href={`/cases/${caseId}/checklist`} style={secondaryLinkStyle}>Checklist</Link>
          <Link href={`/cases/${caseId}/packets`} style={secondaryLinkStyle}>Packets</Link>
          <Link href={`/cases/${caseId}/communication-drafts`} style={secondaryLinkStyle}>Communication drafts</Link>
          <Link href={`/cases/${caseId}/submission-drafts`} style={secondaryLinkStyle}>Submission drafts</Link>
          <Link href={`/cases/${caseId}/automation-runs`} style={secondaryLinkStyle}>Automation runs</Link>
        </div>

        <header style={headerStyle}>
          <p style={breadcrumbStyle}>Workflow Packs</p>
          <h1 style={titleStyle}>{caseTitle || "Workflow Pack Workspace"}</h1>
          <p style={subtitleStyle}>
            Domain-specific multi-stage workflows that compose extraction, readiness, packet
            assembly, and submission-draft foundations into a structured operator review sequence.
            All outputs reflect explicit case data — no fabricated facts, no autonomous decisions.
          </p>
          {caseTypeId && (
            <p style={{ ...metaTextStyle, marginTop: "0.5rem" }}>
              Case type: <span style={monoStyle}>{caseTypeId}</span>
            </p>
          )}
        </header>

        {message && <div style={panelStyle}>{message}</div>}

        {loading ? (
          <div style={panelStyle}>Loading…</div>
        ) : error ? (
          <div style={errorPanelStyle}>{error}</div>
        ) : (
          <>
            {/* Execute workflow pack */}
            <section style={sectionCardStyle}>
              <h2 style={sectionTitleStyle}>Execute Workflow Pack</h2>
              {packs.length === 0 ? (
                <div style={subtlePanelStyle}>
                  No workflow packs are compatible with this case type.
                </div>
              ) : (
                <form onSubmit={handleExecute} style={formStyle}>
                  <label style={fieldStyle}>
                    <span style={labelStyle}>Workflow Pack</span>
                    <select
                      value={selectedPackId}
                      onChange={(event) => setSelectedPackId(event.target.value)}
                      style={inputStyle}
                    >
                      <option value="">Select workflow pack</option>
                      {packs.map((pack) => (
                        <option key={pack.workflow_pack_id} value={pack.workflow_pack_id}>
                          {pack.display_name} (v{pack.version})
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
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.82rem" }}>
                    <input
                      type="checkbox"
                      checked={skipOptional}
                      onChange={(event) => setSkipOptional(event.target.checked)}
                    />
                    Skip optional stages
                  </label>
                  <button type="submit" style={primaryButtonStyle} disabled={working || !selectedPackId}>
                    {working ? "Working…" : "Run Workflow Pack"}
                  </button>
                </form>
              )}
              <SelectedPackInfo packs={packs} selectedPackId={selectedPackId} />
            </section>

            {/* Past runs */}
            <section style={sectionCardStyle}>
              <h2 style={sectionTitleStyle}>Workflow Pack Runs</h2>
              {runs.length === 0 ? (
                <div style={subtlePanelStyle}>No workflow pack runs have been created for this case yet.</div>
              ) : (
                <div style={stackStyle}>
                  {runs.map((entry) => (
                    <article
                      key={entry.run.run_id}
                      style={{
                        ...itemCardStyle,
                        cursor: "pointer",
                        borderColor: selectedRunId === entry.run.run_id ? "#0d6efd" : "#d7dee8",
                      }}
                      onClick={() => setSelectedRunId(entry.run.run_id)}
                    >
                      <div style={itemHeaderStyle}>
                        <strong>{entry.run.run_id.slice(0, 12)}…</strong>
                        <span style={{ ...badgeStyle, backgroundColor: statusColor(entry.run.status) }}>
                          {entry.run.status.replace(/_/g, " ")}
                        </span>
                      </div>
                      <div style={metaGridStyle}>
                        <span>Pack</span><span style={monoStyle}>{entry.run.workflow_pack_id}</span>
                        <span>Operator</span><span>{entry.run.operator_id || "—"}</span>
                        <span>Stages</span><span>{entry.run.stage_results.length}</span>
                        <span>Created</span><span>{formatTs(entry.run.created_at)}</span>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>

            {/* Run detail */}
            {runDetail && (
              <>
                <RunOverviewPanel run={runDetail.run} domainPackName={runDetail.domain_pack_display_name} />
                <StageResultsPanel stages={runDetail.run.stage_results} caseId={caseId} />
                <RecommendationPanel run={runDetail.run} />
              </>
            )}
          </>
        )}
      </section>
    </main>
  );
}

/* ------------------------------------------------------------------ */
/* Sub-components                                                      */
/* ------------------------------------------------------------------ */

function SelectedPackInfo({
  packs,
  selectedPackId,
}: {
  packs: WorkflowPackMetadata[];
  selectedPackId: string;
}) {
  const pack = packs.find((p) => p.workflow_pack_id === selectedPackId);
  if (!pack) {
    return null;
  }
  return (
    <div style={{ ...subtlePanelStyle, marginTop: "0.75rem" }}>
      <strong>{pack.display_name}</strong>
      <p style={metaTextStyle}>{pack.description}</p>
      <div style={metaGridStyle}>
        <span>Domain</span><span>{pack.domain_category} • {pack.jurisdiction}</span>
        <span>Stages</span><span>{pack.stage_count}</span>
        <span>Version</span><span>{pack.version}</span>
      </div>
      {pack.limitations.length > 0 && (
        <div style={{ marginTop: "0.5rem" }}>
          <strong style={{ fontSize: "0.8rem" }}>Limitations</strong>
          <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.25rem", fontSize: "0.78rem", color: "#64748b" }}>
            {pack.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function RunOverviewPanel({
  run,
  domainPackName,
}: {
  run: WorkflowPackRunRecord;
  domainPackName: string;
}) {
  const completedCount = run.stage_results.filter((s) => s.status === "completed").length;
  const failedCount = run.stage_results.filter((s) => s.status === "failed").length;
  const skippedCount = run.stage_results.filter((s) => s.status === "skipped").length;
  const blockedCount = run.stage_results.filter((s) => s.status === "blocked").length;

  return (
    <section style={sectionCardStyle}>
      <h2 style={sectionTitleStyle}>Run Overview</h2>
      <div style={metaGridStyle}>
        <span>Run ID</span><span style={monoStyle}>{run.run_id}</span>
        <span>Status</span>
        <span style={{ ...badgeStyle, backgroundColor: statusColor(run.status), width: "fit-content" }}>
          {run.status.replace(/_/g, " ")}
        </span>
        <span>Workflow Pack</span><span style={monoStyle}>{run.workflow_pack_id}</span>
        <span>Domain Pack</span><span>{domainPackName || "—"}</span>
        <span>Operator</span><span>{run.operator_id || "—"}</span>
        <span>Started</span><span>{formatTs(run.started_at)}</span>
        <span>Completed</span><span>{formatTs(run.completed_at)}</span>
      </div>
      <div style={{ ...subtlePanelStyle, marginTop: "0.75rem" }}>
        <div style={metaGridStyle}>
          <span>Total stages</span><span>{run.stage_results.length}</span>
          <span>Completed</span><span>{completedCount}</span>
          <span>Partial</span><span>{run.stage_results.filter((s) => s.status === "completed_partial").length}</span>
          <span>Skipped</span><span>{skippedCount}</span>
          <span>Blocked</span><span>{blockedCount}</span>
          <span>Failed</span><span>{failedCount}</span>
        </div>
        {run.notes.map((note) => (
          <p key={note} style={metaTextStyle}>{note}</p>
        ))}
      </div>
    </section>
  );
}

function StageResultsPanel({
  stages,
  caseId,
}: {
  stages: WorkflowPackStageResult[];
  caseId: string;
}) {
  if (stages.length === 0) {
    return null;
  }
  return (
    <section style={sectionCardStyle}>
      <h2 style={sectionTitleStyle}>Stage Results</h2>
      <div style={stackStyle}>
        {stages.map((stage, index) => (
          <StageSummaryCard key={stage.stage_id} stage={stage} index={index} caseId={caseId} />
        ))}
      </div>
    </section>
  );
}

function StageSummaryCard({
  stage,
  index,
  caseId,
}: {
  stage: WorkflowPackStageResult;
  index: number;
  caseId: string;
}) {
  return (
    <article style={itemCardStyle}>
      <div style={itemHeaderStyle}>
        <strong>{index + 1}. {stage.display_name || stage.stage_id.replace(/_/g, " ")}</strong>
        <span style={{ ...badgeStyle, backgroundColor: statusColor(stage.status) }}>
          {stage.status.replace(/_/g, " ")}
        </span>
      </div>
      <div style={metaGridStyle}>
        <span>Stage</span><span style={monoStyle}>{stage.stage_id}</span>
        <span>Started</span><span>{formatTs(stage.started_at)}</span>
        <span>Completed</span><span>{formatTs(stage.completed_at)}</span>
      </div>

      {stage.error_message && (
        <div style={{ ...errorPanelStyle, marginTop: "0.5rem" }}>{stage.error_message}</div>
      )}

      {/* Stage-specific summary rendering */}
      <StageSummaryDetails stage={stage} caseId={caseId} />

      {stage.notes.length > 0 && (
        <div style={{ marginTop: "0.5rem" }}>
          {stage.notes.map((note) => (
            <p key={note} style={metaTextStyle}>{note}</p>
          ))}
        </div>
      )}
    </article>
  );
}

function StageSummaryDetails({
  stage,
  caseId,
}: {
  stage: WorkflowPackStageResult;
  caseId: string;
}) {
  const s = stage.summary as Record<string, unknown>;
  if (!s || Object.keys(s).length === 0) {
    return null;
  }

  const num = (key: string): number => (typeof s[key] === "number" ? (s[key] as number) : 0);
  const str = (key: string): string => (typeof s[key] === "string" ? (s[key] as string) : "");
  const bool = (key: string): boolean => s[key] === true;
  const strArr = (key: string): string[] => (Array.isArray(s[key]) ? (s[key] as string[]) : []);

  switch (stage.stage_id) {
    case "intake_document_check":
      return (
        <div style={{ ...subtlePanelStyle, marginTop: "0.5rem" }}>
          <div style={metaGridStyle}>
            <span>Linked documents</span><span>{num("linked_document_count")}</span>
            <span>Required categories</span><span>{num("required_document_count")}</span>
            <span>Review linked docs</span>
            <Link href={`/cases/${caseId}`} style={secondaryLinkStyle}>Case documents</Link>
          </div>
          {strArr("missing_categories").length > 0 && (
            <div style={{ marginTop: "0.4rem" }}>
              <strong style={{ fontSize: "0.78rem", color: "#b91c1c" }}>Missing categories:</strong>
              <span style={{ fontSize: "0.78rem", marginLeft: "0.5rem" }}>
                {strArr("missing_categories").join(", ")}
              </span>
            </div>
          )}
        </div>
      );

    case "extraction_pass":
      return (
        <div style={{ ...subtlePanelStyle, marginTop: "0.5rem" }}>
          <div style={metaGridStyle}>
            <span>Total runs</span><span>{num("total_runs")}</span>
            <span>Completed</span><span>{num("completed_runs")}</span>
            <span>Failed</span><span>{num("failed_runs")}</span>
            <span>Extracted fields</span><span>{num("extracted_field_count")}</span>
            <span>Extraction workspace</span><Link href="/extraction" style={secondaryLinkStyle}>Open extraction</Link>
          </div>
        </div>
      );

    case "checklist_refresh":
      return (
        <div style={{ ...subtlePanelStyle, marginTop: "0.5rem" }}>
          <div style={metaGridStyle}>
            <span>Generated</span><span>{bool("checklist_generated") ? "Yes" : "No"}</span>
            {str("checklist_id") && (
              <>
                <span>Checklist</span>
                <Link href={`/cases/${caseId}/checklist`} style={secondaryLinkStyle}>
                  {str("checklist_id").slice(0, 16)}…
                </Link>
              </>
            )}
            <span>Items</span><span>{num("total_items")}</span>
          </div>
        </div>
      );

    case "readiness_evaluation":
      return (
        <div style={{ ...subtlePanelStyle, marginTop: "0.5rem" }}>
          <div style={metaGridStyle}>
            <span>Readiness</span>
            <span style={{ ...badgeStyle, backgroundColor: readinessColor(str("readiness_status")), width: "fit-content" }}>
              {str("readiness_status").replace(/_/g, " ") || "unknown"}
            </span>
            <span>Total items</span><span>{num("total_items")}</span>
            <span>Supported</span><span>{num("supported_items")}</span>
            <span>Missing</span><span>{num("missing_items")}</span>
          </div>
          {strArr("missing_required_names").length > 0 && (
            <div style={{ marginTop: "0.4rem" }}>
              <strong style={{ fontSize: "0.78rem", color: "#b91c1c" }}>Missing required:</strong>
              <span style={{ fontSize: "0.78rem", marginLeft: "0.5rem" }}>
                {strArr("missing_required_names").join(", ")}
              </span>
            </div>
          )}
        </div>
      );

    case "action_generation":
      return (
        <div style={{ ...subtlePanelStyle, marginTop: "0.5rem" }}>
          <div style={metaGridStyle}>
            <span>Total actions</span><span>{num("total_actions")}</span>
            <span>Open</span><span>{num("open_actions")}</span>
            <span>High priority</span><span>{num("high_priority_actions")}</span>
          </div>
          {strArr("action_categories").length > 0 && (
            <p style={metaTextStyle}>
              Categories: {strArr("action_categories").join(", ")}
            </p>
          )}
        </div>
      );

    case "packet_assembly":
      return (
        <div style={{ ...subtlePanelStyle, marginTop: "0.5rem" }}>
          <div style={metaGridStyle}>
            <span>Generated</span><span>{bool("packet_generated") ? "Yes" : "No"}</span>
            {str("packet_id") && (
              <>
                <span>Packet</span>
                <Link href={`/cases/${caseId}/packets`} style={secondaryLinkStyle}>
                  {str("packet_id").slice(0, 16)}…
                </Link>
              </>
            )}
            <span>Artifacts</span><span>{num("artifact_count")}</span>
          </div>
          {str("skipped_reason") && (
            <p style={metaTextStyle}>{str("skipped_reason")}</p>
          )}
        </div>
      );

    case "submission_draft_preparation":
      return (
        <div style={{ ...subtlePanelStyle, marginTop: "0.5rem" }}>
          <div style={metaGridStyle}>
            <span>Draft generated</span><span>{bool("draft_generated") ? "Yes" : "No"}</span>
            {str("draft_id") && (
              <>
                <span>Draft</span>
                <Link href={`/cases/${caseId}/submission-drafts`} style={secondaryLinkStyle}>
                  {str("draft_id").slice(0, 16)}…
                </Link>
              </>
            )}
            <span>Plan generated</span><span>{bool("plan_generated") ? "Yes" : "No"}</span>
          </div>
          {str("skipped_reason") && (
            <p style={metaTextStyle}>{str("skipped_reason")}</p>
          )}
        </div>
      );

    default:
      return (
        <pre style={preStyle}>{JSON.stringify(s, null, 2)}</pre>
      );
  }
}

function RecommendationPanel({ run }: { run: WorkflowPackRunRecord }) {
  const rec = run.review_recommendation;
  if (!rec) {
    return null;
  }
  const packetStage = run.stage_results.find((stage) => stage.stage_id === "packet_assembly");
  const packetId =
    packetStage
    && packetStage.summary
    && typeof (packetStage.summary as Record<string, unknown>).packet_id === "string"
      ? ((packetStage.summary as Record<string, unknown>).packet_id as string)
      : "";

  const flags: string[] = [];
  if (rec.has_missing_required_documents) flags.push("Missing required documents");
  if (rec.has_open_high_priority_actions) flags.push("Open high-priority actions");
  if (rec.has_failed_stages) flags.push("Failed stages");

  return (
    <section style={sectionCardStyle}>
      <h2 style={sectionTitleStyle}>Operator Review Recommendation</h2>
      <div style={metaGridStyle}>
        <span>Readiness</span>
        <span style={{ ...badgeStyle, backgroundColor: readinessColor(rec.readiness_status), width: "fit-content" }}>
          {rec.readiness_status.replace(/_/g, " ")}
        </span>
        <span>Suggested review stage</span><span>{rec.suggested_next_stage.replace(/_/g, " ")}</span>
      </div>
      {flags.length > 0 && (
        <div style={{ ...subtlePanelStyle, marginTop: "0.75rem", borderColor: "#fbbf24" }}>
          <strong style={{ fontSize: "0.82rem" }}>Attention Required</strong>
          <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.25rem", fontSize: "0.8rem" }}>
            {flags.map((flag) => (
              <li key={flag}>{flag}</li>
            ))}
          </ul>
        </div>
      )}
      {rec.notes.length > 0 && (
        <div style={{ marginTop: "0.5rem" }}>
          {rec.notes.map((note) => (
            <p key={note} style={metaTextStyle}>{note}</p>
          ))}
        </div>
      )}
      <div style={{ ...subtlePanelStyle, marginTop: "0.75rem" }}>
        <strong style={{ fontSize: "0.82rem" }}>Communication follow-ups</strong>
        <div style={{ ...linkRowStyle, marginTop: "0.5rem", marginBottom: 0 }}>
          {rec.has_missing_required_documents && (
            <Link
              href={
                `/cases/${run.case_id}/communication-drafts?template=missing_document_request&workflowPackRunId=${encodeURIComponent(run.run_id)}`
              }
              style={secondaryLinkStyle}
            >
              Prepare missing-document draft
            </Link>
          )}
          <Link
            href={
              `/cases/${run.case_id}/communication-drafts?template=internal_handoff_note&workflowPackRunId=${encodeURIComponent(run.run_id)}`
            }
            style={secondaryLinkStyle}
          >
            Prepare internal handoff draft
          </Link>
          {packetId && (
            <Link
              href={
                `/cases/${run.case_id}/communication-drafts?template=packet_cover_note&workflowPackRunId=${encodeURIComponent(run.run_id)}&packetId=${encodeURIComponent(packetId)}`
              }
              style={secondaryLinkStyle}
            >
              Prepare packet cover note
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function formatTs(value: string): string {
  if (!value) {
    return "—";
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function statusColor(status: string): string {
  switch (status) {
    case "completed":
      return "#15803d";
    case "running":
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

function readinessColor(status: string): string {
  switch (status) {
    case "ready":
    case "complete":
      return "#15803d";
    case "needs_review":
    case "partially_ready":
      return "#b45309";
    case "incomplete":
    case "not_ready":
      return "#b91c1c";
    default:
      return "#64748b";
  }
}

/* ------------------------------------------------------------------ */
/* Styles                                                              */
/* ------------------------------------------------------------------ */

const pageStyle: CSSProperties = { minHeight: "100vh", padding: "2.5rem 1.25rem 3rem", backgroundColor: "#f5f7fa" };
const containerStyle: CSSProperties = { maxWidth: "1180px", margin: "0 auto" };
const linkRowStyle: CSSProperties = { display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1rem" };
const headerStyle: CSSProperties = { marginBottom: "1.5rem" };
const breadcrumbStyle: CSSProperties = { margin: 0, textTransform: "uppercase", letterSpacing: "0.08em", fontSize: "0.8rem", color: "#64748b" };
const titleStyle: CSSProperties = { fontSize: "1.65rem", fontWeight: 700, margin: "0.25rem 0 0.5rem" };
const subtitleStyle: CSSProperties = { color: "#64748b", fontSize: "0.92rem", margin: 0, maxWidth: "840px", lineHeight: 1.55 };
const sectionCardStyle: CSSProperties = { backgroundColor: "white", borderRadius: "0.75rem", padding: "1.25rem 1.5rem", marginBottom: "1.25rem", border: "1px solid #e2e8f0" };
const sectionTitleStyle: CSSProperties = { fontSize: "1.1rem", fontWeight: 600, margin: "0 0 0.75rem" };
const formStyle: CSSProperties = { display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "flex-end" };
const fieldStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: "0.25rem", minWidth: "220px" };
const labelStyle: CSSProperties = { fontSize: "0.8rem", fontWeight: 600, color: "#334155" };
const inputStyle: CSSProperties = { padding: "0.5rem 0.75rem", borderRadius: "0.375rem", border: "1px solid #cbd5e1", fontSize: "0.875rem", width: "100%" };
const primaryButtonStyle: CSSProperties = { padding: "0.5rem 1.25rem", borderRadius: "0.375rem", backgroundColor: "#0d6efd", color: "white", border: "none", fontWeight: 600, cursor: "pointer", fontSize: "0.875rem" };
const panelStyle: CSSProperties = { padding: "0.75rem 1rem", backgroundColor: "#e0f2fe", borderRadius: "0.5rem", marginBottom: "1rem", fontSize: "0.88rem" };
const errorPanelStyle: CSSProperties = { padding: "0.75rem 1rem", backgroundColor: "#fee2e2", color: "#b91c1c", borderRadius: "0.5rem", marginBottom: "1rem", fontSize: "0.88rem" };
const subtlePanelStyle: CSSProperties = { padding: "0.75rem 1rem", backgroundColor: "#f8fafc", borderRadius: "0.5rem", border: "1px solid #e2e8f0" };
const stackStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: "0.75rem" };
const itemCardStyle: CSSProperties = { padding: "0.85rem 1rem", backgroundColor: "#f8fafc", borderRadius: "0.5rem", border: "1px solid #d7dee8" };
const itemHeaderStyle: CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem", gap: "0.75rem", flexWrap: "wrap" };
const metaGridStyle: CSSProperties = { display: "grid", gridTemplateColumns: "160px 1fr", gap: "0.25rem 0.75rem", fontSize: "0.82rem" };
const metaTextStyle: CSSProperties = { margin: "0.25rem 0 0", fontSize: "0.8rem", color: "#64748b" };
const monoStyle: CSSProperties = { fontFamily: "monospace", fontSize: "0.78rem" };
const preStyle: CSSProperties = { backgroundColor: "#f1f5f9", padding: "0.5rem", borderRadius: "0.25rem", fontSize: "0.78rem", whiteSpace: "pre-wrap", margin: "0.5rem 0" };
const badgeStyle: CSSProperties = { fontSize: "0.72rem", fontWeight: 600, color: "white", padding: "0.15rem 0.5rem", borderRadius: "0.25rem", textTransform: "uppercase" };
const secondaryLinkStyle: CSSProperties = { fontSize: "0.82rem", color: "#475569", textDecoration: "underline" };
