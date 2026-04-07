import type { Metadata } from "next";

import CasePacketsClient from "./case-packets-client";

export const metadata: Metadata = { title: "Packets" };

export default async function CasePacketsPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <CasePacketsClient caseId={caseId} />;
}
