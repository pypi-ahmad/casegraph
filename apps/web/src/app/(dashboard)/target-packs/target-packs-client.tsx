"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";

import type {
  TargetPackCategory,
  TargetPackDetail,
  TargetPackStatus,
  TargetPackSummary,
} from "@casegraph/agent-sdk";

import { fetchTargetPackDetail, fetchTargetPacks } from "@/lib/target-packs-api";

const CATEGORY_OPTIONS: Array<{ value: TargetPackCategory; label: string }> = [
  { value: "payer_prior_auth_pack", label: "Payer prior auth" },
  { value: "insurer_claim_pack", label: "Insurer claim" },
  { value: "insurance_correspondence_pack", label: "Insurance correspondence" },
  { value: "tax_notice_pack", label: "Tax notice" },
  { value: "tax_intake_pack", label: "Tax intake" },
  { value: "generic_form_pack", label: "Generic form" },
];

const STATUS_OPTIONS: Array<{ value: TargetPackStatus; label: string }> = [
  { value: "draft_metadata", label: "Draft metadata" },
  { value: "active_metadata", label: "Active metadata" },
  { value: "superseded", label: "Superseded" },
];

export default function TargetPacksClient() {
  const [packs, setPacks] = useState<TargetPackSummary[]>([]);
  const [selectedPackId, setSelectedPackId] = useState<string | null>(null);
  const [selectedPack, setSelectedPack] = useState<TargetPackDetail | null>(null);
  const [category, setCategory] = useState<TargetPackCategory | "">("");
  const [status, setStatus] = useState<TargetPackStatus | "">("");
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchTargetPacks({
      category: category || null,
      status: status || null,
    })
      .then((response) => {
        if (cancelled) return;
        setPacks(response.packs);
        setSelectedPackId((current) => {
          if (current && response.packs.some((pack) => pack.metadata.pack_id === current)) {
            return current;
          }
          return response.packs[0]?.metadata.pack_id ?? null;
        });
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to load target packs.");
          setPacks([]);
          setSelectedPackId(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [category, status]);

  useEffect(() => {
    let cancelled = false;
    if (!selectedPackId) {
      setSelectedPack(null);
      return () => {
        cancelled = true;
      };
    }

    setLoadingDetail(true);
    setError(null);
    fetchTargetPackDetail(selectedPackId)
      .then((response) => {
        if (!cancelled) setSelectedPack(response.pack);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to load target-pack detail.");
          setSelectedPack(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingDetail(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedPackId]);

  const selectedSummary = useMemo(
    () => packs.find((pack) => pack.metadata.pack_id === selectedPackId) ?? null,
    [packs, selectedPackId],
  );

  if (loading) {
    return (
      <main style={pageStyle}>
        <section style={containerStyle}>
          <div style={panelStyle}>Loading target-pack explorer...</div>
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
        <header style={headerStyle}>
          <div>
            <p style={breadcrumbStyle}>Platform</p>
            <h1 style={titleStyle}>Target Packs</h1>
            <p style={subtitleStyle}>
              Browse versioned target-pack metadata for destination-specific field schemas,
              requirement overlays, template bindings, and explicit compatibility. Selection
              remains case-scoped and descriptive only.
            </p>
          </div>
          <div style={linkRowStyle}>
            <Link href="/domain-packs" style={secondaryLinkStyle}>
              Domain packs
            </Link>
            <Link href="/cases" style={secondaryLinkStyle}>
              Cases
            </Link>
          </div>
        </header>

        <section style={filterPanelStyle}>
          <label style={filterFieldStyle}>
            <span style={labelStyle}>Category</span>
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value as TargetPackCategory | "")}
              style={inputStyle}
            >
              <option value="">All categories</option>
              {CATEGORY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label style={filterFieldStyle}>
            <span style={labelStyle}>Status</span>
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value as TargetPackStatus | "")}
              style={inputStyle}
            >
              <option value="">All statuses</option>
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <div style={statCardStyle}>
            <span style={statLabelStyle}>Visible packs</span>
            <strong style={statValueStyle}>{packs.length}</strong>
          </div>
        </section>

        <div style={workspaceStyle}>
          <aside style={listPanelStyle}>
            <h2 style={sectionTitleStyle}>Registry</h2>
            {packs.length === 0 ? (
              <div style={panelStyle}>No target packs match the current filters.</div>
            ) : (
              <div style={listStyle}>
                {packs.map((pack) => (
                  <button
                    key={pack.metadata.pack_id}
                    type="button"
                    onClick={() => setSelectedPackId(pack.metadata.pack_id)}
                    style={{
                      ...packCardStyle,
                      borderColor:
                        pack.metadata.pack_id === selectedPackId ? "#0d6efd" : "#d6dee9",
                      backgroundColor:
                        pack.metadata.pack_id === selectedPackId ? "#eff6ff" : "#ffffff",
                    }}
                  >
                    <div style={itemHeaderStyle}>
                      <strong style={packNameStyle}>{pack.metadata.display_name}</strong>
                      <span style={statusBadge(pack.metadata.status)}>
                        {formatStatus(pack.metadata.status)}
                      </span>
                    </div>
                    <p style={packIdStyle}>
                      {pack.metadata.pack_id} · v{pack.metadata.version}
                    </p>
                    <p style={packDescStyle}>{pack.metadata.description}</p>
                    <div style={tagRowStyle}>
                      <span style={tagStyle}>{formatCategory(pack.metadata.category)}</span>
                      <span style={tagStyle}>{pack.metadata.organization.display_name}</span>
                      <span style={tagStyle}>{pack.field_count} mapped fields</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </aside>

          <section style={detailPanelStyle}>
            {!selectedPackId ? (
              <div style={panelStyle}>Select a target pack to inspect compatibility and field schema.</div>
            ) : loadingDetail ? (
              <div style={panelStyle}>Loading target-pack detail...</div>
            ) : !selectedPack || !selectedSummary ? (
              <div style={panelStyle}>Target-pack detail is unavailable.</div>
            ) : (
              <>
                <div style={detailHeaderStyle}>
                  <div>
                    <p style={breadcrumbStyle}>Versioned Registry Entry</p>
                    <h2 style={detailTitleStyle}>{selectedPack.metadata.display_name}</h2>
                    <p style={subtitleStyle}>{selectedPack.metadata.description}</p>
                  </div>
                  <div style={tagRowStyle}>
                    <span style={tagStyle}>{selectedPack.metadata.pack_id}</span>
                    <span style={tagStyle}>v{selectedPack.metadata.version}</span>
                    <span style={tagStyle}>{formatStatus(selectedPack.metadata.status)}</span>
                  </div>
                </div>

                <div style={detailGridStyle}>
                  <article style={cardStyle}>
                    <h3 style={cardTitleStyle}>Organization</h3>
                    <p style={itemMetaStyle}>{selectedPack.metadata.organization.display_name}</p>
                    <p style={monoTextStyle}>{selectedPack.metadata.organization.organization_id}</p>
                    <p style={itemMetaStyle}>{selectedPack.metadata.organization.description}</p>
                    {selectedPack.metadata.organization.notes.length > 0 && (
                      <div style={bulletListStyle}>
                        {selectedPack.metadata.organization.notes.map((note) => (
                          <p key={note} style={listItemStyle}>{note}</p>
                        ))}
                      </div>
                    )}
                  </article>

                  <article style={cardStyle}>
                    <h3 style={cardTitleStyle}>Compatibility</h3>
                    <DetailList
                      label="Domain packs"
                      values={selectedPack.compatibility.compatible_domain_pack_ids}
                    />
                    <DetailList
                      label="Case types"
                      values={selectedPack.compatibility.compatible_case_type_ids}
                    />
                    <DetailList
                      label="Workflow packs"
                      values={selectedPack.compatibility.compatible_workflow_pack_ids}
                    />
                    <DetailList
                      label="Submission targets"
                      values={selectedPack.submission_compatibility.submission_target_ids}
                    />
                    <DetailList label="Compatibility notes" values={selectedPack.compatibility.notes} />
                  </article>

                  <article style={cardStyle}>
                    <h3 style={cardTitleStyle}>Automation</h3>
                    <DetailList
                      label="Allowed backends"
                      values={selectedPack.automation_compatibility.supported_backend_ids}
                    />
                    <p style={itemMetaStyle}>
                      Dry-run planning: {selectedPack.automation_compatibility.supports_dry_run_planning ? "supported" : "not supported"}
                    </p>
                    <p style={itemMetaStyle}>
                      Live execution: {selectedPack.automation_compatibility.supports_live_execution ? "supported" : "not supported"}
                    </p>
                    <DetailList
                      label="Automation notes"
                      values={selectedPack.automation_compatibility.notes}
                    />
                  </article>
                </div>

                <article style={sectionCardStyle}>
                  <div style={sectionHeaderStyle}>
                    <h3 style={sectionTitleStyle}>Target Field Schema</h3>
                    <span style={tagStyle}>{selectedSummary.field_count} total fields</span>
                  </div>
                  {selectedPack.field_schema.notes.length > 0 && (
                    <div style={inlineNoteStyle}>
                      {selectedPack.field_schema.notes.join(" ")}
                    </div>
                  )}
                  <div style={schemaGridStyle}>
                    {selectedPack.field_schema.sections.map((section) => (
                      <article key={section.section_id} style={schemaSectionStyle}>
                        <div style={itemHeaderStyle}>
                          <strong>{section.display_name}</strong>
                          <span style={subtleBadgeStyle}>{section.section_id}</span>
                        </div>
                        <p style={itemMetaStyle}>{section.description}</p>
                        <div style={fieldListStyle}>
                          {section.fields.map((field) => (
                            <article key={field.field_id} style={fieldCardStyle}>
                              <div style={itemHeaderStyle}>
                                <strong>{field.display_name}</strong>
                                <span style={subtleBadgeStyle}>{field.field_type}</span>
                              </div>
                              <p style={monoTextStyle}>{field.field_id}</p>
                              <p style={itemMetaStyle}>{field.description}</p>
                              <p style={itemMetaStyle}>
                                {field.required ? "Required" : "Optional"}
                              </p>
                              <DetailList
                                label="Candidate source paths"
                                values={field.candidate_source_paths}
                                compact
                              />
                              <DetailList label="Field notes" values={field.notes} compact />
                            </article>
                          ))}
                        </div>
                      </article>
                    ))}
                  </div>
                </article>

                <div style={detailGridStyle}>
                  <article style={sectionCardStyle}>
                    <h3 style={sectionTitleStyle}>Requirement Overrides</h3>
                    {selectedPack.requirement_overrides.length === 0 ? (
                      <div style={panelStyle}>No target-specific requirement overlays are registered.</div>
                    ) : (
                      <div style={stackStyle}>
                        {selectedPack.requirement_overrides.map((requirement) => (
                          <article key={requirement.override_id} style={itemCardStyle}>
                            <div style={itemHeaderStyle}>
                              <strong>{requirement.display_name}</strong>
                              <span style={subtleBadgeStyle}>{requirement.mode}</span>
                            </div>
                            <p style={monoTextStyle}>{requirement.override_id}</p>
                            <p style={itemMetaStyle}>{requirement.description}</p>
                            <div style={tagRowStyle}>
                              <span style={tagStyle}>{requirement.document_category}</span>
                              <span style={tagStyle}>{requirement.priority}</span>
                              <span style={tagStyle}>{requirement.requirement_group}</span>
                              {requirement.base_requirement_id && (
                                <span style={tagStyle}>{requirement.base_requirement_id}</span>
                              )}
                            </div>
                            <DetailList label="Notes" values={requirement.notes} compact />
                          </article>
                        ))}
                      </div>
                    )}
                  </article>

                  <article style={sectionCardStyle}>
                    <h3 style={sectionTitleStyle}>Template Bindings</h3>
                    {selectedPack.template_bindings.length === 0 ? (
                      <div style={panelStyle}>No template bindings are registered.</div>
                    ) : (
                      <div style={stackStyle}>
                        {selectedPack.template_bindings.map((binding) => (
                          <article
                            key={`${binding.binding_type}:${binding.template_id}`}
                            style={itemCardStyle}
                          >
                            <div style={itemHeaderStyle}>
                              <strong>{binding.display_name}</strong>
                              <span style={subtleBadgeStyle}>{binding.binding_type}</span>
                            </div>
                            <p style={monoTextStyle}>{binding.template_id}</p>
                            <p style={itemMetaStyle}>{binding.description}</p>
                            <DetailList label="Notes" values={binding.notes} compact />
                          </article>
                        ))}
                      </div>
                    )}
                  </article>
                </div>

                <article style={sectionCardStyle}>
                  <h3 style={sectionTitleStyle}>Registry Notes and Limits</h3>
                  <DetailList label="Pack notes" values={selectedPack.metadata.notes} />
                  <DetailList label="Intentional limitations" values={selectedPack.metadata.limitations} />
                  <p style={inlineNoteStyle}>
                    Select a target pack from an individual case workspace. Downstream submission drafts,
                    automation planning, and reviewed release provenance record only the selected target-pack
                    reference and version, not a frozen copy of the registry entry.
                  </p>
                </article>
              </>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}

function DetailList({
  label,
  values,
  compact = false,
}: {
  label: string;
  values: string[];
  compact?: boolean;
}) {
  if (values.length === 0) {
    return (
      <div style={compact ? compactListBlockStyle : listBlockStyle}>
        <strong>{label}</strong>
        <p style={itemMetaStyle}>None registered.</p>
      </div>
    );
  }

  return (
    <div style={compact ? compactListBlockStyle : listBlockStyle}>
      <strong>{label}</strong>
      <div style={tagRowStyle}>
        {values.map((value) => (
          <span key={`${label}:${value}`} style={tagStyle}>
            {value}
          </span>
        ))}
      </div>
    </div>
  );
}

function formatCategory(category: TargetPackCategory): string {
  return category.replace(/_/g, " ");
}

function formatStatus(status: TargetPackStatus): string {
  return status.replace(/_/g, " ");
}

function statusBadge(status: TargetPackStatus): CSSProperties {
  if (status === "active_metadata") {
    return { ...subtleBadgeStyle, backgroundColor: "#dcfce7", color: "#166534" };
  }
  if (status === "superseded") {
    return { ...subtleBadgeStyle, backgroundColor: "#fee2e2", color: "#991b1b" };
  }
  return { ...subtleBadgeStyle, backgroundColor: "#e0f2fe", color: "#0f4c81" };
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "2.5rem 1.25rem 3rem",
  backgroundColor: "#f5f7fa",
};

const containerStyle: CSSProperties = {
  maxWidth: "1280px",
  margin: "0 auto",
  display: "grid",
  gap: "1.5rem",
};

const headerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "1rem",
  flexWrap: "wrap",
};

const breadcrumbStyle: CSSProperties = {
  margin: 0,
  fontSize: "0.75rem",
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#64748b",
  fontWeight: 700,
};

const titleStyle: CSSProperties = {
  margin: "0.35rem 0 0.5rem",
  fontSize: "2rem",
  lineHeight: 1.1,
  color: "#102033",
};

const detailTitleStyle: CSSProperties = {
  margin: "0.35rem 0 0.5rem",
  fontSize: "1.5rem",
  lineHeight: 1.15,
  color: "#102033",
};

const subtitleStyle: CSSProperties = {
  margin: 0,
  color: "#526173",
  lineHeight: 1.6,
  maxWidth: "76ch",
};

const linkRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.75rem",
  flexWrap: "wrap",
};

const secondaryLinkStyle: CSSProperties = {
  padding: "0.65rem 1rem",
  borderRadius: "999px",
  border: "1px solid #d6dee9",
  backgroundColor: "#ffffff",
  color: "#0f4c81",
  textDecoration: "none",
  fontWeight: 600,
};

const filterPanelStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "1rem",
  padding: "1rem",
  borderRadius: "20px",
  backgroundColor: "#ffffff",
  border: "1px solid #d6dee9",
};

const filterFieldStyle: CSSProperties = {
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

const statCardStyle: CSSProperties = {
  borderRadius: "14px",
  border: "1px solid #d6dee9",
  backgroundColor: "#f8fafc",
  padding: "0.9rem 1rem",
  display: "grid",
  alignContent: "center",
};

const statLabelStyle: CSSProperties = {
  fontSize: "0.8rem",
  color: "#64748b",
};

const statValueStyle: CSSProperties = {
  fontSize: "1.5rem",
  color: "#102033",
};

const workspaceStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: "1.5rem",
  alignItems: "start",
};

const listPanelStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
};

const detailPanelStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
};

const sectionCardStyle: CSSProperties = {
  borderRadius: "20px",
  border: "1px solid #d6dee9",
  backgroundColor: "#ffffff",
  padding: "1.1rem 1.2rem",
  display: "grid",
  gap: "1rem",
};

const panelStyle: CSSProperties = {
  borderRadius: "18px",
  border: "1px solid #d6dee9",
  backgroundColor: "#ffffff",
  padding: "1rem 1.1rem",
  color: "#475569",
};

const errorPanelStyle: CSSProperties = {
  ...panelStyle,
  borderColor: "#fecaca",
  backgroundColor: "#fff7f7",
  color: "#991b1b",
};

const sectionTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.05rem",
  color: "#102033",
};

const listStyle: CSSProperties = {
  display: "grid",
  gap: "0.85rem",
};

const packCardStyle: CSSProperties = {
  borderRadius: "18px",
  border: "1px solid #d6dee9",
  backgroundColor: "#ffffff",
  padding: "1rem",
  textAlign: "left",
  cursor: "pointer",
  display: "grid",
  gap: "0.65rem",
};

const itemHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "flex-start",
  flexWrap: "wrap",
};

const packNameStyle: CSSProperties = {
  color: "#102033",
};

const packIdStyle: CSSProperties = {
  margin: 0,
  color: "#0f4c81",
  fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace',
  fontSize: "0.8rem",
};

const packDescStyle: CSSProperties = {
  margin: 0,
  color: "#526173",
  lineHeight: 1.5,
};

const tagRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.5rem",
  flexWrap: "wrap",
};

const tagStyle: CSSProperties = {
  borderRadius: "999px",
  backgroundColor: "#eef2f7",
  color: "#465569",
  padding: "0.3rem 0.7rem",
  fontSize: "0.78rem",
  fontWeight: 600,
};

const subtleBadgeStyle: CSSProperties = {
  borderRadius: "999px",
  backgroundColor: "#eef2f7",
  color: "#465569",
  padding: "0.25rem 0.6rem",
  fontSize: "0.75rem",
  fontWeight: 700,
};

const detailHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "flex-start",
  flexWrap: "wrap",
  padding: "1.2rem",
  borderRadius: "20px",
  border: "1px solid #d6dee9",
  backgroundColor: "#ffffff",
};

const detailGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "1rem",
};

const cardStyle: CSSProperties = {
  borderRadius: "18px",
  border: "1px solid #d6dee9",
  backgroundColor: "#ffffff",
  padding: "1rem",
  display: "grid",
  gap: "0.75rem",
};

const cardTitleStyle: CSSProperties = {
  margin: 0,
  color: "#102033",
  fontSize: "0.98rem",
};

const listBlockStyle: CSSProperties = {
  display: "grid",
  gap: "0.55rem",
};

const compactListBlockStyle: CSSProperties = {
  display: "grid",
  gap: "0.45rem",
};

const itemMetaStyle: CSSProperties = {
  margin: 0,
  color: "#526173",
  lineHeight: 1.5,
};

const monoTextStyle: CSSProperties = {
  margin: 0,
  color: "#0f4c81",
  fontSize: "0.82rem",
  fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace',
};

const bulletListStyle: CSSProperties = {
  display: "grid",
  gap: "0.4rem",
};

const listItemStyle: CSSProperties = {
  margin: 0,
  color: "#526173",
  lineHeight: 1.5,
};

const sectionHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  alignItems: "center",
  flexWrap: "wrap",
};

const inlineNoteStyle: CSSProperties = {
  borderRadius: "14px",
  backgroundColor: "#f8fafc",
  color: "#526173",
  padding: "0.85rem 0.9rem",
  lineHeight: 1.55,
};

const schemaGridStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
};

const schemaSectionStyle: CSSProperties = {
  borderRadius: "18px",
  border: "1px solid #d6dee9",
  backgroundColor: "#f8fafc",
  padding: "1rem",
  display: "grid",
  gap: "0.85rem",
};

const fieldListStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "0.75rem",
};

const fieldCardStyle: CSSProperties = {
  borderRadius: "16px",
  border: "1px solid #d6dee9",
  backgroundColor: "#ffffff",
  padding: "0.85rem",
  display: "grid",
  gap: "0.55rem",
};

const stackStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const itemCardStyle: CSSProperties = {
  borderRadius: "16px",
  border: "1px solid #d6dee9",
  backgroundColor: "#f8fafc",
  padding: "0.9rem",
  display: "grid",
  gap: "0.55rem",
};