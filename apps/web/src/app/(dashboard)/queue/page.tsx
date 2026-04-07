import type { Metadata } from "next";

import OperatorQueueClient from "./operator-queue-client";

export const metadata: Metadata = { title: "Operator Queue" };

export default function OperatorQueuePage() {
  return <OperatorQueueClient />;
}