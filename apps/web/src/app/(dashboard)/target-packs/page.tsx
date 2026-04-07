import type { Metadata } from "next";

import TargetPacksClient from "./target-packs-client";

export const metadata: Metadata = { title: "Target Packs" };

export default function TargetPacksPage() {
  return <TargetPacksClient />;
}