"use client";

import Link from "next/link";
import AiDisclosureBanner from "@/components/ai-disclosure-banner";
import { useCallback, useEffect, useState } from "react";
import type {
  ReleaseBundleRecord,
  ReleaseEligibilitySummary,
  ReleaseArtifactEntry,
  ReleaseIssue,
  SessionUser,
  WorkStatusSummary,
} from "@casegraph/agent-sdk";
import { WorkStatusSnapshot } from "@/components/work-management/work-status-panels";
import { titleCase } from "@/lib/display-labels";
import {
  createRelease,
  fetchReleaseEligibility,
  fetchReleases,
} from "@/lib/reviewed-release-api";
import { fetchCaseWorkStatus } from "@/lib/work-management-api";

/* ---------- Component ---------- */

export default function ReleasesClient({ caseId, currentUser }: { caseId: string; currentUser: SessionUser }) {
  const [releases, setReleases] = useState<ReleaseBundleRecord[]>([]);
  const [eligibility, setEligibility] = useState<ReleaseEligibilitySummary | null>(null);
  const [workStatus, setWorkStatus] = useState<WorkStatusSummary | null>(null);
  const [note, setNote] = useState("");
  const [operatorId, setOperatorId] = useState(currentUser.id);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [selectedRelease, setSelectedRelease] = useState<ReleaseBundleRecord | null>(null);
  const [lastIssues, setLastIssues] = useState<ReleaseIssue[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [relRes, eligRes, workResponse] = await Promise.all([
        fetchReleases(caseId),
        fetchReleaseEligibility(caseId),
        fetchCaseWorkStatus(caseId),
      ]);
      setReleases(relRes.releases);
      setEligibility(eligRes.eligibility);
      setWorkStatus(workResponse.work_status);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load release data. Try refreshing the page.");
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    setCreating(true);
    setError("");
    setLastIssues([]);
    try {
      const result = await createRelease(caseId, {
        operator_id: operatorId.trim() || currentUser.id,
        operator_display_name: currentUser.name || currentUser.email,
        note: note.trim(),
        generate_packet: true,
        generate_submission_draft: true,
        generate_communication_draft: true,
        include_automation_plan_metadata: true,
      });
      if (result.result?.issues?.length) {
        setLastIssues(result.result.issues);
      }
      setNote("");
      await load();
      if (result.release) {
        setSelectedRelease(result.release);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Release creation failed. Ensure a signed-off snapshot is available and try again.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div style={containerStyle}>
      {/* Navigation */}
      <div style={linkRowStyle}>
        <Link href={`/cases/${caseId}`} style={secondaryLinkStyle}>Case workspace</Link>
        <Link href={`/cases/${caseId}/handoff`} style={secondaryLinkStyle}>Reviewed handoff</Link>
        <Link href={`/cases/${caseId}/packets`} style={secondaryLinkStyle}>Packets</Link>
        <Link href={`/cases/${caseId}/submission-drafts`} style={secondaryLinkStyle}>Submission drafts</Link>
        <Link href={`/cases/${caseId}/communication-drafts`} style={secondaryLinkStyle}>Communication drafts</Link>
        <Link href={`/cases/${caseId}/audit`} style={secondaryLinkStyle}>Audit timeline</Link>
      </div>

      <h1 style={headingStyle}>Releases</h1>
      <p style={subtitleStyle}>
        View and create finalized case releases.
      </p>

      <AiDisclosureBanner />

      {loading && <p style={mutedStyle}>Loading releases…</p>}
      {error && <p style={errorStyle}>{error}</p>}

      {workStatus && (
        <section style={sectionStyle}>
          <WorkStatusSnapshot
            status={workStatus}
            label="Work Context"
            compact
            actions={[
              { href: "/work", label: "Open Work Board", tone: "primary" },
              { href: `/cases/${caseId}`, label: "Case Workspace" },
            ]}
          />
        </section>
      )}

      {/* Eligibility */}
      {eligibility && (
        <section style={sectionStyle}>
          <h2 style={sectionHeadingStyle}>Release eligibility</h2>
          <p>
            <strong>Eligible:</strong>{" "}
            <span style={{ color: eligibility.eligible ? "#198754" : "#dc3545" }}>
              {eligibility.eligible ? "Yes" : "No"}
            </span>
          </p>
          {eligibility.snapshot_id && (
            <p><strong>Snapshot:</strong> <code>{eligibility.snapshot_id}</code></p>
          )}
          {eligibility.signoff_status && (
            <p><strong>Sign-off status:</strong> {eligibility.signoff_status}</p>
          )}
          {eligibility.reasons.length > 0 && (
            <ul style={reasonListStyle}>
              {eligibility.reasons.map((r, i) => (
                <li key={i} style={{ color: r.blocking ? "#dc3545" : "#856404" }}>
                  [{r.code}] {r.message}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* Create release */}
      {eligibility?.eligible && (
        <section style={sectionStyle}>
          <h2 style={sectionHeadingStyle}>Create release bundle</h2>
          <div style={fieldGroupStyle}>
            <label style={labelStyle}>Operator</label>
            <input
              type="text"
              value={currentUser.name || currentUser.email}
              readOnly
              style={{ ...inputStyle, backgroundColor: "#f8fafc", color: "#475569" }}
            />
          </div>
          <div style={fieldGroupStyle}>
            <label style={labelStyle}>Note (optional)</label>
            <textarea
              value={note}
              onChange={e => setNote(e.target.value)}
              rows={2}
              style={inputStyle}
            />
          </div>
          <button
            onClick={handleCreate}
            disabled={creating}
            style={creating ? { ...btnStyle, opacity: 0.6 } : btnStyle}
          >
            {creating ? "Creating release…" : "Create release bundle"}
          </button>
        </section>
      )}

      {/* Issues from last creation */}
      {lastIssues.length > 0 && (
        <section style={sectionStyle}>
          <h2 style={sectionHeadingStyle}>Issues from last release</h2>
          <ul style={reasonListStyle}>
            {lastIssues.map((issue, i) => (
              <li key={i} style={{ color: issue.severity === "error" ? "#dc3545" : "#856404" }}>
                [{issue.severity}] {issue.code}: {issue.message}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Release detail */}
      {selectedRelease && (
        <section style={sectionStyle}>
          <h2 style={sectionHeadingStyle}>Release detail</h2>
          <ReleaseDetail release={selectedRelease} onClose={() => setSelectedRelease(null)} />
        </section>
      )}

      {/* Release list */}
      <section style={sectionStyle}>
        <h2 style={sectionHeadingStyle}>Past releases ({releases.length})</h2>
        {releases.length === 0 && !loading && (
          <p style={mutedStyle}>No releases yet. Complete the handoff review and sign off on a snapshot first, then come back here to create a release.</p>
        )}
        {releases.map(r => (
          <div
            key={r.release_id}
            style={{
              ...cardStyle,
              borderLeft: r.status === "created" ? "4px solid #198754" : "4px solid #ffc107",
              cursor: "pointer",
            }}
            onClick={() => setSelectedRelease(r)}
          >
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <strong>{titleCase(r.status)}</strong>
              <span style={mutedStyle}>{r.created_at}</span>
            </div>
            <p style={{ margin: 0, fontSize: 13 }}>
              {r.summary.generated_artifacts}/{r.summary.total_artifacts} artifact(s) generated
              {r.note ? ` — ${r.note}` : ""}
            </p>
            <p style={{ margin: "2px 0 0", fontSize: 12, color: "#6c757d" }}>
              Source: reviewed snapshot
            </p>
          </div>
        ))}
      </section>
    </div>
  );
}

/* ---------- Sub-components ---------- */

function ReleaseDetail({
  release,
  onClose,
}: {
  release: ReleaseBundleRecord;
  onClose: () => void;
}) {
  return (
    <div>
      <button onClick={onClose} style={{ ...btnSmStyle, marginBottom: 8 }}>Close detail</button>
      <table style={tableStyle}>
        <tbody>
          <Row label="Status" value={titleCase(release.status)} />
          <Row label="Created by" value={release.created_by} />
          <Row label="Created at" value={release.created_at} />
          <Row label="Sign-off" value={`${titleCase(release.source.signoff_status)} (by ${release.source.signed_off_by || "—"})`} />
          <Row label="Total artifacts" value={String(release.summary.total_artifacts)} />
          <Row label="Generated" value={String(release.summary.generated_artifacts)} />
          <Row label="Skipped" value={String(release.summary.skipped_artifacts)} />
          <Row label="Failed" value={String(release.summary.failed_artifacts)} />
          {release.note && <Row label="Note" value={release.note} />}
        </tbody>
      </table>

      <h3 style={{ marginTop: 16, fontSize: 15 }}>Artifacts</h3>
      {release.artifacts.length === 0 && <p style={mutedStyle}>No artifacts were generated for this release.</p>}
      {release.artifacts.map((a: ReleaseArtifactEntry) => (
        <ArtifactCard key={a.artifact_ref_id} artifact={a} />
      ))}
    </div>
  );
}

function ArtifactCard({ artifact: a }: { artifact: ReleaseArtifactEntry }) {
  const borderColor =
    a.status === "generated" ? "#198754" :
    a.status === "failed" ? "#dc3545" :
    a.status === "blocked" ? "#dc3545" : "#ffc107";
  return (
    <div style={{ ...cardStyle, borderLeft: `3px solid ${borderColor}`, marginBottom: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <strong>{a.display_label}</strong>
        <span style={{ fontSize: 12, color: "#6c757d" }}>{titleCase(a.status)}</span>
      </div>
      <p style={{ margin: "2px 0 0", fontSize: 12, color: "#6c757d" }}>
        Type: {titleCase(a.artifact_type)} | Source: {titleCase(a.source_mode)}
      </p>
      {a.notes && a.notes.length > 0 && (
        <ul style={{ margin: "4px 0 0", paddingLeft: 18, fontSize: 12 }}>
          {a.notes.map((n, i) => <li key={i}>{n}</li>)}
        </ul>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <tr>
      <td style={tdLabelStyle}>{label}</td>
      <td style={tdValueStyle}>{value}</td>
    </tr>
  );
}

/* ---------- Styles ---------- */

const containerStyle: React.CSSProperties = {
  maxWidth: 900,
  margin: "0 auto",
  padding: "32px 16px",
  fontFamily: "system-ui, -apple-system, sans-serif",
};
const linkRowStyle: React.CSSProperties = {
  display: "flex",
  gap: 12,
  flexWrap: "wrap",
  marginBottom: 24,
};
const secondaryLinkStyle: React.CSSProperties = {
  fontSize: 13,
  color: "#6c757d",
  textDecoration: "underline",
};
const headingStyle: React.CSSProperties = { fontSize: 24, marginBottom: 4 };
const subtitleStyle: React.CSSProperties = { color: "#6c757d", marginBottom: 24 };
const sectionStyle: React.CSSProperties = {
  marginBottom: 28,
  padding: 16,
  border: "1px solid #dee2e6",
  borderRadius: 8,
  background: "#fff",
};
const sectionHeadingStyle: React.CSSProperties = { fontSize: 17, marginTop: 0, marginBottom: 12 };
const fieldGroupStyle: React.CSSProperties = { marginBottom: 10 };
const labelStyle: React.CSSProperties = { display: "block", fontWeight: 600, fontSize: 13, marginBottom: 4 };
const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "6px 10px",
  fontSize: 14,
  border: "1px solid #ced4da",
  borderRadius: 6,
  boxSizing: "border-box",
};
const btnStyle: React.CSSProperties = {
  padding: "8px 18px",
  background: "#0d6efd",
  color: "#fff",
  border: "none",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 14,
};
const btnSmStyle: React.CSSProperties = {
  padding: "4px 10px",
  fontSize: 12,
  background: "#6c757d",
  color: "#fff",
  border: "none",
  borderRadius: 4,
  cursor: "pointer",
};
const cardStyle: React.CSSProperties = {
  padding: "10px 14px",
  marginBottom: 8,
  border: "1px solid #dee2e6",
  borderRadius: 6,
  background: "#f8f9fa",
};
const mutedStyle: React.CSSProperties = { color: "#6c757d", fontSize: 13 };
const errorStyle: React.CSSProperties = { color: "#dc3545", fontWeight: 600 };
const reasonListStyle: React.CSSProperties = { paddingLeft: 20, fontSize: 13 };
const tableStyle: React.CSSProperties = { width: "100%", borderCollapse: "collapse", fontSize: 13 };
const tdLabelStyle: React.CSSProperties = {
  padding: "4px 8px",
  fontWeight: 600,
  whiteSpace: "nowrap",
  verticalAlign: "top",
  borderBottom: "1px solid #eee",
};
const tdValueStyle: React.CSSProperties = {
  padding: "4px 8px",
  wordBreak: "break-all",
  verticalAlign: "top",
  borderBottom: "1px solid #eee",
};
