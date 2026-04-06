"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

import type {
  AuditEventRecord,
  AuditTimelineResponse,
  DecisionLedgerEntry,
  DecisionLedgerResponse,
  LineageRecord,
  LineageResponse,
} from "@casegraph/agent-sdk";

import { fetchCaseDetail } from "@/lib/cases-api";
import {
  fetchCaseAudit,
  fetchCaseDecisions,
  fetchCaseLineage,
} from "@/lib/audit-api";

export default function AuditClient({ caseId }: { caseId: string }) {
  const [caseTitle, setCaseTitle] = useState("");
  const [timeline, setTimeline] = useState<AuditTimelineResponse | null>(null);
  const [decisions, setDecisions] = useState<DecisionLedgerResponse | null>(null);
  const [lineage, setLineage] = useState<LineageResponse | null>(null);
  const [category, setCategory] = useState("");
  const [eventType, setEventType] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load(nextCategory = category, nextEventType = eventType) {
    setLoading(true);
    setError(null);
    try {
      const [caseDetail, auditData, decisionData, lineageData] = await Promise.all([
        fetchCaseDetail(caseId),
        fetchCaseAudit(caseId, { category: nextCategory || undefined, eventType: nextEventType || undefined }),
        fetchCaseDecisions(caseId),
        fetchCaseLineage(caseId),
      ]);
      setCaseTitle(caseDetail.case.title);
      setTimeline(auditData);
      setDecisions(decisionData);
      setLineage(lineageData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load case audit workspace.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [caseId]);

  async function applyFilters() {
    await load(category, eventType);
  }

  if (loading) {
    return <main style={pageStyle}><section style={containerStyle}><div style={panelStyle}>Loading case audit workspace...</div></section></main>;
  }

  if (error || !timeline || !decisions || !lineage) {
    return <main style={pageStyle}><section style={containerStyle}><div style={errorPanelStyle}>{error ?? "Audit data unavailable."}</div></section></main>;
  }

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <div style={linkRowStyle}>
          <Link href={`/cases/${caseId}`} style={secondaryLinkStyle}>Case workspace</Link>
          <Link href={`/cases/${caseId}/validation`} style={secondaryLinkStyle}>Validation</Link>
          <Link href={`/cases/${caseId}/packets`} style={secondaryLinkStyle}>Packets</Link>
          <Link href={`/cases/${caseId}/submission-drafts`} style={secondaryLinkStyle}>Submission drafts</Link>
          <Link href={`/cases/${caseId}/automation-runs`} style={secondaryLinkStyle}>Automation runs</Link>
        </div>

        <header style={headerStyle}>
          <div>
            <p style={breadcrumbStyle}>Case Audit</p>
            <h1 style={titleStyle}>Audit Timeline &amp; Lineage</h1>
            <p style={subtitleStyle}>
              Persisted operational history for selected case events, decisions, and derived artifact lineage.
              This is an append-oriented local traceability workspace, not a formal compliance archive.
            </p>
          </div>
          <div style={summaryCardStyle}>
            <div style={summaryValueStyle}>{timeline.events.length}</div>
            <div style={summaryLabelStyle}>Timeline events</div>
            <div style={summaryValueStyle}>{decisions.decisions.length}</div>
            <div style={summaryLabelStyle}>Ledger entries</div>
            <div style={summaryValueStyle}>{lineage.records.length}</div>
            <div style={summaryLabelStyle}>Lineage records</div>
          </div>
        </header>

        <div style={caseTitleStyle}>{caseTitle}</div>

        <section style={sectionCardStyle}>
          <h2 style={sectionTitleStyle}>Timeline Filters</h2>
          <div style={filterRowStyle}>
            <label style={fieldStyle}>
              <span style={labelStyle}>Category</span>
              <select value={category} onChange={(event) => setCategory(event.target.value)} style={inputStyle}>
                <option value="">All categories</option>
                {timeline.filters.categories.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <label style={fieldStyle}>
              <span style={labelStyle}>Event Type</span>
              <select value={eventType} onChange={(event) => setEventType(event.target.value)} style={inputStyle}>
                <option value="">All event types</option>
                {timeline.filters.event_types.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <button type="button" style={primaryButtonStyle} onClick={() => void applyFilters()}>
              Apply Filters
            </button>
          </div>
        </section>

        <div style={layoutStyle}>
          <section style={sectionCardStyle}>
            <h2 style={sectionTitleStyle}>Audit Timeline</h2>
            {timeline.events.length === 0 ? (
              <div style={panelStyle}>No persisted audit events match the current filter.</div>
            ) : (
              <div style={stackStyle}>
                {timeline.events.map((event) => <AuditEventCard key={event.event_id} event={event} />)}
              </div>
            )}
          </section>

          <section style={sectionCardStyle}>
            <h2 style={sectionTitleStyle}>Decision Ledger</h2>
            {decisions.decisions.length === 0 ? (
              <div style={panelStyle}>No persisted decision ledger entries for this case yet.</div>
            ) : (
              <div style={stackStyle}>
                {decisions.decisions.map((entry) => <DecisionCard key={entry.decision_id} entry={entry} />)}
              </div>
            )}
          </section>
        </div>

        <section style={sectionCardStyle}>
          <h2 style={sectionTitleStyle}>Artifact Lineage</h2>
          {lineage.records.length === 0 ? (
            <div style={panelStyle}>No derived artifact lineage has been recorded for this case yet.</div>
          ) : (
            <div style={stackStyle}>
              {lineage.records.map((record) => <LineageCard key={record.record_id} record={record} />)}
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

function AuditEventCard({ event }: { event: AuditEventRecord }) {
  return (
    <article style={entryCardStyle}>
      <div style={entryHeaderStyle}>
        <div>
          <span style={badgeStyle}>{event.category}</span>
          <span style={monoLabelStyle}>{event.event_type}</span>
        </div>
        <span style={timestampStyle}>{formatTimestamp(event.created_at)}</span>
      </div>
      <p style={entryMessageStyle}>{event.change_summary.message || event.entity.display_label || event.event_type}</p>
      <div style={metaTextStyle}>Actor: {event.actor.display_name || event.actor.actor_id || event.actor.actor_type}</div>
      <div style={metaTextStyle}>Entity: {event.entity.entity_type} · {event.entity.entity_id}</div>
      {event.change_summary.field_changes.length > 0 && (
        <ul style={detailListStyle}>
          {event.change_summary.field_changes.map((change, index) => (
            <li key={`${event.event_id}-${index}`} style={detailItemStyle}>
              {change.field_path}: {stringifyValue(change.old_value)} → {stringifyValue(change.new_value)}
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function DecisionCard({ entry }: { entry: DecisionLedgerEntry }) {
  return (
    <article style={entryCardStyle}>
      <div style={entryHeaderStyle}>
        <span style={monoLabelStyle}>{entry.decision_type}</span>
        <span style={timestampStyle}>{formatTimestamp(entry.created_at)}</span>
      </div>
      <p style={entryMessageStyle}>{entry.outcome || entry.decision_type}</p>
      <div style={metaTextStyle}>Actor: {entry.actor.display_name || entry.actor.actor_id || entry.actor.actor_type}</div>
      <div style={metaTextStyle}>Source: {entry.source_entity.entity_type} · {entry.source_entity.entity_id}</div>
      {entry.reason && <div style={metaTextStyle}>Reason: {entry.reason}</div>}
      {entry.note && <div style={metaTextStyle}>Note: {entry.note}</div>}
    </article>
  );
}

function LineageCard({ record }: { record: LineageRecord }) {
  return (
    <article style={entryCardStyle}>
      <div style={entryHeaderStyle}>
        <div>
          <span style={badgeStyle}>{record.artifact.artifact_type}</span>
          <span style={monoLabelStyle}>{record.artifact.artifact_id}</span>
        </div>
        <span style={timestampStyle}>{formatTimestamp(record.created_at)}</span>
      </div>
      <p style={entryMessageStyle}>{record.artifact.display_label || record.artifact.artifact_id}</p>
      {record.notes.length > 0 && <div style={metaTextStyle}>{record.notes.join(" ")}</div>}
      <ul style={detailListStyle}>
        {record.edges.map((edge) => (
          <li key={edge.edge_id} style={detailItemStyle}>
            {edge.relationship_type}: {edge.source.artifact_type} · {edge.source.display_label || edge.source.artifact_id}
          </li>
        ))}
      </ul>
    </article>
  );
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function formatTimestamp(value: string): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

const pageStyle: CSSProperties = { minHeight: "100vh", padding: "2.5rem 1.25rem 2rem", backgroundColor: "#f5f7fa" };
const containerStyle: CSSProperties = { maxWidth: "1180px", margin: "0 auto" };
const linkRowStyle: CSSProperties = { display: "flex", flexWrap: "wrap", gap: "0.75rem", marginBottom: "1rem" };
const secondaryLinkStyle: CSSProperties = { color: "#0d6efd", textDecoration: "none", fontWeight: 500 };
const headerStyle: CSSProperties = { display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "flex-start", marginBottom: "1rem" };
const breadcrumbStyle: CSSProperties = { margin: 0, textTransform: "uppercase", letterSpacing: "0.08em", fontSize: "0.8rem", color: "#64748b" };
const titleStyle: CSSProperties = { margin: "0.35rem 0", fontSize: "2.1rem", color: "#102033" };
const subtitleStyle: CSSProperties = { margin: 0, color: "#55657a", lineHeight: 1.6, maxWidth: "760px" };
const caseTitleStyle: CSSProperties = { marginBottom: "1rem", color: "#334155", fontWeight: 600 };
const summaryCardStyle: CSSProperties = { minWidth: "180px", padding: "0.9rem 1rem", borderRadius: "16px", border: "1px solid #d7dee8", backgroundColor: "#fff" };
const summaryValueStyle: CSSProperties = { fontSize: "1.35rem", fontWeight: 700, color: "#102033" };
const summaryLabelStyle: CSSProperties = { fontSize: "0.82rem", color: "#64748b", marginBottom: "0.5rem" };
const sectionCardStyle: CSSProperties = { marginBottom: "1rem", padding: "1.1rem 1.25rem", borderRadius: "16px", border: "1px solid #d7dee8", backgroundColor: "#fff" };
const sectionTitleStyle: CSSProperties = { margin: "0 0 0.85rem", fontSize: "1.05rem", color: "#102033" };
const panelStyle: CSSProperties = { padding: "0.9rem 1rem", borderRadius: "12px", border: "1px solid #d7dee8", backgroundColor: "#f8fafc", color: "#334155" };
const errorPanelStyle: CSSProperties = { ...panelStyle, borderColor: "#fca5a5", backgroundColor: "#fef2f2", color: "#991b1b" };
const filterRowStyle: CSSProperties = { display: "flex", flexWrap: "wrap", alignItems: "end", gap: "0.9rem" };
const fieldStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: "0.35rem", minWidth: "220px" };
const labelStyle: CSSProperties = { fontSize: "0.82rem", fontWeight: 600, color: "#334155" };
const inputStyle: CSSProperties = { padding: "0.65rem 0.8rem", borderRadius: "10px", border: "1px solid #cbd5e1", backgroundColor: "#fff", color: "#0f172a" };
const primaryButtonStyle: CSSProperties = { padding: "0.7rem 1rem", borderRadius: "10px", border: "none", backgroundColor: "#102033", color: "#fff", fontWeight: 600, cursor: "pointer" };
const layoutStyle: CSSProperties = { display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) minmax(0, 1fr)", gap: "1rem", marginBottom: "1rem" };
const stackStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: "0.85rem" };
const entryCardStyle: CSSProperties = { padding: "0.9rem 1rem", borderRadius: "12px", border: "1px solid #e2e8f0", backgroundColor: "#f8fafc" };
const entryHeaderStyle: CSSProperties = { display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "center", marginBottom: "0.45rem" };
const badgeStyle: CSSProperties = { display: "inline-block", padding: "0.15rem 0.55rem", borderRadius: "999px", backgroundColor: "#e0e7ff", color: "#3730a3", fontSize: "0.74rem", marginRight: "0.5rem" };
const monoLabelStyle: CSSProperties = { fontFamily: "monospace", fontSize: "0.8rem", color: "#475569" };
const timestampStyle: CSSProperties = { fontSize: "0.76rem", color: "#64748b" };
const entryMessageStyle: CSSProperties = { margin: "0 0 0.35rem", fontWeight: 600, color: "#102033" };
const metaTextStyle: CSSProperties = { fontSize: "0.83rem", color: "#55657a", lineHeight: 1.5 };
const detailListStyle: CSSProperties = { margin: "0.55rem 0 0", paddingLeft: "1.15rem" };
const detailItemStyle: CSSProperties = { color: "#475569", fontSize: "0.82rem", lineHeight: 1.5 };