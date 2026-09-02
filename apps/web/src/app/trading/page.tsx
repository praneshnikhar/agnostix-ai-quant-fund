"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge, Button, EmptyState, ErrorState, LoadingState, MetricTile, Panel, PanelHeader, SectionHeader, Skeleton } from "@/components/ui";
import { useWebSocket } from "@/hooks/use-websocket";
import {
  getDeskStatus,
  getEquity,
  getJournal,
  postKill,
  postResume,
  postRun,
  postSnapshot,
  type DecisionDto,
  type JournalEntry,
} from "@/lib/trading-api";
import { cn } from "@/lib/utils";

const WATCHLIST = ["SPY", "AAPL", "MSFT", "NVDA"];

function money(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function Sparkline({ points }: { points: { equity: number }[] }) {
  if (points.length < 2) return <div className="text-2xs text-subtle">collecting equity samples…</div>;
  const w = 600;
  const h = 120;
  const min = Math.min(...points.map((p) => p.equity));
  const max = Math.max(...points.map((p) => p.equity));
  const span = max - min || 1;
  const coords = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * w;
      const y = h - ((p.equity - min) / span) * (h - 10) - 5;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-32 w-full" preserveAspectRatio="none" role="img" aria-label="equity curve">
      <polyline points={coords} fill="none" stroke="var(--accent)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function StrategyCard({ d }: { d: DecisionDto }) {
  const verdict = d.risk?.verdict;
  const tone = d.status === "executed" ? "positive" : d.status === "refused" ? "negative" : "neutral";
  return (
    <Panel className="p-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm font-semibold">{d.symbol}</span>
        <Badge tone={tone}>{d.status}</Badge>
      </div>
      {d.strategy ? (
        <div className="mt-2 space-y-1 text-xs text-muted">
          <p><span className="text-subtle">strategy</span> {d.strategy.name.replace(/_/g, " ")}</p>
          <p><span className="text-subtle">max loss</span> <span className="tnum">{money(d.strategy.max_loss)}</span> · <span className="text-subtle">max profit</span> <span className="tnum">{money(d.strategy.max_profit)}</span></p>
          <p><span className="text-subtle">legs</span> {d.strategy.legs.map((l) => `${l.side === "sell_to_open" ? "S" : "B"} ${l.contract.strike}${l.contract.option_type === "put" ? "P" : "C"}`).join(" · ")}</p>
        </div>
      ) : null}
      {d.signal?.thesis ? <p className="mt-2 text-xs text-foreground/80">{d.signal.thesis}</p> : null}
      {verdict ? <p className="mt-2 text-2xs text-subtle">risk: {verdict}</p> : null}
    </Panel>
  );
}

export default function TradingPage() {
  const qc = useQueryClient();
  const ws = useWebSocket(process.env.NEXT_PUBLIC_WS_URL);
  const status = useQuery({ queryKey: ["trading-status"], queryFn: getDeskStatus, refetchInterval: 10_000 });
  const equity = useQuery({ queryKey: ["trading-equity"], queryFn: getEquity, refetchInterval: 15_000 });
  const journal = useQuery({ queryKey: ["trading-journal"], queryFn: () => getJournal(30), refetchInterval: 10_000 });

  const [live, setLive] = useState<JournalEntry[]>([]);

  useEffect(() => {
    if (ws.lastMessage) {
      qc.invalidateQueries({ queryKey: ["trading-status"] });
      qc.invalidateQueries({ queryKey: ["trading-journal"] });
    }
  }, [ws.lastMessage, qc]);

  // Record an equity sample on an interval while the desk page is open.
  useEffect(() => {
    const id = setInterval(() => {
      postSnapshot().then(() => qc.invalidateQueries({ queryKey: ["trading-equity"] })).catch(() => {});
    }, 20_000);
    return () => clearInterval(id);
  }, [qc]);

  const run = useMutation({ mutationFn: (symbols: string[]) => postRun(symbols), onSuccess: () => qc.invalidateQueries() });
  const kill = useMutation({ mutationFn: postKill, onSuccess: () => qc.invalidateQueries() });
  const resume = useMutation({ mutationFn: postResume, onSuccess: () => qc.invalidateQueries() });

  const account = status.data?.account;
  const decisions = status.data?.open_strategies ?? [];

  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="TRADING DESK / PAPER"
        title="Options War Room"
        description="Autonomous options desk on Alpaca paper. The LLM proposes a direction; deterministic code chooses strikes, sizes, and risk gates — and can refuse."
        actions={
          <div className="flex items-center gap-2">
            <Badge tone={status.data?.kill_switch ? "negative" : account ? "positive" : "neutral"}>
              {status.data?.kill_switch ? "KILLED" : account ? "LIVE (PAPER)" : "NOT CONNECTED"}
            </Badge>
            <Badge tone={ws.connected ? "positive" : "warning"}>WS {ws.connected ? "live" : "offline"}</Badge>
          </div>
        }
      />

      {status.isError ? (
        <ErrorState title="Trading desk unavailable" description={status.error instanceof Error ? status.error.message : "Alpaca credentials may be missing (API_ALPACA_API_KEY / API_ALPACA_SECRET_KEY)."} />
      ) : (
        <>
          <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <MetricTile label="Equity" value={account ? money(account.equity) : undefined} />
            <MetricTile label="Cash" value={account ? money(account.cash) : undefined} />
            <MetricTile label="Buying power" value={account ? money(account.buying_power) : undefined} />
            <MetricTile label="Daily P&L" value={account ? money(account.daily_pl) : undefined} delta={account && account.daily_pl >= 0 ? "up" : "down"} deltaTone={account && account.daily_pl >= 0 ? "positive" : "negative"} />
            <MetricTile label="Committed risk" value={account ? money(account.defined_risk_committed) : undefined} />
          </section>

          <section className="grid gap-3 xl:grid-cols-3">
            <Panel className="xl:col-span-2">
              <PanelHeader title="Equity curve (paper)" actions={<span className="text-2xs text-subtle">{equity.data?.length ?? 0} samples</span>} />
              <div className="p-3">{equity.isLoading ? <Skeleton className="h-32 w-full" /> : <Sparkline points={equity.data ?? []} />}</div>
            </Panel>
            <Panel>
              <PanelHeader title="Desk controls" />
              <div className="flex flex-col gap-2 p-3">
                <Button onClick={() => run.mutate(WATCHLIST)} disabled={run.isPending || status.data?.kill_switch}>Run cycle (SPY · AAPL · MSFT · NVDA)</Button>
                {status.data?.kill_switch ? <Button variant="positive" onClick={() => resume.mutate()} disabled={resume.isPending}>Resume desk</Button> : <Button variant="danger" onClick={() => kill.mutate()} disabled={kill.isPending}>Trigger kill switch</Button>}
                <p className="mt-1 text-2xs text-subtle">The kill switch halts all future decisions; deterministic risk gates still veto any single order.</p>
                <div className="mt-2 border-t border-border pt-2 text-xs text-muted">
                  <p>journal head <span className="font-mono text-2xs text-accent">{status.data?.journal_head?.slice(0, 12)}…</span></p>
                  <p>chain <Badge tone={status.data?.journal_verified ? "positive" : "negative"}>{status.data?.journal_verified ? "verified" : "unverified"}</Badge></p>
                </div>
              </div>
            </Panel>
          </section>

          <section className="grid gap-3 xl:grid-cols-2">
            <Panel>
              <PanelHeader title="Open strategies" />
              {decisions.length ? <div className="grid gap-2 p-3">{decisions.map((d) => <StrategyCard key={d.decision_id} d={d} />)}</div> : <EmptyState title="No open positions" description="Run a cycle or challenge the agent to open a defined-risk strategy." />}
            </Panel>
            <Panel>
              <PanelHeader title="Decision journal (hash-chained)" />
              {journal.isLoading ? <LoadingState label="Reading ledger…" /> : journal.data?.entries.length ? (
                <ul className="divide-y divide-border/50">
                  {journal.data.entries.slice(0, 12).map((e) => (
                    <li key={e.seq} className="flex items-center justify-between gap-2 px-3 py-2 text-xs">
                      <span className={cn("font-mono uppercase text-2xs", e.kind === "execution" ? "text-positive" : e.kind === "refusal" ? "text-negative" : "text-muted")}>{e.kind}</span>
                      <span className="font-mono text-muted">{e.symbol}</span>
                      <span className="font-mono text-2xs text-subtle">{e.hash.slice(0, 10)}</span>
                      <time className="text-2xs text-subtle">{new Date(e.timestamp).toLocaleTimeString()}</time>
                    </li>
                  ))}
                </ul>
              ) : <EmptyState title="Empty ledger" description="No decisions recorded yet." />}
            </Panel>
          </section>
        </>
      )}
    </div>
  );
}
