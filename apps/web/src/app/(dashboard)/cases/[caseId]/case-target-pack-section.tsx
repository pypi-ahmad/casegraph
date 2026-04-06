"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";

import type {
  CaseTargetPackSelection,
  TargetPackDetail,
  TargetPackSummary,
} from "@casegraph/agent-sdk";

import {
  fetchTargetPackDetail,
  fetchTargetPacks,
  updateCaseTargetPack,
} from "@/lib/target-packs-api";

export default function CaseTargetPackSection({
  caseId,
  domainPackId,
  caseTypeId,
  initialSelection,
}: {
  caseId: string;
  domainPackId?: string | null;
  caseTypeId?: string | null;
  initialSelection: CaseTargetPackSelection | null;
}) {
  const [selection, setSelection] = useState<CaseTargetPackSelection | null>(initialSelection);
  const [selectedPackId, setSelectedPackId] = useState(initialSelection?.pack_id ?? "");
  const [availablePacks, setAvailablePacks] = useState<TargetPackSummary[]>([]);
  const [selectedPack, setSelectedPack] = useState<TargetPackDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setSelection(initialSelection);
    setSelectedPackId(initialSelection?.pack_id ?? "");
  }, [caseId, initialSelection]);

  useEffect(() => {
    let cancelled = false;
    if (!domainPackId && !caseTypeId) {
      setAvailablePacks([]);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }

    setLoading(true);
    fetchTargetPacks({
      domain_pack_id: domainPackId ?? null,
      case_type_id: caseTypeId ?? null,
    })
      .then((response) => {
        if (cancelled) return;
        setAvailablePacks(response.packs);
      })
      .catch((err) => {
        if (!cancelled) {
          setMessage(err instanceof Error ? err.message : "Unable to load compatible target packs.");
          setAvailablePacks([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [domainPackId, caseTypeId]);

  useEffect(() => {
    let cancelled = false;
    if (!selectedPackId) {
      setSelectedPack(null);
      return () => {
        cancelled = true;
      };
    }

    fetchTargetPackDetail(selectedPackId)
      .then((response) => {
        if (!cancelled) setSelectedPack(response.pack);
      })
      .catch((err) => {
        if (!cancelled) {
          setMessage(err instanceof Error ? err.message : "Unable to load target-pack detail.");
          setSelectedPack(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedPackId]);

  const selectedSummary = useMemo(
    () => availablePacks.find((pack) => pack.metadata.pack_id === selectedPackId) ?? null,
    [availablePacks, selectedPackId],
  );

  const hasUnsavedChange = selectedPackId !== (selection?.pack_id ?? "");

  async function handleSave() {
    if (!selectedPackId) return;
    setWorking(true);
    setMessage(null);
    try {
      const response = await updateCaseTargetPack(caseId, { pack_id: selectedPackId });
      setSelection(response.selection);
      setMessage(response.result.message || "Target pack saved.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to save target-pack selection.");
    } finally {
      setWorking(false);
    }
  }

  async function handleClear() {
    setWorking(true);
    setMessage(null);
    try {
      const response = await updateCaseTargetPack(caseId, { clear_selection: true });
      setSelection(response.selection);
      setSelectedPackId("");
      setSelectedPack(null);
      setMessage(response.result.message || "Target pack cleared.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to clear target-pack selection.");
    } finally {
      setWorking(false);
    }
  }

  if (!domainPackId && !caseTypeId) {
    return (
      <section style={sectionCardStyle}>
        <div style={sectionHeaderStyle}>
          <div>
            <h2 style={sectionTitleStyle}>Target Pack</h2>
            <p style={helperTextStyle}>
              Target packs are selected only after domain pack and case-type context exists for the case.
            </p>
          </div>
          <Link href="/target-packs" style={linkStyle}>
            Browse target packs
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section style={sectionCardStyle}>
      <div style={sectionHeaderStyle}>
        <div>
          <h2 style={sectionTitleStyle}>Target Pack</h2>
          <p style={helperTextStyle}>
            Case-scoped selection for submission target overlays, field schema hints, and reviewed release provenance.
          </p>
        </div>
        <Link href="/target-packs" style={linkStyle}>
          Explore registry
        </Link>
      </div>

      {message && <div style={messageStyle}>{message}</div>}

      {loading ? (
        <div style={panelStyle}>Loading compatible target packs...</div>
      ) : availablePacks.length === 0 ? (
        <div style={panelStyle}>
          No target packs are registered for this case domain and case-type combination yet.
        </div>
      ) : (
        <>
          <div style={selectionGridStyle}>
            <label style={fieldStyle}>
              <span style={labelStyle}>Compatible target pack</span>
              <select
                value={selectedPackId}
                onChange={(event) => setSelectedPackId(event.target.value)}
                style={inputStyle}
              >
                <option value="">No target pack selected</option>
                {availablePacks.map((pack) => (
                  <option key={pack.metadata.pack_id} value={pack.metadata.pack_id}>
                    {pack.metadata.display_name} · v{pack.metadata.version}
                  </option>
                ))}
              </select>
            </label>

            <div style={actionRowStyle}>
              <button
                type="button"
                onClick={handleSave}
                style={primaryButtonStyle}
                disabled={working || !selectedPackId || !hasUnsavedChange}
              >
                Save target pack
              </button>
              <button
                type="button"
                onClick={handleClear}
                style={secondaryButtonStyle}
                disabled={working || !selection}
              >
                Clear selection
              </button>
            </div>
          </div>

          {selection ? (
            <div style={messageStyle}>
              Current selection: {selection.display_name} ({selection.pack_id} · v{selection.version})
              {selection.selected_at ? ` selected ${formatTimestamp(selection.selected_at)}` : ""}
            </div>
          ) : (
            <div style={panelStyle}>No target pack is currently selected for this case.</div>
          )}

          {selectedPack && selectedSummary && (
            <article style={previewCardStyle}>
              <div style={itemHeaderStyle}>
                <div>
                  <strong style={previewTitleStyle}>{selectedPack.metadata.display_name}</strong>
                  <p style={monoTextStyle}>
                    {selectedPack.metadata.pack_id} · v{selectedPack.metadata.version}
                  </p>
                </div>
                <span style={badgeStyle}>{selectedPack.metadata.category.replace(/_/g, " ")}</span>
              </div>
              <p style={helperTextStyle}>{selectedPack.metadata.description}</p>
              <div style={tagRowStyle}>
                <span style={tagStyle}>{selectedSummary.field_count} mapped fields</span>
                <span style={tagStyle}>
                  {selectedSummary.requirement_override_count} requirement overlays
                </span>
                <span style={tagStyle}>
                  {selectedSummary.submission_target_count} submission targets
                </span>
              </div>
              <div style={detailGridStyle}>
                <div>
                  <strong>Submission targets</strong>
                  <div style={tagRowStyle}>
                    {selectedPack.submission_compatibility.submission_target_ids.map((targetId) => (
                      <span key={targetId} style={tagStyle}>
                        {targetId}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <strong>Workflow packs</strong>
                  <div style={tagRowStyle}>
                    {selectedPack.compatibility.compatible_workflow_pack_ids.length === 0 ? (
                      <span style={subtleTextStyle}>No workflow-pack restriction.</span>
                    ) : (
                      selectedPack.compatibility.compatible_workflow_pack_ids.map((workflowId) => (
                        <span key={workflowId} style={tagStyle}>
                          {workflowId}
                        </span>
                      ))
                    )}
                  </div>
                </div>
              </div>
              {selectedPack.metadata.limitations.length > 0 && (
                <div style={notesBlockStyle}>
                  <strong>Limits</strong>
                  {selectedPack.metadata.limitations.map((note) => (
                    <p key={note} style={helperTextStyle}>{note}</p>
                  ))}
                </div>
              )}
              <div style={inlineLinkRowStyle}>
                <Link href={`/cases/${caseId}/submission-drafts`} style={linkStyle}>
                  Submission drafts
                </Link>
                <Link href={`/cases/${caseId}/releases`} style={linkStyle}>
                  Release bundles
                </Link>
              </div>
            </article>
          )}
        </>
      )}
    </section>
  );
}

function formatTimestamp(value: string): string {
  const timestamp = Number.isNaN(Date.parse(value)) ? null : new Date(value);
  return timestamp ? timestamp.toLocaleString() : value;
}

const sectionCardStyle: CSSProperties = {
  backgroundColor: "#ffffff",
  border: "1px solid #d7dee8",
  borderRadius: "18px",
  padding: "1.25rem",
  display: "grid",
  gap: "1rem",
};

const sectionHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "1rem",
  flexWrap: "wrap",
};

const sectionTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.1rem",
  color: "#102033",
};

const helperTextStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  color: "#526173",
  lineHeight: 1.55,
};

const linkStyle: CSSProperties = {
  textDecoration: "none",
  color: "#0d6efd",
  fontWeight: 600,
};

const panelStyle: CSSProperties = {
  borderRadius: "14px",
  backgroundColor: "#f8fafc",
  border: "1px solid #d7dee8",
  padding: "0.9rem 1rem",
  color: "#526173",
};

const messageStyle: CSSProperties = {
  borderRadius: "14px",
  backgroundColor: "#eef6ff",
  border: "1px solid #cfe0ff",
  padding: "0.9rem 1rem",
  color: "#0f4c81",
};

const selectionGridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  alignItems: "end",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.45rem",
};

const labelStyle: CSSProperties = {
  fontSize: "0.82rem",
  fontWeight: 700,
  color: "#475569",
};

const inputStyle: CSSProperties = {
  borderRadius: "12px",
  border: "1px solid #cbd5e1",
  padding: "0.75rem 0.9rem",
  fontSize: "0.95rem",
  backgroundColor: "#ffffff",
  color: "#102033",
};

const actionRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.75rem",
  flexWrap: "wrap",
};

const primaryButtonStyle: CSSProperties = {
  borderRadius: "12px",
  border: "1px solid #0d6efd",
  backgroundColor: "#0d6efd",
  color: "#ffffff",
  padding: "0.75rem 1rem",
  fontWeight: 600,
  cursor: "pointer",
};

const secondaryButtonStyle: CSSProperties = {
  borderRadius: "12px",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  color: "#334155",
  padding: "0.75rem 1rem",
  fontWeight: 600,
  cursor: "pointer",
};

const previewCardStyle: CSSProperties = {
  borderRadius: "16px",
  border: "1px solid #d7dee8",
  backgroundColor: "#f8fafc",
  padding: "1rem",
  display: "grid",
  gap: "0.8rem",
};

const itemHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "flex-start",
  flexWrap: "wrap",
};

const previewTitleStyle: CSSProperties = {
  color: "#102033",
};

const monoTextStyle: CSSProperties = {
  margin: "0.2rem 0 0",
  color: "#0f4c81",
  fontSize: "0.82rem",
  fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace',
};

const badgeStyle: CSSProperties = {
  borderRadius: "999px",
  backgroundColor: "#eef2f7",
  color: "#465569",
  padding: "0.25rem 0.6rem",
  fontSize: "0.75rem",
  fontWeight: 700,
};

const tagRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.5rem",
  flexWrap: "wrap",
};

const tagStyle: CSSProperties = {
  borderRadius: "999px",
  backgroundColor: "#ffffff",
  color: "#465569",
  padding: "0.3rem 0.7rem",
  fontSize: "0.78rem",
  fontWeight: 600,
  border: "1px solid #d7dee8",
};

const subtleTextStyle: CSSProperties = {
  color: "#64748b",
  fontSize: "0.85rem",
};

const detailGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "1rem",
};

const notesBlockStyle: CSSProperties = {
  display: "grid",
  gap: "0.35rem",
};

const inlineLinkRowStyle: CSSProperties = {
  display: "flex",
  gap: "1rem",
  flexWrap: "wrap",
};