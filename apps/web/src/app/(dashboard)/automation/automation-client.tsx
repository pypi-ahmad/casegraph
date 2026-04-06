"use client";

import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";
import type {
  AutomationCapabilitiesResponse,
  ToolMetadata,
  AutomationBackend,
  ComputerUseProviderMeta,
} from "@casegraph/agent-sdk";
import { fetchAutomationCapabilities } from "@/lib/automation-api";

export default function AutomationClient() {
  const [data, setData] = useState<AutomationCapabilitiesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchAutomationCapabilities());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load automation capabilities.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <main style={pageStyle}>
      <section style={headerSection}>
        <p style={breadcrumbStyle}>Automation</p>
        <h1 style={titleStyle}>Automation & Tool Inspector</h1>
        <p style={subtitleStyle}>
          Foundation-level automation tools, Playwright MCP status, and
          computer-use provider metadata. Inspection only — this is not a tool
          runner or browser preview.
        </p>
        <div style={{ padding: "0.6rem 1rem", borderRadius: "8px", backgroundColor: "#fef3c7", border: "1px solid #fde68a", color: "#92400e", fontSize: "0.85rem", marginTop: "0.75rem" }}>
          <strong>Scaffolded module</strong> — This surface proxies metadata from the agent-runtime. No local business logic runs here. Tool execution requires a running agent-runtime with Playwright MCP wired.
        </div>
      </section>

      {loading ? (
        <div style={panelStyle}>Loading automation capabilities…</div>
      ) : error ? (
        <div style={errorPanelStyle}>
          <p>{error}</p>
          <button type="button" onClick={load} style={retryBtnStyle}>
            Retry
          </button>
        </div>
      ) : data ? (
        <>
          {/* Tools */}
          <section style={sectionStyle}>
            <h2 style={sectionTitleStyle}>Registered Tools</h2>
            <div style={gridStyle}>
              {data.tools.length > 0 ? (
                data.tools.map((tool) => (
                  <ToolCard key={tool.id} tool={tool} />
                ))
              ) : (
                <div style={panelStyle}>
                  No tools registered. The agent-runtime may not be running.
                </div>
              )}
            </div>
          </section>

          {/* Backends */}
          <section style={sectionStyle}>
            <h2 style={sectionTitleStyle}>Automation Backends</h2>
            <div style={gridStyle}>
              {data.backends.length > 0 ? (
                data.backends.map((b) => (
                  <BackendCard key={b.id} backend={b} />
                ))
              ) : (
                <div style={panelStyle}>No backends reported.</div>
              )}
            </div>
          </section>

          {/* Computer-use providers */}
          <section style={sectionStyle}>
            <h2 style={sectionTitleStyle}>Computer-Use Provider Support</h2>
            <div style={gridStyle}>
              {data.computer_use_providers.length > 0 ? (
                data.computer_use_providers.map((p) => (
                  <CUProviderCard key={p.provider_id} provider={p} />
                ))
              ) : (
                <div style={panelStyle}>No computer-use providers reported.</div>
              )}
            </div>
          </section>

          {/* Limitations */}
          <section style={sectionStyle}>
            <h2 style={sectionTitleStyle}>Current Limitations</h2>
            {data.limitations.length > 0 ? (
              <ul style={listStyle}>
                {data.limitations.map((text) => (
                  <li key={text} style={listItemStyle}>
                    {text}
                  </li>
                ))}
              </ul>
            ) : (
              <div style={panelStyle}>No current limitations reported.</div>
            )}
          </section>
        </>
      ) : (
        <div style={panelStyle}>No automation capability data available.</div>
      )}
    </main>
  );
}

/* ------------------------------------------------------------------ */
/* Sub-components                                                      */
/* ------------------------------------------------------------------ */

function ToolCard({ tool }: { tool: ToolMetadata }) {
  const statusColor =
    tool.implementation_status === "implemented"
      ? "#16a34a"
      : tool.implementation_status === "adapter_only"
        ? "#ca8a04"
        : "#94a3b8";
  const statusLabel =
    tool.implementation_status === "implemented"
      ? "Implemented"
      : tool.implementation_status === "adapter_only"
        ? "Adapter only"
        : "Planned";

  return (
    <div style={cardStyle}>
      <div style={cardHeaderStyle}>
        <span style={cardTitleStyle}>{tool.display_name}</span>
        <span style={{ ...badgeStyle, backgroundColor: statusColor }}>{statusLabel}</span>
      </div>
      <p style={cardDescStyle}>{tool.description}</p>
      <div style={tagRowStyle}>
        <span style={tagStyle}>{tool.category.replace(/_/g, " ")}</span>
        <span style={tagStyle}>{tool.safety_level.replace(/_/g, " ")}</span>
      </div>
      <code style={codeStyle}>{tool.id}@{tool.version}</code>
    </div>
  );
}

