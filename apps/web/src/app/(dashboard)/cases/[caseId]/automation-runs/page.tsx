import type { Metadata } from "next";
import { redirect } from "next/navigation";
import type { SessionUser } from "@casegraph/agent-sdk";
import { auth } from "@/lib/auth/config";
import AutomationRunClient from "./automation-run-client";

export const metadata: Metadata = { title: "Automation Runs" };

export default async function AutomationRunPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const session = await auth();
  if (!session?.user) {
    redirect("/sign-in");
  }
  const { caseId } = await params;
  return <AutomationRunClient caseId={caseId} currentUser={session.user as SessionUser} />;
}
