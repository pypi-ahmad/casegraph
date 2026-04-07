import type { Metadata } from "next";

import DocumentIngestionClient from "./document-ingestion-client";

export const metadata: Metadata = { title: "Documents" };

export default function DocumentsPage() {
  return <DocumentIngestionClient />;
}
