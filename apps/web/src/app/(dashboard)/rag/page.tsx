import type { Metadata } from "next";

import RagLabClient from "./rag-lab-client";

export const metadata: Metadata = { title: "RAG Lab" };

export default function RagLabPage() {
  return <RagLabClient />;
}
