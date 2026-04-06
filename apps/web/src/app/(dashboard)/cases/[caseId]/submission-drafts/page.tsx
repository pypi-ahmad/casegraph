import SubmissionDraftsClient from "./submission-drafts-client";

export default async function SubmissionDraftsPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <SubmissionDraftsClient caseId={caseId} />;
}