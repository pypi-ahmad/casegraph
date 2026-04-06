import CasePacketsClient from "./case-packets-client";

export default async function CasePacketsPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <CasePacketsClient caseId={caseId} />;
}
