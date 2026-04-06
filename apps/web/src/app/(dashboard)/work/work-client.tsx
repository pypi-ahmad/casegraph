"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";

import type {
  AssignmentStatus,
  EscalationReadinessState,
  SessionUser,
  SLAState,
  WorkStatusSummary,
  WorkSummaryResponse,
} from "@casegraph/agent-sdk";

import {
  WorkStatusSnapshot,
  WorkloadSummaryCards,
} from "@/components/work-management/work-status-panels";
import { fetchWorkQueue, fetchWorkSummary } from "@/lib/work-management-api";

type ScopeFilter =
  | "my_work"
  | "unassigned"
  | "priority"
  | "due_soon"
  | "overdue"
  | "attention_needed"
  | "escalation_ready"
  | "all";

const SCOPE_OPTIONS: Array<{ value: ScopeFilter; label: string }> = [
  { value: "my_work", label: "My work" },
  { value: "unassigned", label: "Unassigned" },
  { value: "priority", label: "Priority" },
  { value: "due_soon", label: "Due soon" },
  { value: "overdue", label: "Overdue" },
  { value: "attention_needed", label: "Attention needed" },
  { value: "escalation_ready", label: "Escalation ready" },
  { value: "all", label: "All cases" },
];

const ASSIGNMENT_OPTIONS: Array<{ value: "" | AssignmentStatus; label: string }> = [
  { value: "", label: "All assignments" },
  { value: "unassigned", label: "Unassigned" },
  { value: "assigned", label: "Assigned" },
  { value: "reassigned", label: "Reassigned" },
];

const SLA_OPTIONS: Array<{ value: "" | SLAState; label: string }> = [
  { value: "", label: "All SLA states" },
  { value: "no_deadline", label: "No deadline" },
  { value: "on_track", label: "On track" },
  { value: "due_soon", label: "Due soon" },
  { value: "overdue", label: "Overdue" },
];

const ESCALATION_OPTIONS: Array<{ value: "" | EscalationReadinessState; label: string }> = [
  { value: "", label: "All escalation states" },
  { value: "not_applicable", label: "Not applicable" },
  { value: "attention_needed", label: "Attention needed" },
  { value: "escalation_ready", label: "Escalation ready" },
];

