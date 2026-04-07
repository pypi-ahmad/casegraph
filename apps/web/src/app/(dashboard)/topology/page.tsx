import type { Metadata } from "next";

import TopologyClient from "./topology-client";

export const metadata: Metadata = { title: "Topology" };

export default function TopologyPage() {
  return <TopologyClient />;
}
