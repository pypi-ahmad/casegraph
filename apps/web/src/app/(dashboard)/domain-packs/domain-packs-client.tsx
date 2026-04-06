"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

import type {
  CaseTypeTemplateMetadata,
  DocumentRequirementDefinition,
  DomainPackMetadata,
  ExtractionBindingMetadata,
  WorkflowBindingMetadata,
} from "@casegraph/agent-sdk";

import { fetchDomainPacks, fetchDomainPackDetail } from "@/lib/domains-api";

export default function DomainPackExplorerClient() {
  const [packs, setPacks] = useState<DomainPackMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPackId, setSelectedPackId] = useState<string | null>(null);
  const [selectedCaseTypes, setSelectedCaseTypes] = useState<
    CaseTypeTemplateMetadata[]
  >([]);
  const [expandedCaseType, setExpandedCaseType] = useState<string | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchDomainPacks()
      .then((resp) => {
        if (!cancelled) setPacks(resp.packs);
      })
      .catch((err) => {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Unable to load domain packs."
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  function handleSelectPack(packId: string) {
    if (selectedPackId === packId) {
      setSelectedPackId(null);
      setSelectedCaseTypes([]);
      setExpandedCaseType(null);
      return;
    }

    setSelectedPackId(packId);
    setLoadingDetail(true);
    setExpandedCaseType(null);

    fetchDomainPackDetail(packId)
      .then((resp) => {
        setSelectedCaseTypes(resp.pack.case_types);
      })
      .catch(() => {
        setSelectedCaseTypes([]);
      })
      .finally(() => setLoadingDetail(false));
  }

  if (loading) {
    return (
      <main style={pageStyle}>
        <section style={containerStyle}>
          <div style={panelStyle}>Loading domain packs...</div>
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main style={pageStyle}>
        <section style={containerStyle}>
          <div style={errorPanelStyle}>{error}</div>
        </section>
      </main>
    );
  }

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <header style={{ marginBottom: "1.5rem" }}>
          <p style={breadcrumbStyle}>Platform</p>
          <h1 style={titleStyle}>Domain Packs</h1>
          <p style={subtitleStyle}>
            Browse registered domain packs, case type templates, workflow
            bindings, extraction bindings, and document requirements across
            jurisdictions. This is a structured operational metadata layer —
            not a rules engine or compliance system.
          </p>
        </header>

        {/* Pack list */}
        <div style={packGridStyle}>
          {packs.map((pack) => (
            <PackCard
              key={pack.pack_id}
              pack={pack}
              selected={selectedPackId === pack.pack_id}
              onSelect={() => handleSelectPack(pack.pack_id)}
            />
          ))}
        </div>

        {/* Case types for selected pack */}
        {selectedPackId && (
          <section style={{ marginTop: "1.5rem" }}>
            <h2 style={sectionTitleStyle}>
              Case Types —{" "}
              {packs.find((p) => p.pack_id === selectedPackId)?.display_name}
            </h2>
            {loadingDetail ? (
              <div style={panelStyle}>Loading case types...</div>
            ) : selectedCaseTypes.length === 0 ? (
              <div style={panelStyle}>No case types registered.</div>
            ) : (
              <div style={caseTypeListStyle}>
                {selectedCaseTypes.map((ct) => (
                  <CaseTypeCard
                    key={ct.case_type_id}
                    caseType={ct}
                    expanded={expandedCaseType === ct.case_type_id}
                    onToggle={() =>
                      setExpandedCaseType(
                        expandedCaseType === ct.case_type_id
                          ? null
                          : ct.case_type_id
                      )
                    }
                    packId={selectedPackId}
                  />
                ))}
              </div>
            )}
          </section>
        )}
      </section>
    </main>
  );
}

/* ------------------------------------------------------------------ */
/* Pack card                                                           */
/* ------------------------------------------------------------------ */

