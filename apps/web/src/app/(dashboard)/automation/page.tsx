import type { Metadata } from "next";

import AutomationClient from "./automation-client";

export const metadata: Metadata = { title: "Automation" };

export default function AutomationPage() {
  return <AutomationClient />;
}
