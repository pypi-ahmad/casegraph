import CommunicationDraftsClient from "./communication-drafts-client";

export default async function CommunicationDraftsPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <CommunicationDraftsClient caseId={caseId} />;
}