"use client";

import Link from "next/link";
import type { CSSProperties } from "react";

/**
 * Platform cross-link map — shows how inspector surfaces connect.
 *
 * Organized by domain flow so operators can navigate between related
 * surfaces without memorizing the nav bar.
 */

interface FlowLink {
  label: string;
  href: string;
  description: string;
}

interface FlowGroup {
  title: string;
  links: FlowLink[];
}

const FLOW_GROUPS: FlowGroup[] = [
  {
    title: "Case Lifecycle",
    links: [
      { label: "Cases", href: "/cases", description: "Create and manage cases" },
      { label: "Domain Packs", href: "/domain-packs", description: "Case type requirements and document rules" },
      { label: "Checklist", href: "#checklist", description: "Per-case requirement tracking (from case detail)" },
      { label: "Workflow Packs", href: "#workflow-packs", description: "Domain-specific stage orchestration (from case detail)" },
      { label: "Packets", href: "#packets", description: "Assembled output bundles (from case detail)" },
      { label: "Submission Drafts", href: "#submissions", description: "Downstream submission preparation (from case detail)" },
    ],
  },
  {
    title: "Evidence Pipeline",
    links: [
      { label: "Documents", href: "/documents", description: "Ingested files and extraction output" },
      { label: "Extraction", href: "/extraction", description: "Template-driven structured extraction" },
      { label: "Knowledge", href: "/knowledge", description: "Chunking, embedding, and vector search" },
      { label: "RAG", href: "/rag", description: "Task registry and evidence-backed retrieval" },
    ],
  },
  {
    title: "Operator Surfaces",
    links: [
      { label: "Work Board", href: "/work", description: "Deadlines, assignment, and queue overview" },
      { label: "Queue", href: "/queue", description: "Operator review queue" },
      { label: "Validation", href: "#validation", description: "Field validation workspace (from case detail)" },
      { label: "Handoff", href: "#handoff", description: "Reviewed handoff and signoff (from case detail)" },
      { label: "Releases", href: "#releases", description: "Reviewed release bundles (from case detail)" },
      { label: "Audit", href: "#audit", description: "Timeline, decisions, and lineage (from case detail)" },
    ],
  },
  {
    title: "Platform Configuration",
    links: [
      { label: "Providers", href: "/settings/providers", description: "API key management and model configuration" },
      { label: "Target Packs", href: "/target-packs", description: "Submission targets and compatibility" },
      { label: "Tasks", href: "/tasks", description: "Task registry and prompt execution" },
      { label: "Evals", href: "/evals", description: "Evaluation suites and regression fixtures" },
    ],
  },
  {
    title: "Runtime & Infrastructure",
    links: [
      { label: "Runtime", href: "/runtime", description: "System agents and workflow configuration" },
      { label: "Automation", href: "/automation", description: "Tool registry and MCP status" },
      { label: "Topology", href: "/topology", description: "Visual graph of agents and workflows." },
    ],
  },
];

export default function PlatformFlowMap({ caseId }: { caseId?: string }) {
  return (
    <div style={containerStyle}>
      <h3 style={mapTitleStyle}>Platform Flow Map</h3>
      <p style={mapSubtitleStyle}>
        Quick links to related surfaces across the platform.
      </p>
      <div style={groupsStyle}>
        {FLOW_GROUPS.map((group) => (
          <div key={group.title} style={groupStyle}>
            <h4 style={groupTitleStyle}>{group.title}</h4>
            <ul style={linkListStyle}>
              {group.links.map((link) => {
                const href = link.href.startsWith("#") && caseId
                  ? `/cases/${caseId}/${link.href.slice(1)}`
                  : link.href;
                const isAnchor = link.href.startsWith("#") && !caseId;
                return (
                  <li key={link.label} style={linkItemStyle}>
                    {isAnchor ? (
                      <span style={disabledLinkStyle} title={link.description}>
                        {link.label}
                      </span>
                    ) : (
                      <Link href={href} style={flowLinkStyle} title={link.description}>
                        {link.label}
                      </Link>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Styles                                                              */
/* ------------------------------------------------------------------ */

const containerStyle: CSSProperties = {
  border: "1px solid #e2e8f0",
  borderRadius: "12px",
  padding: "1.25rem 1.5rem",
  backgroundColor: "#f8fafc",
  marginTop: "1.5rem",
};

const mapTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1rem",
  fontWeight: 600,
  color: "#1e293b",
};

const mapSubtitleStyle: CSSProperties = {
  margin: "0.35rem 0 1rem",
  fontSize: "0.85rem",
  color: "#64748b",
  lineHeight: 1.5,
};

const groupsStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
  gap: "1rem",
};

const groupStyle: CSSProperties = {
  backgroundColor: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "8px",
  padding: "0.75rem 1rem",
};

const groupTitleStyle: CSSProperties = {
  margin: "0 0 0.5rem",
  fontSize: "0.8rem",
  fontWeight: 600,
  color: "#475569",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
};

const linkListStyle: CSSProperties = {
  listStyle: "none",
  margin: 0,
  padding: 0,
};

const linkItemStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.4rem",
  padding: "0.2rem 0",
};

const flowLinkStyle: CSSProperties = {
  fontSize: "0.85rem",
  color: "#0d6efd",
  textDecoration: "none",
  fontWeight: 500,
};

const disabledLinkStyle: CSSProperties = {
  fontSize: "0.85rem",
  color: "#94a3b8",
  fontWeight: 500,
  cursor: "default",
};


