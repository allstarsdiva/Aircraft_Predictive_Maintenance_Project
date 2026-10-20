import type { Metadata } from "next";
import { MaintenanceView } from "@/components/fleet/maintenance-view";

export const metadata: Metadata = { title: "Maintenance center" };

export default function Page() {
  return <MaintenanceView />;
}
