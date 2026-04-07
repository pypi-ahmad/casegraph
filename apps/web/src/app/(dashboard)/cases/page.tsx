import type { Metadata } from "next";

import CasesClient from "./cases-client";

export const metadata: Metadata = { title: "Cases" };

export default function CasesPage() {
  return <CasesClient />;
}