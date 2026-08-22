"use client";

import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/lib/api";
import {
  Badge,
  EmptyState,
  MetricTile,
  Panel,
  PanelHeader,
  Skeleton,
} from "@/components/ui";

/**
 * Dashboard foundation — structurally answers the five questions from
 * documents/16_Design_System_Direction.md §2:
 *   1. How is the fund doing?      → KPI strip
 *   2. What is the AI doing?       → AI activity panel
 *   3. What does it want to trade? → intended trades panel
 *   4. Why?                        → evidence/thesis link (M2+)
 *   5. How risky is it?            → risk panel
 *
 * M0 shows NO fabricated data: every metric renders an explicit
 * "awaiting first data" state until its milestone populates it.
 */

export default function DashboardPage() {
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold">Fund Overview</h1>
        <Badge tone={health?.status === "healthy" ? "positive" : "warning"}>
          {health ? `API ${health.status}` : "API connecting…"}
        </Badge>
      </div>

      {/* Q1 — How is the fund doing? */}
      <section aria-label="fund performance">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
          {["NAV", "Daily P&L", "MTD", "YTD", "Sharpe", "Sortino", "Drawdown"].map(
            (label) => (
              <MetricTile key={label} label={label} loading />
            )
          )}
        </div>
        <p className="mt-1 text-2xs text-subtle">
          Portfolio metrics populate at M6/M7 (portfolio engine + paper execution).
        </p>
      </section>

      <div className="grid gap-3 lg:grid-cols-3">
        {/* Q2 — What is the AI doing? */}
        <Panel className="lg:col-span-1">
          <PanelHeader title="AI Activity" />
          <EmptyState
            title="No agent activity yet"
            description="Research and strategy agents come online in M2–M3."
          />
        </Panel>

        {/* Q3/Q4 — What does it want to trade? Why? */}
        <Panel className="lg:col-span-1">
          <PanelHeader title="Intended Trades" />
          <EmptyState
            title="No proposals"
            description="Signal agents begin producing proposals in M3; each will carry evidence and a thesis."
          />
        </Panel>

        {/* Q5 — How risky is it? */}
        <Panel className="lg:col-span-1">
          <PanelHeader title="Risk" />
          <div className="space-y-2 p-3">
            {["Gross exposure", "Net exposure", "VaR", "Concentration"].map((k) => (
              <div key={k} className="flex items-center justify-between">
                <span className="text-xs text-muted">{k}</span>
                <Skeleton className="h-3 w-12" />
              </div>
            ))}
            <p className="pt-1 text-2xs text-subtle">
              Deterministic risk engine arrives in M5.
            </p>
          </div>
        </Panel>
      </div>
    </div>
  );
}