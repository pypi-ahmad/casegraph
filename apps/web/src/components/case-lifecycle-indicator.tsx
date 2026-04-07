"use client";

import type { CSSProperties } from "react";
import type { CaseStage } from "@casegraph/agent-sdk";

/** Ordered lifecycle stages with display labels. */
const STAGES: { key: CaseStage; label: string }[] = [
  { key: "intake", label: "Intake" },
  { key: "document_review", label: "Document Review" },
  { key: "awaiting_documents", label: "Awaiting Documents" },
  { key: "readiness_review", label: "Readiness Review" },
  { key: "ready_for_next_step", label: "Ready" },
  { key: "closed_placeholder", label: "Closed" },
];

export default function CaseLifecycleIndicator({
  currentStage,
}: {
  currentStage: CaseStage;
}) {
  const currentIndex = STAGES.findIndex((s) => s.key === currentStage);

  return (
    <nav aria-label="Case lifecycle" style={wrapperStyle}>
      <ol style={listStyle}>
        {STAGES.map((stage, index) => {
          const isCurrent = index === currentIndex;
          const isCompleted = index < currentIndex;

          return (
            <li key={stage.key} style={itemStyle}>
              {/* Connector line (skip first) */}
              {index > 0 && (
                <span
                  style={{
                    ...connectorStyle,
                    backgroundColor: isCompleted || isCurrent ? "#3b82f6" : "#e2e8f0",
                  }}
                />
              )}
              {/* Dot */}
              <span
                style={{
                  ...dotStyle,
                  ...(isCurrent
                    ? currentDotStyle
                    : isCompleted
                      ? completedDotStyle
                      : futureDotStyle),
                }}
              >
                {isCompleted && (
                  <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                    <path d="M2.5 6L5 8.5L9.5 3.5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </span>
              {/* Label */}
              <span
                style={{
                  ...labelStyle,
                  ...(isCurrent
                    ? currentLabelStyle
                    : isCompleted
                      ? completedLabelStyle
                      : futureLabelStyle),
                }}
              >
                {stage.label}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/* ---------- styles ---------- */

const wrapperStyle: CSSProperties = {
  backgroundColor: "#f8fafc",
  border: "1px solid #e2e8f0",
  borderRadius: "0.75rem",
  padding: "0.75rem 1.25rem",
  marginBottom: "1rem",
  overflowX: "auto",
};

const listStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  listStyle: "none",
  margin: 0,
  padding: 0,
  gap: 0,
};

const itemStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  flex: 1,
  minWidth: 0,
};

const connectorStyle: CSSProperties = {
  flex: 1,
  height: 2,
  minWidth: 12,
  borderRadius: 1,
};

const dotBase: CSSProperties = {
  flexShrink: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  width: 20,
  height: 20,
  borderRadius: "50%",
  transition: "background-color 0.15s",
};

const dotStyle: CSSProperties = { ...dotBase };

const currentDotStyle: CSSProperties = {
  backgroundColor: "#3b82f6",
  boxShadow: "0 0 0 3px rgba(59,130,246,0.25)",
};

const completedDotStyle: CSSProperties = {
  backgroundColor: "#3b82f6",
};

const futureDotStyle: CSSProperties = {
  backgroundColor: "#cbd5e1",
};

const labelStyle: CSSProperties = {
  marginLeft: 6,
  fontSize: "0.78rem",
  whiteSpace: "nowrap",
  lineHeight: 1.2,
};

const currentLabelStyle: CSSProperties = {
  color: "#1e40af",
  fontWeight: 600,
};

const completedLabelStyle: CSSProperties = {
  color: "#475569",
  fontWeight: 500,
};

const futureLabelStyle: CSSProperties = {
  color: "#94a3b8",
  fontWeight: 400,
};
