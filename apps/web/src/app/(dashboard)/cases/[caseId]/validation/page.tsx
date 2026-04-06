import ValidationClient from "./validation-client";

export default async function CaseValidationPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <ValidationClient caseId={caseId} />;
}
