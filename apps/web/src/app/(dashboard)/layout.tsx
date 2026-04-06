import type { ReactNode } from "react";

import { auth } from "@/lib/auth/config";
import { redirect } from "next/navigation";

import DashboardHeader from "./dashboard-header";

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  const session = await auth();
  if (!session?.user) {
    redirect("/sign-in");
  }

  return (
    <>
      <DashboardHeader user={session.user} />
      {children}
    </>
  );
}
