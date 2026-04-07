"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import { titleCase } from "@/lib/display-labels";

import type {
  AssignmentHistoryEntry,
  WorkStatusSummary,
  WorkloadSummary,
} from "@casegraph/agent-sdk";

export interface WorkActionLink {
  href: string;
  label: string;
  tone?: "primary" | "secondary";
}

export function WorkStatusSnapshot({
  status,
  label = "Work Status",
  compact = false,
  actions = [],
}: {
  status: WorkStatusSummary;
  label?: string;
  compact?: boolean;
  actions?: WorkActionLink[];
}) {
  const dueDate = status.sla_target.due_date;
  const owner = status.ownership.current_assignee;

  return (
    <section
      style={{
        ...snapshotCardStyle,
        padding: compact ? "1rem" : snapshotCardStyle.padding,
      }}
    >
      <div style={snapshotHeaderStyle}>
        <div>
          <p style={snapshotLabelStyle}>{label}</p>
          <h3 style={{ ...snapshotTitleStyle, fontSize: compact ? "1rem" : "1.1rem" }}>
            {status.title}
          </h3>
        </div>
        <div style={badgeRowStyle}>
          <span style={{ ...badgeStyle, ...assignmentBadgeTone(status.ownership.assignment_status) }}>
            {formatLabel(status.ownership.assignment_status)}
          </span>
          <span style={{ ...badgeStyle, ...segmentBadgeTone(status.workload_segment) }}>
            {formatLabel(status.workload_segment)}
          </span>
          <span style={{ ...badgeStyle, ...slaBadgeTone(status.sla_state) }}>
            {formatLabel(status.sla_state)}
          </span>
          <span style={{ ...badgeStyle, ...escalationBadgeTone(status.escalation.state) }}>
            {formatLabel(status.escalation.state)}
          </span>
        </div>
      </div>

      <div
        style={{
          ...metaGridStyle,
          gridTemplateColumns: compact
            ? "repeat(auto-fit, minmax(160px, 1fr))"
            : metaGridStyle.gridTemplateColumns,
        }}
      >
        <span>Owner</span>
        <span>{owner ? owner.display_name : "Unassigned"}</span>
        <span>Note</span>
        <span>{status.ownership.note || "No note recorded."}</span>
        <span>Deadline</span>
        <span>{dueDate ? formatWorkTimestamp(dueDate.due_at) : "No deadline set"}</span>
        <span>Stage</span>
        <span>{formatLabel(status.current_stage)}</span>
        <span>Readiness</span>
        <span>{status.readiness_status ? formatLabel(status.readiness_status) : "Not evaluated"}</span>
        <span>Open actions</span>
        <span>{status.open_action_count}</span>
        <span>Items needing review</span>
        <span>{status.unresolved_review_item_count}</span>
        {!compact && (
          <>
            <span>Domain</span>
            <span>{status.domain_pack_id ? titleCase(status.domain_pack_id) : "Not linked"}</span>
            <span>Case type</span>
            <span>{status.case_type_id ? titleCase(status.case_type_id) : "Not linked"}</span>
            {(status.release_blocked || status.submission_planning_blocked) && (
              <>
                {status.release_blocked && <><span>Release</span><span style={{ color: "#b91c1c" }}>Blocked</span></>}
                {status.submission_planning_blocked && <><span>Submission</span><span style={{ color: "#b91c1c" }}>Blocked</span></>}
              </>
            )}
          </>
        )}
        <span>Updated</span>
        <span>{formatWorkTimestamp(status.updated_at)}</span>
      </div>

      {status.escalation.reasons.length > 0 && (
        <div style={chipRowStyle}>
          {status.escalation.reasons.map((reason) => (
            <span key={reason} style={chipStyle}>
              {formatLabel(reason)}
            </span>
          ))}
        </div>
      )}

      {(status.escalation.note || status.assignment_expected) && (
        <div style={notePanelStyle}>
          {status.escalation.note && <p style={noteTextStyle}>{status.escalation.note}</p>}
          {status.assignment_expected && !owner && (
            <p style={noteTextStyle}>An explicit assignee is expected for this case based on its current active state.</p>
          )}
        </div>
      )}

      {actions.length > 0 && (
        <div style={actionsRowStyle}>
          {actions.map((action) => (
            <Link
              key={`${action.href}:${action.label}`}
              href={action.href}
              style={action.tone === "primary" ? primaryLinkStyle : secondaryLinkStyle}
            >
              {action.label}
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

export function WorkloadSummaryCards({ summary }: { summary: WorkloadSummary }) {
  return (
    <section style={summaryGridStyle}>
      <SummaryCard label="Tracked cases" value={summary.total_cases} />
      <SummaryCard label="Assigned" value={summary.assigned_cases} />
      <SummaryCard label="Unassigned" value={summary.unassigned_cases} />
      <SummaryCard label="Due soon" value={summary.due_soon_cases} />
      <SummaryCard label="Overdue" value={summary.overdue_cases} />
      <SummaryCard label="Attention needed" value={summary.attention_needed_cases} />
      <SummaryCard label="Needs escalation" value={summary.escalation_ready_cases} />
    </section>
  );
}

export function AssignmentHistoryList({
  history,
  title = "Assignment History",
}: {
  history: AssignmentHistoryEntry[];
  title?: string;
}) {
  return (
    <div>
      <div style={historyHeaderStyle}>
        <h3 style={historyTitleStyle}>{title}</h3>
        <span style={historyCountStyle}>{history.length} event(s)</span>
      </div>
      {history.length === 0 ? (
        <div style={emptyPanelStyle}>No assignment changes yet. History will appear here when the case is assigned or reassigned.</div>
      ) : (
        <div style={historyStackStyle}>
          {history.map((entry) => {
            const assignee = entry.assignee;
            return (
              <article key={entry.record_id} style={historyCardStyle}>
                <div style={historyCardHeaderStyle}>
                  <div>
                    <strong style={historyActorStyle}>
                      {assignee ? assignee.display_name : "Assignment cleared"}
                    </strong>
                    <p style={snapshotMetaStyle}>{formatWorkTimestamp(entry.created_at)}</p>
                  </div>
                  <span style={{ ...badgeStyle, ...assignmentBadgeTone(entry.status) }}>
                    {formatLabel(entry.status)}
                  </span>
                </div>
                <div style={historyMetaGridStyle}>
                  <span>Reason</span>
                  <span>{formatLabel(entry.reason)}</span>
                  <span>Changed by</span>
                  <span>{entry.changed_by_display_name || entry.changed_by_id || "Unknown"}</span>
                  <span>Assignee</span>
                  <span>{assignee ? assignee.display_name : "Unassigned"}</span>
                </div>
                {entry.note && <p style={historyNoteStyle}>{entry.note}</p>}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function formatWorkTimestamp(value: string | null | undefined): string {
  if (!value) return "Not available";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export function toDateTimeLocal(value: string | null | undefined): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  const offsetMinutes = parsed.getTimezoneOffset();
  const local = new Date(parsed.getTime() - offsetMinutes * 60_000);
  return local.toISOString().slice(0, 16);
}

export function formatLabel(value: string): string {
  return titleCase(value);
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div style={summaryCardStyle}>
      <span style={summaryLabelStyle}>{label}</span>
      <strong style={summaryValueStyle}>{value}</strong>
    </div>
  );
}

function assignmentBadgeTone(status: string): CSSProperties {
  switch (status) {
    case "assigned":
      return { backgroundColor: "#dbeafe", color: "#1d4ed8" };
    case "reassigned":
      return { backgroundColor: "#ede9fe", color: "#6d28d9" };
    default:
      return { backgroundColor: "#e2e8f0", color: "#334155" };
  }
}

function segmentBadgeTone(segment: string): CSSProperties {
  switch (segment) {
    case "overdue":
      return { backgroundColor: "#fee2e2", color: "#991b1b" };
    case "due_soon":
      return { backgroundColor: "#fef3c7", color: "#92400e" };
    case "escalation_ready":
      return { backgroundColor: "#dbeafe", color: "#1d4ed8" };
    case "attention_needed":
      return { backgroundColor: "#ffedd5", color: "#9a3412" };
    default:
      return { backgroundColor: "#ecfccb", color: "#3f6212" };
  }
}

function slaBadgeTone(state: string): CSSProperties {
  switch (state) {
    case "overdue":
      return { backgroundColor: "#fee2e2", color: "#991b1b" };
    case "due_soon":
      return { backgroundColor: "#fef3c7", color: "#92400e" };
    case "on_track":
      return { backgroundColor: "#dcfce7", color: "#166534" };
    default:
      return { backgroundColor: "#e2e8f0", color: "#334155" };
  }
}

function escalationBadgeTone(state: string): CSSProperties {
  switch (state) {
    case "escalation_ready":
      return { backgroundColor: "#fee2e2", color: "#991b1b" };
    case "attention_needed":
      return { backgroundColor: "#ffedd5", color: "#9a3412" };
    default:
      return { backgroundColor: "#e2e8f0", color: "#334155" };
  }
}

const snapshotCardStyle: CSSProperties = {
  padding: "1.15rem",
  borderRadius: "16px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
};

const snapshotHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "flex-start",
};

const snapshotLabelStyle: CSSProperties = {
  margin: 0,
  fontSize: "0.74rem",
  fontWeight: 700,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  color: "#64748b",
};

const snapshotTitleStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  color: "#102033",
};

const snapshotMetaStyle: CSSProperties = {
  margin: "0.2rem 0 0",
  fontSize: "0.82rem",
  color: "#64748b",
};

const badgeRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.45rem",
  justifyContent: "flex-end",
};

const badgeStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "0.28rem 0.6rem",
  borderRadius: "999px",
  fontSize: "0.74rem",
  fontWeight: 700,
  textTransform: "uppercase",
};

const metaGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(140px, 180px) minmax(0, 1fr)",
  gap: "0.55rem 0.85rem",
  marginTop: "1rem",
  fontSize: "0.92rem",
  color: "#334155",
};

const chipRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.45rem",
  marginTop: "1rem",
};

const chipStyle: CSSProperties = {
  padding: "0.28rem 0.55rem",
  borderRadius: "999px",
  backgroundColor: "#f1f5f9",
  color: "#334155",
  fontSize: "0.78rem",
  fontWeight: 600,
};

const notePanelStyle: CSSProperties = {
  marginTop: "1rem",
  padding: "0.8rem 0.9rem",
  borderRadius: "12px",
  border: "1px solid #d7dee8",
  backgroundColor: "#f8fafc",
};

const noteTextStyle: CSSProperties = {
  margin: 0,
  color: "#475569",
  lineHeight: 1.55,
};

const actionsRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.65rem",
  marginTop: "1rem",
};

const primaryLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "0.65rem 0.9rem",
  borderRadius: "10px",
  backgroundColor: "#102033",
  color: "#ffffff",
  textDecoration: "none",
  fontWeight: 600,
};

const secondaryLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "0.65rem 0.9rem",
  borderRadius: "10px",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  color: "#102033",
  textDecoration: "none",
  fontWeight: 600,
};

const summaryGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
  gap: "0.8rem",
};

const summaryCardStyle: CSSProperties = {
  padding: "1rem",
  borderRadius: "16px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
};

const summaryLabelStyle: CSSProperties = {
  display: "block",
  fontSize: "0.8rem",
  color: "#64748b",
};

const summaryValueStyle: CSSProperties = {
  display: "block",
  marginTop: "0.35rem",
  fontSize: "1.5rem",
  color: "#102033",
};

const historyHeaderStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "1rem",
  marginBottom: "0.85rem",
};

const historyTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1rem",
  color: "#102033",
};

const historyCountStyle: CSSProperties = {
  fontSize: "0.82rem",
  color: "#64748b",
};

const emptyPanelStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  borderRadius: "12px",
  border: "1px solid #d7dee8",
  backgroundColor: "#f8fafc",
  color: "#475569",
};

const historyStackStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const historyCardStyle: CSSProperties = {
  padding: "0.95rem 1rem",
  borderRadius: "14px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
};

const historyCardHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "flex-start",
};

const historyActorStyle: CSSProperties = {
  color: "#102033",
};

const historyMetaGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(100px, 140px) minmax(0, 1fr)",
  gap: "0.45rem 0.75rem",
  marginTop: "0.8rem",
  fontSize: "0.88rem",
  color: "#334155",
};

const historyNoteStyle: CSSProperties = {
  margin: "0.8rem 0 0",
  color: "#475569",
  lineHeight: 1.5,
};