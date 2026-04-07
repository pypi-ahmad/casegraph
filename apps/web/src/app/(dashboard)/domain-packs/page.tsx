import type { Metadata } from "next";

import DomainPackExplorerClient from "./domain-packs-client";

export const metadata: Metadata = { title: "Domain Packs" };

export default function DomainPacksPage() {
  return <DomainPackExplorerClient />;
}
