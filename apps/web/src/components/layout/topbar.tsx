"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { getHealth } from "@/lib/api";
import { StatusDot } from "@/components/ui";

/** Top header: market status, system status, command/search affordance. */
export function Topbar() {
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
  });

  const systemStatus =
    health?.status === "healthy"
      ? "ok"
      : health?.status === "degraded"
        ? "warn"
        : "error";

  return (
    <header className="flex h-11 items-center justify-between border-b border-border bg-surface px-4">
      <div className="flex items-center gap-4">
        {/* Market status — real state arrives with M1; idle until then. */}
        <span className="flex items-center gap-1.5 text-2xs text-muted">
          <StatusDot status="idle" /> MARKET
        </span>
        <span className="flex items-center gap-1.5 text-2xs text-muted">
          <StatusDot status={systemStatus} />
          SYSTEM {health ? `· ${health.status.toUpperCase()}` : ""}
        </span>
      </div>
      <button className="flex items-center gap-2 rounded border border-border bg-elevated px-2 py-1 text-2xs text-subtle hover:border-border-strong">
        <Search className="h-3 w-3" />
        Search… <kbd className="tnum text-[10px]">⌘K</kbd>
      </button>
    </header>
  );
}