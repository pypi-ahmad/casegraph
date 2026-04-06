import ReleasesClient from "./releases-client";

export default async function ReleasesPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <ReleasesClient caseId={caseId} />;
}
