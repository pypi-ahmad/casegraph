import AuditClient from "./audit-client";

export default async function CaseAuditPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <AuditClient caseId={caseId} />;
}