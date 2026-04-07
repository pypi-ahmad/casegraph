import type { Metadata } from "next";

import ExtractionLabClient from "./extraction-lab-client";

export const metadata: Metadata = { title: "Extraction Lab" };

export default function ExtractionLabPage() {
  return <ExtractionLabClient />;
}
