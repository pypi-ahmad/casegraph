"use client";

import { useEffect, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import type {
  AssignmentHistoryEntry,
  CaseWorkStatusResponse,
  SessionUser,
} from "@casegraph/agent-sdk";

import {
  AssignmentHistoryList,
  WorkStatusSnapshot,
  toDateTimeLocal,
} from "@/components/work-management/work-status-panels";
import {
  fetchAssignmentHistory,
  fetchCaseWorkStatus,
  updateCaseAssignment,
  updateCaseSLA,
} from "@/lib/work-management-api";

interface Props {
  caseId: string;
  currentUser: SessionUser;
}

export default function CaseWorkManagementSection({ caseId, currentUser }: Props) {
  const [workStatus, setWorkStatus] = useState<CaseWorkStatusResponse | null>(null);
  const [history, setHistory] = useState<AssignmentHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [selectedAssigneeId, setSelectedAssigneeId] = useState("");
  const [assignmentNote, setAssignmentNote] = useState("");
  const [slaDueAt, setSlaDueAt] = useState("");
  const [slaPolicyId, setSlaPolicyId] = useState("");
  const [slaWindowHours, setSlaWindowHours] = useState("24");
  const [slaNote, setSlaNote] = useState("");
  const [showSlaAdvanced, setShowSlaAdvanced] = useState(false);

  async function loadWorkData(showLoading = true) {
    if (showLoading) {
      setLoading(true);
    }
    setError(null);

    try {
      const [statusResponse, historyResponse] = await Promise.all([
        fetchCaseWorkStatus(caseId),
        fetchAssignmentHistory(caseId),
      ]);

      setWorkStatus(statusResponse);
      setHistory(historyResponse.history);
      setSelectedAssigneeId(
        statusResponse.work_status.ownership.current_assignee?.user_id ?? "",
      );
      setAssignmentNote(statusResponse.work_status.ownership.note ?? "");
      setSlaDueAt(toDateTimeLocal(statusResponse.work_status.sla_target.due_date?.due_at));
      setSlaPolicyId(statusResponse.work_status.sla_target.policy_id ?? "");
      setSlaWindowHours(
        String(
          statusResponse.work_status.sla_target.due_date?.due_soon_window_hours ?? 24,
        ),
      );
      setSlaNote(statusResponse.work_status.sla_target.due_date?.note ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load case work management.");
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    void loadWorkData();
  }, [caseId]);

  async function handleAssignmentSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedAssigneeId) {
      setError("Select a local operator before saving assignment.");
      return;
    }

    setWorking(true);
    setMessage(null);
    setError(null);
    try {
      const response = await updateCaseAssignment(caseId, {
        assignee_id: selectedAssigneeId,
        note: assignmentNote.trim() || null,
        actor_id: currentUser.id,
        actor_display_name: currentUser.name || currentUser.email,
      });
      setMessage(response.result.message || "Case assignment updated.");
      await loadWorkData(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update case assignment.");
    } finally {
      setWorking(false);
    }
  }

  async function handleClearAssignment() {
    setWorking(true);
    setMessage(null);
    setError(null);
    try {
      const response = await updateCaseAssignment(caseId, {
        clear_assignment: true,
        note: assignmentNote.trim() || null,
        actor_id: currentUser.id,
        actor_display_name: currentUser.name || currentUser.email,
      });
      setMessage(response.result.message || "Case assignment cleared.");
      await loadWorkData(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to clear case assignment.");
    } finally {
      setWorking(false);
    }
  }

  async function handleSlaSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!slaDueAt) {
      setError("Provide a due date before saving deadline metadata.");
      return;
    }

    const parsed = new Date(slaDueAt);
    if (Number.isNaN(parsed.getTime())) {
      setError("Due date must be a valid local date/time.");
      return;
    }

    setWorking(true);
    setMessage(null);
    setError(null);
    try {
      const response = await updateCaseSLA(caseId, {
        due_at: parsed.toISOString(),
        policy_id: slaPolicyId.trim() || null,
        due_soon_window_hours: Math.max(1, Number.parseInt(slaWindowHours, 10) || 24),
        note: slaNote.trim() || null,
        actor_id: currentUser.id,
        actor_display_name: currentUser.name || currentUser.email,
      });
      setMessage(response.result.message || "Case deadline updated.");
      await loadWorkData(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update case deadline.");
    } finally {
      setWorking(false);
    }
  }

  async function handleClearDueDate() {
    setWorking(true);
    setMessage(null);
    setError(null);
    try {
      const response = await updateCaseSLA(caseId, {
        clear_due_date: true,
        note: slaNote.trim() || null,
        actor_id: currentUser.id,
        actor_display_name: currentUser.name || currentUser.email,
      });
      setMessage(response.result.message || "Case deadline cleared.");
      await loadWorkData(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to clear case deadline.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <section style={sectionCardStyle}>
      <div style={sectionHeaderStyle}>
        <div>
          <h2 style={sectionTitleStyle}>Ownership & Deadlines</h2>
          <p style={sectionSubtitleStyle}>
            Who owns this case and when it's due.
          </p>
        </div>
        <span style={actorBadgeStyle}>Acting as {currentUser.name || currentUser.email}</span>
      </div>

      {message && <div style={panelStyle}>{message}</div>}
      {error && <div style={errorPanelStyle}>{error}</div>}

      {loading ? (
        <div style={panelStyle}>Loading case work management...</div>
      ) : workStatus ? (
        <>
          <div style={layoutStyle}>
            <div style={stackStyle}>
              <WorkStatusSnapshot
                status={workStatus.work_status}
                label="Current Work Status"
                actions={[
                  { href: "/work", label: "Open Work Board", tone: "primary" },
                  { href: `/cases/${caseId}/review`, label: "Open Review" },
                ]}
              />
            </div>

            <div style={stackStyle}>
              <section style={subsectionCardStyle}>
                <h3 style={subsectionTitleStyle}>Assignment</h3>
                <form onSubmit={handleAssignmentSubmit} style={formStyle}>
                  <label style={fieldStyle}>
                    <span style={labelStyle}>Assignee</span>
                    <select
                      value={selectedAssigneeId}
                      onChange={(event) => setSelectedAssigneeId(event.target.value)}
                      style={inputStyle}
                    >
                      <option value="">Select local operator</option>
                      {workStatus.available_assignees.map((assignee) => (
                        <option key={assignee.user_id} value={assignee.user_id}>
                          {assignee.display_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label style={fieldStyle}>
                    <span style={labelStyle}>Assignment note</span>
                    <input
                      value={assignmentNote}
                      onChange={(event) => setAssignmentNote(event.target.value)}
                      style={inputStyle}
                      placeholder="Why this case is assigned here"
                    />
                  </label>
                  <div style={buttonRowStyle}>
                    <button
                      type="submit"
                      style={primaryButtonStyle}
                      disabled={working || !selectedAssigneeId}
                    >
                      {working ? "Saving..." : "Save Assignment"}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void handleClearAssignment();
                      }}
                      style={secondaryButtonStyle}
                      disabled={working || !workStatus.work_status.ownership.current_assignee}
                    >
                      Clear Assignment
                    </button>
                  </div>
                </form>
              </section>

              <section style={subsectionCardStyle}>
                <h3 style={subsectionTitleStyle}>Deadline / SLA</h3>
                <form onSubmit={handleSlaSubmit} style={formStyle}>
                  <label style={fieldStyle}>
                    <span style={labelStyle}>Due date</span>
                    <input
                      type="datetime-local"
                      value={slaDueAt}
                      onChange={(event) => setSlaDueAt(event.target.value)}
                      style={inputStyle}
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowSlaAdvanced((prev) => !prev)}
                    style={{ background: "none", border: "none", color: "#0d6efd", cursor: "pointer", fontSize: "0.82rem", padding: "0.25rem 0", textAlign: "left" }}
                  >
                    {showSlaAdvanced ? "Hide advanced options ▾" : "Advanced options ▸"}
                  </button>
                  {showSlaAdvanced && (
                    <>
                      <label style={fieldStyle}>
                        <span style={labelStyle}>Policy identifier</span>
                        <input
                          value={slaPolicyId}
                          onChange={(event) => setSlaPolicyId(event.target.value)}
                          style={inputStyle}
                          placeholder="local-default"
                        />
                      </label>
                      <label style={fieldStyle}>
                        <span style={labelStyle}>Due-soon window (hours)</span>
                        <input
                          type="number"
                          min={1}
                          value={slaWindowHours}
                          onChange={(event) => setSlaWindowHours(event.target.value)}
                          style={inputStyle}
                        />
                      </label>
                    </>
                  )}
                  <label style={fieldStyle}>
                    <span style={labelStyle}>Deadline note</span>
                    <input
                      value={slaNote}
                      onChange={(event) => setSlaNote(event.target.value)}
                      style={inputStyle}
                      placeholder="Why this due date matters"
                    />
                  </label>
                  <div style={buttonRowStyle}>
                    <button
                      type="submit"
                      style={primaryButtonStyle}
                      disabled={working || !slaDueAt}
                    >
                      {working ? "Saving..." : "Save Deadline"}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void handleClearDueDate();
                      }}
                      style={secondaryButtonStyle}
                      disabled={working || !workStatus.work_status.sla_target.due_date}
                    >
                      Clear Deadline
                    </button>
                  </div>
                </form>
              </section>
            </div>
          </div>

          <div style={{ marginTop: "1rem" }}>
            <AssignmentHistoryList history={history} />
          </div>
        </>
      ) : (
        <div style={errorPanelStyle}>Work status is not available for this case.</div>
      )}
    </section>
  );
}

const sectionCardStyle: CSSProperties = {
  padding: "1.25rem",
  border: "1px solid #d7dee8",
  borderRadius: "16px",
  backgroundColor: "#ffffff",
};

const sectionHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "1rem",
  marginBottom: "1rem",
};

const sectionTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.15rem",
  color: "#102033",
};

const sectionSubtitleStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  color: "#55657a",
  lineHeight: 1.5,
};

const actorBadgeStyle: CSSProperties = {
  padding: "0.3rem 0.65rem",
  borderRadius: "999px",
  backgroundColor: "#e2e8f0",
  color: "#334155",
  fontSize: "0.78rem",
  fontWeight: 600,
};

const layoutStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: "1rem",
};

const stackStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
};

const subsectionCardStyle: CSSProperties = {
  padding: "1rem",
  borderRadius: "14px",
  border: "1px solid #d7dee8",
  backgroundColor: "#f8fafc",
};

const subsectionTitleStyle: CSSProperties = {
  margin: "0 0 0.85rem",
  fontSize: "1rem",
  color: "#102033",
};

const formStyle: CSSProperties = {
  display: "grid",
  gap: "0.85rem",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.45rem",
};

const labelStyle: CSSProperties = {
  fontSize: "0.88rem",
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

const buttonRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.75rem",
};

const primaryButtonStyle: CSSProperties = {
  padding: "0.7rem 1rem",
  borderRadius: "10px",
  border: "none",
  backgroundColor: "#102033",
  color: "#ffffff",
  fontWeight: 600,
  cursor: "pointer",
};

const secondaryButtonStyle: CSSProperties = {
  padding: "0.7rem 1rem",
  borderRadius: "10px",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  color: "#102033",
  fontWeight: 600,
  cursor: "pointer",
};

const panelStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  border: "1px solid #d7dee8",
  borderRadius: "12px",
  backgroundColor: "#f8fafc",
  color: "#334155",
  marginBottom: "1rem",
};

const errorPanelStyle: CSSProperties = {
  ...panelStyle,
  borderColor: "#ef4444",
  backgroundColor: "#fff1f2",
  color: "#991b1b",
};