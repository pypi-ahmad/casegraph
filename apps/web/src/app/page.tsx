import Link from "next/link";

export default function Home() {
  return (
    <main
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        padding: "2rem",
        backgroundColor: "#f5f7fa",
      }}
    >
      <section
        style={{
          width: "100%",
          maxWidth: "720px",
          padding: "2.5rem",
          border: "1px solid #d9e0e8",
          borderRadius: "20px",
          backgroundColor: "#ffffff",
          boxShadow: "0 18px 45px rgba(15, 23, 42, 0.08)",
        }}
      >
        <h1 style={{ margin: 0, fontSize: "2.5rem", fontWeight: 700, color: "#102033" }}>
          CaseGraph
        </h1>
        <p style={{ color: "#4f5f75", marginTop: "0.75rem", marginBottom: "1rem" }}>
          Local-first BYOK multi-agent platform.
        </p>
        <p style={{ color: "#5f6f84", lineHeight: 1.6, marginTop: 0 }}>
          The current foundation supports provider discovery for OpenAI, Anthropic, and
          Gemini, an agent runtime with registered agents and workflow definitions,
          document ingestion for readable PDFs and OCR-routed files, and a knowledge
          retrieval foundation with local vector search. Sign in to access internal tools.
        </p>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginTop: "1rem" }}>
          <Link
            href="/sign-in"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0.8rem 1.1rem",
              borderRadius: "999px",
              backgroundColor: "#102033",
              color: "#ffffff",
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            Sign in
          </Link>
          <Link
            href="/settings/providers"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0.8rem 1.1rem",
              borderRadius: "999px",
              border: "1px solid #c7d2e0",
              backgroundColor: "#ffffff",
              color: "#102033",
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            BYOK Settings
          </Link>
          <Link
            href="/runtime"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0.8rem 1.1rem",
              borderRadius: "999px",
              border: "1px solid #c7d2e0",
              backgroundColor: "#ffffff",
              color: "#102033",
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            Agents &amp; Workflows
          </Link>
          <Link
            href="/documents"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0.8rem 1.1rem",
              borderRadius: "999px",
              border: "1px solid #c7d2e0",
              backgroundColor: "#eef4fb",
              color: "#102033",
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            Documents
          </Link>
          <Link
            href="/knowledge"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0.8rem 1.1rem",
              borderRadius: "999px",
              border: "1px solid #c7d2e0",
              backgroundColor: "#eef4fb",
              color: "#102033",
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            Knowledge
          </Link>
        </div>
      </section>
    </main>
  );
}
