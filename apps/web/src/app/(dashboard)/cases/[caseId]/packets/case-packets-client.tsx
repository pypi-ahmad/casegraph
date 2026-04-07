"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import type {
  DownstreamSourceMode,
  ExportArtifact,
  HandoffEligibilitySummary,
  PacketManifest,
  PacketSection,
  PacketSummary,
  ReviewedSnapshotRecord,
} from "@casegraph/agent-sdk";

import {
  artifactDownloadUrl,
  fetchPacketArtifacts,
  fetchPacketDetail,
  fetchPackets,
  generatePacket,
} from "@/lib/packets-api";
import {
  fetchHandoffEligibility,
  fetchReviewedSnapshots,
} from "@/lib/reviewed-handoff-api";

export default function CasePacketsClient({ caseId }: { caseId: string }) {
  const [packets, setPackets] = useState<PacketSummary[]>([]);
  const [reviewedSnapshots, setReviewedSnapshots] = useState<ReviewedSnapshotRecord[]>([]);
  const [handoffEligibility, setHandoffEligibility] = useState<HandoffEligibilitySummary | null>(null);
  const [selectedManifest, setSelectedManifest] = useState<PacketManifest | null>(null);
  const [selectedArtifacts, setSelectedArtifacts] = useState<ExportArtifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [note, setNote] = useState("");
  const [sourceMode, setSourceMode] = useState<DownstreamSourceMode>("live_case_state");
  const [reviewedSnapshotId, setReviewedSnapshotId] = useState("");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [packetResponse, snapshotResponse, eligibilityResponse] = await Promise.all([
        fetchPackets(caseId),
        fetchReviewedSnapshots(caseId),
        fetchHandoffEligibility(caseId),
      ]);
      setPackets(packetResponse.packets);
      setReviewedSnapshots(snapshotResponse.snapshots);
      setHandoffEligibility(eligibilityResponse.eligibility);
      if (!reviewedSnapshotId) {
        setReviewedSnapshotId(
          eligibilityResponse.eligibility.selected_snapshot_id
            || snapshotResponse.snapshots[0]?.snapshot_id
            || "",
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load exports. Try refreshing the page.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [caseId]);

  async function handleGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWorking(true);
    setMessage(null);
    try {
      const response = await generatePacket(caseId, {
        note: note.trim(),
        source_mode: sourceMode,
        reviewed_snapshot_id: sourceMode === "reviewed_snapshot" ? reviewedSnapshotId : "",
      });
      setMessage(response.result.message || "Packet generated.");
      setNote("");
      if (response.packet) {
        setPackets((prev) => [response.packet!, ...prev]);
      }
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to create export. Please try again.");
    } finally {
      setWorking(false);
    }
  }

  async function handleSelect(packetId: string) {
    setWorking(true);
    setMessage(null);
    try {
      const [detail, arts] = await Promise.all([
        fetchPacketDetail(packetId),
        fetchPacketArtifacts(packetId),
      ]);
      setSelectedManifest(detail.manifest);
      setSelectedArtifacts(arts.artifacts);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to load export details. Please try again.");
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
          <Link href={`/cases/${caseId}/handoff`} style={secondaryLinkStyle}>Reviewed handoff</Link>
          <Link href={`/cases/${caseId}/audit`} style={secondaryLinkStyle}>Audit timeline</Link>
          <Link href={`/cases/${caseId}/review`} style={secondaryLinkStyle}>Operator review</Link>
          <Link href={`/cases/${caseId}/checklist`} style={secondaryLinkStyle}>Checklist</Link>
          <Link href={`/cases/${caseId}/communication-drafts`} style={secondaryLinkStyle}>Communication drafts</Link>
          <Link href={`/cases/${caseId}/submission-drafts`} style={secondaryLinkStyle}>Submission drafts</Link>
        </div>

        <header style={headerStyle}>
          <div>
            <p style={breadcrumbStyle}>Case Packets</p>
            <h1 style={titleStyle}>Case Export</h1>
            <p style={subtitleStyle}>
              Generate a complete export package for this case. Includes documents, extraction results, readiness summary, and review history.
            </p>
          </div>
        </header>

        {message && <div style={panelStyle}>{message}</div>}

        <section style={sectionCardStyle}>
          <h2 style={sectionTitleStyle}>Generate New Packet</h2>
          <form onSubmit={handleGenerate} style={formStyle}>
            <label style={fieldStyle}>
              <span style={labelStyle}>Source Mode</span>
              <select
                value={sourceMode}
                onChange={(event) => setSourceMode(event.target.value as DownstreamSourceMode)}
                style={inputStyle}
              >
                <option value="live_case_state">Live case state</option>
                <option value="reviewed_snapshot">Reviewed snapshot</option>
              </select>
            </label>
            {sourceMode === "reviewed_snapshot" && (
              <label style={fieldStyle}>
                <span style={labelStyle}>Reviewed Snapshot</span>
                <select
                  value={reviewedSnapshotId}
                  onChange={(event) => setReviewedSnapshotId(event.target.value)}
                  style={inputStyle}
                >
                  <option value="">Use selected or latest eligible snapshot</option>
                  {reviewedSnapshots.map((snapshot) => (
                    <option key={snapshot.snapshot_id} value={snapshot.snapshot_id}>
                      {snapshot.snapshot_id.slice(0, 12)}… • {snapshot.signoff_status.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label style={fieldStyle}>
              <span style={labelStyle}>Note (optional)</span>
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                style={inputStyle}
                placeholder="Optional packet generation note"
              />
            </label>
            <button type="submit" style={primaryButtonStyle} disabled={working}>
              {working ? "Working..." : "Create Export"}
            </button>
          </form>
          {sourceMode === "reviewed_snapshot" && handoffEligibility && (
            <div style={{ ...subtlePanelStyle, marginTop: "0.75rem" }}>
              <p style={metaTextStyle}>
                Handoff gate: {handoffEligibility.release_gate_status.replace(/_/g, " ")}
              </p>
              {handoffEligibility.reasons.map((reason) => (
                <p key={reason.code} style={metaTextStyle}>
                  {reason.blocking ? "Blocking" : "Info"}: {reason.message}
                </p>
              ))}
            </div>
          )}
        </section>

        {loading ? (
          <div style={panelStyle}>Loading packets...</div>
        ) : error ? (
          <div style={errorPanelStyle}>{error}</div>
        ) : (
          <>
            <section style={sectionCardStyle}>
              <h2 style={sectionTitleStyle}>Generated Packets</h2>
              {packets.length === 0 ? (
                <div style={subtlePanelStyle}>No exports yet. Use the form above to create an export package from this case.</div>
              ) : (
                <div style={stackStyle}>
                  {packets.map((p) => (
                    <article
                      key={p.packet_id}
                      style={{
                        ...itemCardStyle,
                        cursor: "pointer",
                        borderColor: selectedManifest?.packet_id === p.packet_id ? "#0d6efd" : "#d7dee8",
                      }}
                      onClick={() => handleSelect(p.packet_id)}
                    >
                      <div style={itemHeaderStyle}>
                        <strong>{p.case_title || p.case_id}</strong>
                        <span style={badgeStyle}>{p.current_stage.replace(/_/g, " ")}</span>
                      </div>
                      <div style={metaGridStyle}>
                        <span>Packet ID</span><span style={monoStyle}>{p.packet_id.slice(0, 12)}…</span>
                        <span>Source mode</span><span>{describeSourceMode(p.source_mode)}</span>
                        <span>Reviewed snapshot</span><span style={monoStyle}>{p.source_reviewed_snapshot_id ? `${p.source_reviewed_snapshot_id.slice(0, 12)}…` : "None"}</span>
                        <span>Readiness</span><span>{p.readiness_status?.replace(/_/g, " ") ?? "Not evaluated"}</span>
                        <span>Sections</span><span>{p.section_count}</span>
                        <span>Artifacts</span><span>{p.artifact_count}</span>
                        <span>Generated</span><span>{formatTimestamp(p.generated_at)}</span>
                      </div>
                      {p.note && <p style={metaTextStyle}>Note: {p.note}</p>}
                    </article>
                  ))}
                </div>
              )}
            </section>

            {selectedManifest && (
              <section style={sectionCardStyle}>
                <h2 style={sectionTitleStyle}>Packet Manifest</h2>
                <div style={metaGridStyle}>
                  <span>Packet ID</span><span style={monoStyle}>{selectedManifest.packet_id.slice(0, 12)}…</span>
                  <span>Case</span><span>{selectedManifest.case_title}</span>
                  <span>Status</span><span>{selectedManifest.case_status}</span>
                  <span>Stage</span><span>{selectedManifest.current_stage.replace(/_/g, " ")}</span>
                  <span>Source mode</span><span>{describeSourceMode(selectedManifest.source_mode)}</span>
                  <span>Reviewed snapshot</span><span style={monoStyle}>{selectedManifest.source_reviewed_snapshot_id || "None"}</span>
                  <span>Snapshot sign-off</span><span>{selectedManifest.source_snapshot_signoff_status.replace(/_/g, " ")}</span>
                  <span>Domain Pack</span><span>{selectedManifest.domain_pack_id ?? "None"}</span>
                  <span>Case Type</span><span>{selectedManifest.case_type_id ?? "None"}</span>
                  <span>Readiness</span><span>{selectedManifest.readiness_status?.replace(/_/g, " ") ?? "Not evaluated"}</span>
                  <span>Documents</span><span>{selectedManifest.linked_document_count}</span>
                  <span>Extractions</span><span>{selectedManifest.extraction_count}</span>
                  <span>Open Actions</span><span>{selectedManifest.open_action_count}</span>
                  <span>Review Notes</span><span>{selectedManifest.review_note_count}</span>
                  <span>Runs</span><span>{selectedManifest.run_count}</span>
                </div>

                <h3 style={{ ...sectionTitleStyle, fontSize: "1.05rem", marginTop: "1rem" }}>Sections</h3>
                <div style={stackStyle}>
                  {selectedManifest.sections.map((section) => (
                    <SectionCard key={section.section_type} section={section} />
                  ))}
                </div>
              </section>
            )}

            {selectedArtifacts.length > 0 && selectedManifest && (
              <section style={sectionCardStyle}>
                <h2 style={sectionTitleStyle}>Export Artifacts</h2>
                <div style={stackStyle}>
                  {selectedArtifacts.map((art) => (
                    <article key={art.artifact_id} style={itemCardStyle}>
                      <div style={itemHeaderStyle}>
                        <strong>{art.filename}</strong>
                        <span style={badgeStyle}>{art.format.replace(/_/g, " ")}</span>
                      </div>
                      <div style={metaGridStyle}>
                        <span>Format</span><span>{art.format}</span>
                        <span>Size</span><span>{(art.size_bytes / 1024).toFixed(1)} KB</span>
                        <span>Content Type</span><span>{art.content_type}</span>
                      </div>
                      <a
                        href={artifactDownloadUrl(selectedManifest.packet_id, art.artifact_id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={primaryLinkStyle}
                      >
                        Download
                      </a>
                    </article>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </section>
    </main>
  );
}

function SectionCard({ section }: { section: PacketSection }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <article style={itemCardStyle}>
      <div
        style={{ ...itemHeaderStyle, cursor: "pointer" }}
        onClick={() => setExpanded(!expanded)}
      >
        <strong>{section.title}</strong>
        <span style={badgeStyle}>
          {section.empty ? "empty" : `${section.item_count} item${section.item_count !== 1 ? "s" : ""}`}
        </span>
      </div>
      {expanded && !section.empty && (
        <pre style={preStyle}>{JSON.stringify(section.data, null, 2)}</pre>
      )}
      {expanded && section.empty && (
        <p style={metaTextStyle}>No data available for this section.</p>
      )}
    </article>
  );
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function describeSourceMode(value: DownstreamSourceMode): string {
  return value === "reviewed_snapshot" ? "Reviewed snapshot" : "Live case state";
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
  maxWidth: "720px",
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
  gridTemplateColumns: "160px 1fr",
  gap: "0.25rem 0.75rem",
  fontSize: "0.9rem",
  color: "#475569",
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

const preStyle: CSSProperties = {
  margin: "0.5rem 0 0",
  padding: "0.75rem",
  borderRadius: "8px",
  backgroundColor: "#f1f5f9",
  fontSize: "0.8rem",
  overflow: "auto",
  maxHeight: "300px",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
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

const primaryLinkStyle: CSSProperties = {
  display: "inline-block",
  marginTop: "0.5rem",
  padding: "0.4rem 1rem",
  borderRadius: "10px",
  backgroundColor: "#0d6efd",
  color: "#ffffff",
  fontSize: "0.9rem",
  fontWeight: 600,
  textDecoration: "none",
};