function BackendCard({ backend }: { backend: AutomationBackend }) {
  const statusColor =
    backend.status === "implemented"
      ? "#16a34a"
      : backend.status === "adapter_only"
        ? "#ca8a04"
        : "#94a3b8";

  return (
    <div style={cardStyle}>
      <div style={cardHeaderStyle}>
        <span style={cardTitleStyle}>{backend.display_name}</span>
        <span style={{ ...badgeStyle, backgroundColor: statusColor }}>
          {backend.status.replace(/_/g, " ")}
        </span>
      </div>
      <ul style={noteListStyle}>
        {backend.notes.map((note) => (
          <li key={note} style={noteStyle}>{note}</li>
        ))}
      </ul>
    </div>
  );
}

function CUProviderCard({ provider }: { provider: ComputerUseProviderMeta }) {
  const supportColor =
    provider.computer_use_support === "supported"
      ? "#16a34a"
      : provider.computer_use_support === "unknown"
        ? "#ca8a04"
        : "#94a3b8";

  return (
    <div style={cardStyle}>
      <div style={cardHeaderStyle}>
        <span style={cardTitleStyle}>{provider.display_name}</span>
        <span style={{ ...badgeStyle, backgroundColor: supportColor }}>
          {provider.computer_use_support.replace(/_/g, " ")}
        </span>
      </div>
      <ul style={noteListStyle}>
        {provider.notes.map((note) => (
          <li key={note} style={noteStyle}>{note}</li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Styles                                                              */
/* ------------------------------------------------------------------ */

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "2.5rem 1.25rem 2rem",
  backgroundColor: "#f5f7fa",
};

const headerSection: CSSProperties = {
  maxWidth: "1120px",
  margin: "0 auto 1.5rem",
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
  maxWidth: "760px",
  color: "#55657a",
  lineHeight: 1.6,
};

const panelStyle: CSSProperties = {
  maxWidth: "1120px",
  margin: "0 auto",
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

const retryBtnStyle: CSSProperties = {
  marginTop: "0.75rem",
  padding: "0.5rem 1.25rem",
  borderRadius: "8px",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  cursor: "pointer",
  fontWeight: 500,
  fontSize: "0.85rem",
};

const sectionStyle: CSSProperties = {
  maxWidth: "1120px",
  margin: "0 auto 2rem",
};

const sectionTitleStyle: CSSProperties = {
  fontSize: "1.3rem",
  color: "#1e293b",
  marginBottom: "0.75rem",
};

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
  gap: "1rem",
};

const cardStyle: CSSProperties = {
  padding: "1rem 1.25rem",
  border: "1px solid #d7dee8",
  borderRadius: "12px",
  backgroundColor: "#ffffff",
};

const cardHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
};

const cardTitleStyle: CSSProperties = {
  fontWeight: 600,
  fontSize: "0.95rem",
  color: "#1e293b",
};

const badgeStyle: CSSProperties = {
  padding: "2px 8px",
  borderRadius: "6px",
  color: "#ffffff",
  fontSize: "0.7rem",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
};

const cardDescStyle: CSSProperties = {
  fontSize: "0.82rem",
  color: "#64748b",
  lineHeight: 1.4,
  margin: "0.5rem 0 0.5rem",
};

const tagRowStyle: CSSProperties = {
  display: "flex",
  gap: "0.5rem",
  marginBottom: "0.5rem",
};

const tagStyle: CSSProperties = {
  padding: "2px 8px",
  borderRadius: "6px",
  backgroundColor: "#e0e7ff",
  color: "#4338ca",
  fontSize: "0.7rem",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
};

const codeStyle: CSSProperties = {
  display: "inline-block",
  padding: "2px 6px",
  borderRadius: "4px",
  backgroundColor: "#f1f5f9",
  color: "#475569",
  fontSize: "0.72rem",
  fontFamily: "monospace",
};

const noteListStyle: CSSProperties = {
  margin: "0.5rem 0 0",
  paddingLeft: "1.1rem",
  listStyle: "disc",
};

const noteStyle: CSSProperties = {
  fontSize: "0.78rem",
  color: "#64748b",
  lineHeight: 1.4,
};

const listStyle: CSSProperties = {
  ...panelStyle,
  paddingLeft: "2rem",
  listStyle: "disc",
};

const listItemStyle: CSSProperties = {
  fontSize: "0.85rem",
  color: "#475569",
  lineHeight: 1.6,
  marginBottom: "0.25rem",
};
