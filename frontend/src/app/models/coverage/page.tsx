import type { Metadata } from "next";
import { CoverageView } from "@/components/models/coverage-view";

export const metadata: Metadata = { title: "Model coverage" };

export default function Page() {
  return <CoverageView />;
}
