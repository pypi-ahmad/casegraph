import { auth } from "@/lib/auth/config";
import { redirect } from "next/navigation";

import SignInForm from "./sign-in-form";

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; callbackUrl?: string }>;
}) {
  const session = await auth();
  if (session?.user) {
    redirect("/settings/providers");
  }

  const params = await searchParams;

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
          maxWidth: "420px",
          padding: "2.5rem",
          border: "1px solid #d9e0e8",
          borderRadius: "20px",
          backgroundColor: "#ffffff",
          boxShadow: "0 18px 45px rgba(15, 23, 42, 0.08)",
        }}
      >
        <h1
          style={{
            margin: 0,
            fontSize: "1.8rem",
            fontWeight: 700,
            color: "#102033",
          }}
        >
          CaseGraph
        </h1>
        <p
          style={{
            color: "#4f5f75",
            marginTop: "0.5rem",
            marginBottom: "1.5rem",
          }}
        >
          Sign in to continue.
        </p>

        {params.error && (
          <div
            style={{
              padding: "0.75rem 1rem",
              marginBottom: "1rem",
              borderRadius: "10px",
              backgroundColor: "#fff1f2",
              border: "1px solid #fecaca",
              color: "#9f1239",
              fontSize: "0.9rem",
            }}
          >
            Invalid credentials. Please try again.
          </div>
        )}

        <SignInForm callbackUrl={params.callbackUrl} />
      </section>
    </main>
  );
}
