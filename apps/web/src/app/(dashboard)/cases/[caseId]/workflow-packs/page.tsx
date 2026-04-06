import WorkflowPackClient from "./workflow-packs-client";

export default async function WorkflowPackPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <WorkflowPackClient caseId={caseId} />;
}
