"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import type {
  CaseDetailResponse,
  CaseTypeDetailResponse,
  CaseStatus,
  IngestionResultSummary,
  SessionUser,
} from "@casegraph/agent-sdk";
import type { WorkflowDefinition } from "@casegraph/workflows";

import {
  createWorkflowRunRecord,
  fetchCaseDetail,
  fetchPersistedDocuments,
  linkCaseDocument,
  updateCase,
} from "@/lib/cases-api";
import { fetchCaseTypeDetail } from "@/lib/domains-api";
import { fetchWorkflows } from "@/lib/runtime-api";

import CaseTargetPackSection from "./case-target-pack-section";
import CaseWorkManagementSection from "./case-work-management-section";
import PlatformFlowMap from "@/components/platform-flow-map";

type EditableCaseStatus = CaseStatus;

export default function CaseDetailClient({
  caseId,
  currentUser,
}: {
  caseId: string;
  currentUser: SessionUser;
}) {
  const [detail, setDetail] = useState<CaseDetailResponse | null>(null);
  const [domainTemplate, setDomainTemplate] =
    useState<CaseTypeDetailResponse | null>(null);
  const [documents, setDocuments] = useState<IngestionResultSummary[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [summary, setSummary] = useState("");
  const [status, setStatus] = useState<EditableCaseStatus>("open");
  const [workflowId, setWorkflowId] = useState("");
  const [documentToLink, setDocumentToLink] = useState("");
  const [runWorkflowId, setRunWorkflowId] = useState("");
  const [runNotes, setRunNotes] = useState("");
  const [selectedRunDocuments, setSelectedRunDocuments] = useState<string[]>([]);
  const [formMessage, setFormMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [caseDetail, persistedDocuments, workflowResponse] = await Promise.all([
        fetchCaseDetail(caseId),
        fetchPersistedDocuments({ limit: 100 }),
        fetchWorkflows(),
      ]);
      let nextDomainTemplate: CaseTypeDetailResponse | null = null;

      if (caseDetail.case.domain_context?.case_type_id) {
        try {
          nextDomainTemplate = await fetchCaseTypeDetail(
            caseDetail.case.domain_context.case_type_id,
          );
        } catch {
          nextDomainTemplate = null;
        }
      }

      setDetail(caseDetail);
      setDomainTemplate(nextDomainTemplate);
      setDocuments(persistedDocuments.documents);
      setWorkflows(workflowResponse.workflows);
      setTitle(caseDetail.case.title);
      setCategory(caseDetail.case.category ?? "");
      setSummary(caseDetail.case.summary ?? "");
      setStatus(caseDetail.case.status);
      setWorkflowId(caseDetail.case.workflow_binding?.workflow_id ?? "");
      setRunWorkflowId(
        caseDetail.case.workflow_binding?.workflow_id ?? workflowResponse.workflows[0]?.id ?? "",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load case workspace. Try refreshing the page.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [caseId]);

  const linkableDocuments = useMemo(() => {
    if (!detail) return [];
    const linkedIds = new Set(detail.documents.map((item) => item.document_id));
    return documents.filter(
      (item) => item.status === "completed" && !linkedIds.has(item.document_id),
    );
  }, [detail, documents]);

  async function handleCaseUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail) return;
    setSubmitting(true);
    setFormMessage(null);
    try {
      const updated = await updateCase(detail.case.case_id, {
        title: title.trim(),
        category: category.trim() || null,
        summary: summary.trim() || null,
        status,
        workflow_id: workflowId || null,
      });
      setDetail((current) =>
        current
          ? {
              ...current,
              case: updated,
            }
          : current,
      );
      setFormMessage("Case metadata updated.");
    } catch (err) {
      setFormMessage(err instanceof Error ? err.message : "Unable to update case.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLinkDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail || !documentToLink) return;
    setSubmitting(true);
    setFormMessage(null);
    try {
      await linkCaseDocument(detail.case.case_id, { document_id: documentToLink });
      setDocumentToLink("");
      await load();
      setFormMessage("Document linked to case.");
    } catch (err) {
      setFormMessage(err instanceof Error ? err.message : "Unable to link document.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCreateRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail || !runWorkflowId) return;
    setSubmitting(true);
    setFormMessage(null);
    try {
      await createWorkflowRunRecord(detail.case.case_id, {
        workflow_id: runWorkflowId,
        input_references: [],
        linked_document_ids: selectedRunDocuments,
        notes: runNotes.trim() || null,
      });
      setRunNotes("");
      setSelectedRunDocuments([]);
      await load();
      setFormMessage("Run record created.");
    } catch (err) {
      setFormMessage(err instanceof Error ? err.message : "Unable to create run record.");
    } finally {
      setSubmitting(false);
    }
  }

  function toggleRunDocument(documentId: string) {
    setSelectedRunDocuments((current) =>
      current.includes(documentId)
        ? current.filter((item) => item !== documentId)
        : [...current, documentId],
    );
  }

  if (loading) {
    return <main style={pageStyle}><section style={containerStyle}><div style={panelStyle}>Loading case workspace...</div></section></main>;
  }

  if (error || !detail) {
    return <main style={pageStyle}><section style={containerStyle}><div style={errorPanelStyle}>{error ?? "Case not found."}</div></section></main>;
  }

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <Link href="/cases" style={backLinkStyle}>
          Back to cases
        </Link>
        <header style={headerStyle}>
          <div>
            <p style={breadcrumbStyle}>Cases</p>
            <h1 style={titleStyle}>{detail.case.title}</h1>
            <p style={subtitleStyle}>
              Persistent case metadata, linked documents, selected workflow, and tracked run records.
            </p>
            <nav style={caseNavStyle}>
              <div style={navGroupStyle}>
                <span style={navGroupLabelStyle}>Review</span>
                <Link href={`/cases/${caseId}/review`} style={navLinkStyle}>Operator Review</Link>
                <Link href={`/cases/${caseId}/validation`} style={navLinkStyle}>Validation</Link>
                {detail.case.domain_context && (
                  <Link href={`/cases/${caseId}/checklist`} style={navLinkStyle}>Requirements</Link>
                )}
                {detail.case.domain_context && (
                  <Link href={`/cases/${caseId}/workflow-packs`} style={navLinkStyle}>Workflow Pack</Link>
                )}
              </div>
              <div style={navGroupStyle}>
                <span style={navGroupLabelStyle}>Prepare</span>
                <Link href={`/cases/${caseId}/packets`} style={navLinkStyle}>Export</Link>
                <Link href={`/cases/${caseId}/communication-drafts`} style={navLinkStyle}>Communications</Link>
                <Link href={`/cases/${caseId}/submission-drafts`} style={navLinkStyle}>Submissions</Link>
                <Link href={`/cases/${caseId}/handoff`} style={navLinkStyle}>Handoff</Link>
              </div>
              <div style={navGroupStyle}>
                <span style={navGroupLabelStyle}>Finalize</span>
                <Link href={`/cases/${caseId}/releases`} style={navLinkStyle}>Releases</Link>
                <Link href={`/cases/${caseId}/audit`} style={navLinkStyle}>Activity History</Link>
              </div>
              <div style={navGroupStyle}>
                <span style={navGroupLabelStyle}>Navigate</span>
                <Link href="/work" style={navLinkStyle}>Work Board</Link>
                <Link href="/target-packs" style={navLinkStyle}>Target Packs</Link>
              </div>
            </nav>
          </div>
          <span style={statusBadgeStyle}>{detail.case.status.replace(/_/g, " ")}</span>
        </header>

        {formMessage && <div style={panelStyle}>{formMessage}</div>}

        <div style={layoutStyle}>
          <CaseWorkManagementSection caseId={caseId} currentUser={currentUser} />

          <CaseTargetPackSection
            caseId={caseId}
            domainPackId={detail.case.domain_context?.domain_pack_id}
            caseTypeId={detail.case.domain_context?.case_type_id}
            initialSelection={detail.case.target_pack_selection}
          />

          <section style={sectionCardStyle}>
            <h2 style={sectionTitleStyle}>Case Metadata</h2>
            <form onSubmit={handleCaseUpdate} style={formGridStyle}>
              <label style={fieldStyle}>
                <span style={labelStyle}>Title</span>
                <input value={title} onChange={(event) => setTitle(event.target.value)} style={inputStyle} />
              </label>
              <label style={fieldStyle}>
                <span style={labelStyle}>Category</span>
                <input value={category} onChange={(event) => setCategory(event.target.value)} style={inputStyle} />
              </label>
              <label style={fieldStyle}>
                <span style={labelStyle}>Status</span>
                <select value={status} onChange={(event) => setStatus(event.target.value as EditableCaseStatus)} style={inputStyle}>
                  <option value="open">Open</option>
                  <option value="active">Active</option>
                  <option value="on_hold">On hold</option>
                  <option value="closed">Closed</option>
                  <option value="archived">Archived</option>
                </select>
              </label>
              <label style={fieldStyle}>
                <span style={labelStyle}>Workflow Binding</span>
                <select value={workflowId} onChange={(event) => setWorkflowId(event.target.value)} style={inputStyle}>
                  <option value="">No workflow selected</option>
                  {workflows.map((workflow) => (
                    <option key={workflow.id} value={workflow.id}>
                      {workflow.display_name}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ ...fieldStyle, gridColumn: "1 / -1" }}>
                <span style={labelStyle}>Summary</span>
                <textarea value={summary} onChange={(event) => setSummary(event.target.value)} style={textareaStyle} rows={4} />
              </label>
              <div style={metaInfoStyle}>
                Created: {formatTimestamp(detail.case.timestamps.created_at)}
              </div>
              <div style={metaInfoStyle}>
                Updated: {formatTimestamp(detail.case.timestamps.updated_at)}
              </div>
              <div style={actionRowStyle}>
                <button type="submit" style={primaryButtonStyle} disabled={submitting}>
                  Save Changes
                </button>
              </div>
            </form>
            <div style={jsonPanelStyle}>
              <strong>Metadata</strong>
              <pre style={preStyle}>{JSON.stringify(detail.case.metadata, null, 2)}</pre>
            </div>
            {detail.case.domain_context && (
              <div style={{ ...jsonPanelStyle, marginTop: "0.75rem" }}>
                <strong>Domain Context</strong>
                <p style={domainContextNoteStyle}>
                  This case stores domain pack linkage only. The bindings and
                  requirement checklist below are resolved from the current
                  registry metadata and do not represent regulatory decisions,
                  payer rules, or tax advice.
                </p>
                <div style={domainContextGridStyle}>
                  <div style={domainContextFieldStyle}>
                    <span style={domainContextLabelStyle}>Pack</span>
                    <span style={domainContextValueStyle}>
                      {detail.case.domain_context.domain_pack_id}
                    </span>
                  </div>
                  <div style={domainContextFieldStyle}>
                    <span style={domainContextLabelStyle}>Jurisdiction</span>
                    <span style={domainContextValueStyle}>
                      {detail.case.domain_context.jurisdiction}
                    </span>
                  </div>
                  <div style={domainContextFieldStyle}>
                    <span style={domainContextLabelStyle}>Domain Category</span>
                    <span style={domainContextValueStyle}>
                      {detail.case.domain_context.domain_category}
                    </span>
                  </div>
                  <div style={{ ...domainContextFieldStyle, gridColumn: "1 / -1" }}>
                    <span style={domainContextLabelStyle}>Case Type</span>
                    <span style={domainContextValueStyle}>
                      {domainTemplate?.case_type.display_name ??
                        detail.case.domain_context.case_type_id}
                    </span>
                    <span style={monoTextStyle}>
                      {detail.case.domain_context.case_type_id}
                    </span>
                  </div>
                </div>

                {domainTemplate ? (
                  <div style={domainSectionStackStyle}>
                    <div>
                      <strong>Linked Workflows</strong>
                      <div style={domainListStyle}>
                        {domainTemplate.case_type.workflow_bindings.map((binding) => (
                          <article
                            key={binding.workflow_id}
                            style={domainListCardStyle}
                          >
                            <div style={itemHeaderStyle}>
                              <strong>{binding.display_name}</strong>
                              <span style={subtleBadgeStyle}>workflow</span>
                            </div>
                            <p style={monoTextStyle}>{binding.workflow_id}</p>
                            {binding.description && (
                              <p style={itemMetaStyle}>{binding.description}</p>
                            )}
                            {binding.binding_notes && (
                              <p style={itemMetaStyle}>{binding.binding_notes}</p>
                            )}
                          </article>
                        ))}
                      </div>
                    </div>

                    <div>
                      <strong>Linked Extraction Templates</strong>
                      <div style={domainListStyle}>
                        {domainTemplate.case_type.extraction_bindings.map((binding) => (
                          <article
                            key={binding.extraction_template_id}
                            style={domainListCardStyle}
                          >
                            <div style={itemHeaderStyle}>
                              <strong>{binding.display_name}</strong>
                              <span style={subtleBadgeStyle}>extraction</span>
                            </div>
                            <p style={monoTextStyle}>
                              {binding.extraction_template_id}
                            </p>
                            {binding.description && (
                              <p style={itemMetaStyle}>{binding.description}</p>
                            )}
                            {binding.binding_notes && (
                              <p style={itemMetaStyle}>{binding.binding_notes}</p>
                            )}
                          </article>
                        ))}
                      </div>
                    </div>

                    <div>
                      <strong>Document Requirement Checklist</strong>
                      <div style={domainListStyle}>
                        {domainTemplate.case_type.document_requirements.map((requirement) => (
                          <article
                            key={requirement.requirement_id}
                            style={domainListCardStyle}
                          >
                            <div style={itemHeaderStyle}>
                              <strong>{requirement.display_name}</strong>
                              <span style={subtleBadgeStyle}>
                                {requirement.priority}
                              </span>
                            </div>
                            <p style={monoTextStyle}>{requirement.document_category}</p>
                            {requirement.description && (
                              <p style={itemMetaStyle}>{requirement.description}</p>
                            )}
                            {requirement.accepted_extensions.length > 0 && (
                              <p style={itemMetaStyle}>
                                Accepted extensions: {requirement.accepted_extensions.join(", ")}
                              </p>
                            )}
                            {requirement.notes && (
                              <p style={itemMetaStyle}>{requirement.notes}</p>
                            )}
                          </article>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <p style={domainContextNoteStyle}>
                    Linked case-type metadata is currently unavailable from the
                    registry.
                  </p>
                )}
              </div>
            )}
          </section>

          <section style={sectionCardStyle}>
            <h2 style={sectionTitleStyle}>Linked Documents</h2>
            <form onSubmit={handleLinkDocument} style={inlineFormStyle}>
              <select value={documentToLink} onChange={(event) => setDocumentToLink(event.target.value)} style={inputStyle}>
                <option value="">Select an ingested document</option>
                {linkableDocuments.map((item) => (
                  <option key={item.document_id} value={item.document_id}>
                    {item.source_file.filename} ({item.document_id})
                  </option>
                ))}
              </select>
              <button type="submit" style={secondaryButtonStyle} disabled={submitting || !documentToLink}>
                Link Document
              </button>
            </form>
            {detail.documents.length === 0 ? (
              <div style={panelStyle}>No documents linked to this case.</div>
            ) : (
              <div style={stackStyle}>
                {detail.documents.map((item) => (
                  <article key={item.link_id} style={itemCardStyle}>
                    <div style={itemHeaderStyle}>
                      <strong>{item.source_file.filename}</strong>
                      <span style={subtleBadgeStyle}>{item.document_status ?? "unknown"}</span>
                    </div>
                    <p style={monoTextStyle}>{item.document_id}</p>
                    <p style={itemMetaStyle}>Mode: {item.resolved_mode ?? "unknown"}</p>
                    <p style={itemMetaStyle}>Linked: {formatTimestamp(item.linked_at)}</p>
                    {item.document_status === "completed" && (
                      <Link
                        href={`/documents/${item.document_id}`}
                        style={reviewDocLinkStyle}
                      >
                        Open Review →
                      </Link>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>

          <section style={sectionCardStyle}>
            <h2 style={sectionTitleStyle}>Run Records</h2>
            <form onSubmit={handleCreateRun} style={formGridStyle}>
              <label style={fieldStyle}>
                <span style={labelStyle}>Workflow</span>
                <select value={runWorkflowId} onChange={(event) => setRunWorkflowId(event.target.value)} style={inputStyle}>
                  <option value="">Select a workflow</option>
                  {workflows.map((workflow) => (
                    <option key={workflow.id} value={workflow.id}>
                      {workflow.display_name}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ ...fieldStyle, gridColumn: "1 / -1" }}>
                <span style={labelStyle}>Notes</span>
                <textarea value={runNotes} onChange={(event) => setRunNotes(event.target.value)} style={textareaStyle} rows={3} />
              </label>
              <div style={{ gridColumn: "1 / -1" }}>
                <span style={labelStyle}>Linked documents for this run</span>
                {detail.documents.length === 0 ? (
                  <div style={panelStyle}>Link case documents first to attach them to a run record.</div>
                ) : (
                  <div style={checkboxListStyle}>
                    {detail.documents.map((item) => (
                      <label key={item.link_id} style={checkboxItemStyle}>
                        <input
                          type="checkbox"
                          checked={selectedRunDocuments.includes(item.document_id)}
                          onChange={() => toggleRunDocument(item.document_id)}
                        />
                        <span>{item.source_file.filename}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
              <div style={actionRowStyle}>
                <button type="submit" style={primaryButtonStyle} disabled={submitting || !runWorkflowId}>
                  Start Workflow
                </button>
              </div>
            </form>

            {detail.runs.length === 0 ? (
              <div style={panelStyle}>No run records created yet.</div>
            ) : (
              <div style={stackStyle}>
                {detail.runs.map((run) => (
                  <article key={run.run_id} style={itemCardStyle}>
                    <div style={itemHeaderStyle}>
                      <strong>{run.workflow_id}</strong>
                      <span style={subtleBadgeStyle}>{run.status.replace(/_/g, " ")}</span>
                    </div>
                    <p style={monoTextStyle}>{run.run_id}</p>
                    <p style={itemMetaStyle}>Created: {formatTimestamp(run.timestamps.created_at)}</p>
                    <p style={itemMetaStyle}>Linked docs: {run.linked_document_ids.length}</p>
                    {run.notes && <p style={itemMetaStyle}>Notes: {run.notes}</p>}
                  </article>
                ))}
              </div>
            )}
          </section>

          <section style={sectionCardStyle}>
            <h2 style={sectionTitleStyle}>Available Workflows</h2>
            {workflows.length === 0 ? (
              <div style={panelStyle}>Workflow metadata is unavailable.</div>
            ) : (
              <div style={stackStyle}>
                {workflows.map((workflow) => (
                  <article key={workflow.id} style={itemCardStyle}>
                    <div style={itemHeaderStyle}>
                      <strong>{workflow.display_name}</strong>
                      <span style={subtleBadgeStyle}>{workflow.steps.length} steps</span>
                    </div>
                    <p style={monoTextStyle}>{workflow.id}</p>
                    <p style={itemMetaStyle}>{workflow.description}</p>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>

        <PlatformFlowMap caseId={caseId} />
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
  maxWidth: "1120px",
  margin: "0 auto",
};

const headerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
  marginBottom: "1.5rem",
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
  maxWidth: "740px",
  color: "#55657a",
  lineHeight: 1.6,
};

const caseNavStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "1.5rem",
  marginTop: "1rem",
};

const navGroupStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  alignItems: "center",
  gap: "0.35rem",
};

const navGroupLabelStyle: CSSProperties = {
  fontSize: "0.72rem",
  fontWeight: 700,
  textTransform: "uppercase",
  color: "#64748b",
  marginRight: "0.25rem",
  letterSpacing: "0.03em",
};

const navLinkStyle: CSSProperties = {
  fontSize: "0.82rem",
  color: "#0d6efd",
  textDecoration: "none",
  padding: "0.2rem 0.55rem",
  borderRadius: "6px",
  backgroundColor: "#f0f4ff",
  fontWeight: 500,
};

const backLinkStyle: CSSProperties = {
  display: "inline-flex",
  marginBottom: "1rem",
  color: "#102033",
  textDecoration: "none",
  fontWeight: 600,
};

const statusBadgeStyle: CSSProperties = {
  alignSelf: "flex-start",
  padding: "0.3rem 0.7rem",
  borderRadius: "999px",
  backgroundColor: "#e2e8f0",
  color: "#334155",
  fontSize: "0.72rem",
  fontWeight: 600,
  textTransform: "uppercase",
};

const layoutStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
};

const sectionCardStyle: CSSProperties = {
  padding: "1.25rem",
  border: "1px solid #d7dee8",
  borderRadius: "16px",
  backgroundColor: "#ffffff",
};

const sectionTitleStyle: CSSProperties = {
  margin: "0 0 1rem",
  fontSize: "1.15rem",
  color: "#102033",
};

const formGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "1rem",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.5rem",
};

const labelStyle: CSSProperties = {
  fontSize: "0.9rem",
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

const textareaStyle: CSSProperties = {
  ...inputStyle,
  resize: "vertical",
};

const actionRowStyle: CSSProperties = {
  gridColumn: "1 / -1",
  display: "flex",
  justifyContent: "flex-end",
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
};

const errorPanelStyle: CSSProperties = {
  ...panelStyle,
  borderColor: "#ef4444",
  backgroundColor: "#fff1f2",
  color: "#991b1b",
};

const jsonPanelStyle: CSSProperties = {
  marginTop: "1rem",
  padding: "0.9rem 1rem",
  borderRadius: "12px",
  backgroundColor: "#f8fafc",
  border: "1px solid #d7dee8",
};

const preStyle: CSSProperties = {
  margin: "0.75rem 0 0",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
  fontSize: "0.8rem",
  color: "#475569",
};

const domainContextNoteStyle: CSSProperties = {
  margin: "0.75rem 0 0",
  fontSize: "0.85rem",
  color: "#475569",
  lineHeight: 1.5,
};

const domainContextGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "0.75rem",
  marginTop: "0.75rem",
};

const domainContextFieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.25rem",
};

const domainContextLabelStyle: CSSProperties = {
  fontSize: "0.72rem",
  fontWeight: 700,
  color: "#64748b",
  letterSpacing: "0.04em",
  textTransform: "uppercase",
};

const domainContextValueStyle: CSSProperties = {
  fontSize: "0.95rem",
  fontWeight: 600,
  color: "#102033",
};

const domainSectionStackStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  marginTop: "1rem",
};

const domainListStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
  marginTop: "0.5rem",
};

const domainListCardStyle: CSSProperties = {
  padding: "0.85rem 0.95rem",
  borderRadius: "12px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
};

const inlineFormStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) auto",
  gap: "0.75rem",
  marginBottom: "1rem",
};

const stackStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
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

const subtleBadgeStyle: CSSProperties = {
  alignSelf: "flex-start",
  padding: "0.2rem 0.55rem",
  borderRadius: "999px",
  backgroundColor: "#e2e8f0",
  color: "#334155",
  fontSize: "0.72rem",
};

const monoTextStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  fontFamily: "monospace",
  fontSize: "0.76rem",
  color: "#64748b",
  wordBreak: "break-all",
};

const itemMetaStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  fontSize: "0.85rem",
  color: "#475569",
};

const checkboxListStyle: CSSProperties = {
  display: "grid",
  gap: "0.5rem",
  marginTop: "0.5rem",
};

const checkboxItemStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.5rem",
  color: "#334155",
};

const metaInfoStyle: CSSProperties = {
  fontSize: "0.85rem",
  color: "#55657a",
};

const reviewDocLinkStyle: CSSProperties = {
  display: "inline-flex",
  marginTop: "0.4rem",
  color: "#102033",
  fontWeight: 600,
  fontSize: "0.85rem",
  textDecoration: "none",
};