export default function WorkClient({ currentUser }: { currentUser: SessionUser }) {
  const [items, setItems] = useState<WorkStatusSummary[]>([]);
  const [summaryResponse, setSummaryResponse] = useState<WorkSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scope, setScope] = useState<ScopeFilter>("my_work");
  const [assigneeId, setAssigneeId] = useState("");
  const [assignmentStatus, setAssignmentStatus] = useState<"" | AssignmentStatus>("");
  const [slaState, setSlaState] = useState<"" | SLAState>("");
  const [escalationState, setEscalationState] = useState<"" | EscalationReadinessState>("");
  const [domainPackId, setDomainPackId] = useState("");
  const [caseTypeId, setCaseTypeId] = useState("");
  const [searchText, setSearchText] = useState("");

  async function loadData(showLoading = true) {
    if (showLoading) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }

    setError(null);
    try {
      const [queueResponse, summary] = await Promise.all([
        fetchWorkQueue({ limit: 200 }),
        fetchWorkSummary({ limit: 200 }),
      ]);
      setItems(queueResponse.items);
      setSummaryResponse(summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load work board.");
    } finally {
      if (showLoading) {
        setLoading(false);
      } else {
        setRefreshing(false);
      }
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  const myItems = useMemo(
    () => items.filter((item) => item.ownership.current_assignee?.user_id === currentUser.id),
    [currentUser.id, items],
  );

  const unassignedItems = useMemo(
    () => items.filter((item) => item.ownership.assignment_status === "unassigned"),
    [items],
  );

  const priorityItems = useMemo(
    () => items.filter(
      (item) =>
        item.sla_state === "due_soon"
        || item.sla_state === "overdue"
        || item.escalation.state === "attention_needed"
        || item.escalation.state === "escalation_ready",
    ),
    [items],
  );

  const filteredItems = useMemo(() => {
    const normalizedSearch = searchText.trim().toLowerCase();
    return items.filter((item) => {
      if (scope === "my_work" && item.ownership.current_assignee?.user_id !== currentUser.id) {
        return false;
      }
      if (scope === "unassigned" && item.ownership.assignment_status !== "unassigned") {
        return false;
      }
      if (
        scope === "priority"
        && item.sla_state !== "due_soon"
        && item.sla_state !== "overdue"
        && item.escalation.state !== "attention_needed"
        && item.escalation.state !== "escalation_ready"
      ) {
        return false;
      }
      if (scope === "due_soon" && item.sla_state !== "due_soon") {
        return false;
      }
      if (scope === "overdue" && item.sla_state !== "overdue") {
        return false;
      }
      if (scope === "attention_needed" && item.escalation.state !== "attention_needed") {
        return false;
      }
      if (scope === "escalation_ready" && item.escalation.state !== "escalation_ready") {
        return false;
      }
      if (assigneeId && item.ownership.current_assignee?.user_id !== assigneeId) {
        return false;
      }
      if (assignmentStatus && item.ownership.assignment_status !== assignmentStatus) {
        return false;
      }
      if (slaState && item.sla_state !== slaState) {
        return false;
      }
      if (escalationState && item.escalation.state !== escalationState) {
        return false;
      }
      if (domainPackId.trim() && item.domain_pack_id !== domainPackId.trim()) {
        return false;
      }
      if (caseTypeId.trim() && item.case_type_id !== caseTypeId.trim()) {
        return false;
      }
      if (
        normalizedSearch
        && !item.title.toLowerCase().includes(normalizedSearch)
        && !item.case_id.toLowerCase().includes(normalizedSearch)
      ) {
        return false;
      }
      return true;
    });
  }, [
    assigneeId,
    assignmentStatus,
    caseTypeId,
    currentUser.id,
    domainPackId,
    escalationState,
    items,
    scope,
    searchText,
    slaState,
  ]);

  function resetFilters() {
    setScope("my_work");
    setAssigneeId("");
    setAssignmentStatus("");
    setSlaState("");
    setEscalationState("");
    setDomainPackId("");
    setCaseTypeId("");
    setSearchText("");
  }

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <header style={headerStyle}>
          <div>
            <p style={breadcrumbStyle}>Work Management</p>
            <h1 style={titleStyle}>Operator Work Board</h1>
            <p style={subtitleStyle}>
              Explicit case ownership, local-user assignment, due-date tracking, and escalation-readiness views for daily operator workflow management.
            </p>
          </div>
          <div style={headerActionsStyle}>
            <span style={userBadgeStyle}>{currentUser.name || currentUser.email}</span>
            <button
              type="button"
              onClick={() => {
                void loadData(false);
              }}
              style={secondaryButtonStyle}
              disabled={refreshing}
            >
              {refreshing ? "Refreshing..." : "Refresh Board"}
            </button>
          </div>
        </header>

        <div style={linkRowStyle}>
          <Link href="/cases" style={secondaryLinkStyle}>Cases</Link>
          <Link href="/queue" style={secondaryLinkStyle}>Operator queue</Link>
          <Link href="/documents" style={secondaryLinkStyle}>Documents</Link>
        </div>

        {loading ? (
          <div style={panelStyle}>Loading work board...</div>
        ) : error ? (
          <div style={errorPanelStyle}>{error}</div>
        ) : (
          <>
            {summaryResponse && <WorkloadSummaryCards summary={summaryResponse.summary} />}

            <section style={laneGridStyle}>
              <FocusLane
                title="My owned work"
                description="Cases currently assigned to the signed-in local operator."
                count={myItems.length}
                items={myItems.slice(0, 3)}
                emptyMessage="No cases are currently assigned to you."
                onOpen={() => setScope("my_work")}
              />
              <FocusLane
                title="Unassigned queue"
                description="Cases that are active but still not explicitly owned."
                count={unassignedItems.length}
                items={unassignedItems.slice(0, 3)}
                emptyMessage="No unassigned cases are currently waiting in the pool."
                onOpen={() => setScope("unassigned")}
              />
              <FocusLane
                title="At-risk and overdue"
                description="Due-soon, overdue, or escalation-sensitive cases that need attention."
                count={priorityItems.length}
                items={priorityItems.slice(0, 3)}
                emptyMessage="No due-soon, overdue, or escalation-flagged cases right now."
                onOpen={() => setScope("priority")}
              />
            </section>

            <section style={filterSectionStyle}>
              <div style={filterSectionHeaderStyle}>
                <div>
                  <h2 style={sectionTitleStyle}>Filtered Work Queue</h2>
                  <p style={sectionSubtitleStyle}>
                    Showing {filteredItems.length} of {items.length} tracked cases.
                  </p>
                </div>
                <button type="button" onClick={resetFilters} style={secondaryButtonStyle}>
                  Reset Filters
                </button>
              </div>

              <div style={scopeRowStyle}>
                {SCOPE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setScope(option.value)}
                    style={scope === option.value ? activeScopeButtonStyle : scopeButtonStyle}
                  >
                    {option.label}
                  </button>
                ))}
              </div>

              <div style={filterGridStyle}>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Search</span>
                  <input
                    value={searchText}
                    onChange={(event) => setSearchText(event.target.value)}
                    style={inputStyle}
                    placeholder="Case title or case ID"
                  />
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Assignee</span>
                  <select
                    value={assigneeId}
                    onChange={(event) => setAssigneeId(event.target.value)}
                    style={inputStyle}
                  >
                    <option value="">All assignees</option>
                    {summaryResponse?.available_assignees.map((assignee) => (
                      <option key={assignee.user_id} value={assignee.user_id}>
                        {assignee.display_name} ({assignee.user_id})
                      </option>
                    ))}
                  </select>
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Assignment status</span>
                  <select
                    value={assignmentStatus}
                    onChange={(event) => setAssignmentStatus(event.target.value as "" | AssignmentStatus)}
                    style={inputStyle}
                  >
                    {ASSIGNMENT_OPTIONS.map((option) => (
                      <option key={option.label} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>SLA state</span>
                  <select
                    value={slaState}
                    onChange={(event) => setSlaState(event.target.value as "" | SLAState)}
                    style={inputStyle}
                  >
                    {SLA_OPTIONS.map((option) => (
                      <option key={option.label} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Escalation state</span>
                  <select
                    value={escalationState}
                    onChange={(event) => setEscalationState(event.target.value as "" | EscalationReadinessState)}
                    style={inputStyle}
                  >
                    {ESCALATION_OPTIONS.map((option) => (
                      <option key={option.label} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Domain pack</span>
                  <input
                    value={domainPackId}
                    onChange={(event) => setDomainPackId(event.target.value)}
                    style={inputStyle}
                    placeholder="medical_us"
                  />
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Case type</span>
                  <input
                    value={caseTypeId}
                    onChange={(event) => setCaseTypeId(event.target.value)}
                    style={inputStyle}
                    placeholder="medical_us:record_review"
                  />
                </label>
              </div>

              {filteredItems.length === 0 ? (
                <div style={panelStyle}>No cases match the current work filters.</div>
              ) : (
                <div style={resultsGridStyle}>
                  {filteredItems.map((item) => (
                    <WorkStatusSnapshot
                      key={item.case_id}
                      status={item}
                      label="Case Work Status"
                      compact
                      actions={[
                        { href: `/cases/${item.case_id}`, label: "Open Case", tone: "primary" },
                        { href: `/cases/${item.case_id}/review`, label: "Review" },
                        { href: `/cases/${item.case_id}/handoff`, label: "Handoff" },
                        { href: `/cases/${item.case_id}/releases`, label: "Releases" },
                      ]}
                    />
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </section>
    </main>
  );
}

function FocusLane({
  title,
  description,
  count,
  items,
  emptyMessage,
  onOpen,
}: {
  title: string;
  description: string;
  count: number;
  items: WorkStatusSummary[];
  emptyMessage: string;
  onOpen: () => void;
}) {
  return (
    <section style={laneCardStyle}>
      <div style={laneHeaderStyle}>
        <div>
          <h2 style={laneTitleStyle}>{title}</h2>
          <p style={laneDescriptionStyle}>{description}</p>
        </div>
        <button type="button" onClick={onOpen} style={secondaryButtonStyle}>
          Open
        </button>
      </div>
      <p style={laneCountStyle}>{count} case(s)</p>
      {items.length === 0 ? (
        <div style={subtlePanelStyle}>{emptyMessage}</div>
      ) : (
        <div style={laneStackStyle}>
          {items.map((item) => (
            <WorkStatusSnapshot
              key={item.case_id}
              status={item}
              label="Work Snapshot"
              compact
              actions={[{ href: `/cases/${item.case_id}`, label: "Open Case", tone: "primary" }]}
            />
          ))}
        </div>
      )}
    </section>
  );
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "2.5rem 1.25rem 3rem",
  backgroundColor: "#f5f7fa",
};

const containerStyle: CSSProperties = {
  maxWidth: "1240px",
  margin: "0 auto",
};

const headerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "1rem",
  marginBottom: "1rem",
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
  fontSize: "2.2rem",
  color: "#102033",
};

const subtitleStyle: CSSProperties = {
  maxWidth: "760px",
  color: "#55657a",
  lineHeight: 1.6,
};

const headerActionsStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.75rem",
};

const userBadgeStyle: CSSProperties = {
  padding: "0.35rem 0.7rem",
  borderRadius: "999px",
  backgroundColor: "#e2e8f0",
  color: "#334155",
  fontSize: "0.8rem",
  fontWeight: 600,
};

const linkRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.75rem",
  marginBottom: "1rem",
};

const secondaryLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "0.55rem 0.8rem",
  borderRadius: "999px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
  color: "#102033",
  textDecoration: "none",
  fontWeight: 600,
};

const panelStyle: CSSProperties = {
  padding: "0.95rem 1rem",
  borderRadius: "12px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
  color: "#334155",
};

const errorPanelStyle: CSSProperties = {
  ...panelStyle,
  borderColor: "#ef4444",
  backgroundColor: "#fff1f2",
  color: "#991b1b",
};

const laneGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
  gap: "1rem",
  marginTop: "1rem",
};

const laneCardStyle: CSSProperties = {
  padding: "1rem",
  borderRadius: "16px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
};

const laneHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "flex-start",
};

const laneTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.05rem",
  color: "#102033",
};

const laneDescriptionStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  color: "#55657a",
  lineHeight: 1.5,
};

const laneCountStyle: CSSProperties = {
  margin: "0.75rem 0",
  fontSize: "0.86rem",
  fontWeight: 600,
  color: "#475569",
};

const laneStackStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const subtlePanelStyle: CSSProperties = {
  padding: "0.85rem 0.95rem",
  borderRadius: "12px",
  backgroundColor: "#f8fafc",
  border: "1px solid #d7dee8",
  color: "#475569",
};

const filterSectionStyle: CSSProperties = {
  marginTop: "1.25rem",
  padding: "1.1rem",
  borderRadius: "18px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
};

const filterSectionHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "flex-start",
};

const sectionTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.1rem",
  color: "#102033",
};

const sectionSubtitleStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  color: "#55657a",
};

const scopeRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.6rem",
  marginTop: "1rem",
};

const scopeButtonStyle: CSSProperties = {
  padding: "0.55rem 0.85rem",
  borderRadius: "999px",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  color: "#334155",
  fontWeight: 600,
  cursor: "pointer",
};

const activeScopeButtonStyle: CSSProperties = {
  ...scopeButtonStyle,
  borderColor: "#102033",
  backgroundColor: "#102033",
  color: "#ffffff",
};

const filterGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "0.85rem",
  marginTop: "1rem",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.45rem",
};

const labelStyle: CSSProperties = {
  fontSize: "0.86rem",
  fontWeight: 600,
  color: "#334155",
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "0.7rem 0.85rem",
  borderRadius: "10px",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  color: "#102033",
};

const secondaryButtonStyle: CSSProperties = {
  padding: "0.65rem 0.9rem",
  borderRadius: "10px",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  color: "#102033",
  fontWeight: 600,
  cursor: "pointer",
};

const resultsGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: "0.9rem",
  marginTop: "1rem",
};