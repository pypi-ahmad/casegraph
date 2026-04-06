import AutomationRunClient from "./automation-run-client";

export default async function AutomationRunPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <AutomationRunClient caseId={caseId} />;
}
