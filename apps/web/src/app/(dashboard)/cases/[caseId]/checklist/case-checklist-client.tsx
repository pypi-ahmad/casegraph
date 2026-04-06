"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

import type {
  ChecklistResponse,
  ChecklistItem,
  ReadinessResponse,
  ReadinessSummary,
  ChecklistItemStatus,
} from "@casegraph/agent-sdk";

import {
  fetchChecklist,
  generateChecklist,
  evaluateChecklist,
  fetchReadiness,
  ReadinessApiError,
} from "@/lib/readiness-api";

// ---------------------------------------------------------------------------
// Status badge helpers
// ---------------------------------------------------------------------------

const STATUS_LABELS: Record<ChecklistItemStatus, string> = {
  missing: "Missing",
  partially_supported: "Partial",
  supported: "Supported",
  needs_human_review: "Needs Review",
  optional_unfilled: "Optional",
  waived: "Waived",
};

const STATUS_COLORS: Record<ChecklistItemStatus, string> = {
  missing: "#dc3545",
  partially_supported: "#fd7e14",
  supported: "#198754",
  needs_human_review: "#6f42c1",
  optional_unfilled: "#6c757d",
  waived: "#0dcaf0",
};

function StatusBadge({ status }: { status: ChecklistItemStatus }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 4,
        fontSize: 12,
        fontWeight: 600,
        color: "#fff",
        backgroundColor: STATUS_COLORS[status] ?? "#6c757d",
      }}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const color =
    priority === "required"
      ? "#dc3545"
      : priority === "recommended"
        ? "#fd7e14"
        : "#6c757d";
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 600,
        color,
        border: `1px solid ${color}`,
        backgroundColor: "transparent",
      }}
    >
      {priority}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Readiness summary panel
// ---------------------------------------------------------------------------

