import type { Metadata } from "next";
import { AnalyticsView } from "@/components/fleet/analytics-view";

export const metadata: Metadata = { title: "Fleet analytics" };

export default function Page() {
  return <AnalyticsView />;
}
