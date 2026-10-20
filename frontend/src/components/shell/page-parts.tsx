import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Info } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { DANGER, SERIES, TRACK } from "@/lib/viz";

/** Title block every page opens with: name, one line, controls on the right. */
export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
  className,
}: {
  title: string;
  description?: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-3 pb-5 md:flex-row md:items-start md:justify-between", className)}>
      <div className="min-w-0">
        {eyebrow ? <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{eyebrow}</div> : null}
        <h1 className="font-display text-[28px] font-semibold leading-tight tracking-tight text-foreground">{title}</h1>
        {description ? <p className="mt-1 max-w-3xl text-[13px] text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/** Standard content padding shared by every page. */
export function PageBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mx-auto w-full max-w-[1600px] px-4 py-6 md:px-6", className)}>{children}</div>;
}

/** Card section with a small heading row. */
export function Section({
  title,
  description,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <Card className={cn("flex flex-col", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pb-3 pt-4">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-foreground">{title}</div>
          {description ? <div className="mt-0.5 text-[12px] text-muted-foreground">{description}</div> : null}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>
      <div className={cn("flex-1 px-5 pb-5", bodyClassName)}>{children}</div>
    </Card>
  );
}

/**
 * One KPI: label (+ optional info tooltip) and a neutral glyph chip on top,
 * the value large beneath. `value` arrives preformatted.
 */
export function StatCard({
  label,
  value,
  sub,
  hint,
  icon: Icon,
  footer,
  className,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  hint?: string;
  icon?: LucideIcon;
  footer?: ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("p-4", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-1.5">
          <span className="text-[13px] text-muted-foreground">{label}</span>
          {hint ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" aria-label={`About ${label}`} className="text-muted-foreground/70 transition-colors hover:text-foreground focus-visible:outline-none">
                  <Info className="h-3.5 w-3.5" />
                </button>
              </TooltipTrigger>
              <TooltipContent>{hint}</TooltipContent>
            </Tooltip>
          ) : null}
        </div>
        {Icon ? (
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted text-foreground">
            <Icon className="h-4 w-4" />
          </span>
        ) : null}
      </div>
      <div className="mt-2.5 min-w-0 truncate font-display text-[26px] font-semibold leading-none tracking-tight text-foreground">{value}</div>
      {sub ? <div className="mt-1.5 text-[12px] text-muted-foreground">{sub}</div> : null}
      {footer ? <div className="mt-3">{footer}</div> : null}
    </Card>
  );
}

/** Label/value pair for dense detail rows. */
export function Metric({ label, value, className }: { label: string; value: ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="mt-0.5 font-display text-xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-muted text-ink-4">
        <Icon className="h-5 w-5" />
      </span>
      <div className="font-display text-base font-semibold">{title}</div>
      {children ? <div className="mt-1 max-w-sm text-[13px] text-muted-foreground">{children}</div> : null}
    </div>
  );
}

/** Small progress track for 0-100 values (flat colour, no gradient). */
export function MiniBar({ value, danger = false, color }: { value: number; danger?: boolean; color?: string }) {
  return (
    <div className="h-1.5 overflow-hidden rounded-full" style={{ background: TRACK }}>
      <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: color ?? (danger ? DANGER : SERIES) }} />
    </div>
  );
}

