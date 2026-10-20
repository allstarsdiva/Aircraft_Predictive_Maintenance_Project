import type { Metadata } from "next";
import { OverviewView } from "@/components/fleet/overview-view";

export const metadata: Metadata = { title: "Fleet overview" };

export default function Page() {
  return <OverviewView />;
}