function ReadinessPanel({ readiness }: { readiness: ReadinessSummary }) {
  const statusColor =
    readiness.readiness_status === "ready"
      ? "#198754"
      : readiness.readiness_status === "incomplete"
        ? "#dc3545"
        : readiness.readiness_status === "needs_review"
          ? "#6f42c1"
          : "#6c757d";

  return (
    <div style={panelStyle}>
      <h3 style={{ margin: "0 0 12px" }}>Readiness Summary</h3>
      <div
        style={{
          display: "inline-block",
          padding: "4px 12px",
          borderRadius: 6,
          fontWeight: 700,
          color: "#fff",
          backgroundColor: statusColor,
          marginBottom: 12,
        }}
      >
        {readiness.readiness_status.replace(/_/g, " ").toUpperCase()}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 14 }}>
        <span>Total items:</span><span>{readiness.total_items}</span>
        <span>Required:</span><span>{readiness.required_items}</span>
        <span>Supported:</span><span style={{ color: "#198754", fontWeight: 600 }}>{readiness.supported_items}</span>
        <span>Partially supported:</span><span style={{ color: "#fd7e14", fontWeight: 600 }}>{readiness.partially_supported_items}</span>
        <span>Missing:</span><span style={{ color: "#dc3545", fontWeight: 600 }}>{readiness.missing_items}</span>
        <span>Needs review:</span><span style={{ color: "#6f42c1", fontWeight: 600 }}>{readiness.needs_review_items}</span>
        <span>Optional unfilled:</span><span>{readiness.optional_unfilled_items}</span>
        <span>Waived:</span><span>{readiness.waived_items}</span>
      </div>
      {readiness.missing_required.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <strong style={{ fontSize: 13, color: "#dc3545" }}>
            Missing required items:
          </strong>
          <ul style={{ margin: "4px 0 0 16px", padding: 0, fontSize: 13 }}>
            {readiness.missing_required.map((m) => (
              <li key={m.item_id}>{m.display_name}</li>
            ))}
          </ul>
        </div>
      )}
      {readiness.evaluated_at && (
        <p style={{ fontSize: 12, color: "#888", marginTop: 8, marginBottom: 0 }}>
          Last evaluated: {new Date(readiness.evaluated_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Checklist item row
// ---------------------------------------------------------------------------

function ItemRow({ item }: { item: ChecklistItem }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div style={itemStyle}>
      <div
        style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
        onClick={() => setExpanded(!expanded)}
      >
        <span style={{ fontSize: 13, minWidth: 60 }}>
          <PriorityBadge priority={item.priority} />
        </span>
        <span style={{ flex: 1, fontWeight: 500, fontSize: 14 }}>
          {item.display_name}
        </span>
        <StatusBadge status={item.status} />
        <span style={{ fontSize: 12, color: "#888" }}>
          {expanded ? "▲" : "▼"}
        </span>
      </div>

      {expanded && (
        <div style={{ marginTop: 10, paddingLeft: 70, fontSize: 13 }}>
          {item.description && (
            <p style={{ margin: "0 0 6px", color: "#666" }}>{item.description}</p>
          )}
          <p style={{ margin: "0 0 4px" }}>
            <strong>Category:</strong> {item.document_category.replace(/_/g, " ")}
          </p>

          {item.linked_documents.length > 0 ? (
            <div style={{ margin: "8px 0" }}>
              <strong>Linked documents:</strong>
              <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
                {item.linked_documents.map((d) => (
                  <li key={d.document_id}>
                    <Link
                      href={`/documents/${d.document_id}`}
                      style={{ color: "#0d6efd" }}
                    >
                      {d.filename || d.document_id}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p style={{ color: "#999", margin: "8px 0 4px" }}>No linked documents.</p>
          )}

          {item.linked_extractions.length > 0 && (
            <div style={{ margin: "8px 0" }}>
              <strong>Linked extractions:</strong>
              <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
                {item.linked_extractions.map((e) => (
                  <li key={e.extraction_id}>
                    Template: {e.template_id} · Fields: {e.field_count}
                    {e.grounding_available && " · Grounding: available"}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div style={{ margin: "8px 0" }}>
            <strong>Linked evidence references:</strong>
            {item.linked_evidence.length > 0 ? (
              <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
                {item.linked_evidence.map((evidence, index) => (
                  <li key={`${evidence.source_document_id}-${index}`}>
                    Source document: {evidence.source_document_id}
                    {evidence.page_number !== null && ` · Page ${evidence.page_number}`}
                    {evidence.chunk_summary ? ` · ${evidence.chunk_summary}` : ""}
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ color: "#999", margin: "4px 0 0" }}>
                No evidence references linked yet.
              </p>
            )}
          </div>

          {item.operator_notes && (
            <p style={{ margin: "8px 0 0", fontStyle: "italic", color: "#666" }}>
              Operator notes: {item.operator_notes}
            </p>
          )}

          {item.last_evaluated_at && (
            <p style={{ fontSize: 11, color: "#888", marginTop: 4, marginBottom: 0 }}>
              Evaluated: {new Date(item.last_evaluated_at).toLocaleString()}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function CaseChecklistClient({ caseId }: { caseId: string }) {
  const [checklist, setChecklist] = useState<ChecklistResponse | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const cl = await fetchChecklist(caseId);
      setChecklist(cl);
      const rd = await fetchReadiness(caseId);
      setReadiness(rd);
    } catch (err) {
      if (err instanceof ReadinessApiError && err.status === 404) {
        setChecklist(null);
        setReadiness(null);
      } else {
        setError(err instanceof Error ? err.message : "Failed to load");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  async function handleGenerate(force = false) {
    setActionLoading(true);
    setError(null);
    try {
      const cl = await generateChecklist(caseId, force);
      setChecklist(cl);
      setReadiness(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleEvaluate() {
    setActionLoading(true);
    setError(null);
    try {
      const rd = await evaluateChecklist(caseId);
      setReadiness(rd);
      // Reload checklist to get updated item statuses.
      const cl = await fetchChecklist(caseId);
      setChecklist(cl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to evaluate");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) return <div style={containerStyle}><p>Loading checklist…</p></div>;

  return (
    <div style={containerStyle}>
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 16 }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>Case Checklist</h1>
        <Link href={`/cases/${caseId}`} style={{ color: "#0d6efd", fontSize: 14 }}>
          ← Back to case
        </Link>
        <Link href={`/cases/${caseId}/review`} style={{ color: "#0d6efd", fontSize: 14 }}>
          Operator review →
        </Link>
      </div>

      {error && <p style={{ color: "#dc3545" }}>{error}</p>}

      <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
        {!checklist ? (
          <button
            style={btnStyle}
            onClick={() => handleGenerate(false)}
            disabled={actionLoading}
          >
            {actionLoading ? "Generating…" : "Generate Checklist"}
          </button>
        ) : (
          <>
            <button
              style={btnStyle}
              onClick={() => handleGenerate(true)}
              disabled={actionLoading}
            >
              {actionLoading ? "Working…" : "Regenerate"}
            </button>
            <button
              style={{ ...btnStyle, backgroundColor: "#0d6efd" }}
              onClick={handleEvaluate}
              disabled={actionLoading}
            >
              {actionLoading ? "Evaluating…" : "Evaluate Coverage"}
            </button>
          </>
        )}
      </div>

      {readiness && <ReadinessPanel readiness={readiness.readiness} />}

      {checklist ? (
        <>
          <div style={{ marginBottom: 12, fontSize: 13, color: "#666" }}>
            <strong>Pack:</strong> {checklist.checklist.generation.domain_pack_id} ·{" "}
            <strong>Case type:</strong> {checklist.checklist.generation.case_type_id} ·{" "}
            <strong>Items:</strong> {checklist.checklist.generation.requirement_count} ·{" "}
            <strong>Generated:</strong>{" "}
            {new Date(checklist.checklist.generation.generated_at).toLocaleString()}
          </div>

          {checklist.checklist.items.length === 0 ? (
            <p style={{ color: "#888" }}>No requirement items in this checklist.</p>
          ) : (
            checklist.checklist.items.map((item) => (
              <ItemRow key={item.item_id} item={item} />
            ))
          )}

          <p style={{ fontSize: 12, color: "#999", marginTop: 20 }}>
            This checklist is derived from the domain pack case type template.
            Coverage evaluation links case documents and extractions to requirement
            items using coarse category matching. It does not perform deep semantic
            verification or claim regulatory compliance.
          </p>
        </>
      ) : (
        <p style={{ color: "#888" }}>
          No checklist exists yet. If this case was created from a domain pack,
          generate a checklist to see document requirement coverage.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const containerStyle: CSSProperties = {
  maxWidth: 900,
  margin: "0 auto",
  padding: "24px 16px",
};

const panelStyle: CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 8,
  padding: 16,
  marginBottom: 20,
  backgroundColor: "#f8f9fa",
};

const itemStyle: CSSProperties = {
  border: "1px solid #e0e0e0",
  borderRadius: 6,
  padding: "10px 14px",
  marginBottom: 8,
  backgroundColor: "#fff",
};

const btnStyle: CSSProperties = {
  padding: "8px 18px",
  borderRadius: 6,
  border: "none",
  cursor: "pointer",
  fontWeight: 600,
  fontSize: 14,
  backgroundColor: "#333",
  color: "#fff",
};
