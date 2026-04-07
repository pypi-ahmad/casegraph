"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import type {
  ActionItem,
  CaseDetailResponse,
  CaseStage,
  CaseStageResponse,
  ReviewDecision,
  ReviewNote,
  StageTransitionRecord,
} from "@casegraph/agent-sdk";

import { fetchCaseDetail } from "@/lib/cases-api";
import {
  createReviewNote,
  fetchCaseActions,
  fetchCaseStage,
  fetchReviewNotes,
  fetchStageHistory,
  generateCaseActions,
  transitionCaseStage,
} from "@/lib/operator-review-api";

const DECISION_OPTIONS: ReviewDecision[] = [
  "note_only",
  "follow_up_required",
  "ready_for_next_step",
  "hold",
  "close_placeholder",
];

const DECISION_LABELS: Record<string, string> = {
  note_only: "Note Only",
  follow_up_required: "Follow-up Required",
  ready_for_next_step: "Ready for Next Step",
  hold: "Hold",
  close_placeholder: "Close",
};

function displayLabel(value: string): string {
  return DECISION_LABELS[value] ?? value.replace(/_/g, " ");
}

export default function CaseReviewClient({ caseId }: { caseId: string }) {
  const [detail, setDetail] = useState<CaseDetailResponse | null>(null);
  const [stage, setStage] = useState<CaseStageResponse | null>(null);
  const [actions, setActions] = useState<ActionItem[]>([]);
  const [notes, setNotes] = useState<ReviewNote[]>([]);
  const [history, setHistory] = useState<StageTransitionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [nextStage, setNextStage] = useState<CaseStage | "">("");
  const [transitionReason, setTransitionReason] = useState("");
  const [transitionNote, setTransitionNote] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [decision, setDecision] = useState<ReviewDecision>("note_only");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [caseDetail, stageResponse, actionResponse, noteResponse, historyResponse] = await Promise.all([
        fetchCaseDetail(caseId),
        fetchCaseStage(caseId),
        fetchCaseActions(caseId),
        fetchReviewNotes(caseId),
        fetchStageHistory(caseId),
      ]);
      setDetail(caseDetail);
      setStage(stageResponse);
      setActions(actionResponse.actions);
      setNotes(noteResponse.notes);
      setHistory(historyResponse.transitions);
      setNextStage(stageResponse.stage.allowed_transitions[0] ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load case review. Try refreshing the page.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [caseId]);

  const openActions = useMemo(
    () => actions.filter((action) => action.status === "open"),
    [actions],
  );

  async function handleGenerateActions() {
    setWorking(true);
    setMessage(null);
    try {
      const response = await generateCaseActions(caseId);
      setActions(response.actions);
      setMessage(response.result.message || "Action items refreshed.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to generate action items.");
    } finally {
      setWorking(false);
    }
  }

  async function handleTransition(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!nextStage) return;
    setWorking(true);
    setMessage(null);
    try {
      const response = await transitionCaseStage(caseId, {
        new_stage: nextStage,
        reason: transitionReason.trim() || null,
        note: transitionNote.trim() || null,
      });
      setStage({ stage: response.stage });
      setHistory((current) => [response.transition, ...current]);
      setNextStage(response.stage.allowed_transitions[0] ?? "");
      setTransitionReason("");
      setTransitionNote("");
      setMessage(response.result.message || "Case stage updated.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to update case stage. Please try again.");
    } finally {
      setWorking(false);
    }
  }

  async function handleAddNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!noteBody.trim()) return;
    setWorking(true);
    setMessage(null);
    try {
      const response = await createReviewNote(caseId, {
        body: noteBody.trim(),
        decision,
      });
      setNotes((current) => [response.note, ...current]);
      setNoteBody("");
      setDecision("note_only");
      setMessage(response.result.message || "Review note recorded.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to record review note. Please try again.");
    } finally {
      setWorking(false);
    }
  }

  if (loading) {
    return <main style={pageStyle}><section style={containerStyle}><div style={panelStyle}>Loading review workspace...</div></section></main>;
  }

  if (error || !detail || !stage) {
    return <main style={pageStyle}><section style={containerStyle}><div style={errorPanelStyle}>{error ?? "Case review workspace not found."}</div></section></main>;
  }

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <div style={linkRowStyle}>
          <Link href="/queue" style={secondaryLinkStyle}>Back to queue</Link>
          <Link href={`/cases/${caseId}`} style={secondaryLinkStyle}>Case workspace</Link>
          <Link href={`/cases/${caseId}/validation`} style={secondaryLinkStyle}>Validation</Link>
          {detail.case.domain_context && (
            <Link href={`/cases/${caseId}/checklist`} style={secondaryLinkStyle}>Checklist</Link>
          )}
          <Link href={`/cases/${caseId}/packets`} style={secondaryLinkStyle}>Packets</Link>
          <Link href={`/cases/${caseId}/communication-drafts`} style={secondaryLinkStyle}>Communication drafts</Link>
          <Link href={`/cases/${caseId}/submission-drafts`} style={secondaryLinkStyle}>Submission drafts</Link>
        </div>

        <header style={headerStyle}>
          <div>
            <p style={breadcrumbStyle}>Operator Review</p>
            <h1 style={titleStyle}>{detail.case.title}</h1>
            <p style={subtitleStyle}>
              Review this case, record decisions, and track follow-ups.
            </p>
          </div>
          <div style={headerStatusBoxStyle}>
            <span style={statusLabelStyle}>Current stage</span>
            <strong style={statusValueStyle}>{stage.stage.current_stage.replace(/_/g, " ")}</strong>
          </div>
        </header>

        {message && <div style={panelStyle}>{message}</div>}

        <div style={layoutStyle}>
          <section style={sectionCardStyle}>
            <div style={sectionHeaderStyle}>
              <h2 style={sectionTitleStyle}>Follow-up Actions</h2>
              <button type="button" style={primaryButtonStyle} onClick={handleGenerateActions} disabled={working}>
                {working ? "Working..." : "Find Next Steps"}
              </button>
            </div>
            <p style={helperTextStyle}>
              Generated from explicit case, checklist, extraction, and workflow state only.
            </p>
            {openActions.length === 0 ? (
              <div style={subtlePanelStyle}>No action items yet. Click “Find Next Steps” above to generate recommended actions from case data.</div>
            ) : (
              <div style={stackStyle}>
                {openActions.map((action) => (
                  <article key={action.action_item_id} style={itemCardStyle}>
                    <div style={itemHeaderStyle}>
                      <strong>{action.title}</strong>
                      <span style={actionBadgeStyle}>{action.category.replace(/_/g, " ")}</span>
                    </div>
                    <p style={itemTextStyle}>{action.description}</p>
                    <p style={metaTextStyle}>{action.source_reason}</p>
                    <div style={metaGridStyle}>
                      <span>Priority</span><span>{action.priority}</span>
                      <span>Source</span><span>{action.source.replace(/_/g, " ")}</span>
                      <span>Status</span><span>{action.status.replace(/_/g, " ")}</span>
                      {action.checklist_item_id && <><span>Checklist item</span><span>{action.checklist_item_id}</span></>}
                      {action.document_id && <><span>Document</span><span>{action.document_id}</span></>}
                      {action.extraction_id && <><span>Extraction</span><span>{action.extraction_id}</span></>}
                      {action.run_id && <><span>Run</span><span>{action.run_id}</span></>}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section style={sectionCardStyle}>
            <h2 style={sectionTitleStyle}>Stage Transition</h2>
            <form onSubmit={handleTransition} style={formStyle}>
              <label style={fieldStyle}>
                <span style={labelStyle}>Next stage</span>
                <select value={nextStage} onChange={(event) => setNextStage(event.target.value as CaseStage | "")} style={inputStyle}>
                  <option value="">Select stage</option>
                  {stage.stage.allowed_transitions.map((item) => (
                    <option key={item} value={item}>{item.replace(/_/g, " ")}</option>
                  ))}
                </select>
              </label>
              <label style={fieldStyle}>
                <span style={labelStyle}>Reason</span>
                <input value={transitionReason} onChange={(event) => setTransitionReason(event.target.value)} style={inputStyle} placeholder="Optional transition reason" />
              </label>
              <label style={fieldStyle}>
                <span style={labelStyle}>Note</span>
                <textarea value={transitionNote} onChange={(event) => setTransitionNote(event.target.value)} style={textareaStyle} rows={3} placeholder="Optional transition note" />
              </label>
              <button type="submit" style={primaryButtonStyle} disabled={working || !nextStage}>
                {working ? "Working..." : "Update Stage"}
              </button>
            </form>
          </section>

          <section style={sectionCardStyle}>
            <h2 style={sectionTitleStyle}>Review Notes</h2>
            <form onSubmit={handleAddNote} style={formStyle}>
              <label style={fieldStyle}>
                <span style={labelStyle}>Decision</span>
                <select value={decision} onChange={(event) => setDecision(event.target.value as ReviewDecision)} style={inputStyle}>
                  {DECISION_OPTIONS.map((item) => (
                    <option key={item} value={item}>{displayLabel(item)}</option>
                  ))}
                </select>
              </label>
              <label style={fieldStyle}>
                <span style={labelStyle}>Note</span>
                <textarea value={noteBody} onChange={(event) => setNoteBody(event.target.value)} style={textareaStyle} rows={4} placeholder="Record an operator review note." />
              </label>
              <button type="submit" style={primaryButtonStyle} disabled={working || !noteBody.trim()}>
                {working ? "Working..." : "Add Review Note"}
              </button>
            </form>
            <div style={stackStyle}>
              {notes.length === 0 ? (
                <div style={subtlePanelStyle}>No review notes recorded yet.</div>
              ) : (
                notes.map((note) => (
                  <article key={note.note_id} style={itemCardStyle}>
                    <div style={itemHeaderStyle}>
                      <strong>{note.decision.replace(/_/g, " ")}</strong>
                      <span style={noteBadgeStyle}>{note.stage_snapshot.replace(/_/g, " ")}</span>
                    </div>
                    <p style={itemTextStyle}>{note.body}</p>
                    <p style={metaTextStyle}>{formatTimestamp(note.created_at)}</p>
                  </article>
                ))
              )}
            </div>
          </section>

          <section style={sectionCardStyle}>
            <h2 style={sectionTitleStyle}>Stage History</h2>
            <div style={stackStyle}>
              {history.length === 0 ? (
                <div style={subtlePanelStyle}>No explicit stage transitions have been recorded yet.</div>
              ) : (
                history.map((transition) => (
                  <article key={transition.transition_id} style={itemCardStyle}>
                    <div style={itemHeaderStyle}>
                      <strong>{transition.from_stage.replace(/_/g, " ")} → {transition.to_stage.replace(/_/g, " ")}</strong>
                      <span style={noteBadgeStyle}>{transition.metadata.transition_type}</span>
                    </div>
                    {transition.metadata.reason && (
                      <p style={itemTextStyle}>Reason: {transition.metadata.reason}</p>
                    )}
                    {transition.metadata.note && (
                      <p style={itemTextStyle}>Note: {transition.metadata.note}</p>
                    )}
                    <p style={metaTextStyle}>{formatTimestamp(transition.created_at)}</p>
                  </article>
                ))
              )}
            </div>
          </section>
        </div>
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
  fontSize: "2.1rem",
  color: "#102033",
};

const subtitleStyle: CSSProperties = {
  maxWidth: "720px",
  color: "#55657a",
  lineHeight: 1.6,
};

const headerStatusBoxStyle: CSSProperties = {
  minWidth: "220px",
  padding: "0.9rem 1rem",
  borderRadius: "14px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
};

const statusLabelStyle: CSSProperties = {
  display: "block",
  fontSize: "0.8rem",
  color: "#64748b",
};

const statusValueStyle: CSSProperties = {
  display: "block",
  marginTop: "0.35rem",
  color: "#102033",
  fontSize: "1rem",
};

const layoutStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: "1rem",
};

const sectionCardStyle: CSSProperties = {
  padding: "1.1rem",
  borderRadius: "16px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
};

const sectionHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "0.75rem",
};

const sectionTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.1rem",
  color: "#102033",
};

const helperTextStyle: CSSProperties = {
  color: "#64748b",
  fontSize: "0.85rem",
  lineHeight: 1.5,
};

const formStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.8rem",
};

const fieldStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.45rem",
};

const labelStyle: CSSProperties = {
  fontSize: "0.85rem",
  color: "#475569",
  fontWeight: 600,
};

const inputStyle: CSSProperties = {
  border: "1px solid #cbd5e1",
  borderRadius: "10px",
  padding: "0.7rem 0.8rem",
  backgroundColor: "#ffffff",
  color: "#102033",
};

const textareaStyle: CSSProperties = {
  ...inputStyle,
  resize: "vertical",
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

const secondaryLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "0.6rem 0.9rem",
  borderRadius: "10px",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  color: "#334155",
  textDecoration: "none",
  fontWeight: 600,
};

const panelStyle: CSSProperties = {
  padding: "1rem 1.25rem",
  border: "1px solid #d7dee8",
  borderRadius: "16px",
  backgroundColor: "#ffffff",
  color: "#334155",
  marginBottom: "1rem",
};

const errorPanelStyle: CSSProperties = {
  ...panelStyle,
  borderColor: "#ef4444",
  color: "#991b1b",
};

const subtlePanelStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  borderRadius: "12px",
  border: "1px dashed #cbd5e1",
  color: "#64748b",
  backgroundColor: "#f8fafc",
};

const stackStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.8rem",
};

const itemCardStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  borderRadius: "12px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
};

const itemHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
};

const actionBadgeStyle: CSSProperties = {
  padding: "0.2rem 0.55rem",
  borderRadius: "999px",
  backgroundColor: "#e2e8f0",
  color: "#334155",
  fontSize: "0.74rem",
  alignSelf: "flex-start",
};

const noteBadgeStyle: CSSProperties = {
  padding: "0.2rem 0.55rem",
  borderRadius: "999px",
  backgroundColor: "#eef2ff",
  color: "#3730a3",
  fontSize: "0.74rem",
  alignSelf: "flex-start",
};

const itemTextStyle: CSSProperties = {
  margin: "0.55rem 0 0",
  color: "#475569",
  lineHeight: 1.5,
};

const metaTextStyle: CSSProperties = {
  margin: "0.55rem 0 0",
  color: "#64748b",
  fontSize: "0.84rem",
};

const metaGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr auto",
  gap: "0.4rem 0.75rem",
  marginTop: "0.7rem",
  fontSize: "0.85rem",
  color: "#475569",
};