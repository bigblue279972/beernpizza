import { getSports } from "@/lib/actions/sports";
import { SettingsPageClient } from "./SettingsPageClient";

export default async function SettingsPage() {
  const sports = await getSports(true);
  return <SettingsPageClient sports={sports} />;
}
