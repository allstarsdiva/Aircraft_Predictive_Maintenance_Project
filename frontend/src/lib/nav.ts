import {
  Activity,
  BrainCircuit,
  ChartNoAxesColumn,
  ClipboardList,
  LayoutDashboard,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";

export type Workspace = "monitor" | "models";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const WORKSPACES: { key: Workspace; label: string; href: string }[] = [
  { key: "monitor", label: "Monitor", href: "/" },
  { key: "models", label: "Models", href: "/models/predict" },
];

export const NAV: Record<Workspace, NavGroup[]> = {
  monitor: [
    {
      label: "Fleet (simulated)",
      items: [
        { href: "/", label: "Overview", icon: LayoutDashboard },
        { href: "/analytics", label: "Analytics", icon: ChartNoAxesColumn },
        { href: "/maintenance", label: "Maintenance", icon: ClipboardList },
      ],
    },
  ],
  models: [
    {
      label: "Trained models",
      items: [
        { href: "/models/predict", label: "AI predictions", icon: BrainCircuit },
        { href: "/models/coverage", label: "Model coverage", icon: Activity },
        { href: "/models/review", label: "Model review", icon: ShieldAlert },
      ],
    },
  ],
};

export function workspaceForPath(pathname: string): Workspace {
  return pathname.startsWith("/models") ? "models" : "monitor";
}

export function isNavActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
