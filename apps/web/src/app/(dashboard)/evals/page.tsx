import type { Metadata } from "next";

import EvalsClient from "./evals-client";

export const metadata: Metadata = { title: "Evaluations" };

export default function EvalsPage() {
  return <EvalsClient />;
}
