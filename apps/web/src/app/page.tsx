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
          Your case processing workspace.
        </p>
        <p style={{ color: "#5f6f84", lineHeight: 1.6, marginTop: 0 }}>
          Process cases, review documents, validate extracted information, and prepare
          submissions — with full human oversight at every step. Sign in to continue.
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
            href="/cases"
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
            Cases
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
        </div>
      </section>
    </main>
  );
}
