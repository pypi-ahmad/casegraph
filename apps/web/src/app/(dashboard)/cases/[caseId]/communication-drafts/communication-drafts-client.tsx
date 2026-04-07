"use client";

import Link from "next/link";
import AiDisclosureBanner from "@/components/ai-disclosure-banner";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import type {
  CommunicationCopyExportArtifact,
  CommunicationDraftDetailResponse,
  CommunicationDraftStatus,
  CommunicationDraftSummary,
  CommunicationDraftType,
  CommunicationTemplateMetadata,
  PacketSummary,
  SessionUser,
  WorkflowPackRunRecord,
  WorkflowPackRunResponse,
  WorkflowRunRecord,
} from "@casegraph/agent-sdk";

import { fetchCaseDetail } from "@/lib/cases-api";
import { readinessLabel, shortRef, titleCase } from "@/lib/display-labels";
import {
  createCommunicationDraft,
  fetchCommunicationDraftDetail,
  fetchCommunicationDrafts,
  fetchCommunicationTemplates,
  updateCommunicationDraftReview,
} from "@/lib/communications-api";
import { fetchPackets } from "@/lib/packets-api";
import { fetchCaseWorkflowPackRuns } from "@/lib/workflow-packs-api";

type DraftStatusChoice = CommunicationDraftStatus;

const DRAFT_STATUS_LABELS: Record<string, string> = {
  needs_human_review: "Needs Review",
  revised_placeholder: "Revised",
  approved_placeholder: "Approved",
  archived_placeholder: "Archived",
};

function draftStatusLabel(status: string): string {
  return DRAFT_STATUS_LABELS[status] ?? titleCase(status);
}

