import type { Metadata } from "next";
import { redirect } from "next/navigation";

import type { SessionUser } from "@casegraph/agent-sdk";

import { auth } from "@/lib/auth/config";

import WorkClient from "./work-client";

export const metadata: Metadata = { title: "My Work" };

export default async function WorkPage() {
  const session = await auth();
  if (!session?.user) {
    redirect("/sign-in");
  }

  return <WorkClient currentUser={session.user as SessionUser} />;
}
