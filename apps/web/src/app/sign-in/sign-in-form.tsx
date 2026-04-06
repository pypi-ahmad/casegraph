"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import type { CSSProperties, FormEvent } from "react";

export default function SignInForm({
  callbackUrl,
}: {
  callbackUrl?: string;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    await signIn("credentials", {
      email,
      password,
      callbackUrl: callbackUrl || "/settings/providers",
    });
    // signIn redirects on success; on failure it redirects back with ?error
    setLoading(false);
  }

  return (
    <form onSubmit={handleSubmit} style={formStyle}>
      <label style={fieldStyle}>
        <span style={labelStyle}>Email</span>
        <input
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={inputStyle}
          placeholder="admin@local.dev"
        />
      </label>

      <label style={fieldStyle}>
        <span style={labelStyle}>Password</span>
        <input
          type="password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={inputStyle}
          placeholder="••••••••"
        />
      </label>

      <button type="submit" disabled={loading} style={buttonStyle}>
        {loading ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}

/* ------------------------------------------------------------------ */
/* Styles                                                              */
/* ------------------------------------------------------------------ */

const formStyle: CSSProperties = { display: "grid", gap: "1rem" };
const fieldStyle: CSSProperties = { display: "grid", gap: "0.35rem" };
const labelStyle: CSSProperties = {
  fontSize: "0.9rem",
  fontWeight: 600,
  color: "#334155",
};
const inputStyle: CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "0.85rem",
  border: "1px solid #cbd5e1",
  borderRadius: "12px",
  backgroundColor: "#ffffff",
  fontSize: "0.95rem",
};
const buttonStyle: CSSProperties = {
  marginTop: "0.5rem",
  padding: "0.9rem",
  borderRadius: "999px",
  border: "none",
  backgroundColor: "#102033",
  color: "#ffffff",
  fontWeight: 600,
  fontSize: "1rem",
  cursor: "pointer",
};
