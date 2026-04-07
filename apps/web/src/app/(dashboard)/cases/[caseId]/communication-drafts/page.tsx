import { redirect } from "next/navigation";
import type { SessionUser } from "@casegraph/agent-sdk";
import { auth } from "@/lib/auth/config";
import CommunicationDraftsClient from "./communication-drafts-client";

export default async function CommunicationDraftsPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const session = await auth();
  if (!session?.user) {
    redirect("/sign-in");
  }
  const { caseId } = await params;
  return <CommunicationDraftsClient caseId={caseId} currentUser={session.user as SessionUser} />;
}