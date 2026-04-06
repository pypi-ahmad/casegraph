import HandoffClient from "./handoff-client";

export default async function HandoffPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <HandoffClient caseId={caseId} />;
}