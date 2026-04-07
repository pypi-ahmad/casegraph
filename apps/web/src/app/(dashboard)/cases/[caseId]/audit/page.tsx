import type { Metadata } from "next";

import AuditClient from "./audit-client";

export const metadata: Metadata = { title: "Audit Trail" };

export default async function CaseAuditPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <AuditClient caseId={caseId} />;
}