import CaseReviewClient from "./case-review-client";

export default async function CaseReviewPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <CaseReviewClient caseId={caseId} />;
}