import type { Metadata } from "next";
import { redirect } from "next/navigation";
import type { SessionUser } from "@casegraph/agent-sdk";
import { auth } from "@/lib/auth/config";
import HandoffClient from "./handoff-client";

export const metadata: Metadata = { title: "Handoff" };

export default async function HandoffPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const session = await auth();
  if (!session?.user) {
    redirect("/sign-in");
  }
  const { caseId } = await params;
  return <HandoffClient caseId={caseId} currentUser={session.user as SessionUser} />;
}