export default function CommunicationDraftsClient({ caseId, currentUser }: { caseId: string; currentUser: SessionUser }) {
  const searchParams = useSearchParams();
  const [caseTitle, setCaseTitle] = useState("");
  const [workflowRuns, setWorkflowRuns] = useState<WorkflowRunRecord[]>([]);
  const [workflowPackRuns, setWorkflowPackRuns] = useState<WorkflowPackRunRecord[]>([]);
  const [packets, setPackets] = useState<PacketSummary[]>([]);
  const [templates, setTemplates] = useState<CommunicationTemplateMetadata[]>([]);
  const [drafts, setDrafts] = useState<CommunicationDraftSummary[]>([]);
  const [selectedDraft, setSelectedDraft] = useState<CommunicationDraftDetailResponse | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [strategy, setStrategy] = useState<"deterministic_template_only" | "provider_assisted_draft">(
    "deterministic_template_only",
  );
  const [operatorId, setOperatorId] = useState(currentUser.id);
  const [selectedPacketId, setSelectedPacketId] = useState("");
  const [selectedWorkflowRunId, setSelectedWorkflowRunId] = useState("");
  const [selectedWorkflowPackRunId, setSelectedWorkflowPackRunId] = useState("");
  const [includeDocumentEvidence, setIncludeDocumentEvidence] = useState(false);
  const [providerId, setProviderId] = useState("openai");
  const [modelId, setModelId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showProviderFields, setShowProviderFields] = useState(false);
  const [generationNote, setGenerationNote] = useState("");
  const [reviewStatus, setReviewStatus] = useState<DraftStatusChoice>("needs_human_review");
  const [reviewedBy, setReviewedBy] = useState(currentUser.id);
  const [reviewNotes, setReviewNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.template_id === selectedTemplateId) ?? null,
    [selectedTemplateId, templates],
  );

  const requiresProviderFields = strategy === "provider_assisted_draft";
  const prefillKey = searchParams.toString();
  const createDisabled =
    working ||
    !selectedTemplateId ||
    (selectedTemplateId === "packet_cover_note" && !selectedPacketId) ||
    (requiresProviderFields && (!providerId.trim() || !modelId.trim() || !apiKey.trim()));

  async function load(preferredDraftId?: string) {
    setLoading(true);
    setError(null);
    try {
      const [caseDetail, packetResponse, templateResponse, draftResponse, workflowPackRunResponse] =
        await Promise.all([
          fetchCaseDetail(caseId),
          fetchPackets(caseId),
          fetchCommunicationTemplates(),
          fetchCommunicationDrafts(caseId),
          fetchCaseWorkflowPackRuns(caseId),
        ]);

      setCaseTitle(caseDetail.case.title);
      setWorkflowRuns(caseDetail.runs);
      setPackets(packetResponse.packets);
      setTemplates(templateResponse.templates);
      setDrafts(draftResponse.drafts);
      setWorkflowPackRuns(workflowPackRunResponse.map((entry: WorkflowPackRunResponse) => entry.run));

      const requestedTemplateId = searchParams.get("template") ?? "";
      const requestedPacketId = searchParams.get("packetId") ?? "";
      const requestedWorkflowRunId = searchParams.get("workflowRunId") ?? "";
      const requestedWorkflowPackRunId = searchParams.get("workflowPackRunId") ?? "";

      const nextTemplateId =
        (requestedTemplateId && templateResponse.templates.some((template) => template.template_id === requestedTemplateId)
          ? requestedTemplateId
          : selectedTemplateId) || templateResponse.templates[0]?.template_id || "";
      const nextPacketId =
        (requestedPacketId && packetResponse.packets.some((packet) => packet.packet_id === requestedPacketId)
          ? requestedPacketId
          : selectedPacketId) || packetResponse.packets[0]?.packet_id || "";
      const nextWorkflowRunId =
        (requestedWorkflowRunId && caseDetail.runs.some((run) => run.run_id === requestedWorkflowRunId)
          ? requestedWorkflowRunId
          : selectedWorkflowRunId) || caseDetail.runs[0]?.run_id || "";
      const nextWorkflowPackRunId =
        (
          requestedWorkflowPackRunId
          && workflowPackRunResponse.some((entry: WorkflowPackRunResponse) => entry.run.run_id === requestedWorkflowPackRunId)
            ? requestedWorkflowPackRunId
            : selectedWorkflowPackRunId
        ) || workflowPackRunResponse[0]?.run.run_id || "";

      setSelectedTemplateId(nextTemplateId);
      setSelectedPacketId(nextPacketId);
      setSelectedWorkflowRunId(nextWorkflowRunId);
      setSelectedWorkflowPackRunId(nextWorkflowPackRunId);

      const nextDraftId = preferredDraftId ?? draftResponse.drafts[0]?.draft_id;
      if (nextDraftId) {
        setSelectedDraft(await fetchCommunicationDraftDetail(nextDraftId));
      } else {
        setSelectedDraft(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load communication drafts. Try refreshing the page.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [caseId, prefillKey]);

  useEffect(() => {
    if (!selectedDraft) {
      setReviewStatus("needs_human_review");
      setReviewedBy("");
      setReviewNotes("");
      return;
    }
    setReviewStatus(selectedDraft.draft.status);
    setReviewedBy(selectedDraft.draft.review.reviewed_by);
    setReviewNotes(selectedDraft.draft.review.review_notes);
  }, [selectedDraft]);

  async function handleCreateDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWorking(true);
    setMessage(null);
    try {
      const response = await createCommunicationDraft(caseId, {
        template_id: selectedTemplateId,
        strategy,
        operator_id: operatorId.trim(),
        packet_id: selectedPacketId || null,
        workflow_run_id: selectedWorkflowRunId || null,
        workflow_pack_run_id: selectedWorkflowPackRunId || null,
        include_document_evidence: includeDocumentEvidence,
        provider_selection: requiresProviderFields
          ? {
              provider: providerId as never,
              model_id: modelId.trim(),
              api_key: apiKey,
            }
          : null,
        note: generationNote.trim(),
      });
      setGenerationNote("");
      setMessage(response.result.message || "Draft created. Review it below and update the status when ready.");
      await load(response.draft.draft_id);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to create communication draft. Check template selection and provider credentials.");
    } finally {
      setWorking(false);
    }
  }

  async function handleSelectDraft(draftId: string) {
    setWorking(true);
    setMessage(null);
    try {
      setSelectedDraft(await fetchCommunicationDraftDetail(draftId));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to load communication draft detail. Try selecting the draft again.");
    } finally {
      setWorking(false);
    }
  }

  async function handleReviewUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDraft) return;
    setWorking(true);
    setMessage(null);
    try {
      const response = await updateCommunicationDraftReview(selectedDraft.draft.draft_id, {
        status: reviewStatus,
        reviewed_by: reviewedBy.trim(),
        review_notes: reviewNotes.trim(),
      });
      setMessage(response.result.message || "Review status updated.");
      setSelectedDraft(await fetchCommunicationDraftDetail(selectedDraft.draft.draft_id));
      setDrafts(await refreshDraftList(caseId));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to update draft review metadata. Try refreshing and resubmitting.");
    } finally {
      setWorking(false);
    }
  }

  async function handleCopyArtifact(artifact: CommunicationCopyExportArtifact) {
    try {
      await navigator.clipboard.writeText(artifact.content_text);
      setMessage(`${artifact.filename} copied to clipboard.`);
    } catch {
      setMessage("Clipboard copy failed in this browser session.");
    }
  }

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <div style={linkRowStyle}>
          <Link href={`/cases/${caseId}`} style={secondaryLinkStyle}>Case workspace</Link>
          <Link href={`/cases/${caseId}/review`} style={secondaryLinkStyle}>Operator review</Link>
          <Link href={`/cases/${caseId}/workflow-packs`} style={secondaryLinkStyle}>Workflow packs</Link>
          <Link href={`/cases/${caseId}/packets`} style={secondaryLinkStyle}>Packets</Link>
          <Link href={`/cases/${caseId}/submission-drafts`} style={secondaryLinkStyle}>Submission drafts</Link>
        </div>

        <header style={headerStyle}>
          <div>
            <p style={breadcrumbStyle}>Communication Drafts</p>
            <h1 style={titleStyle}>{caseTitle || "Communication Drafts"}</h1>
            <p style={subtitleStyle}>
              Draft and review communications for this case. AI writes the first version; you decide what gets sent.
            </p>
          </div>
        </header>

        <AiDisclosureBanner />

        {message && <div style={panelStyle}>{message}</div>}

        {loading ? (
          <div style={panelStyle}>Loading communication drafts…</div>
        ) : error ? (
          <div style={errorPanelStyle}>{error}</div>
        ) : (
          <>
            <section style={sectionCardStyle}>
              <h2 style={sectionTitleStyle}>Create Communication Draft</h2>
              <form onSubmit={handleCreateDraft} style={formStyle}>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Template</span>
                  <select
                    value={selectedTemplateId}
                    onChange={(event) => setSelectedTemplateId(event.target.value)}
                    style={inputStyle}
                  >
                    <option value="">Select template</option>
                    {templates.map((template) => (
                      <option key={template.template_id} value={template.template_id}>
                        {template.display_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Drafting Approach</span>
                  <select
                    value={strategy}
                    onChange={(event) => setStrategy(event.target.value as typeof strategy)}
                    style={inputStyle}
                  >
                    <option value="deterministic_template_only">Template only (no AI)</option>
                    <option value="provider_assisted_draft">AI-assisted wording</option>
                  </select>
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Operator</span>
                  <input
                    value={currentUser.name || currentUser.email || operatorId}
                    readOnly
                    style={{ ...inputStyle, backgroundColor: "#f8fafc", color: "#475569" }}
                  />
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Export Package</span>
                  <select
                    value={selectedPacketId}
                    onChange={(event) => setSelectedPacketId(event.target.value)}
                    style={inputStyle}
                  >
                    <option value="">Latest export or none</option>
                    {packets.map((packet) => (
                      <option key={packet.packet_id} value={packet.packet_id}>
                        Packet {packets.indexOf(packet) + 1} • {formatTimestamp(packet.generated_at)}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Workflow Run</span>
                  <select
                    value={selectedWorkflowRunId}
                    onChange={(event) => setSelectedWorkflowRunId(event.target.value)}
                    style={inputStyle}
                  >
                    <option value="">Latest run or none</option>
                    {workflowRuns.map((run, idx) => (
                      <option key={run.run_id} value={run.run_id}>
                        Workflow run {idx + 1} • {titleCase(run.status)}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Processing Run</span>
                  <select
                    value={selectedWorkflowPackRunId}
                    onChange={(event) => setSelectedWorkflowPackRunId(event.target.value)}
                    style={inputStyle}
                  >
                    <option value="">Latest processing run or none</option>
                    {workflowPackRuns.map((run, idx) => (
                      <option key={run.run_id} value={run.run_id}>
                        Pack run {idx + 1} • {titleCase(run.status)}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={checkboxFieldStyle}>
                  <input
                    type="checkbox"
                    checked={includeDocumentEvidence}
                    onChange={(event) => setIncludeDocumentEvidence(event.target.checked)}
                  />
                  <span>Attach retrieval evidence when available</span>
                </label>
                <label style={{ ...fieldStyle, minWidth: "280px" }}>
                  <span style={labelStyle}>Note (optional)</span>
                  <input
                    value={generationNote}
                    onChange={(event) => setGenerationNote(event.target.value)}
                    style={inputStyle}
                    placeholder="Tracked but not inserted into draft content"
                  />
                </label>

                <button type="submit" style={primaryButtonStyle} disabled={createDisabled}>
                  {working ? "Working..." : "Create Draft"}
                </button>

                {requiresProviderFields && (
                  <div style={{ flexBasis: "100%", display: "grid", gap: "0.6rem" }}>
                    <button
                      type="button"
                      onClick={() => setShowProviderFields((prev) => !prev)}
                      style={{ background: "none", border: "none", cursor: "pointer", padding: "0.25rem 0 0", fontSize: "0.82rem", color: "#3b82f6", fontWeight: 500, textAlign: "left" }}
                    >
                      {showProviderFields ? "Hide advanced options \u25be" : "Advanced options \u25b8"}
                    </button>
                    {showProviderFields && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.85rem", alignItems: "flex-end" }}>
                        <p style={{ flexBasis: "100%", fontSize: "0.82rem", color: "#64748b", margin: 0 }}>
                          Override the default AI provider for this request. Credentials are not stored.
                        </p>
                        <label style={fieldStyle}>
                          <span style={labelStyle}>Provider</span>
                          <input
                            value={providerId}
                            onChange={(event) => setProviderId(event.target.value)}
                            style={inputStyle}
                            placeholder="openai"
                          />
                        </label>
                        <label style={fieldStyle}>
                          <span style={labelStyle}>Model</span>
                          <input
                            value={modelId}
                            onChange={(event) => setModelId(event.target.value)}
                            style={inputStyle}
                            placeholder="gpt-4.1-mini or similar"
                          />
                        </label>
                        <label style={fieldStyle}>
                          <span style={labelStyle}>API Key</span>
                          <input
                            type="password"
                            value={apiKey}
                            onChange={(event) => setApiKey(event.target.value)}
                            style={inputStyle}
                            autoComplete="off"
                            placeholder="Provider API key"
                          />
                        </label>
                      </div>
                    )}
                  </div>
                )}
              </form>

              {selectedTemplate && (
                <div style={subtlePanelStyle}>
                  <strong>{selectedTemplate.display_name}</strong>
                  <p style={helperTextStyle}>{selectedTemplate.description}</p>
                  <div style={metaGridStyle}>
                    <span>Audience</span><span>{titleCase(selectedTemplate.audience_type)}</span>
                    <span>AI drafting</span><span>{selectedTemplate.provider_assisted_available ? "Available" : "Not available"}</span>
                    <span>Template sections</span><span>{selectedTemplate.uses_deterministic_sections ? "Yes" : "No"}</span>
                  </div>
                  <div style={stackStyle}>
                    {selectedTemplate.required_source_inputs.map((input) => (
                      <div key={input.input_id} style={miniCardStyle}>
                        <strong>{input.display_name}</strong>
                        <p style={metaTextStyle}>{input.description}</p>
                        <p style={metaTextStyle}>Required: {input.required ? "Yes" : "No"}</p>
                      </div>
                    ))}
                    {selectedTemplate.notes.map((note) => (
                      <p key={note} style={metaTextStyle}>{note}</p>
                    ))}
                  </div>
                </div>
              )}
            </section>

            <section style={sectionCardStyle}>
              <h2 style={sectionTitleStyle}>Draft Records</h2>
              {drafts.length === 0 ? (
                <div style={subtlePanelStyle}>No communication drafts yet. Use the form above to generate a draft from a template.</div>
              ) : (
                <div style={stackStyle}>
                  {drafts.map((draft) => (
                    <article
                      key={draft.draft_id}
                      style={{
                        ...itemCardStyle,
                        cursor: "pointer",
                        borderColor:
                          selectedDraft?.draft.draft_id === draft.draft_id ? "#0d6efd" : "#d7dee8",
                      }}
                      onClick={() => handleSelectDraft(draft.draft_id)}
                    >
                      <div style={itemHeaderStyle}>
                        <strong>{labelForDraftType(draft.draft_type)}</strong>
                        <span style={{ ...badgeStyle, backgroundColor: statusColor(draft.status) }}>
                          {draftStatusLabel(draft.status)}
                        </span>
                      </div>
                      <div style={metaGridStyle}>
                        <span>Template</span><span>{draft.template_id}</span>
                        <span>Approach</span><span>{strategyLabel(draft.strategy)}</span>
                        <span>Audience</span><span>{titleCase(draft.audience_type)}</span>
                        <span>Updated</span><span>{formatTimestamp(draft.updated_at)}</span>
                      </div>
                      <p style={metaTextStyle}>{draft.subject}</p>
                    </article>
                  ))}
                </div>
              )}
            </section>

            {selectedDraft && (
              <>
                <section style={sectionCardStyle}>
                  <h2 style={sectionTitleStyle}>Draft Overview</h2>
                  <div style={metaGridStyle}>
                    <span>Title</span><span>{selectedDraft.draft.title}</span>
                    <span>Subject</span><span>{selectedDraft.draft.subject}</span>
                    <span>Status</span><span>{draftStatusLabel(selectedDraft.draft.status)}</span>
                    <span>Template</span><span>{selectedDraft.template?.display_name ?? selectedDraft.draft.template_id}</span>
                    <span>Approach</span><span>{strategyLabel(selectedDraft.draft.strategy)}</span>
                    <span>Documents</span><span>{selectedDraft.draft.source_metadata.linked_document_count}</span>
                    <span>Missing required items</span><span>{selectedDraft.draft.source_metadata.missing_required_item_count}</span>
                    <span>Open actions</span><span>{selectedDraft.draft.source_metadata.open_action_count}</span>
                    <span>Document evidence</span><span>{selectedDraft.draft.source_metadata.includes_document_evidence ? "Included" : "Not included"}</span>
                  </div>
                  {selectedDraft.draft.generation.notes.length > 0 && (
                    <div style={subtlePanelStyle}>
                      {selectedDraft.draft.generation.notes.map((note) => (
                        <p key={note} style={metaTextStyle}>{note}</p>
                      ))}
                    </div>
                  )}
                </section>

                <section style={sectionCardStyle}>
                  <h2 style={sectionTitleStyle}>Draft Content</h2>
                  <div style={stackStyle}>
                    {selectedDraft.draft.sections.map((section) => (
                      <article key={section.section_type} style={itemCardStyle}>
                        <div style={itemHeaderStyle}>
                          <strong>{section.title}</strong>
                          <span style={subtleBadgeStyle}>{titleCase(section.section_type)}</span>
                        </div>
                        {section.body && <p style={itemTextStyle}>{section.body}</p>}
                        {section.bullet_items.length > 0 && (
                          <ul style={bulletListStyle}>
                            {section.bullet_items.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        )}
                        {section.evidence_reference_ids.length > 0 && (
                          <p style={metaTextStyle}>
                            Evidence: {section.evidence_reference_ids.join(", ")}
                          </p>
                        )}
                      </article>
                    ))}
                  </div>
                </section>

                <section style={sectionCardStyle}>
                  <h2 style={sectionTitleStyle}>Source Data</h2>
                  <div style={groundingLayoutStyle}>
                    <div style={groundingColumnStyle}>
                      <strong style={subheadingStyle}>Case Context</strong>
                      <div style={subtlePanelStyle}>
                        <div style={metaGridStyle}>
                          <span>Case status</span><span>{selectedDraft.draft.source_metadata.case_status}</span>
                          <span>Readiness</span><span>{readinessLabel(selectedDraft.draft.source_metadata.readiness_status)}</span>
                          <span>Export package</span><span>{shortRef(selectedDraft.draft.source_metadata.latest_packet_id)}</span>
                          <span>Workflow run</span><span>{shortRef(selectedDraft.draft.source_metadata.workflow_run_id)}</span>
                          <span>Processing run</span><span>{shortRef(selectedDraft.draft.source_metadata.workflow_pack_run_id)}</span>
                        </div>
                        {selectedDraft.draft.source_metadata.notes.map((note) => (
                          <p key={note} style={metaTextStyle}>{note}</p>
                        ))}
                      </div>
                      <strong style={subheadingStyle}>Source References</strong>
                      <div style={stackStyle}>
                        {selectedDraft.draft.source_entities.length === 0 ? (
                          <div style={subtlePanelStyle}>No source references were attached.</div>
                        ) : (
                          selectedDraft.draft.source_entities.map((entity) => (
                            <article key={`${entity.source_entity_type}-${entity.source_entity_id}-${entity.source_path}`} style={miniCardStyle}>
                              <div style={itemHeaderStyle}>
                                <strong>{entity.display_label || entity.source_entity_id || entity.source_entity_type}</strong>
                                <span style={subtleBadgeStyle}>{titleCase(entity.source_entity_type)}</span>
                              </div>
                              <p style={monoMetaStyle}>{entity.source_path || "—"}</p>
                              {entity.notes.map((note) => (
                                <p key={note} style={metaTextStyle}>{note}</p>
                              ))}
                            </article>
                          ))
                        )}
                      </div>
                    </div>

                    <div style={groundingColumnStyle}>
                      <strong style={subheadingStyle}>Supporting Evidence</strong>
                      <div style={stackStyle}>
                        {selectedDraft.draft.evidence_references.length === 0 ? (
                          <div style={subtlePanelStyle}>No supporting evidence was attached.</div>
                        ) : (
                          selectedDraft.draft.evidence_references.map((reference) => (
                            <article key={reference.evidence_id} style={itemCardStyle}>
                              <div style={itemHeaderStyle}>
                                <strong>{reference.label}</strong>
                                <span style={subtleBadgeStyle}>{titleCase(reference.kind)}</span>
                              </div>
                              <p style={itemTextStyle}>{reference.snippet_text || "No snippet text recorded."}</p>
                              <div style={metaGridStyle}>
                                <span>Reference</span><span>{shortRef(reference.evidence_id)}</span>
                                <span>Source type</span><span>{titleCase(reference.source_entity_type)}</span>
                                <span>Source</span><span>{shortRef(reference.source_entity_id)}</span>
                                <span>Document</span><span>{shortRef(reference.source_reference?.document_id)}</span>
                                <span>Page</span><span>{reference.source_reference?.page_number ?? "—"}</span>
                              </div>
                              {reference.notes.map((note) => (
                                <p key={note} style={metaTextStyle}>{note}</p>
                              ))}
                            </article>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </section>

                <section style={sectionCardStyle}>
                  <h2 style={sectionTitleStyle}>Review</h2>
                  <form onSubmit={handleReviewUpdate} style={formStyle}>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Draft Status</span>
                      <select
                        value={reviewStatus}
                        onChange={(event) => setReviewStatus(event.target.value as DraftStatusChoice)}
                        style={inputStyle}
                      >
                        <option value="needs_human_review">Needs Review</option>
                        <option value="revised_placeholder">Revised</option>
                        <option value="approved_placeholder">Approved</option>
                        <option value="archived_placeholder">Archived</option>
                      </select>
                    </label>
                    <label style={fieldStyle}>
                      <span style={labelStyle}>Reviewed By</span>
                      <input
                        value={currentUser.name || currentUser.email || reviewedBy}
                        readOnly
                        style={{ ...inputStyle, backgroundColor: "#f8fafc", color: "#475569" }}
                      />
                    </label>
                    <label style={{ ...fieldStyle, minWidth: "320px" }}>
                      <span style={labelStyle}>Review Notes</span>
                      <input
                        value={reviewNotes}
                        onChange={(event) => setReviewNotes(event.target.value)}
                        style={inputStyle}
                        placeholder="Observed issues, edits, or approval caveats"
                      />
                    </label>
                    <button type="submit" style={primaryButtonStyle} disabled={working}>
                      {working ? "Working..." : "Update Review"}
                    </button>
                  </form>
                </section>

                <section style={sectionCardStyle}>
                  <h2 style={sectionTitleStyle}>Copy / Export</h2>
                  <div style={stackStyle}>
                    {selectedDraft.copy_artifacts.map((artifact) => (
                      <article key={artifact.format} style={itemCardStyle}>
                        <div style={sectionHeaderStyle}>
                          <div>
                            <strong>{artifact.filename}</strong>
                            <p style={metaTextStyle}>{titleCase(artifact.format)}</p>
                          </div>
                          <button
                            type="button"
                            style={primaryButtonStyle}
                            onClick={() => void handleCopyArtifact(artifact)}
                          >
                            Copy
                          </button>
                        </div>
                        <textarea readOnly value={artifact.content_text} style={artifactTextStyle} />
                      </article>
                    ))}
                  </div>
                </section>
              </>
            )}
          </>
        )}
      </section>
    </main>
  );
}

async function refreshDraftList(caseId: string): Promise<CommunicationDraftSummary[]> {
  const response = await fetchCommunicationDrafts(caseId);
  return response.drafts;
}

function labelForDraftType(draftType: CommunicationDraftType): string {
  switch (draftType) {
    case "missing_document_request":
      return "Missing document request";
    case "internal_handoff_note":
      return "Internal handoff note";
    case "packet_cover_note":
      return "Packet cover note";
    default:
      return draftType;
  }
}

function strategyLabel(strategy: string): string {
  switch (strategy) {
    case "deterministic_template_only":
      return "Template only";
    case "provider_assisted_draft":
      return "AI-assisted";
    default:
      return titleCase(strategy);
  }
}

function formatTimestamp(value: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function statusColor(status: string): string {
  switch (status) {
    case "approved_placeholder":
      return "#d5f5dd";
    case "revised_placeholder":
      return "#fff1c2";
    case "archived_placeholder":
      return "#e5e7eb";
    default:
      return "#ffd7d2";
  }
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  background: "linear-gradient(180deg, #f7fafc 0%, #edf2f7 100%)",
  padding: "2rem 1rem 3rem",
};

const containerStyle: CSSProperties = {
  maxWidth: "1180px",
  margin: "0 auto",
  display: "grid",
  gap: "1rem",
};

const linkRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.75rem",
};

const secondaryLinkStyle: CSSProperties = {
  color: "#0f4c81",
  textDecoration: "none",
  fontSize: "0.88rem",
  fontWeight: 600,
};

const headerStyle: CSSProperties = {
  background: "#ffffff",
  border: "1px solid #d7dee8",
  borderRadius: "20px",
  padding: "1.5rem",
};

const breadcrumbStyle: CSSProperties = {
  margin: 0,
  color: "#64748b",
  fontSize: "0.78rem",
  textTransform: "uppercase",
  letterSpacing: "0.08em",
};

const titleStyle: CSSProperties = {
  margin: "0.35rem 0 0.5rem",
  fontSize: "2rem",
  lineHeight: 1.15,
  color: "#0f172a",
};

const subtitleStyle: CSSProperties = {
  margin: 0,
  maxWidth: "880px",
  color: "#475569",
  lineHeight: 1.6,
};

const panelStyle: CSSProperties = {
  background: "#ffffff",
  border: "1px solid #d7dee8",
  borderRadius: "16px",
  padding: "0.95rem 1rem",
  color: "#0f172a",
};

const errorPanelStyle: CSSProperties = {
  ...panelStyle,
  borderColor: "#f5b1aa",
  background: "#fff5f3",
  color: "#7f1d1d",
};

const sectionCardStyle: CSSProperties = {
  background: "#ffffff",
  border: "1px solid #d7dee8",
  borderRadius: "20px",
  padding: "1.25rem",
  display: "grid",
  gap: "1rem",
};

const sectionTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.15rem",
  color: "#0f172a",
};

const formStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.85rem",
  alignItems: "flex-end",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.35rem",
  minWidth: "220px",
  flex: "1 1 220px",
};

const checkboxFieldStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.5rem",
  minHeight: "42px",
  color: "#334155",
  fontSize: "0.9rem",
};

const labelStyle: CSSProperties = {
  fontSize: "0.8rem",
  fontWeight: 600,
  color: "#334155",
};

const inputStyle: CSSProperties = {
  border: "1px solid #cbd5e1",
  borderRadius: "12px",
  padding: "0.7rem 0.8rem",
  fontSize: "0.92rem",
  color: "#0f172a",
  background: "#ffffff",
};

const primaryButtonStyle: CSSProperties = {
  border: "none",
  borderRadius: "999px",
  padding: "0.75rem 1.1rem",
  background: "#0f4c81",
  color: "#ffffff",
  fontWeight: 700,
  cursor: "pointer",
};

const subtlePanelStyle: CSSProperties = {
  background: "#f8fafc",
  border: "1px solid #e2e8f0",
  borderRadius: "16px",
  padding: "0.95rem 1rem",
};

const helperTextStyle: CSSProperties = {
  margin: "0.25rem 0 0",
  color: "#475569",
  lineHeight: 1.55,
};

const metaTextStyle: CSSProperties = {
  margin: "0.25rem 0 0",
  color: "#64748b",
  fontSize: "0.82rem",
  lineHeight: 1.5,
};

const stackStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const miniCardStyle: CSSProperties = {
  background: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "14px",
  padding: "0.8rem",
};

const itemCardStyle: CSSProperties = {
  background: "#ffffff",
  border: "1px solid #d7dee8",
  borderRadius: "16px",
  padding: "0.95rem 1rem",
};

const itemHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "0.75rem",
};

const badgeStyle: CSSProperties = {
  borderRadius: "999px",
  padding: "0.28rem 0.65rem",
  fontSize: "0.74rem",
  fontWeight: 700,
  color: "#102a43",
};

const subtleBadgeStyle: CSSProperties = {
  borderRadius: "999px",
  padding: "0.28rem 0.65rem",
  fontSize: "0.72rem",
  fontWeight: 700,
  color: "#334155",
  background: "#e2e8f0",
};

const metaGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, max-content) minmax(0, 1fr))",
  gap: "0.35rem 0.85rem",
  alignItems: "start",
  fontSize: "0.82rem",
  color: "#334155",
};

const monoStyle: CSSProperties = {
  fontFamily: "Consolas, Monaco, 'Courier New', monospace",
  fontSize: "0.8rem",
};

const monoMetaStyle: CSSProperties = {
  ...monoStyle,
  color: "#64748b",
  margin: "0.25rem 0 0",
};

const itemTextStyle: CSSProperties = {
  margin: "0.75rem 0 0",
  color: "#0f172a",
  lineHeight: 1.6,
};

const bulletListStyle: CSSProperties = {
  margin: "0.75rem 0 0",
  paddingLeft: "1.25rem",
  color: "#334155",
  lineHeight: 1.6,
};

const groundingLayoutStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
};

const groundingColumnStyle: CSSProperties = {
  display: "grid",
  gap: "0.75rem",
};

const subheadingStyle: CSSProperties = {
  fontSize: "0.92rem",
  color: "#0f172a",
};

const sectionHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "0.75rem",
};

const artifactTextStyle: CSSProperties = {
  width: "100%",
  minHeight: "220px",
  border: "1px solid #cbd5e1",
  borderRadius: "14px",
  padding: "0.85rem",
  fontFamily: "Consolas, Monaco, 'Courier New', monospace",
  fontSize: "0.8rem",
  lineHeight: 1.6,
  color: "#0f172a",
  resize: "vertical",
  background: "#f8fafc",
};