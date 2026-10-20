import type { Metadata } from "next";
import { PredictView } from "@/components/models/predict-view";

export const metadata: Metadata = { title: "AI predictions" };

export default function Page() {
  return <PredictView />;
}
