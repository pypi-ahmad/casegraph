import { redirect } from "next/navigation";
import type { SessionUser } from "@casegraph/agent-sdk";
import { auth } from "@/lib/auth/config";
import ReleasesClient from "./releases-client";

export default async function ReleasesPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const session = await auth();
  if (!session?.user) {
    redirect("/sign-in");
  }
  const { caseId } = await params;
  return <ReleasesClient caseId={caseId} currentUser={session.user as SessionUser} />;
}
