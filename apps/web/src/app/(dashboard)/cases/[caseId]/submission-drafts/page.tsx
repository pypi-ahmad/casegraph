import type { Metadata } from "next";
import { redirect } from "next/navigation";
import type { SessionUser } from "@casegraph/agent-sdk";
import { auth } from "@/lib/auth/config";
import SubmissionDraftsClient from "./submission-drafts-client";

export const metadata: Metadata = { title: "Submission Drafts" };

export default async function SubmissionDraftsPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const session = await auth();
  if (!session?.user) {
    redirect("/sign-in");
  }
  const { caseId } = await params;
  return <SubmissionDraftsClient caseId={caseId} currentUser={session.user as SessionUser} />;
}