"use client";

import { signOut } from "next-auth/react";
import Link from "next/link";
import type { CSSProperties } from "react";

interface Props {
  user: { name?: string | null; email?: string | null };
}

export default function DashboardHeader({ user }: Props) {
  return (
    <header style={headerStyle}>
      <nav style={navStyle}>
        <Link href="/" style={logoStyle}>
          CaseGraph
        </Link>

        <div style={linksStyle}>
          <Link href="/settings/providers" style={linkStyle}>
            Providers
          </Link>
          <Link href="/cases" style={linkStyle}>
            Cases
          </Link>
          <Link href="/work" style={linkStyle}>
            Work
          </Link>
          <Link href="/queue" style={linkStyle}>
            Queue
          </Link>
          <Link href="/runtime" style={linkStyle}>
            Runtime <span style={scaffoldedTagStyle}>scaffolded</span>
          </Link>
          <Link href="/documents" style={linkStyle}>
            Documents
          </Link>
          <Link href="/knowledge" style={linkStyle}>
            Knowledge
          </Link>
          <Link href="/topology" style={linkStyle}>
            Topology <span style={scaffoldedTagStyle}>scaffolded</span>
          </Link>
          <Link href="/evals" style={linkStyle}>
            Evals
          </Link>
          <Link href="/automation" style={linkStyle}>
            Automation <span style={scaffoldedTagStyle}>scaffolded</span>
          </Link>
          <Link href="/tasks" style={linkStyle}>
            Tasks
          </Link>
          <Link href="/rag" style={linkStyle}>
            RAG
          </Link>
          <Link href="/extraction" style={linkStyle}>
            Extraction
          </Link>
          <Link href="/domain-packs" style={linkStyle}>
            Domain Packs
          </Link>
          <Link href="/target-packs" style={linkStyle}>
            Target Packs
          </Link>
        </div>
      </nav>

      <div style={userAreaStyle}>
        <span style={userNameStyle}>{user.name ?? user.email}</span>
        <button
          type="button"
          onClick={() => signOut({ callbackUrl: "/" })}
          style={signOutStyle}
        >
          Sign out
        </button>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ */
/* Styles                                                              */
/* ------------------------------------------------------------------ */

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "0 1.5rem",
  height: "56px",
  borderBottom: "1px solid #e2e8f0",
  backgroundColor: "#ffffff",
};

const navStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "2rem",
};

const logoStyle: CSSProperties = {
  fontWeight: 700,
  fontSize: "1.1rem",
  color: "#102033",
  textDecoration: "none",
};

const linksStyle: CSSProperties = {
  display: "flex",
  gap: "1.25rem",
};

const linkStyle: CSSProperties = {
  fontSize: "0.9rem",
  color: "#475569",
  textDecoration: "none",
  fontWeight: 500,
};

const userAreaStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "1rem",
};

const userNameStyle: CSSProperties = {
  fontSize: "0.85rem",
  color: "#64748b",
};

const signOutStyle: CSSProperties = {
  padding: "0.4rem 0.85rem",
  borderRadius: "999px",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  color: "#475569",
  fontSize: "0.85rem",
  cursor: "pointer",
  fontWeight: 500,
};

const scaffoldedTagStyle: CSSProperties = {
  display: "inline-block",
  padding: "0.05rem 0.3rem",
  borderRadius: "3px",
  backgroundColor: "#fef3c7",
  color: "#92400e",
  fontSize: "0.6rem",
  fontWeight: 600,
  verticalAlign: "super",
  lineHeight: 1,
};
