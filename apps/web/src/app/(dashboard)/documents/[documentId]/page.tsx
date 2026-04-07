import type { Metadata } from "next";

import DocumentReviewClient from "./document-review-client";

export const metadata: Metadata = { title: "Document Review" };

interface Props {
  params: Promise<{ documentId: string }>;
}

export default async function DocumentReviewPage({ params }: Props) {
  const { documentId } = await params;
  return <DocumentReviewClient documentId={documentId} />;
}
