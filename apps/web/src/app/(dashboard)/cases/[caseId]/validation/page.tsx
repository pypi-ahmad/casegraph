import type { Metadata } from "next";

import ValidationClient from "./validation-client";

export const metadata: Metadata = { title: "Validation" };

export default async function CaseValidationPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <ValidationClient caseId={caseId} />;
}