function PackCard({
  pack,
  selected,
  onSelect,
}: {
  pack: DomainPackMetadata;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      style={{
        ...packCardStyle,
        borderColor: selected ? "#3b82f6" : "#d7dee8",
        backgroundColor: selected ? "#eff6ff" : "#ffffff",
      }}
    >
      <div style={packHeaderStyle}>
        <span style={packNameStyle}>{pack.display_name}</span>
        <span style={badgeStyle}>{pack.jurisdiction.toUpperCase()}</span>
      </div>
      <p style={packDescStyle}>{pack.description}</p>
      <div style={packMetaRowStyle}>
        <span style={metaTagStyle}>{pack.domain_category}</span>
        <span style={metaTagStyle}>
          {pack.case_type_count} case type
          {pack.case_type_count !== 1 ? "s" : ""}
        </span>
      </div>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Case type card                                                      */
/* ------------------------------------------------------------------ */

function CaseTypeCard({
  caseType,
  expanded,
  onToggle,
  packId,
}: {
  caseType: CaseTypeTemplateMetadata;
  expanded: boolean;
  onToggle: () => void;
  packId: string;
}) {
  return (
    <article style={caseTypeCardStyle}>
      <button type="button" onClick={onToggle} style={caseTypeHeaderBtn}>
        <div>
          <span style={caseTypeNameStyle}>{caseType.display_name}</span>
          <span style={caseTypeIdStyle}>{caseType.case_type_id}</span>
        </div>
        <span style={caretStyle}>{expanded ? "▾" : "▸"}</span>
      </button>
      <p style={caseTypeDescStyle}>{caseType.description}</p>

      {expanded && (
        <div style={expandedPanelStyle}>
          {/* Stages */}
          {caseType.typical_stages.length > 0 && (
            <div style={subSectionStyle}>
              <strong>Typical Stages:</strong>
              <div style={tagRowStyle}>
                {caseType.typical_stages.map((s) => (
                  <span key={s} style={stageTagStyle}>
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Workflow bindings */}
          {caseType.workflow_bindings.length > 0 && (
            <div style={subSectionStyle}>
              <strong>Workflow Bindings:</strong>
              {caseType.workflow_bindings.map((wb) => (
                <BindingRow key={wb.workflow_id} binding={wb} kind="workflow" />
              ))}
            </div>
          )}

          {/* Extraction bindings */}
          {caseType.extraction_bindings.length > 0 && (
            <div style={subSectionStyle}>
              <strong>Extraction Bindings:</strong>
              {caseType.extraction_bindings.map((eb) => (
                <BindingRow
                  key={eb.extraction_template_id}
                  binding={eb}
                  kind="extraction"
                />
              ))}
            </div>
          )}

          {/* Document requirements */}
          {caseType.document_requirements.length > 0 && (
            <div style={subSectionStyle}>
              <strong>Document Requirements:</strong>
              {caseType.document_requirements.map((req) => (
                <RequirementRow key={req.requirement_id} requirement={req} />
              ))}
            </div>
          )}

          {/* Create case link */}
          <div style={{ marginTop: "0.75rem" }}>
            <Link
              href={`/cases/new?domain_pack_id=${packId}&case_type_id=${caseType.case_type_id}`}
              style={linkBtnStyle}
            >
              Create Case from this Template →
            </Link>
          </div>
        </div>
      )}
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* Sub-components                                                      */
/* ------------------------------------------------------------------ */

function BindingRow({
  binding,
  kind,
}: {
  binding: WorkflowBindingMetadata | ExtractionBindingMetadata;
  kind: "workflow" | "extraction";
}) {
  const id =
    kind === "workflow"
      ? (binding as WorkflowBindingMetadata).workflow_id
      : (binding as ExtractionBindingMetadata).extraction_template_id;
  return (
    <div style={bindingRowStyle}>
      <span style={bindingIdStyle}>{id}</span>
      <span style={bindingNameStyle}>{binding.display_name}</span>
      {binding.binding_notes && (
        <span style={bindingNotesStyle}>{binding.binding_notes}</span>
      )}
    </div>
  );
}

function RequirementRow({
  requirement,
}: {
  requirement: DocumentRequirementDefinition;
}) {
  return (
    <div style={reqRowStyle}>
      <div style={reqHeaderStyle}>
        <span style={reqNameStyle}>{requirement.display_name}</span>
        <span
          style={{
            ...priorityBadgeStyle,
            backgroundColor:
              requirement.priority === "required"
                ? "#dcfce7"
                : requirement.priority === "recommended"
                  ? "#fef9c3"
                  : "#f1f5f9",
            color:
              requirement.priority === "required"
                ? "#166534"
                : requirement.priority === "recommended"
                  ? "#854d0e"
                  : "#64748b",
          }}
        >
          {requirement.priority}
        </span>
        <span style={reqCatStyle}>{requirement.document_category}</span>
      </div>
      {requirement.description && (
        <p style={reqDescStyle}>{requirement.description}</p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Styles                                                              */
/* ------------------------------------------------------------------ */

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "2.5rem 1.25rem 3rem",
  backgroundColor: "#f5f7fa",
};

const containerStyle: CSSProperties = {
  maxWidth: "1100px",
  margin: "0 auto",
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
  maxWidth: "780px",
  color: "#55657a",
  lineHeight: 1.6,
};

const panelStyle: CSSProperties = {
  padding: "1rem 1.25rem",
  border: "1px solid #d7dee8",
  borderRadius: "12px",
  backgroundColor: "#f8fafc",
  color: "#334155",
};

const errorPanelStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  border: "1px solid #ef4444",
  borderRadius: "12px",
  backgroundColor: "#fff1f2",
  color: "#991b1b",
};

const sectionTitleStyle: CSSProperties = {
  margin: "0 0 1rem",
  fontSize: "1.05rem",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "#475569",
};

const packGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
  gap: "1rem",
};

const packCardStyle: CSSProperties = {
  padding: "1rem 1.25rem",
  border: "2px solid #d7dee8",
  borderRadius: "14px",
  backgroundColor: "#ffffff",
  cursor: "pointer",
  textAlign: "left",
  width: "100%",
  transition: "border-color 0.15s",
};

const packHeaderStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "0.5rem",
};

const packNameStyle: CSSProperties = {
  fontWeight: 700,
  fontSize: "1.05rem",
  color: "#102033",
};

const badgeStyle: CSSProperties = {
  padding: "0.15rem 0.5rem",
  borderRadius: "6px",
  fontSize: "0.72rem",
  fontWeight: 700,
  backgroundColor: "#e0edff",
  color: "#1e40af",
};

const packDescStyle: CSSProperties = {
  margin: "0.5rem 0",
  color: "#55657a",
  fontSize: "0.88rem",
  lineHeight: 1.5,
};

const packMetaRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.5rem",
  flexWrap: "wrap",
};

const metaTagStyle: CSSProperties = {
  padding: "0.15rem 0.5rem",
  borderRadius: "6px",
  fontSize: "0.72rem",
  fontWeight: 600,
  backgroundColor: "#f1f5f9",
  color: "#475569",
};

const caseTypeListStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.75rem",
};

const caseTypeCardStyle: CSSProperties = {
  padding: "1rem 1.25rem",
  border: "1px solid #d7dee8",
  borderRadius: "14px",
  backgroundColor: "#ffffff",
};

const caseTypeHeaderBtn: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  width: "100%",
  background: "none",
  border: "none",
  cursor: "pointer",
  padding: 0,
  textAlign: "left",
};

const caseTypeNameStyle: CSSProperties = {
  fontWeight: 700,
  fontSize: "1rem",
  color: "#102033",
  display: "block",
};

const caseTypeIdStyle: CSSProperties = {
  fontSize: "0.78rem",
  color: "#64748b",
  fontFamily: "monospace",
};

const caseTypeDescStyle: CSSProperties = {
  margin: "0.4rem 0 0",
  color: "#55657a",
  fontSize: "0.88rem",
  lineHeight: 1.5,
};

const caretStyle: CSSProperties = {
  fontSize: "1.1rem",
  color: "#94a3b8",
};

const expandedPanelStyle: CSSProperties = {
  marginTop: "0.75rem",
  paddingTop: "0.75rem",
  borderTop: "1px solid #e2e8f0",
};

const subSectionStyle: CSSProperties = {
  marginBottom: "0.75rem",
};

const tagRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.35rem",
  flexWrap: "wrap",
  marginTop: "0.35rem",
};

const stageTagStyle: CSSProperties = {
  padding: "0.15rem 0.45rem",
  borderRadius: "5px",
  fontSize: "0.72rem",
  fontWeight: 600,
  backgroundColor: "#f1f5f9",
  color: "#334155",
};

const bindingRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.5rem",
  alignItems: "center",
  flexWrap: "wrap",
  padding: "0.3rem 0",
};

const bindingIdStyle: CSSProperties = {
  fontFamily: "monospace",
  fontSize: "0.78rem",
  color: "#3b82f6",
};

const bindingNameStyle: CSSProperties = {
  fontSize: "0.88rem",
  color: "#102033",
};

const bindingNotesStyle: CSSProperties = {
  fontSize: "0.78rem",
  color: "#94a3b8",
};

const reqRowStyle: CSSProperties = {
  padding: "0.35rem 0",
  borderBottom: "1px solid #f1f5f9",
};

const reqHeaderStyle: CSSProperties = {
  display: "flex",
  gap: "0.5rem",
  alignItems: "center",
  flexWrap: "wrap",
};

const reqNameStyle: CSSProperties = {
  fontWeight: 600,
  fontSize: "0.88rem",
  color: "#102033",
};

const priorityBadgeStyle: CSSProperties = {
  padding: "0.1rem 0.4rem",
  borderRadius: "5px",
  fontSize: "0.7rem",
  fontWeight: 700,
};

const reqCatStyle: CSSProperties = {
  fontSize: "0.72rem",
  color: "#64748b",
  fontFamily: "monospace",
};

const reqDescStyle: CSSProperties = {
  margin: "0.2rem 0 0",
  fontSize: "0.82rem",
  color: "#55657a",
};

const linkBtnStyle: CSSProperties = {
  display: "inline-block",
  padding: "0.5rem 1rem",
  borderRadius: "8px",
  fontSize: "0.85rem",
  fontWeight: 600,
  color: "#1e40af",
  backgroundColor: "#eff6ff",
  border: "1px solid #bfdbfe",
  textDecoration: "none",
};
