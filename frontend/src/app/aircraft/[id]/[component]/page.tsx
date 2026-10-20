import type { Metadata } from "next";
import { ComponentView } from "@/components/fleet/component-view";

type Params = Promise<{ id: string; component: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id, component } = await params;
  return { title: `${component.replace(/-/g, " ")} · ${id}` };
}

export default async function Page({ params }: { params: Params }) {
  const { id, component } = await params;
  return <ComponentView id={id} slug={component} />;
}
