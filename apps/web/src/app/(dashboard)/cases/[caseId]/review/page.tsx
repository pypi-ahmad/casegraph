import type { Metadata } from "next";

import CaseReviewClient from "./case-review-client";

export const metadata: Metadata = { title: "Case Review" };

export default async function CaseReviewPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <CaseReviewClient caseId={caseId} />;
}