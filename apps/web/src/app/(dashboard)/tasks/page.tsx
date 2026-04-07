import type { Metadata } from "next";

import TaskLabClient from "./task-lab-client";

export const metadata: Metadata = { title: "Task Lab" };

export default function TaskLabPage() {
  return <TaskLabClient />;
}
