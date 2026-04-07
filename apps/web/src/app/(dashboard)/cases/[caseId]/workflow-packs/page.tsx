import type { Metadata } from "next";
import { redirect } from "next/navigation";
import type { SessionUser } from "@casegraph/agent-sdk";
import { auth } from "@/lib/auth/config";

import WorkflowPackClient from "./workflow-packs-client";

export const metadata: Metadata = { title: "Workflow Packs" };

export default async function WorkflowPackPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const session = await auth();
  if (!session?.user) {
    redirect("/sign-in");
  }
  const { caseId } = await params;
  return <WorkflowPackClient caseId={caseId} currentUser={session.user as SessionUser} />;
}
