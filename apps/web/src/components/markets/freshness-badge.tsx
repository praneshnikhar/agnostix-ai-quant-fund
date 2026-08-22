"use client";

import { cn } from "@/lib/utils";
import type { FreshnessState } from "@/lib/markets-api";

const styles: Record<FreshnessState, string> = {
  fresh: "text-positive border-positive/40 bg-positive/10",
  stale: "text-warning border-warning/40 bg-warning/10",
  missing: "text-muted border-border bg-elevated",
  invalid: "text-negative border-negative/40 bg-negative/10",
};

const labels: Record<FreshnessState, string> = {
  fresh: "Fresh",
  stale: "Stale",
  missing: "Missing",
  invalid: "Invalid",
};

export function FreshnessBadge({
  state,
  datatype,
}: {
  state: FreshnessState;
  datatype?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-2xs font-medium uppercase tracking-wide",
        styles[state]
      )}
      title={datatype ? `${datatype}: ${state}` : state}
    >
      {datatype ? `${datatype}: ` : ""}
      {labels[state]}
    </span>
  );
}