"use client";

import Link from "next/link";
import AiDisclosureBanner from "@/components/ai-disclosure-banner";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import type {
  ApprovalStatus,
  AutomationPlan,
  SessionUser,
  SubmissionDraftDetailResponse,
  SubmissionDraftSummary,
  SubmissionMappingFieldDefinition,
  SubmissionTargetMetadata,
  PacketSummary,
} from "@casegraph/agent-sdk";

import { fetchCaseDetail } from "@/lib/cases-api";
import { fetchPackets } from "@/lib/packets-api";
import { shortRef, sourceModeLabel, titleCase } from "@/lib/display-labels";
import {
  createSubmissionDraft,
  fetchSubmissionDraftDetail,
  fetchSubmissionDrafts,
  fetchSubmissionTargets,
  generateSubmissionPlan,
  updateSubmissionApproval,
} from "@/lib/submissions-api";

type ApprovalChoice = ApprovalStatus;

const APPROVAL_LABELS: Record<string, string> = {
  not_requested: "Not Requested",
  awaiting_operator_review: "Awaiting Review",
  approved_for_future_execution: "Approved",
  rejected: "Rejected",
};

function approvalLabel(status: string): string {
  return APPROVAL_LABELS[status] ?? titleCase(status);
}

export default function SubmissionDraftsClient({ caseId, currentUser }: { caseId: string; currentUser: SessionUser }) {
  const [caseTitle, setCaseTitle] = useState("");
  const [packets, setPackets] = useState<PacketSummary[]>([]);
  const [targets, setTargets] = useState<SubmissionTargetMetadata[]>([]);
  const [drafts, setDrafts] = useState<SubmissionDraftSummary[]>([]);
  const [selectedDraft, setSelectedDraft] = useState<SubmissionDraftDetailResponse | null>(null);
  const [selectedPacketId, setSelectedPacketId] = useState("");
  const [selectedTargetId, setSelectedTargetId] = useState("portal_submission");
  const [draftNote, setDraftNote] = useState("");
  const [approvalStatus, setApprovalStatus] = useState<ApprovalChoice>("awaiting_operator_review");
  const [approvedBy, setApprovedBy] = useState(currentUser.id);
  const [approvalNote, setApprovalNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load(preferredDraftId?: string) {
    setLoading(true);
    setError(null);
    try {
      const [caseDetail, packetResponse, targetResponse, draftResponse] = await Promise.all([
        fetchCaseDetail(caseId),
        fetchPackets(caseId),
        fetchSubmissionTargets(),
        fetchSubmissionDrafts(caseId),
      ]);

      setCaseTitle(caseDetail.case.title);
      setPackets(packetResponse.packets);
      setTargets(targetResponse.targets);
      setDrafts(draftResponse.drafts);

      if (!selectedPacketId && packetResponse.packets.length > 0) {
        setSelectedPacketId(packetResponse.packets[0].packet_id);
      }
      if (!selectedTargetId && targetResponse.targets.length > 0) {
        setSelectedTargetId(targetResponse.targets[0].target_id);
      }

      const nextDraftId = preferredDraftId ?? draftResponse.drafts[0]?.draft_id;
      if (nextDraftId) {
        const detail = await fetchSubmissionDraftDetail(nextDraftId);
        setSelectedDraft(detail);
      } else {
        setSelectedDraft(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load submission drafts. Try refreshing the page.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [caseId]);

  useEffect(() => {
    if (!selectedDraft) {
      setApprovalStatus("awaiting_operator_review");
      setApprovedBy("");
      setApprovalNote("");
      return;
    }
    setApprovalStatus(selectedDraft.approval.approval_status);
    setApprovedBy(selectedDraft.approval.approved_by);
    setApprovalNote(selectedDraft.approval.approval_note);
  }, [selectedDraft]);

  const selectedTarget = useMemo(
    () => targets.find((target) => target.target_id === selectedTargetId) ?? null,
    [targets, selectedTargetId],
  );

  async function handleCreateDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPacketId || !selectedTargetId) return;
    setWorking(true);
    setMessage(null);
    try {
      const response = await createSubmissionDraft(caseId, {
        packet_id: selectedPacketId,
        submission_target_id: selectedTargetId,
        note: draftNote.trim(),
      });
      setDraftNote("");
      setMessage(response.result.message || "Submission draft created. Review the field mappings below before approving.");
      await load(response.draft.draft_id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to create submission draft. Verify packet and target selections.");
    } finally {
      setWorking(false);
    }
  }

  async function handleSelectDraft(draftId: string) {
    setWorking(true);
    setMessage(null);
    try {
      setSelectedDraft(await fetchSubmissionDraftDetail(draftId));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to load submission draft detail. Try selecting the draft again.");
    } finally {
      setWorking(false);
    }
  }

  async function handleGeneratePlan() {
    if (!selectedDraft) return;
    setWorking(true);
    setMessage(null);
    try {
      const response = await generateSubmissionPlan(selectedDraft.draft.draft_id, { dry_run: true });
      setMessage(response.result.message || "Automation preview generated. Review the plan steps before approving.");
      setSelectedDraft(await fetchSubmissionDraftDetail(selectedDraft.draft.draft_id));
      setDrafts(await refreshDraftList(caseId));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to generate automation plan. The draft may need more mappings resolved first.");
    } finally {
      setWorking(false);
    }
  }

  async function handleApprovalUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDraft) return;
    setWorking(true);
    setMessage(null);
    try {
      const response = await updateSubmissionApproval(selectedDraft.draft.draft_id, {
        approval_status: approvalStatus,
        approved_by: approvedBy.trim(),
        approval_note: approvalNote.trim(),
      });
      setMessage(response.result.message || "Approval status updated.");
      setSelectedDraft(await fetchSubmissionDraftDetail(selectedDraft.draft.draft_id));
      setDrafts(await refreshDraftList(caseId));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to update approval metadata. Check operator identity and try again.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <div style={linkRowStyle}>
          <Link href={`/cases/${caseId}`} style={secondaryLinkStyle}>Case workspace</Link>
          <Link href={`/cases/${caseId}/handoff`} style={secondaryLinkStyle}>Reviewed handoff</Link>
          <Link href={`/cases/${caseId}/packets`} style={secondaryLinkStyle}>Packets &amp; export</Link>
          <Link href={`/cases/${caseId}/communication-drafts`} style={secondaryLinkStyle}>Communication drafts</Link>
          <Link href={`/cases/${caseId}/review`} style={secondaryLinkStyle}>Operator review</Link>
          <Link href={`/cases/${caseId}/automation-runs`} style={secondaryLinkStyle}>Automation runs</Link>
        </div>

        <header style={headerStyle}>
          <div>
            <p style={breadcrumbStyle}>Submission Drafts</p>
            <h1 style={titleStyle}>{caseTitle || "Submission Preparation"}</h1>
            <p style={subtitleStyle}>
              Prepare and review submissions for this case. Nothing is sent until you approve it.
            </p>
          </div>
        </header>

        <AiDisclosureBanner />

        {message && <div style={panelStyle}>{message}</div>}

        {loading ? (
          <div style={panelStyle}>Loading submission drafts…</div>
        ) : error ? (
          <div style={errorPanelStyle}>{error}</div>
        ) : (
          <>
            <section style={sectionCardStyle}>
              <h2 style={sectionTitleStyle}>Create Submission Draft</h2>
              <form onSubmit={handleCreateDraft} style={formStyle}>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Case Packet</span>
                  <select
                    value={selectedPacketId}
                    onChange={(event) => setSelectedPacketId(event.target.value)}
                    style={inputStyle}
                  >
                    <option value="">Select packet</option>
                    {packets.map((packet) => (
                      <option key={packet.packet_id} value={packet.packet_id}>
                          Packet {packets.indexOf(packet) + 1} • {formatTimestamp(packet.generated_at)} • {describeSourceMode(packet.source_mode)}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Submission Target</span>
                  <select
                    value={selectedTargetId}
                    onChange={(event) => setSelectedTargetId(event.target.value)}
                    style={inputStyle}
                  >
                    {targets.map((target) => (
                      <option key={target.target_id} value={target.target_id}>
                        {target.display_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={{ ...fieldStyle, minWidth: "260px" }}>
                  <span style={labelStyle}>Draft Note (optional)</span>
                  <input
                    value={draftNote}
                    onChange={(event) => setDraftNote(event.target.value)}
                    style={inputStyle}
                    placeholder="Reason or operator context"
                  />
                </label>
                <button
                  type="submit"
                  style={primaryButtonStyle}
                  disabled={working || !selectedPacketId || !selectedTargetId}
                >
                  {working ? "Working..." : "Create Draft"}
                </button>
              </form>
              {selectedTarget && (
                <div style={subtlePanelStyle}>
                  <strong>{selectedTarget.display_name}</strong>
                  <p style={helperTextStyle}>{selectedTarget.description}</p>
                  {selectedTarget.notes.map((note) => (
                    <p key={note} style={metaTextStyle}>{note}</p>
                  ))}
                </div>
              )}
            </section>

            <section style={sectionCardStyle}>
              <h2 style={sectionTitleStyle}>Submission Drafts</h2>
              {drafts.length === 0 ? (
                <div style={subtlePanelStyle}>No submission drafts yet. Select a target and packet above to create one.</div>
              ) : (
                <div style={stackStyle}>
                  {drafts.map((draft) => (
                    <article
                      key={draft.draft_id}
                      style={{
                        ...itemCardStyle,
                        cursor: "pointer",
                        borderColor: selectedDraft?.draft.draft_id === draft.draft_id ? "#0d6efd" : "#d7dee8",
                      }}
                      onClick={() => handleSelectDraft(draft.draft_id)}
                    >
                      <div style={itemHeaderStyle}>
                        <strong>{titleCase(draft.submission_target_id)}</strong>
                        <span style={{ ...badgeStyle, backgroundColor: statusColor(draft.status) }}>
                          {titleCase(draft.status)}
                        </span>
                      </div>
                      <div style={metaGridStyle}>
                        <span>Data source</span><span>{describeSourceMode(draft.source_mode)}</span>
                        <span>Approval</span><span>{approvalLabel(draft.approval_status)}</span>
                        <span>Mappings</span><span>{draft.mapping_count}</span>
                        <span>Needs review</span><span>{draft.unresolved_mapping_count}</span>
                        <span>Updated</span><span>{formatTimestamp(draft.updated_at)}</span>
                      </div>
                      {draft.note && <p style={metaTextStyle}>Note: {draft.note}</p>}
                    </article>
                  ))}
                </div>
              )}
            </section>

            {selectedDraft && (
              <>
                <section style={sectionCardStyle}>
                  <div style={sectionHeaderStyle}>
                    <h2 style={sectionTitleStyle}>Draft Overview</h2>
                    <button type="button" style={primaryButtonStyle} onClick={handleGeneratePlan} disabled={working}>
                      {selectedDraft.plan ? "Refresh Automation Preview" : "Preview Automation Steps"}
                    </button>
                  </div>
                  <div style={metaGridStyle}>
                    <span>Target</span><span>{selectedDraft.target.display_name}</span>
                    <span>Draft status</span><span>{titleCase(selectedDraft.draft.status)}</span>
                    <span>Approval</span><span>{approvalLabel(selectedDraft.approval.approval_status)}</span>
                    <span>Data source</span><span>{describeSourceMode(selectedDraft.source_metadata.source_mode)}</span>
                    <span>Snapshot sign-off</span><span>{titleCase(selectedDraft.source_metadata.source_snapshot_signoff_status)}</span>
                    <span>Domain pack</span><span>{selectedDraft.source_metadata.domain_pack_id ? titleCase(selectedDraft.source_metadata.domain_pack_id) : "None"}</span>
                    <span>Case type</span><span>{selectedDraft.source_metadata.case_type_id ? titleCase(selectedDraft.source_metadata.case_type_id) : "None"}</span>
                    <span>Readiness</span><span>{selectedDraft.source_metadata.readiness_status ? titleCase(selectedDraft.source_metadata.readiness_status) : "Not evaluated"}</span>
                    <span>Documents</span><span>{selectedDraft.source_metadata.linked_document_count}</span>
                    <span>Extractions</span><span>{selectedDraft.source_metadata.extraction_count}</span>
                    <span>Candidate sources</span><span>{selectedDraft.source_metadata.candidate_source_count}</span>
                  </div>
                  <div style={subtlePanelStyle}>
                    {selectedDraft.target.notes.map((note) => (
                      <p key={note} style={metaTextStyle}>{note}</p>
                    ))}
                  </div>
                </section>

                <section style={sectionCardStyle}>
                  <h2 style={sectionTitleStyle}>Mapping Preview</h2>
                  <div style={stackStyle}>
                    {selectedDraft.mappings.map((mapping) => (
                      <MappingCard key={mapping.mapping_id} mapping={mapping} />
                    ))}
                  </div>
                </section>

                <section style={sectionCardStyle}>
                  <h2 style={sectionTitleStyle}>Approval Metadata</h2>
                  <form onSubmit={handleApprovalUpdate} style={formStyle}>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Approval Status</span>
                      <select
                        value={approvalStatus}
                        onChange={(event) => setApprovalStatus(event.target.value as ApprovalChoice)}
                        style={inputStyle}
                      >
                        <option value="not_requested">Not Requested</option>
                        <option value="awaiting_operator_review">Awaiting Review</option>
                        <option value="approved_for_future_execution">Approved</option>
                        <option value="rejected">Rejected</option>
                      </select>
                    </label>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Operator</span>
                      <input
                        value={currentUser.name || currentUser.email || approvedBy}
                        readOnly
                        style={{ ...inputStyle, backgroundColor: "#f8fafc", color: "#475569" }}
                      />
                    </label>
                    <label style={{ ...fieldStyle, minWidth: "280px" }}>
                      <span style={labelStyle}>Approval Note</span>
                      <input
                        value={approvalNote}
                        onChange={(event) => setApprovalNote(event.target.value)}
                        style={inputStyle}
                        placeholder="Reason, caveat, or review comment"
                      />
                    </label>
                    <button type="submit" style={primaryButtonStyle} disabled={working}>
                      {working ? "Working..." : "Save Approval"}
                    </button>
                  </form>
                </section>

                <section style={sectionCardStyle}>
                  <h2 style={sectionTitleStyle}>Automation Preview</h2>
                  {selectedDraft.plan ? (
                    <PlanPanel plan={selectedDraft.plan} />
                  ) : (
                    <div style={subtlePanelStyle}>
                      No automation preview has been generated for this draft yet.
                    </div>
                  )}
                </section>
              </>
            )}
          </>
        )}
      </section>
    </main>
  );
}

function MappingCard({ mapping }: { mapping: SubmissionMappingFieldDefinition }) {
  return (
    <article style={itemCardStyle}>
      <div style={itemHeaderStyle}>
        <strong>{mapping.target_field.display_label || mapping.target_field.field_name}</strong>
        <span style={{ ...badgeStyle, backgroundColor: statusColor(mapping.status) }}>
          {titleCase(mapping.status)}
        </span>
      </div>
      <div style={metaGridStyle}>
        <span>Section</span><span>{mapping.target_field.target_section}</span>
        <span>Required</span><span>{mapping.target_field.required ? "Yes" : "No"}</span>
        <span>Preview</span><span>{mapping.value_preview?.text_value || "No value available"}</span>
        <span>Source</span><span>{mapping.source_reference?.source_path || "Unresolved"}</span>
      </div>
      {mapping.notes.length > 0 && mapping.notes.map((note) => (
        <p key={note} style={metaTextStyle}>{note}</p>
      ))}
    </article>
  );
}

function PlanPanel({ plan }: { plan: AutomationPlan }) {
  return (
    <div style={stackStyle}>
      <div style={subtlePanelStyle}>
        <div style={metaGridStyle}>
          <span>Plan status</span><span>{titleCase(plan.status)}</span>
          <span>Data source</span><span>{describeSourceMode(plan.source_mode)}</span>
          <span>Approved review</span><span>{shortRef(plan.source_reviewed_snapshot_id) || "None"}</span>
          <span>Generated</span><span>{formatTimestamp(plan.generated_at)}</span>
          <span>Total steps</span><span>{plan.dry_run_summary.total_steps}</span>
          <span>Future automation</span><span>{plan.dry_run_summary.future_automation_steps}</span>
          <span>Needs input</span><span>{plan.dry_run_summary.requires_human_input_steps}</span>
          <span>Blocked</span><span>{plan.dry_run_summary.blocked_steps}</span>
        </div>
        {plan.dry_run_summary.notes.map((note) => (
          <p key={note} style={metaTextStyle}>{note}</p>
        ))}
      </div>
      {plan.steps.map((step) => (
        <article key={step.step_id} style={itemCardStyle}>
          <div style={itemHeaderStyle}>
            <strong>{step.step_index}. {step.title}</strong>
            <div style={badgeRowStyle}>
              <span style={{ ...badgeStyle, backgroundColor: executionModeColor(step.execution_mode) }}>
                {titleCase(step.execution_mode)}
              </span>
              <span style={{ ...badgeStyle, backgroundColor: statusColor(step.status) }}>
                {titleCase(step.status)}
              </span>
            </div>
          </div>
          <p style={itemTextStyle}>{step.description}</p>
          <div style={metaGridStyle}>
            <span>Step type</span><span>{titleCase(step.step_type)}</span>
            <span>Target ref</span><span>{step.target_reference || "-"}</span>
            <span>Backend</span><span>{step.backend_id ?? "None"}</span>
            <span>Tool</span><span>{step.tool_id ?? "None"}</span>
            <span>Checkpoint required</span><span>{step.checkpoint_required ? "Yes" : "No"}</span>
            {step.checkpoint_reason && <><span>Checkpoint reason</span><span>{step.checkpoint_reason}</span></>}
          </div>
          {step.fallback_hint && (
            <div style={{ ...subtlePanelStyle, marginTop: "0.75rem" }}>
              <div style={metaGridStyle}>
                <span>Fallback mode</span><span>{titleCase(step.fallback_hint.recommended_mode)}</span>
                <span>Providers</span><span>{step.fallback_hint.supported_provider_ids.join(", ") || "None"}</span>
              </div>
              <p style={metaTextStyle}>{step.fallback_hint.reason}</p>
              {step.fallback_hint.notes.map((note) => (
                <p key={note} style={metaTextStyle}>{note}</p>
              ))}
            </div>
          )}
          {step.notes.map((note) => (
            <p key={note} style={metaTextStyle}>{note}</p>
          ))}
        </article>
      ))}
    </div>
  );
}

async function refreshDraftList(caseId: string): Promise<SubmissionDraftSummary[]> {
  const response = await fetchSubmissionDrafts(caseId);
  return response.drafts;
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function describeSourceMode(value: string): string {
  return sourceModeLabel(value);
}

function statusColor(status: string): string {
  switch (status) {
    case "approved_for_future_execution":
    case "mapped_preview":
      return "#15803d";
    case "awaiting_operator_review":
    case "future_automation_placeholder":
      return "#0d6efd";
    case "candidate_available":
    case "partial":
      return "#b45309";
    case "blocked":
    case "rejected":
    case "requires_human_input":
      return "#b91c1c";
    case "superseded_placeholder":
      return "#475569";
    default:
      return "#64748b";
  }
}

function executionModeColor(mode: string): string {
  switch (mode) {
    case "playwright_mcp":
      return "#0d6efd";
    case "computer_use_fallback":
      return "#b45309";
    case "manual_only":
      return "#475569";
    case "blocked":
      return "#b91c1c";
    default:
      return "#64748b";
  }
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "2.5rem 1.25rem 3rem",
  backgroundColor: "#f5f7fa",
};

const containerStyle: CSSProperties = {
  maxWidth: "1180px",
  margin: "0 auto",
};

const linkRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.75rem",
  flexWrap: "wrap",
  marginBottom: "1rem",
};

const headerStyle: CSSProperties = {
  marginBottom: "1.5rem",
};

const breadcrumbStyle: CSSProperties = {
  margin: 0,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  fontSize: "0.8rem",
  color: "#64748b",
};

const titleStyle: CSSProperties = {
  margin: "0.5rem 0 0",
  fontSize: "2.1rem",
  color: "#102033",
};

const subtitleStyle: CSSProperties = {
  maxWidth: "760px",
  color: "#55657a",
  lineHeight: 1.6,
};

const sectionCardStyle: CSSProperties = {
  padding: "1.1rem",
  borderRadius: "16px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
  marginBottom: "1rem",
};

const sectionHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "center",
  flexWrap: "wrap",
};

const sectionTitleStyle: CSSProperties = {
  margin: "0 0 0.75rem",
  fontSize: "1.2rem",
  color: "#102033",
};

const formStyle: CSSProperties = {
  display: "flex",
  gap: "0.75rem",
  alignItems: "flex-end",
  flexWrap: "wrap",
};

const fieldStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.35rem",
  flex: 1,
  minWidth: "220px",
};

const labelStyle: CSSProperties = {
  fontSize: "0.85rem",
  color: "#475569",
  fontWeight: 600,
};

const inputStyle: CSSProperties = {
  padding: "0.6rem 0.8rem",
  borderRadius: "10px",
  border: "1px solid #cbd5e1",
  fontSize: "0.95rem",
  color: "#1e293b",
  backgroundColor: "#f8fafc",
};

const primaryButtonStyle: CSSProperties = {
  padding: "0.6rem 1.3rem",
  borderRadius: "10px",
  border: "none",
  backgroundColor: "#0d6efd",
  color: "#ffffff",
  fontWeight: 600,
  fontSize: "0.95rem",
  cursor: "pointer",
};

const panelStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  borderRadius: "12px",
  backgroundColor: "#edf4ff",
  border: "1px solid #bfd7ff",
  color: "#123a74",
  marginBottom: "1rem",
};

const errorPanelStyle: CSSProperties = {
  ...panelStyle,
  backgroundColor: "#fff1f2",
  borderColor: "#fecdd3",
  color: "#9f1239",
};

const subtlePanelStyle: CSSProperties = {
  padding: "0.85rem 1rem",
  borderRadius: "12px",
  backgroundColor: "#f8fafc",
  border: "1px solid #e2e8f0",
};

const stackStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.75rem",
};

const itemCardStyle: CSSProperties = {
  padding: "0.95rem 1rem",
  borderRadius: "14px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
};

const itemHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "center",
  flexWrap: "wrap",
  marginBottom: "0.6rem",
};

const badgeStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "0.25rem 0.6rem",
  borderRadius: "999px",
  color: "#ffffff",
  fontSize: "0.8rem",
  fontWeight: 700,
};

const badgeRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.4rem",
  justifyContent: "flex-end",
};

const metaGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "max-content 1fr",
  gap: "0.35rem 0.85rem",
  fontSize: "0.92rem",
  color: "#334155",
};

const metaTextStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  fontSize: "0.9rem",
  color: "#55657a",
};

const itemTextStyle: CSSProperties = {
  margin: "0 0 0.6rem",
  color: "#334155",
  lineHeight: 1.55,
};

const helperTextStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  color: "#55657a",
  lineHeight: 1.5,
};

const monoStyle: CSSProperties = {
  fontFamily: "Consolas, monospace",
};

const secondaryLinkStyle: CSSProperties = {
  color: "#0d6efd",
  fontWeight: 600,
  textDecoration: "none",
};