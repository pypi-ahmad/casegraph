import { redirect } from "next/navigation";

import type { SessionUser } from "@casegraph/agent-sdk";

import { auth } from "@/lib/auth/config";

import CaseDetailClient from "./case-detail-client";

export default async function CaseDetailPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const session = await auth();
  if (!session?.user) {
    redirect("/sign-in");
  }

  const { caseId } = await params;
  return <CaseDetailClient caseId={caseId} currentUser={session.user as SessionUser} />;
}