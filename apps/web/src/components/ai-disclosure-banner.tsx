import type { CSSProperties } from "react";

const bannerStyle: CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  gap: "0.5rem",
  padding: "0.625rem 1rem",
  backgroundColor: "#fffbeb",
  border: "1px solid #f59e0b",
  borderRadius: "0.5rem",
  marginBottom: "1rem",
  fontSize: "0.85rem",
  lineHeight: 1.5,
  color: "#92400e",
};

const iconStyle: CSSProperties = {
  flexShrink: 0,
  fontSize: "1rem",
  lineHeight: 1,
  marginTop: "0.1rem",
};

export default function AiDisclosureBanner() {
  return (
    <div role="status" style={bannerStyle}>
      <span aria-hidden="true" style={iconStyle}>⚠️</span>
      <span>
        <strong>AI-generated content</strong> — outputs on this page were
        produced by automated processing. Review all results against source
        documents before taking action.
      </span>
    </div>
  );
}
