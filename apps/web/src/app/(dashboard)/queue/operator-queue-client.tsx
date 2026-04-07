"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";

import type {
  CaseStage,
  DomainPackMetadata,
  CaseTypeTemplateMetadata,
  QueueFilterMetadata,
  QueueSummaryResponse,
  ReviewQueueItem,
  ReviewQueueResponse,
} from "@casegraph/agent-sdk";

import { fetchDomainPacks, fetchDomainPackDetail } from "@/lib/domains-api";
import {
  fetchOperatorQueue,
  fetchOperatorQueueSummary,
} from "@/lib/operator-review-api";

const STAGE_OPTIONS: Array<{ value: "" | CaseStage; label: string }> = [
  { value: "", label: "All stages" },
  { value: "intake", label: "Intake" },
  { value: "document_review", label: "Document review" },
  { value: "readiness_review", label: "Readiness review" },
  { value: "awaiting_documents", label: "Awaiting documents" },
  { value: "ready_for_next_step", label: "Ready for next step" },
  { value: "closed_placeholder", label: "Closed placeholder" },
];

export default function OperatorQueueClient() {
  const [queue, setQueue] = useState<ReviewQueueResponse | null>(null);
  const [summary, setSummary] = useState<QueueSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stage, setStage] = useState<"" | CaseStage>("");
  const [hasMissingItems, setHasMissingItems] = useState(false);
  const [hasOpenActions, setHasOpenActions] = useState(false);
  const [domainPackId, setDomainPackId] = useState("");
  const [caseTypeId, setCaseTypeId] = useState("");
  const [domainPacks, setDomainPacks] = useState<DomainPackMetadata[]>([]);
  const [caseTypes, setCaseTypes] = useState<CaseTypeTemplateMetadata[]>([]);

  const filters = useMemo<Partial<QueueFilterMetadata>>(
    () => ({
      stage: stage || undefined,
      has_missing_items: hasMissingItems ? true : undefined,
      has_open_actions: hasOpenActions ? true : undefined,
      domain_pack_id: domainPackId.trim() || undefined,
      case_type_id: caseTypeId.trim() || undefined,
      limit: 100,
    }),
    [caseTypeId, domainPackId, hasMissingItems, hasOpenActions, stage],
  );

  useEffect(() => {
    fetchDomainPacks()
      .then((res) => setDomainPacks(res.packs))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!domainPackId) { setCaseTypes([]); return; }
    fetchDomainPackDetail(domainPackId)
      .then((res) => setCaseTypes(res.pack.case_types))
      .catch(() => setCaseTypes([]));
  }, [domainPackId]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [queueResponse, summaryResponse] = await Promise.all([
          fetchOperatorQueue(filters),
          fetchOperatorQueueSummary(filters),
        ]);
        if (!cancelled) {
          setQueue(queueResponse);
          setSummary(summaryResponse);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to load review queue. Try refreshing the page.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [filters]);

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <header style={headerStyle}>
          <div>
            <p style={breadcrumbStyle}>Operator Queue</p>
            <h1 style={titleStyle}>Review Queue</h1>
            <p style={subtitleStyle}>
              Cases that need your attention right now.
            </p>
          </div>
          <Link href="/cases" style={secondaryLinkStyle}>
            View Cases
          </Link>
        </header>

        <section style={filterPanelStyle}>
          <label style={fieldStyle}>
            <span style={labelStyle}>Stage</span>
            <select value={stage} onChange={(event) => setStage(event.target.value as "" | CaseStage)} style={inputStyle}>
              {STAGE_OPTIONS.map((option) => (
                <option key={option.label} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label style={fieldStyle}>
            <span style={labelStyle}>Domain Pack</span>
            <select value={domainPackId} onChange={(event) => { setDomainPackId(event.target.value); setCaseTypeId(""); }} style={inputStyle}>
              <option value="">All domain packs</option>
              {domainPacks.map((pack) => (
                <option key={pack.pack_id} value={pack.pack_id}>{pack.display_name}</option>
              ))}
            </select>
          </label>
          <label style={fieldStyle}>
            <span style={labelStyle}>Case Type</span>
            <select value={caseTypeId} onChange={(event) => setCaseTypeId(event.target.value)} style={inputStyle} disabled={!domainPackId}>
              <option value="">All case types</option>
              {caseTypes.map((ct) => (
                <option key={ct.case_type_id} value={ct.case_type_id}>{ct.display_name}</option>
              ))}
            </select>
          </label>
          <label style={checkboxStyle}>
            <input type="checkbox" checked={hasMissingItems} onChange={(event) => setHasMissingItems(event.target.checked)} />
            Missing required checklist items
          </label>
          <label style={checkboxStyle}>
            <input type="checkbox" checked={hasOpenActions} onChange={(event) => setHasOpenActions(event.target.checked)} />
            Generated open action items only
          </label>
        </section>

        {loading ? (
          <div style={panelStyle}>Loading operator queue...</div>
        ) : error ? (
          <div style={errorPanelStyle}>{error}</div>
        ) : (
          <>
            {summary && (
              <section style={summaryGridStyle}>
                <SummaryCard label="Cases in queue" value={summary.summary.total_cases} />
                <SummaryCard label="With open actions" value={summary.summary.cases_with_open_actions} />
                <SummaryCard label="With missing required" value={summary.summary.cases_with_missing_items} />
                <SummaryCard label="Needing attention" value={summary.summary.cases_needing_attention} />
              </section>
            )}

            {summary && summary.summary.stage_counts.length > 0 && (
              <div style={stageCountRowStyle}>
                {summary.summary.stage_counts.map((item) => (
                  <span key={item.stage} style={stageCountBadgeStyle}>
                    {item.stage.replace(/_/g, " ")}: {item.case_count}
                  </span>
                ))}
              </div>
            )}

            {queue && queue.items.length === 0 ? (
              <div style={panelStyle}>No cases need review right now. Try adjusting your filters or check back later.</div>
            ) : (
              <div style={queueGridStyle}>
                {queue?.items.map((item) => (
                  <QueueCard key={item.case_id} item={item} />
                ))}
              </div>
            )}
          </>
        )}
      </section>
    </main>
  );
}

function QueueCard({ item }: { item: ReviewQueueItem }) {
  return (
    <article style={cardStyle}>
      <div style={cardHeaderStyle}>
        <div>
          <h2 style={cardTitleStyle}>{item.title}</h2>
          <p style={cardIdStyle}>{item.case_id}</p>
        </div>
        <span style={badgeStyle}>{item.current_stage.replace(/_/g, " ")}</span>
      </div>

      <div style={metaGridStyle}>
        <span>Case status</span><span>{item.case_status.replace(/_/g, " ")}</span>
        <span>Readiness</span><span>{item.readiness_status?.replace(/_/g, " ") ?? "Not available"}</span>
        <span>Linked documents</span><span>{item.linked_document_count}</span>
        <span>Open action items</span><span>{item.open_action_count}</span>
        <span>Detected follow-ups</span><span>{item.detected_action_count}</span>
        <span>Missing required</span><span>{item.missing_required_count}</span>
        <span>Needs review</span><span>{item.needs_review_count}</span>
        <span>Failed runs</span><span>{item.failed_run_count}</span>
      </div>

      {item.attention_categories.length > 0 && (
        <div style={chipRowStyle}>
          {item.attention_categories.map((category) => (
            <span key={category} style={chipStyle}>{category.replace(/_/g, " ")}</span>
          ))}
        </div>
      )}

      <p style={cardMetaStyle}>Updated: {formatTimestamp(item.last_activity_at)}</p>

      <div style={cardActionsStyle}>
        <Link href={`/cases/${item.case_id}/review`} style={primaryLinkStyle}>
          Open Review
        </Link>
        <Link href={`/cases/${item.case_id}`} style={secondaryLinkStyle}>
          Open Case
        </Link>
      </div>
    </article>
  );
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div style={summaryCardStyle}>
      <span style={summaryLabelStyle}>{label}</span>
      <strong style={summaryValueStyle}>{value}</strong>
    </div>
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

const headerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
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
  maxWidth: "720px",
  color: "#55657a",
  lineHeight: 1.6,
};

const filterPanelStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "0.9rem",
  padding: "1rem 1.1rem",
  border: "1px solid #d7dee8",
  borderRadius: "16px",
  backgroundColor: "#ffffff",
  marginBottom: "1rem",
};

const fieldStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.45rem",
};

const checkboxStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.5rem",
  color: "#334155",
  fontSize: "0.9rem",
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

const summaryGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "0.9rem",
  marginBottom: "1rem",
};

const summaryCardStyle: CSSProperties = {
  padding: "1rem 1.1rem",
  borderRadius: "16px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
};

const summaryLabelStyle: CSSProperties = {
  display: "block",
  fontSize: "0.85rem",
  color: "#64748b",
};

const summaryValueStyle: CSSProperties = {
  display: "block",
  marginTop: "0.45rem",
  fontSize: "1.8rem",
  color: "#102033",
};

const stageCountRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.5rem",
  marginBottom: "1rem",
};

const stageCountBadgeStyle: CSSProperties = {
  padding: "0.35rem 0.7rem",
  borderRadius: "999px",
  backgroundColor: "#e2e8f0",
  color: "#334155",
  fontSize: "0.8rem",
};

const queueGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
  gap: "1rem",
};

const cardStyle: CSSProperties = {
  padding: "1.15rem",
  border: "1px solid #d7dee8",
  borderRadius: "16px",
  backgroundColor: "#ffffff",
};

const cardHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "1rem",
};

const cardTitleStyle: CSSProperties = {
  margin: 0,
  color: "#102033",
  fontSize: "1.1rem",
};

const cardIdStyle: CSSProperties = {
  margin: "0.3rem 0 0",
  color: "#94a3b8",
  fontSize: "0.78rem",
  fontFamily: "monospace",
};

const badgeStyle: CSSProperties = {
  alignSelf: "flex-start",
  padding: "0.25rem 0.7rem",
  borderRadius: "999px",
  backgroundColor: "#e2e8f0",
  color: "#334155",
  fontSize: "0.75rem",
  fontWeight: 600,
};

const metaGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr auto",
  gap: "0.45rem 0.75rem",
  marginTop: "0.9rem",
  fontSize: "0.9rem",
  color: "#475569",
};

const chipRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.5rem",
  marginTop: "0.9rem",
};

const chipStyle: CSSProperties = {
  padding: "0.25rem 0.6rem",
  borderRadius: "999px",
  backgroundColor: "#f1f5f9",
  color: "#334155",
  fontSize: "0.76rem",
};

const cardMetaStyle: CSSProperties = {
  margin: "0.9rem 0 0",
  fontSize: "0.85rem",
  color: "#64748b",
};

const cardActionsStyle: CSSProperties = {
  display: "flex",
  gap: "0.75rem",
  marginTop: "1rem",
};

const primaryLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "0.65rem 0.95rem",
  borderRadius: "10px",
  backgroundColor: "#102033",
  color: "#ffffff",
  textDecoration: "none",
  fontWeight: 600,
};

const secondaryLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "0.65rem 0.95rem",
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
};

const errorPanelStyle: CSSProperties = {
  ...panelStyle,
  borderColor: "#ef4444",
  color: "#991b1b",
};