"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import type {
  HandoffEligibilitySummary,
  ReviewedSnapshotRecord,
  WorkStatusSummary,
} from "@casegraph/agent-sdk";

import { WorkStatusSnapshot } from "@/components/work-management/work-status-panels";
import { fetchCaseDetail } from "@/lib/cases-api";
import {
  createReviewedSnapshot,
  fetchHandoffEligibility,
  fetchReviewedSnapshots,
  selectReviewedSnapshotForHandoff,
  signoffReviewedSnapshot,
} from "@/lib/reviewed-handoff-api";
import { fetchCaseWorkStatus } from "@/lib/work-management-api";

export default function HandoffClient({ caseId }: { caseId: string }) {
  const [caseTitle, setCaseTitle] = useState("");
  const [snapshots, setSnapshots] = useState<ReviewedSnapshotRecord[]>([]);
  const [eligibility, setEligibility] = useState<HandoffEligibilitySummary | null>(null);
  const [workStatus, setWorkStatus] = useState<WorkStatusSummary | null>(null);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState("");
  const [operatorId, setOperatorId] = useState("");
  const [operatorDisplayName, setOperatorDisplayName] = useState("");
  const [createNote, setCreateNote] = useState("");
  const [signoffNote, setSignoffNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load(preferredSnapshotId?: string) {
    setLoading(true);
    setError(null);
    try {
      const [caseDetail, snapshotsResponse, eligibilityResponse, workResponse] = await Promise.all([
        fetchCaseDetail(caseId),
        fetchReviewedSnapshots(caseId),
        fetchHandoffEligibility(caseId),
        fetchCaseWorkStatus(caseId),
      ]);

      setCaseTitle(caseDetail.case.title);
      setSnapshots(snapshotsResponse.snapshots);
      setEligibility(eligibilityResponse.eligibility);
      setWorkStatus(workResponse.work_status);

      const nextSnapshotId = preferredSnapshotId
        ?? eligibilityResponse.eligibility.selected_snapshot_id
        ?? snapshotsResponse.snapshots[0]?.snapshot_id
        ?? "";
      setSelectedSnapshotId(nextSnapshotId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load reviewed handoff workspace.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [caseId]);

  const selectedSnapshot = useMemo(
    () => snapshots.find((snapshot) => snapshot.snapshot_id === selectedSnapshotId) ?? null,
    [selectedSnapshotId, snapshots],
  );

  const selectedSnapshotSelectionIssues = useMemo(() => {
    if (!selectedSnapshot) {
      return [] as string[];
    }

    const issues: string[] = [];
    if (selectedSnapshot.signoff_status !== "signed_off") {
      issues.push("This snapshot must be explicitly signed off before it can be selected for downstream handoff.");
    }
    if (selectedSnapshot.summary.unresolved_item_count > 0) {
      issues.push(
        `${selectedSnapshot.summary.unresolved_item_count} unresolved review item(s) must be cleared before selection.`,
      );
    }
    if (!selectedSnapshot.summary.required_requirement_reviews_complete) {
      issues.push("Every required checklist item must be explicitly reviewed before selection.");
    }
    return issues;
  }, [selectedSnapshot]);

  async function handleCreateSnapshot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWorking(true);
    setMessage(null);
    try {
      const response = await createReviewedSnapshot(caseId, {
        note: createNote.trim(),
        operator_id: operatorId.trim(),
        operator_display_name: operatorDisplayName.trim(),
      });
      setMessage(response.result.message || "Reviewed snapshot created.");
      setCreateNote("");
      await load(response.snapshot.snapshot_id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to create reviewed snapshot.");
    } finally {
      setWorking(false);
    }
  }

  async function handleSignoff() {
    if (!selectedSnapshot) {
      return;
    }
    setWorking(true);
    setMessage(null);
    try {
      const response = await signoffReviewedSnapshot(selectedSnapshot.snapshot_id, {
        operator_id: operatorId.trim(),
        operator_display_name: operatorDisplayName.trim(),
        note: signoffNote.trim(),
      });
      setMessage(response.result.message || "Reviewed snapshot signed off.");
      setSignoffNote("");
      await load(selectedSnapshot.snapshot_id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to sign off reviewed snapshot.");
    } finally {
      setWorking(false);
    }
  }

  async function handleSelectForHandoff() {
    if (!selectedSnapshot) {
      return;
    }
    setWorking(true);
    setMessage(null);
    try {
      const response = await selectReviewedSnapshotForHandoff(caseId, selectedSnapshot.snapshot_id);
      setMessage(response.result.message || "Reviewed snapshot selected for handoff.");
      await load(selectedSnapshot.snapshot_id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to select reviewed snapshot for handoff.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <div style={linkRowStyle}>
          <Link href={`/cases/${caseId}`} style={secondaryLinkStyle}>Case workspace</Link>
          <Link href={`/cases/${caseId}/validation`} style={secondaryLinkStyle}>Validation</Link>
          <Link href={`/cases/${caseId}/packets`} style={secondaryLinkStyle}>Packets</Link>
          <Link href={`/cases/${caseId}/submission-drafts`} style={secondaryLinkStyle}>Submission drafts</Link>
          <Link href={`/cases/${caseId}/audit`} style={secondaryLinkStyle}>Audit timeline</Link>
          <Link href={`/cases/${caseId}/releases`} style={secondaryLinkStyle}>Release bundles</Link>
        </div>

        <header style={headerStyle}>
          <div>
            <p style={breadcrumbStyle}>Reviewed Handoff</p>
            <h1 style={titleStyle}>{caseTitle || "Reviewed Snapshot Workspace"}</h1>
            <p style={subtitleStyle}>
              Create immutable reviewed snapshots from current validation state, record explicit operator sign-off,
              inspect descriptive handoff eligibility, and mark the eligible snapshot downstream packet generation should use.
            </p>
          </div>
        </header>

        {message && <div style={panelStyle}>{message}</div>}

        {workStatus && (
          <WorkStatusSnapshot
            status={workStatus}
            label="Work Context"
            compact
            actions={[
              { href: "/work", label: "Open Work Board", tone: "primary" },
              { href: `/cases/${caseId}`, label: "Case Workspace" },
            ]}
          />
        )}

        {loading ? (
          <div style={panelStyle}>Loading reviewed handoff workspace...</div>
        ) : error ? (
          <div style={errorPanelStyle}>{error}</div>
        ) : (
          <>
            {eligibility && (
              <section style={sectionCardStyle}>
                <h2 style={sectionTitleStyle}>Current Handoff Eligibility</h2>
                <div style={metaGridStyle}>
                  <span>Release gate</span><span style={{ ...badgeStyle, backgroundColor: eligibility.eligible ? "#15803d" : "#b91c1c", color: "#ffffff" }}>{eligibility.release_gate_status.replace(/_/g, " ")}</span>
                  <span>Candidate snapshot</span><span style={monoStyle}>{eligibility.snapshot_id || "None"}</span>
                  <span>Selected snapshot</span><span style={monoStyle}>{eligibility.selected_snapshot_id || "None"}</span>
                  <span>Snapshot status</span><span>{eligibility.snapshot_status?.replace(/_/g, " ") ?? "None"}</span>
                  <span>Sign-off</span><span>{eligibility.signoff_status.replace(/_/g, " ")}</span>
                  <span>Unresolved items</span><span>{eligibility.unresolved_review_item_count}</span>
                  <span>Required requirement reviews complete</span><span>{eligibility.required_requirement_reviews_complete ? "Yes" : "No"}</span>
                </div>
                <div style={{ ...subtlePanelStyle, marginTop: "0.75rem" }}>
                  {eligibility.reasons.map((reason) => (
                    <p key={reason.code} style={metaTextStyle}>
                      {reason.blocking ? "Blocking" : "Info"}: {reason.message}
                    </p>
                  ))}
                </div>
              </section>
            )}

            <section style={sectionCardStyle}>
              <h2 style={sectionTitleStyle}>Create Reviewed Snapshot</h2>
              <form onSubmit={handleCreateSnapshot} style={formStyle}>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Operator identifier</span>
                  <input value={operatorId} onChange={(event) => setOperatorId(event.target.value)} style={inputStyle} placeholder="Optional for snapshot creation" />
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Display name</span>
                  <input value={operatorDisplayName} onChange={(event) => setOperatorDisplayName(event.target.value)} style={inputStyle} placeholder="Optional operator name" />
                </label>
                <label style={{ ...fieldStyle, minWidth: "280px" }}>
                  <span style={labelStyle}>Snapshot note</span>
                  <input value={createNote} onChange={(event) => setCreateNote(event.target.value)} style={inputStyle} placeholder="Reason or review context" />
                </label>
                <button type="submit" style={primaryButtonStyle} disabled={working}>
                  {working ? "Working..." : "Create Snapshot"}
                </button>
              </form>
            </section>

            <section style={sectionCardStyle}>
              <h2 style={sectionTitleStyle}>Reviewed Snapshots</h2>
              {snapshots.length === 0 ? (
                <div style={subtlePanelStyle}>No reviewed snapshots have been created for this case yet.</div>
              ) : (
                <div style={stackStyle}>
                  {snapshots.map((snapshot) => (
                    <article
                      key={snapshot.snapshot_id}
                      style={{
                        ...itemCardStyle,
                        cursor: "pointer",
                        borderColor: selectedSnapshotId === snapshot.snapshot_id ? "#0d6efd" : "#d7dee8",
                      }}
                      onClick={() => setSelectedSnapshotId(snapshot.snapshot_id)}
                    >
                      <div style={itemHeaderStyle}>
                        <strong style={monoStyle}>{snapshot.snapshot_id.slice(0, 12)}…</strong>
                        <div style={badgeRowStyle}>
                          <span style={badgeStyle}>{snapshot.status.replace(/_/g, " ")}</span>
                          <span style={{ ...badgeStyle, backgroundColor: snapshot.signoff_status === "signed_off" ? "#dcfce7" : "#fee2e2", color: snapshot.signoff_status === "signed_off" ? "#166534" : "#991b1b" }}>
                            {snapshot.signoff_status.replace(/_/g, " ")}
                          </span>
                        </div>
                      </div>
                      <div style={metaGridStyle}>
                        <span>Created</span><span>{formatTimestamp(snapshot.created_at)}</span>
                        <span>Selected</span><span>{snapshot.selected_at ? formatTimestamp(snapshot.selected_at) : "No"}</span>
                        <span>Included fields</span><span>{snapshot.summary.included_fields}</span>
                        <span>Reviewed requirements</span><span>{snapshot.summary.reviewed_requirements}</span>
                        <span>Unresolved items</span><span>{snapshot.summary.unresolved_item_count}</span>
                      </div>
                      {snapshot.note && <p style={metaTextStyle}>Note: {snapshot.note}</p>}
                    </article>
                  ))}
                </div>
              )}
            </section>

            {selectedSnapshot && (
              <section style={sectionCardStyle}>
                <div style={sectionHeaderStyle}>
                  <h2 style={sectionTitleStyle}>Snapshot Detail</h2>
                  <div style={actionRowStyle}>
                    <button
                      type="button"
                      style={secondaryButtonStyle}
                      onClick={handleSelectForHandoff}
                      disabled={
                        working
                        || selectedSnapshot.status === "selected_for_handoff"
                        || selectedSnapshotSelectionIssues.length > 0
                      }
                    >
                      {selectedSnapshot.status === "selected_for_handoff" ? "Selected for Handoff" : "Select for Handoff"}
                    </button>
                    <button type="button" style={primaryButtonStyle} onClick={handleSignoff} disabled={working || selectedSnapshot.signoff_status === "signed_off" || !operatorId.trim()}>
                      {selectedSnapshot.signoff_status === "signed_off" ? "Signed Off" : "Sign Off Snapshot"}
                    </button>
                  </div>
                </div>

                <div style={metaGridStyle}>
                  <span>Snapshot ID</span><span style={monoStyle}>{selectedSnapshot.snapshot_id}</span>
                  <span>Status</span><span>{selectedSnapshot.status.replace(/_/g, " ")}</span>
                  <span>Sign-off</span><span>{selectedSnapshot.signoff_status.replace(/_/g, " ")}</span>
                  <span>Created</span><span>{formatTimestamp(selectedSnapshot.created_at)}</span>
                  <span>Selected at</span><span>{selectedSnapshot.selected_at ? formatTimestamp(selectedSnapshot.selected_at) : "Not selected"}</span>
                  <span>Linked documents</span><span>{selectedSnapshot.source_metadata.linked_document_ids.length}</span>
                  <span>Extraction runs</span><span>{selectedSnapshot.source_metadata.extraction_ids.length}</span>
                  <span>Validation records</span><span>{selectedSnapshot.source_metadata.validation_record_ids.length}</span>
                  <span>Requirement reviews</span><span>{selectedSnapshot.source_metadata.requirement_review_ids.length}</span>
                </div>

                <div style={{ ...subtlePanelStyle, marginTop: "0.75rem" }}>
                  {selectedSnapshot.note && <p style={metaTextStyle}>Snapshot note: {selectedSnapshot.note}</p>}
                  {selectedSnapshot.signoff && (
                    <p style={metaTextStyle}>
                      Signed off by {selectedSnapshot.signoff.actor.display_name || selectedSnapshot.signoff.actor.actor_id} at {formatTimestamp(selectedSnapshot.signoff.created_at)}.
                    </p>
                  )}
                </div>

                {selectedSnapshotSelectionIssues.length > 0 && (
                  <div style={{ ...errorPanelStyle, marginTop: "0.75rem" }}>
                    {selectedSnapshotSelectionIssues.map((issue) => (
                      <p key={issue} style={metaTextStyle}>{issue}</p>
                    ))}
                  </div>
                )}

                <div style={formStyle}>
                  <label style={{ ...fieldStyle, minWidth: "280px" }}>
                    <span style={labelStyle}>Sign-off note</span>
                    <input value={signoffNote} onChange={(event) => setSignoffNote(event.target.value)} style={inputStyle} placeholder="Optional sign-off note" />
                  </label>
                </div>

                <div style={detailGridStyle}>
                  <div style={detailPanelStyle}>
                    <h3 style={detailTitleStyle}>Included Reviewed Fields</h3>
                    {selectedSnapshot.fields.filter((field) => field.included_in_snapshot).length === 0 ? (
                      <p style={metaTextStyle}>No reviewed fields were included in this snapshot.</p>
                    ) : (
                      <div style={stackStyle}>
                        {selectedSnapshot.fields.filter((field) => field.included_in_snapshot).map((field) => (
                          <div key={`${field.extraction_id}/${field.field_id}`} style={detailRowStyle}>
                            <strong>{field.field_id}</strong>
                            <span style={monoStyle}>{String(field.snapshot_value ?? "")}</span>
                            <span style={metaTextStyle}>{field.validation_status.replace(/_/g, " ")}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div style={detailPanelStyle}>
                    <h3 style={detailTitleStyle}>Reviewed Requirements</h3>
                    {selectedSnapshot.requirements.filter((requirement) => requirement.included_in_snapshot).length === 0 ? (
                      <p style={metaTextStyle}>No reviewed requirements were included in this snapshot.</p>
                    ) : (
                      <div style={stackStyle}>
                        {selectedSnapshot.requirements.filter((requirement) => requirement.included_in_snapshot).map((requirement) => (
                          <div key={requirement.item_id} style={detailRowStyle}>
                            <strong>{requirement.display_name}</strong>
                            <span>{requirement.priority}</span>
                            <span style={metaTextStyle}>{requirement.review_status.replace(/_/g, " ")}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {selectedSnapshot.unresolved_items.length > 0 && (
                  <div style={{ ...detailPanelStyle, marginTop: "1rem" }}>
                    <h3 style={detailTitleStyle}>Unresolved Review Items</h3>
                    <div style={stackStyle}>
                      {selectedSnapshot.unresolved_items.map((item) => (
                        <div key={`${item.item_type}/${item.entity_id}`} style={detailRowStyle}>
                          <strong>{item.display_label || item.entity_id}</strong>
                          <span>{item.current_status.replace(/_/g, " ")}</span>
                          {item.note && <span style={metaTextStyle}>{item.note}</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </section>
    </main>
  );
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
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
  gap: "0.75rem",
  alignItems: "center",
  marginBottom: "0.75rem",
  flexWrap: "wrap",
};

const sectionTitleStyle: CSSProperties = {
  margin: 0,
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
  minWidth: "200px",
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

const secondaryButtonStyle: CSSProperties = {
  padding: "0.6rem 1.1rem",
  borderRadius: "10px",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  color: "#334155",
  fontWeight: 600,
  fontSize: "0.95rem",
  cursor: "pointer",
};

const actionRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.75rem",
  flexWrap: "wrap",
};

const panelStyle: CSSProperties = {
  padding: "1rem",
  borderRadius: "12px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
  color: "#334155",
  marginBottom: "1rem",
};

const errorPanelStyle: CSSProperties = {
  ...panelStyle,
  borderColor: "#f43f5e",
  backgroundColor: "#fff1f2",
  color: "#9f1239",
};

const subtlePanelStyle: CSSProperties = {
  padding: "0.85rem",
  color: "#64748b",
  fontSize: "0.95rem",
};

const stackStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.65rem",
};

const itemCardStyle: CSSProperties = {
  padding: "0.85rem 1rem",
  borderRadius: "12px",
  border: "1px solid #d7dee8",
  backgroundColor: "#f8fafc",
};

const itemHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "0.75rem",
  marginBottom: "0.5rem",
};

const badgeRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.5rem",
  flexWrap: "wrap",
};

const badgeStyle: CSSProperties = {
  display: "inline-block",
  padding: "0.2rem 0.7rem",
  borderRadius: "8px",
  fontSize: "0.8rem",
  backgroundColor: "#e2e8f0",
  color: "#334155",
  textTransform: "capitalize",
};

const metaGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "200px 1fr",
  gap: "0.25rem 0.75rem",
  fontSize: "0.9rem",
  color: "#475569",
};

const detailGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
  gap: "1rem",
  marginTop: "1rem",
};

const detailPanelStyle: CSSProperties = {
  padding: "0.85rem",
  borderRadius: "12px",
  border: "1px solid #d7dee8",
  backgroundColor: "#f8fafc",
};

const detailTitleStyle: CSSProperties = {
  margin: "0 0 0.75rem",
  fontSize: "1rem",
  color: "#102033",
};

const detailRowStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.15rem",
  paddingBottom: "0.55rem",
  borderBottom: "1px solid #e2e8f0",
};

const monoStyle: CSSProperties = {
  fontFamily: "monospace",
  fontSize: "0.85rem",
};

const metaTextStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  fontSize: "0.85rem",
  color: "#64748b",
};

const secondaryLinkStyle: CSSProperties = {
  display: "inline-block",
  padding: "0.45rem 0.9rem",
  borderRadius: "10px",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  color: "#334155",
  fontSize: "0.9rem",
  fontWeight: 500,
  textDecoration: "none",
};