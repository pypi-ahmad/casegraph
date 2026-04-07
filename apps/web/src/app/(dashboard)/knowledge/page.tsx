import type { Metadata } from "next";

import KnowledgeInspectorClient from "./knowledge-inspector-client";

export const metadata: Metadata = { title: "Knowledge Inspector" };

export default function KnowledgePage() {
  return <KnowledgeInspectorClient />;
}
