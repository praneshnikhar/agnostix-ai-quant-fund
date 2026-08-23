"use client";

/**
 * Core design-system primitives (M0).
 * Institutional dark terminal aesthetic: restrained borders, small radii,
 * semantic status colors, tabular numerals. No gradients, no neon.
 *
 * NOTE: intentionally consolidated in one module while small; split into
 * individual files as each primitive grows (see DESIGN_SYSTEM.md).
 */

import { forwardRef } from "react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ Panel */

export function Panel({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-md border border-border bg-surface",
        className
      )}
      {...props}
    />
  );
}

export function PanelHeader({
  title,
  actions,
  className,
}: {
  title: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-between border-b border-border px-3 py-2",
        className
      )}
    >
      <h2 className="text-2xs font-medium uppercase tracking-wider text-muted">
        {title}
      </h2>
      {actions}
    </div>
  );
}

/* ----------------------------------------------------------------- Button */

type ButtonVariant = "default" | "ghost" | "danger" | "positive";
type ButtonSize = "sm" | "md";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const buttonVariants: Record<ButtonVariant, string> = {
  default:
    "bg-elevated text-foreground border border-border hover:border-border-strong",
  ghost: "bg-transparent text-muted hover:text-foreground",
  danger:
    "bg-transparent text-negative border border-negative/40 hover:bg-negative/10",
  positive:
    "bg-transparent text-positive border border-positive/40 hover:bg-positive/10",
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-7 px-2.5 text-xs",
  md: "h-8 px-3 text-sm",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "md", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center rounded font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
        buttonVariants[variant],
        buttonSizes[size],
        className
      )}
      {...props}
    />
  )
);
Button.displayName = "Button";

/* ------------------------------------------------------------------ Badge */

export type BadgeTone =
  | "neutral"
  | "positive"
  | "negative"
  | "warning"
  | "info"
  | "accent";

const badgeTones: Record<BadgeTone, string> = {
  neutral: "border-border text-muted",
  positive: "border-positive/40 text-positive",
  negative: "border-negative/40 text-negative",
  warning: "border-warning/40 text-warning",
  info: "border-info/40 text-info",
  accent: "border-accent/40 text-accent",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-2xs font-medium uppercase tracking-wide",
        badgeTones[tone],
        className
      )}
      {...props}
    />
  );
}

/* -------------------------------------------------------------- StatusDot */

export function StatusDot({
  status,
  className,
}: {
  status: "ok" | "error" | "warn" | "idle";
  className?: string;
}) {
  const color = {
    ok: "bg-positive",
    error: "bg-negative",
    warn: "bg-warning",
    idle: "bg-subtle",
  }[status];
  return (
    <span
      role="status"
      aria-label={`status: ${status}`}
      className={cn("inline-block h-1.5 w-1.5 rounded-full", color, className)}
    />
  );
}

/* ------------------------------------------------------------ MetricTile */

export function MetricTile({
  label,
  value,
  delta,
  deltaTone,
  loading,
}: {
  label: string;
  value?: string;
  delta?: string;
  deltaTone?: BadgeTone;
  loading?: boolean;
}) {
  return (
    <Panel className="px-3 py-2.5">
      <div className="text-2xs uppercase tracking-wider text-subtle">
        {label}
      </div>
      <div className="mt-1 flex items-baseline gap-2">
        {loading || value === undefined ? (
          <Skeleton className="h-5 w-20" />
        ) : (
          <span className="tnum text-lg font-semibold">{value}</span>
        )}
        {delta && !loading ? (
          <Badge tone={deltaTone ?? "neutral"}>{delta}</Badge>
        ) : null}
      </div>
    </Panel>
  );
}

/* --------------------------------------------------------------- Skeleton */

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("animate-pulse rounded bg-elevated", className)}
    />
  );
}

/* ------------------------------------------------------------- EmptyState */

export function EmptyState({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 px-6 py-12 text-center">
      <p className="text-sm font-medium text-muted">{title}</p>
      {description ? (
        <p className="max-w-md text-xs text-subtle">{description}</p>
      ) : null}
    </div>
  );
}

export function SectionHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: React.ReactNode }) {
  return <div className="flex flex-wrap items-end justify-between gap-3">
    <div>
      {eyebrow ? <p className="text-2xs uppercase tracking-[0.18em] text-accent">{eyebrow}</p> : null}
      <h1 className="mt-1 text-lg font-semibold tracking-tight text-foreground">{title}</h1>
      {description ? <p className="mt-1 max-w-2xl text-xs text-muted">{description}</p> : null}
    </div>
    {actions}
  </div>;
}

export function ErrorState({ title = "Unable to load data", description }: { title?: string; description?: string }) {
  return <div role="alert" className="flex flex-col items-center justify-center gap-1 px-6 py-12 text-center">
    <p className="text-sm font-medium text-negative">{title}</p>
    <p className="max-w-md text-xs text-muted">{description ?? "The service may be unavailable. Try again when the backend is reachable."}</p>
  </div>;
}

export function LoadingState({ label = "Loading data…" }: { label?: string }) {
  return <div role="status" className="space-y-3 px-4 py-5">
    <Skeleton className="h-3 w-32" />
    <Skeleton className="h-3 w-2/3" />
    <p className="text-2xs text-subtle">{label}</p>
  </div>;
}

export function ConfidenceIndicator({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-subtle">unavailable</span>;
  return <span className="tnum text-muted">{(value * 100).toFixed(0)}%</span>;
}

export function ModelBadge({ provider, model }: { provider?: string | null; model?: string | null }) {
  if (!provider && !model) return <Badge>not connected</Badge>;
  return <Badge tone="info">{provider ?? "provider unavailable"}{model ? ` / ${model}` : ""}</Badge>;
}

export function DataQualityBadge({ state }: { state: string | null | undefined }) {
  const normalized = (state ?? "unavailable").toLowerCase();
  const tone = normalized === "fresh" || normalized === "ok" ? "positive" : normalized === "stale" || normalized === "incomplete" ? "warning" : normalized === "invalid" ? "negative" : "neutral";
  return <Badge tone={tone}>{normalized === "unavailable" ? "not connected" : normalized}</Badge>;
}

export function EvidenceItem({ id, source, sourceType, claim, period, href }: { id: string; source: string; sourceType: string; claim: string; period?: string | null; href?: string | null }) {
  return <li className="border-b border-border/50 px-3 py-3 last:border-0"><div className="flex flex-wrap items-center gap-2 text-xs"><span className="font-mono text-accent">{id}</span><span className="text-subtle">{sourceType}</span><span className="text-foreground">{source}</span>{period ? <span className="text-2xs text-subtle">{period}</span> : null}{href ? <a href={href} target="_blank" rel="noreferrer" className="text-2xs text-accent hover:underline">source ↗</a> : null}</div><p className="mt-1 text-xs leading-relaxed text-muted">{claim}</p></li>;
}
