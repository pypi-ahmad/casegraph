"use client";

import Link from "next/link";
import AiDisclosureBanner from "@/components/ai-disclosure-banner";
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { titleCase } from "@/lib/display-labels";

import type {
  CaseDocumentReference,
  ChecklistItem,
  ExtractedFieldResult,
  ExtractionFieldDefinition,
  ExtractionValidationsResponse,
  FieldValidationRecord,
  FieldValidationStatus,
  GroundingReference,
  RequirementReviewRecord,
  RequirementReviewsResponse,
  RequirementReviewStatus,
  ReviewedCaseStateResponse,
} from "@casegraph/agent-sdk";

import { fetchCaseDetail } from "@/lib/cases-api";
import {
  fetchDocumentExtractions,
  fetchExtractionResult,
  fetchExtractionTemplateDetail,
} from "@/lib/extraction-api";
import {
  fetchReviewedCaseState,
  fetchExtractionValidations,
  fetchRequirementReviews,
  validateField,
  reviewRequirement,
} from "@/lib/human-validation-api";
import { fetchChecklist } from "@/lib/readiness-api";

interface CaseExtractionEntry {
  extraction_id: string;
  document_id: string;
  template_id: string;
  fields: ExtractedFieldResult[];
}

export default function ValidationClient({ caseId }: { caseId: string }) {
  const [caseTitle, setCaseTitle] = useState("");
  const [reviewState, setReviewState] = useState<ReviewedCaseStateResponse | null>(null);
  const [validations, setValidations] = useState<ExtractionValidationsResponse | null>(null);
  const [requirementReviews, setRequirementReviews] = useState<RequirementReviewsResponse | null>(null);
  const [extractions, setExtractions] = useState<CaseExtractionEntry[]>([]);
  const [checklistItems, setChecklistItems] = useState<ChecklistItem[]>([]);
  const [fieldDisplayNames, setFieldDisplayNames] = useState<Map<string, string>>(new Map());
  const [templateDisplayNames, setTemplateDisplayNames] = useState<Map<string, string>>(new Map());
  const [documentFilenames, setDocumentFilenames] = useState<Map<string, string>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [caseDetail, stateData, validationData, reviewData] = await Promise.all([
        fetchCaseDetail(caseId),
        fetchReviewedCaseState(caseId),
        fetchExtractionValidations(caseId),
        fetchRequirementReviews(caseId),
      ]);
      setCaseTitle(caseDetail.case.title);
      setReviewState(stateData);
      setValidations(validationData);
      setRequirementReviews(reviewData);

      // Build document filename lookup from case detail
      const docFilenameMap = new Map<string, string>();
      for (const doc of caseDetail.documents) {
        docFilenameMap.set(doc.document_id, doc.source_file.filename);
      }
      setDocumentFilenames(docFilenameMap);

      const extractionIds = new Map<string, { extraction_id: string }>();
      for (const validation of validationData.validations) {
        extractionIds.set(validation.extraction_id, { extraction_id: validation.extraction_id });
      }

      try {
        const documentExtractions = await Promise.all(
          caseDetail.documents.map(async (documentRef) => {
            try {
              return await fetchDocumentExtractions(documentRef.document_id);
            } catch {
              return { document_id: documentRef.document_id, extractions: [] };
            }
          }),
        );

        for (const docExtraction of documentExtractions) {
          for (const extraction of docExtraction.extractions) {
            if (extraction.case_id === caseId) {
              extractionIds.set(extraction.extraction_id, { extraction_id: extraction.extraction_id });
            }
          }
        }
      } catch {
        // Extraction summaries are best-effort; detailed results are fetched below.
      }

      const extractionResults = await Promise.all(
        Array.from(extractionIds.values()).map(async ({ extraction_id }) => {
          try {
            const result = await fetchExtractionResult(extraction_id);
            return {
              extraction_id: result.run.extraction_id,
              document_id: result.run.document_id,
              template_id: result.run.template_id,
              fields: result.fields,
            } satisfies CaseExtractionEntry;
          } catch {
            return null;
          }
        }),
      );
      setExtractions(extractionResults.filter((value): value is CaseExtractionEntry => value !== null));

      // Build field display name and template display name lookups
      const templateIds = new Set(
        extractionResults
          .filter((value): value is CaseExtractionEntry => value !== null)
          .map((entry) => entry.template_id),
      );
      const fieldNames = new Map<string, string>();
      const templateNames = new Map<string, string>();
      await Promise.all(
        Array.from(templateIds).map(async (templateId) => {
          try {
            const detail = await fetchExtractionTemplateDetail(templateId);
            templateNames.set(templateId, detail.metadata.display_name);
            for (const field of detail.schema_definition.fields) {
              fieldNames.set(`${templateId}/${field.field_id}`, field.display_name);
              if (field.nested_fields) {
                for (const nested of field.nested_fields) {
                  fieldNames.set(`${templateId}/${nested.field_id}`, nested.display_name);
                }
              }
            }
          } catch {
            // Template detail is best-effort; field_id will be humanized as fallback.
          }
        }),
      );
      setFieldDisplayNames(fieldNames);
      setTemplateDisplayNames(templateNames);

      try {
        const checklistData = await fetchChecklist(caseId);
        setChecklistItems(checklistData.checklist.items ?? []);
      } catch {
        setChecklistItems([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load validation data. Try refreshing the page.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadData(); }, [caseId]);

  async function handleValidateField(extractionId: string, fieldId: string, status: FieldValidationStatus, correctedValue?: unknown) {
    setSubmitting(`${extractionId}/${fieldId}`);
    try {
      await validateField(extractionId, fieldId, { status, reviewed_value: correctedValue, note: "" });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed. Check the field value and try again.");
    } finally {
      setSubmitting(null);
    }
  }

  async function handleReviewRequirement(itemId: string, status: RequirementReviewStatus, note: string) {
    setSubmitting(itemId);
    try {
      await reviewRequirement(caseId, itemId, { status, note });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Requirement review update failed. Try refreshing the page and resubmitting.");
    } finally {
      setSubmitting(null);
    }
  }

  if (loading) {
    return <main style={pageStyle}><section style={containerStyle}><div style={panelStyle}>Loading validation results…</div></section></main>;
  }

  if (error || !reviewState) {
    return <main style={pageStyle}><section style={containerStyle}><div style={errorPanelStyle}>{error ?? "Validation data unavailable."}</div></section></main>;
  }

  const state = reviewState.state;
  const validationMap = new Map<string, FieldValidationRecord>();
  for (const v of validations?.validations ?? []) {
    validationMap.set(`${v.extraction_id}/${v.field_id}`, v);
  }
  const reviewMap = new Map<string, RequirementReviewRecord>();
  for (const r of requirementReviews?.reviews ?? []) {
    reviewMap.set(r.item_id, r);
  }

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <div style={linkRowStyle}>
          <Link href={`/cases/${caseId}`} style={secondaryLinkStyle}>Case workspace</Link>
          <Link href={`/cases/${caseId}/handoff`} style={secondaryLinkStyle}>Reviewed handoff</Link>
          <Link href={`/cases/${caseId}/audit`} style={secondaryLinkStyle}>Audit timeline</Link>
          <Link href={`/cases/${caseId}/packets`} style={secondaryLinkStyle}>Packets</Link>
        </div>

        <header style={headerStyle}>
          <div>
            <p style={breadcrumbStyle}>Human Validation</p>
            <h1 style={titleStyle}>Review Extracted Information</h1>
            <p style={subtitleStyle}>
              Review and correct information extracted from your documents. Your changes are saved alongside the originals.
            </p>
          </div>
          <div style={summaryCardStyle}>
            <div style={summaryValueStyle}>{state.field_validation.reviewed_fields}/{state.field_validation.total_fields}</div>
            <div style={summaryLabelStyle}>Fields reviewed</div>
            <div style={summaryValueStyle}>{state.requirement_review.reviewed_items}/{state.requirement_review.total_items}</div>
            <div style={summaryLabelStyle}>Requirements reviewed</div>
            <div style={summaryValueStyle}>{state.unresolved_items.length}</div>
            <div style={summaryLabelStyle}>Unresolved items</div>
          </div>
        </header>

        <AiDisclosureBanner />

        <div style={caseTitleStyle}>{caseTitle}</div>

        {/* Review state summary */}
        <section style={sectionCardStyle}>
          <h2 style={sectionTitleStyle}>Review Summary</h2>
          <div style={gridTwoStyle}>
            <div style={statGroupStyle}>
              <div style={statLabelStyle}>Field Validation</div>
              <div style={statRowStyle}><span>Accepted:</span> <strong>{state.field_validation.accepted_fields}</strong></div>
              <div style={statRowStyle}><span>Corrected:</span> <strong>{state.field_validation.corrected_fields}</strong></div>
              <div style={statRowStyle}><span>Rejected:</span> <strong>{state.field_validation.rejected_fields}</strong></div>
              <div style={statRowStyle}><span>Needs follow-up:</span> <strong>{state.field_validation.needs_followup_fields}</strong></div>
            </div>
            <div style={statGroupStyle}>
              <div style={statLabelStyle}>Requirement Review</div>
              <div style={statRowStyle}><span>Confirmed supported:</span> <strong>{state.requirement_review.confirmed_supported}</strong></div>
              <div style={statRowStyle}><span>Confirmed missing:</span> <strong>{state.requirement_review.confirmed_missing}</strong></div>
              <div style={statRowStyle}><span>More info needed:</span> <strong>{state.requirement_review.requires_more_information}</strong></div>
              <div style={statRowStyle}><span>Manually overridden:</span> <strong>{state.requirement_review.manually_overridden}</strong></div>
            </div>
          </div>
        </section>

        {/* Extracted fields */}
        <section style={sectionCardStyle}>
          <h2 style={sectionTitleStyle}>Extracted Fields</h2>
          {extractions.length === 0 ? (
            <div style={panelStyle}>No extraction results yet. Upload documents and run extraction from the case workspace to see results here.</div>
          ) : (
            <div style={stackStyle}>
              {extractions.map((ext) => (
                <div key={ext.extraction_id} style={extractionGroupStyle}>
                  <div style={extractionHeaderStyle}>
                    <div style={stackedHeaderStyle}>
                      <span style={{ fontWeight: 600, color: "#102033", fontSize: "0.9rem" }}>
                        {templateDisplayNames.get(ext.template_id) || titleCase(ext.template_id)}
                      </span>
                      {documentFilenames.get(ext.document_id) && (
                        <span style={metaTextStyle}>{documentFilenames.get(ext.document_id)}</span>
                      )}
                    </div>
                    <Link href={`/documents/${ext.document_id}`} style={secondaryLinkStyle}>Open document review</Link>
                  </div>
                  <div style={fieldListStyle}>
                    {ext.fields.map((field) => {
                      const key = `${ext.extraction_id}/${field.field_id}`;
                      const validation = validationMap.get(key);
                      const isSubmitting = submitting === key;
                      const displayName = fieldDisplayNames.get(`${ext.template_id}/${field.field_id}`) || null;
                      return (
                        <FieldRow
                          key={key}
                          extractionId={ext.extraction_id}
                          documentId={ext.document_id}
                          field={field}
                          displayName={displayName}
                          validation={validation ?? null}
                          isSubmitting={isSubmitting}
                          onValidate={handleValidateField}
                        />
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Checklist requirements */}
        <section style={sectionCardStyle}>
          <h2 style={sectionTitleStyle}>Requirement Review</h2>
          {checklistItems.length === 0 ? (
            <div style={panelStyle}>No checklist items yet. Set up a domain pack with requirements to enable the checklist.</div>
          ) : (
            <div style={stackStyle}>
              {checklistItems.map((item) => {
                const review = reviewMap.get(item.item_id);
                const isSubmitting = submitting === item.item_id;
                return (
                  <RequirementRow
                    key={item.item_id}
                    item={item}
                    review={review ?? null}
                    documentFilenames={documentFilenames}
                    isSubmitting={isSubmitting}
                    onReview={handleReviewRequirement}
                  />
                );
              })}
            </div>
          )}
        </section>

        {/* Unresolved items */}
        {state.unresolved_items.length > 0 && (
          <section style={sectionCardStyle}>
            <h2 style={sectionTitleStyle}>Unresolved Items</h2>
            <div style={stackStyle}>
              {state.unresolved_items.map((item, idx) => (
                <div key={idx} style={unresolvedCardStyle}>
                  <span style={badgeStyle}>{titleCase(item.item_type)}</span>
                  <span style={{ fontWeight: 600, color: "#102033", fontSize: "0.85rem" }}>{item.display_label}</span>
                  <span style={metaTextStyle}>{titleCase(item.current_status)}</span>
                  {item.note && <span style={metaTextStyle}>{item.note}</span>}
                </div>
              ))}
            </div>
          </section>
        )}
      </section>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Field row component
// ---------------------------------------------------------------------------

function FieldRow({
  extractionId,
  documentId,
  field,
  displayName,
  validation,
  isSubmitting,
  onValidate,
}: {
  extractionId: string;
  documentId: string;
  field: ExtractedFieldResult;
  displayName: string | null;
  validation: FieldValidationRecord | null;
  isSubmitting: boolean;
  onValidate: (extractionId: string, fieldId: string, status: FieldValidationStatus, correctedValue?: unknown) => void;
}) {
  const [correctedValue, setCorrectedValue] = useState("");
  const [showCorrection, setShowCorrection] = useState(false);

  const currentStatus = validation?.status ?? "unreviewed";
  const displayValue = validation?.status === "corrected" && validation.reviewed_value !== null
    ? String(validation.reviewed_value)
    : stringifyValue(field.value);
  const grounding = validation?.original.grounding.length
    ? validation.original.grounding
    : field.grounding;
  const primaryGrounding = getPrimaryGrounding(grounding, documentId);

  return (
    <div style={fieldRowStyle}>
      <div style={fieldInfoStyle}>
        <div style={fieldNameStyle}>{displayName || formatFieldId(field.field_id)}</div>
        <div style={fieldValueStyle}>
          {field.is_present ? displayValue : <span style={missingStyle}>(not extracted)</span>}
        </div>
        <div style={fieldMetaStyle}>
          <span style={typeBadgeStyle}>{titleCase(field.field_type)}</span>
          {validation?.status === "corrected" && (
            <span style={correctedBadgeStyle}>Original: {stringifyValue(validation.original.value)}</span>
          )}
          {grounding.length > 0 && (
            <span style={groundingBadgeStyle}>{field.grounding.length} source reference(s)</span>
          )}
          <Link href={`/documents/${primaryGrounding.document_id}`} style={contextLinkStyle}>
            Source context{primaryGrounding.page_number ? ` (p.${primaryGrounding.page_number})` : ""}
          </Link>
        </div>
      </div>
      <div style={fieldActionsStyle}>
        <StatusBadge status={currentStatus} />
        {!isSubmitting ? (
          <div style={buttonGroupStyle}>
            <button type="button" style={actionBtnStyle} onClick={() => onValidate(extractionId, field.field_id, "accepted")} disabled={currentStatus === "accepted"}>Accept</button>
            <button type="button" style={actionBtnStyle} onClick={() => setShowCorrection(true)}>Correct</button>
            <button type="button" style={actionBtnStyle} onClick={() => onValidate(extractionId, field.field_id, "rejected")}>Reject</button>
            <button type="button" style={actionBtnStyle} onClick={() => onValidate(extractionId, field.field_id, "needs_followup")}>Follow-up</button>
          </div>
        ) : (
          <span style={metaTextStyle}>Saving...</span>
        )}
        {showCorrection && (
          <div style={correctionRowStyle}>
            <input
              type="text"
              value={correctedValue}
              onChange={(e) => setCorrectedValue(e.target.value)}
              placeholder="Enter corrected value"
              style={correctedValue.trim() ? inputStyle : { ...inputStyle, borderColor: "#fbbf24" }}
            />
            <button
              type="button"
              style={primaryButtonStyle}
              disabled={!correctedValue.trim()}
              onClick={() => { onValidate(extractionId, field.field_id, "corrected", correctedValue); setShowCorrection(false); setCorrectedValue(""); }}
            >
              Save correction
            </button>
            <button type="button" style={secondaryBtnStyle} onClick={() => setShowCorrection(false)}>Cancel</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Requirement row component
// ---------------------------------------------------------------------------

function RequirementRow({
  item,
  review,
  isSubmitting,
  documentFilenames,
  onReview,
}: {
  item: ChecklistItem;
  review: RequirementReviewRecord | null;
  isSubmitting: boolean;
  documentFilenames: Map<string, string>;
  onReview: (itemId: string, status: RequirementReviewStatus, note: string) => void;
}) {
  const [note, setNote] = useState(review?.note ?? "");
  const currentStatus = review?.status ?? "unreviewed";

  useEffect(() => {
    setNote(review?.note ?? "");
  }, [review?.note]);

  return (
    <div style={requirementRowStyle}>
      <div style={reqInfoStyle}>
        <div style={reqNameStyle}>{item.display_name}</div>
        {item.description && <div style={metaTextStyle}>{item.description}</div>}
        <div style={fieldMetaStyle}>
          <span style={typeBadgeStyle}>{item.priority}</span>
          <span style={typeBadgeStyle}>Auto-detected: {titleCase(review?.original_machine_status || item.status)}</span>
        </div>
        {review && review.linked_document_ids.length > 0 && (
          <div style={fieldMetaStyle}>
            {review.linked_document_ids.map((documentId) => (
              <Link key={documentId} href={`/documents/${documentId}`} style={contextLinkStyle}>
                {documentFilenames.get(documentId) || "Document"}
              </Link>
            ))}
          </div>
        )}
      </div>
      <div style={fieldActionsStyle}>
        <StatusBadge status={currentStatus} />
        {!isSubmitting ? (
          <>
            <div style={buttonGroupStyle}>
              <button type="button" style={actionBtnStyle} onClick={() => onReview(item.item_id, "confirmed_supported", note)}>Confirmed</button>
              <button type="button" style={actionBtnStyle} onClick={() => onReview(item.item_id, "confirmed_missing", note)}>Missing</button>
              <button type="button" style={actionBtnStyle} onClick={() => onReview(item.item_id, "requires_more_information", note)}>Need info</button>
              <button type="button" style={actionBtnStyle} onClick={() => onReview(item.item_id, "manually_overridden", note)}>Override</button>
            </div>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Review note (optional)"
              style={{ ...inputStyle, marginTop: "0.4rem" }}
            />
          </>
        ) : (
          <span style={metaTextStyle}>Saving...</span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const labelMap: Record<string, string> = {
    unreviewed: "Unreviewed",
    accepted: "Accepted",
    confirmed_supported: "Confirmed",
    corrected: "Corrected",
    manually_overridden: "Overridden",
    rejected: "Rejected",
    confirmed_missing: "Missing",
    needs_followup: "Needs Follow-up",
    requires_more_information: "Needs More Info",
  };
  const colorMap: Record<string, { bg: string; fg: string }> = {
    unreviewed: { bg: "#e2e8f0", fg: "#475569" },
    accepted: { bg: "#d1fae5", fg: "#065f46" },
    confirmed_supported: { bg: "#d1fae5", fg: "#065f46" },
    corrected: { bg: "#fef3c7", fg: "#92400e" },
    manually_overridden: { bg: "#fef3c7", fg: "#92400e" },
    rejected: { bg: "#fecaca", fg: "#991b1b" },
    confirmed_missing: { bg: "#fecaca", fg: "#991b1b" },
    needs_followup: { bg: "#e0e7ff", fg: "#3730a3" },
    requires_more_information: { bg: "#e0e7ff", fg: "#3730a3" },
  };
  const colors = colorMap[status] ?? { bg: "#e2e8f0", fg: "#475569" };
  return (
    <span style={{ ...statusBadgeBaseStyle, backgroundColor: colors.bg, color: colors.fg }}>
      {labelMap[status] ?? titleCase(status)}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "string") return value;
  try { return JSON.stringify(value); } catch { return String(value); }
}

function formatFieldId(fieldId: string): string {
  return titleCase(fieldId);
}

function getPrimaryGrounding(
  grounding: GroundingReference[],
  documentId: string,
): { document_id: string; page_number?: number | null } {
  const first = grounding.find((entry) => entry.document_id) ?? grounding[0];
  return {
    document_id: first?.document_id ?? documentId,
    page_number: first?.page_number ?? null,
  };
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const pageStyle: CSSProperties = { minHeight: "100vh", padding: "2.5rem 1.25rem 2rem", backgroundColor: "#f5f7fa" };
const containerStyle: CSSProperties = { maxWidth: "1180px", margin: "0 auto" };
const linkRowStyle: CSSProperties = { display: "flex", flexWrap: "wrap", gap: "0.75rem", marginBottom: "1rem" };
const secondaryLinkStyle: CSSProperties = { color: "#0d6efd", textDecoration: "none", fontWeight: 500 };
const headerStyle: CSSProperties = { display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "flex-start", marginBottom: "1rem" };
const breadcrumbStyle: CSSProperties = { margin: 0, textTransform: "uppercase", letterSpacing: "0.08em", fontSize: "0.8rem", color: "#64748b" };
const titleStyle: CSSProperties = { margin: "0.35rem 0", fontSize: "2.1rem", color: "#102033" };
const subtitleStyle: CSSProperties = { margin: 0, color: "#55657a", lineHeight: 1.6, maxWidth: "760px" };
const caseTitleStyle: CSSProperties = { marginBottom: "1rem", color: "#334155", fontWeight: 600 };
const summaryCardStyle: CSSProperties = { minWidth: "180px", padding: "0.9rem 1rem", borderRadius: "16px", border: "1px solid #d7dee8", backgroundColor: "#fff" };
const summaryValueStyle: CSSProperties = { fontSize: "1.35rem", fontWeight: 700, color: "#102033" };
const summaryLabelStyle: CSSProperties = { fontSize: "0.82rem", color: "#64748b", marginBottom: "0.5rem" };
const sectionCardStyle: CSSProperties = { marginBottom: "1rem", padding: "1.1rem 1.25rem", borderRadius: "16px", border: "1px solid #d7dee8", backgroundColor: "#fff" };
const sectionTitleStyle: CSSProperties = { margin: "0 0 0.85rem", fontSize: "1.05rem", color: "#102033" };
const panelStyle: CSSProperties = { padding: "0.9rem 1rem", borderRadius: "12px", border: "1px solid #d7dee8", backgroundColor: "#f8fafc", color: "#334155" };
const errorPanelStyle: CSSProperties = { ...panelStyle, borderColor: "#fca5a5", backgroundColor: "#fef2f2", color: "#991b1b" };
const stackStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: "0.85rem" };
const gridTwoStyle: CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" };
const statGroupStyle: CSSProperties = { padding: "0.8rem", borderRadius: "12px", border: "1px solid #e2e8f0", backgroundColor: "#f8fafc" };
const statLabelStyle: CSSProperties = { fontWeight: 600, color: "#102033", marginBottom: "0.5rem" };
const statRowStyle: CSSProperties = { display: "flex", justifyContent: "space-between", fontSize: "0.88rem", color: "#475569", padding: "0.15rem 0" };
const monoLabelStyle: CSSProperties = { fontFamily: "monospace", fontSize: "0.8rem", color: "#475569" };
const metaTextStyle: CSSProperties = { fontSize: "0.83rem", color: "#55657a", lineHeight: 1.5 };
const badgeStyle: CSSProperties = { display: "inline-block", padding: "0.15rem 0.55rem", borderRadius: "999px", backgroundColor: "#e0e7ff", color: "#3730a3", fontSize: "0.74rem", marginRight: "0.5rem" };
const extractionGroupStyle: CSSProperties = { padding: "0.8rem", borderRadius: "12px", border: "1px solid #e2e8f0", backgroundColor: "#f8fafc" };
const extractionHeaderStyle: CSSProperties = { display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" };
const stackedHeaderStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: "0.1rem" };
const fieldListStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: "0.6rem" };
const fieldRowStyle: CSSProperties = { display: "flex", justifyContent: "space-between", gap: "1rem", padding: "0.65rem 0.75rem", borderRadius: "10px", border: "1px solid #e2e8f0", backgroundColor: "#fff" };
const fieldInfoStyle: CSSProperties = { flex: 1, minWidth: 0 };
const fieldNameStyle: CSSProperties = { fontWeight: 600, color: "#102033", fontSize: "0.9rem" };
const fieldValueStyle: CSSProperties = { color: "#334155", fontSize: "0.88rem", marginTop: "0.15rem" };
const fieldMetaStyle: CSSProperties = { display: "flex", gap: "0.5rem", marginTop: "0.3rem", flexWrap: "wrap" };
const fieldActionsStyle: CSSProperties = { display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "0.35rem", minWidth: "200px" };
const buttonGroupStyle: CSSProperties = { display: "flex", gap: "0.35rem", flexWrap: "wrap" };
const actionBtnStyle: CSSProperties = { padding: "0.3rem 0.6rem", borderRadius: "8px", border: "1px solid #cbd5e1", backgroundColor: "#fff", color: "#334155", fontSize: "0.78rem", cursor: "pointer", fontWeight: 500 };
const primaryButtonStyle: CSSProperties = { padding: "0.35rem 0.7rem", borderRadius: "8px", border: "none", backgroundColor: "#102033", color: "#fff", fontWeight: 600, cursor: "pointer", fontSize: "0.78rem" };
const secondaryBtnStyle: CSSProperties = { padding: "0.35rem 0.7rem", borderRadius: "8px", border: "1px solid #cbd5e1", backgroundColor: "#f8fafc", color: "#475569", cursor: "pointer", fontSize: "0.78rem" };
const correctionRowStyle: CSSProperties = { display: "flex", gap: "0.4rem", alignItems: "center", marginTop: "0.3rem" };
const inputStyle: CSSProperties = { padding: "0.4rem 0.6rem", borderRadius: "8px", border: "1px solid #cbd5e1", backgroundColor: "#fff", color: "#0f172a", fontSize: "0.82rem", minWidth: "160px" };
const typeBadgeStyle: CSSProperties = { display: "inline-block", padding: "0.1rem 0.4rem", borderRadius: "6px", backgroundColor: "#f1f5f9", color: "#64748b", fontSize: "0.72rem" };
const correctedBadgeStyle: CSSProperties = { ...typeBadgeStyle, backgroundColor: "#fef3c7", color: "#92400e" };
const groundingBadgeStyle: CSSProperties = { ...typeBadgeStyle, backgroundColor: "#ecfdf5", color: "#065f46" };
const contextLinkStyle: CSSProperties = { color: "#0d6efd", fontSize: "0.78rem", textDecoration: "none", fontWeight: 500 };
const missingStyle: CSSProperties = { color: "#94a3b8", fontStyle: "italic" };
const statusBadgeBaseStyle: CSSProperties = { display: "inline-block", padding: "0.15rem 0.55rem", borderRadius: "999px", fontSize: "0.74rem", fontWeight: 600, whiteSpace: "nowrap" };
const requirementRowStyle: CSSProperties = { ...fieldRowStyle };
const reqInfoStyle: CSSProperties = { flex: 1, minWidth: 0 };
const reqNameStyle: CSSProperties = { fontWeight: 600, color: "#102033", fontSize: "0.9rem" };
const unresolvedCardStyle: CSSProperties = { display: "flex", gap: "0.75rem", alignItems: "center", padding: "0.55rem 0.75rem", borderRadius: "10px", border: "1px solid #fbbf24", backgroundColor: "#fffbeb" };
