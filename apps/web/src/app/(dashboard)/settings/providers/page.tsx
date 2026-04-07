import type { Metadata } from "next";

import ProviderSettingsClient from "./provider-settings-client";

export const metadata: Metadata = { title: "Provider Settings" };

export default function ProviderSettingsPage() {
  return <ProviderSettingsClient />;
}