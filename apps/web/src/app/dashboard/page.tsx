"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getAgentEvents, getHealth } from "@/lib/api";
import { getMarkets } from "@/lib/markets-api";
import { Badge, EmptyState, ErrorState, LoadingState, MetricTile, Panel, PanelHeader, SectionHeader, StatusDot } from "@/components/ui";

export default function DashboardPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth, refetchInterval: 30_000 });
  const markets = useQuery({ queryKey: ["markets"], queryFn: getMarkets, refetchInterval: 60_000 });
  const events = useQuery({ queryKey: ["agent-events", 20], queryFn: () => getAgentEvents(20), refetchInterval: 30_000 });
  const status = health.data?.status;

  return <div className="space-y-5">
    <SectionHeader eyebrow="AGNOSTIX / OPERATING CONSOLE" title="Command Center" description="A factual view of market coverage, research operations, and system health. Unavailable capabilities remain explicitly unconnected." actions={<Badge tone={status === "healthy" ? "positive" : status ? "warning" : "neutral"}>{status ? `API ${status}` : "API unavailable"}</Badge>} />
    <section aria-label="market and system state" className="grid gap-3 md:grid-cols-3">
      <Panel className="p-3"><div className="flex items-center justify-between"><span className="text-2xs uppercase tracking-wider text-subtle">Market coverage</span><StatusDot status={markets.data ? "ok" : markets.isError ? "error" : "idle"} /></div><p className="mt-2 tnum text-xl font-semibold">{markets.data?.watchlist.length ?? "—"}</p><p className="mt-1 text-xs text-muted">{markets.data ? "securities in configured watchlist" : "awaiting market API"}</p></Panel>
      <Panel className="p-3"><div className="flex items-center justify-between"><span className="text-2xs uppercase tracking-wider text-subtle">Data health</span><StatusDot status={health.data?.database && health.data.redis ? "ok" : health.data ? "warn" : "idle"} /></div><p className="mt-2 text-xl font-semibold">{health.data ? health.data.status.toUpperCase() : "—"}</p><p className="mt-1 text-xs text-muted">Database and Redis readiness from /health</p></Panel>
      <Panel className="p-3"><div className="flex items-center justify-between"><span className="text-2xs uppercase tracking-wider text-subtle">Agent events</span><StatusDot status={events.data ? "ok" : events.isError ? "error" : "idle"} /></div><p className="mt-2 tnum text-xl font-semibold">{events.data?.length ?? "—"}</p><p className="mt-1 text-xs text-muted">latest append-only events returned</p></Panel>
    </section>
    <section aria-label="fund performance unavailable"><div className="grid grid-cols-2 gap-3 md:grid-cols-4"><MetricTile label="NAV" /><MetricTile label="P&L" /><MetricTile label="Positions" /><MetricTile label="Drawdown" /></div><p className="mt-1 text-2xs text-subtle">Portfolio and execution APIs are not connected. No financial values are inferred.</p></section>
    <div className="grid gap-3 xl:grid-cols-2"><Panel><PanelHeader title="Research operations" actions={<Link href="/research" className="text-2xs text-accent hover:underline">open workspace</Link>} /><EmptyState title="Research runs are symbol-scoped" description="Open Research to inspect evidence-backed runs, critic verdicts, model metadata, and data-quality limitations." /></Panel><Panel><PanelHeader title="AI / model activity" actions={<Link href="/agents" className="text-2xs text-accent hover:underline">agent registry</Link>} /><EmptyState title="Agent status is not yet connected" description="The UI is ready for registry, latency, and run status contracts when the backend exposes them." /></Panel></div>
    <Panel><PanelHeader title="System activity" actions={<Link href="/audit" className="text-2xs text-accent hover:underline">view system</Link>} />{events.isLoading ? <LoadingState label="Reading append-only agent events…" /> : events.isError ? <ErrorState description="Agent event history is unavailable from the API." /> : events.data?.length ? <ul className="divide-y divide-border/50">{events.data.slice(0, 8).map((event) => <li key={event.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-xs"><span className="font-mono text-accent">{event.event_type}</span><span className="text-muted">{event.agent_id}</span><time className="text-2xs text-subtle" dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleString()}</time></li>)}</ul> : <EmptyState title="No system activity" description="The audit event stream has not returned any records." />}</Panel>
  </div>;
}
