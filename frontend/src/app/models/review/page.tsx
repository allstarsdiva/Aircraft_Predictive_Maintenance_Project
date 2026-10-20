import type { Metadata } from "next";
import { ReviewView } from "@/components/models/review-view";

export const metadata: Metadata = { title: "Model review" };

export default function Page() {
  return <ReviewView />;
}
