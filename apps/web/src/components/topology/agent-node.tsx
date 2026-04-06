"use client";

import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";
import type { CSSProperties } from "react";
import type { AgentNodeData } from "@/lib/topology-transform";

export default function AgentNode({ data }: NodeProps) {
  const d = data as AgentNodeData;
  return (
    <div style={containerStyle}>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <div style={badgeStyle}>Agent</div>
      <div style={labelStyle}>{d.label}</div>
      {d.description && <div style={descStyle}>{d.description}</div>}
      {d.acceptedTaskTypes && d.acceptedTaskTypes.length > 0 && (
        <div style={chipRowStyle}>
          {d.acceptedTaskTypes.map((t: string) => (
            <span key={t} style={chipStyle}>
              {t}
            </span>
          ))}
        </div>
      )}
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </div>
  );
}

const containerStyle: CSSProperties = {
  padding: "12px 16px",
  borderRadius: "12px",
  border: "1.5px solid #6366f1",
  backgroundColor: "#ffffff",
  minWidth: 180,
  maxWidth: 260,
  fontFamily: "system-ui, sans-serif",
};

const badgeStyle: CSSProperties = {
  display: "inline-block",
  padding: "2px 8px",
  borderRadius: "6px",
  backgroundColor: "#eef2ff",
  color: "#4338ca",
  fontSize: "0.7rem",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  marginBottom: 6,
};

const labelStyle: CSSProperties = {
  fontWeight: 600,
  fontSize: "0.92rem",
  color: "#1e293b",
  marginBottom: 2,
};

const descStyle: CSSProperties = {
  fontSize: "0.78rem",
  color: "#64748b",
  lineHeight: 1.35,
  marginBottom: 6,
};

const chipRowStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 4,
  marginTop: 4,
};

const chipStyle: CSSProperties = {
  padding: "1px 6px",
  borderRadius: "4px",
  backgroundColor: "#f1f5f9",
  color: "#475569",
  fontSize: "0.68rem",
};

const handleStyle: CSSProperties = {
  width: 8,
  height: 8,
  backgroundColor: "#6366f1",
};
