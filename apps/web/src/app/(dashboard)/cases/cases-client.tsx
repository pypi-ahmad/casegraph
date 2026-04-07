"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

import type { CaseRecord } from "@casegraph/agent-sdk";

import { fetchCases } from "@/lib/cases-api";
import { caseStatusLabel } from "@/lib/display-labels";

export default function CasesClient() {
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetchCases();
        if (!cancelled) {
          setCases(response.cases);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to load cases. Try refreshing the page.");
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
  }, []);

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <header style={headerStyle}>
          <div>
            <p style={breadcrumbStyle}>Cases</p>
            <h1 style={titleStyle}>Cases</h1>
            <p style={subtitleStyle}>
              All your open cases and their current status.
            </p>
          </div>
          <Link href="/cases/new" style={primaryLinkStyle}>
            Create Case
          </Link>
        </header>

        {loading ? (
          <div style={panelStyle}>Loading your cases…</div>
        ) : error ? (
          <div style={errorPanelStyle}>{error}</div>
        ) : cases.length === 0 ? (
          <div style={panelStyle}>No cases yet. Click "Create Case" above to get started.</div>
        ) : (
          <div style={gridStyle}>
            {cases.map((item) => (
              <article key={item.case_id} style={cardStyle}>
                <div style={cardHeaderStyle}>
                  <div>
                    <h2 style={cardTitleStyle}>{item.title}</h2>
                    <p style={cardIdStyle}>Created {formatTimestamp(item.timestamps.created_at)}</p>
                  </div>
                  <span style={statusBadgeStyle}>{caseStatusLabel(item.status)}</span>
                </div>

                <p style={cardMetaStyle}>
                  Category: {item.category ?? "Unspecified"}
                </p>
                <p style={cardBodyStyle}>{item.summary ?? "No summary provided."}</p>
                <p style={cardMetaStyle}>
                  Workflow: {item.workflow_binding?.workflow_id ?? "Not selected"}
                </p>
                <p style={cardMetaStyle}>
                  Updated: {formatTimestamp(item.timestamps.updated_at)}
                </p>

                <Link href={`/cases/${item.case_id}`} style={secondaryLinkStyle}>
                  Open Case
                </Link>
              </article>
            ))}
          </div>
        )}
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
  maxWidth: "700px",
  color: "#55657a",
  lineHeight: 1.6,
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

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: "1rem",
};

const cardStyle: CSSProperties = {
  padding: "1.25rem",
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
  fontSize: "1.1rem",
  color: "#102033",
};

const cardIdStyle: CSSProperties = {
  margin: "0.25rem 0 0",
  fontFamily: "monospace",
  fontSize: "0.78rem",
  color: "#94a3b8",
};

const cardMetaStyle: CSSProperties = {
  margin: "0.5rem 0 0",
  fontSize: "0.85rem",
  color: "#475569",
};

const cardBodyStyle: CSSProperties = {
  margin: "0.75rem 0",
  color: "#55657a",
  lineHeight: 1.55,
};

const statusBadgeStyle: CSSProperties = {
  alignSelf: "flex-start",
  padding: "0.25rem 0.65rem",
  borderRadius: "999px",
  backgroundColor: "#e2e8f0",
  color: "#334155",
  fontSize: "0.72rem",
  fontWeight: 600,
  textTransform: "uppercase",
};

const primaryLinkStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "0.7rem 1rem",
  borderRadius: "10px",
  backgroundColor: "#102033",
  color: "#ffffff",
  textDecoration: "none",
  fontWeight: 600,
};

const secondaryLinkStyle: CSSProperties = {
  display: "inline-flex",
  marginTop: "0.9rem",
  color: "#102033",
  fontWeight: 600,
  textDecoration: "none",
};