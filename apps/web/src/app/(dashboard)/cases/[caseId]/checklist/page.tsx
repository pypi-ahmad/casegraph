import { redirect } from "next/navigation";
import { auth } from "@/lib/auth/config";
import CaseChecklistClient from "./case-checklist-client";

export default async function CaseChecklistPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const session = await auth();
  if (!session?.user) redirect("/sign-in");
  const { caseId } = await params;
  return <CaseChecklistClient caseId={caseId} />;
}
