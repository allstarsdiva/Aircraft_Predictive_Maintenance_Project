import type { Metadata } from "next";
import { AircraftView } from "@/components/fleet/aircraft-view";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id } = await params;
  return { title: `Aircraft ${id}` };
}

export default async function Page({ params }: { params: Params }) {
  const { id } = await params;
  return <AircraftView id={id} />;
}
