import DocumentReviewClient from "./document-review-client";

interface Props {
  params: Promise<{ documentId: string }>;
}

export default async function DocumentReviewPage({ params }: Props) {
  const { documentId } = await params;
  return <DocumentReviewClient documentId={documentId} />;
}
