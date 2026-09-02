"use client";

import { useRef, useState } from "react";
import { Badge, Button, Panel, PanelHeader, SectionHeader } from "@/components/ui";
import type { DecisionDto, GateDto } from "@/lib/trading-api";
import { cn } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface StreamEvent {
  type: string;
  payload: Record<string, unknown>;
}

const SCENARIOS = [
  { label: "No scenario", value: "" },
  { label: "Earnings miss tonight", value: "The company reports earnings tonight and misses consensus EPS by 20%; guidance is cut." },
  { label: "IV crush after earnings", value: "Implied volatility collapses 40% immediately after earnings." },
  { label: "Market down 5%", value: "A broad market selloff pushes the index down 5% intraday with a VIX spike." },
  { label: "Fed hikes 50bps", value: "The Fed surprises with a 50bps rate hike; yields jump." },
];

export default function PlaygroundPage() {
  const [symbol, setSymbol] = useState("SPY");
  const [scenario, setScenario] = useState(SCENARIOS[0].value);
  const [execute, setExecute] = useState(false);
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [decision, setDecision] = useState<DecisionDto | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const challenge = async () => {
    setRunning(true);
    setEvents([]);
    setDecision(null);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const resp = await fetch(`${API_URL}/playground/challenge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: symbol.toUpperCase(), scenario: scenario || null, execute }),
        signal: controller.signal,
      });
      if (!resp.body) return;
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          try {
            const evt = JSON.parse(line.slice(6)) as StreamEvent;
            setEvents((prev) => [...prev, evt]);
            if (evt.type === "decision") setDecision(evt.payload as unknown as DecisionDto);
          } catch {
            // skip malformed frame
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setEvents((prev) => [...prev, { type: "error", payload: { reason: String(err) } }]);
      }
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="PLAYGROUND / DRY-RUN"
        title="Challenge the agent"
        description="Type a symbol (and optionally inject a hypothetical scenario). Watch the agent think live: market context → LLM signal → deterministic strategy → every risk gate → verdict."
      />

      <Panel className="p-4">
        <div className="grid gap-3 md:grid-cols-4">
          <label className="flex flex-col gap-1 text-2xs text-subtle">
            Symbol
            <input value={symbol} onChange={(e) => setSymbol(e.target.value)} className="h-8 rounded border border-border bg-elevated px-2 font-mono text-sm text-foreground" placeholder="SPY" />
          </label>
          <label className="flex flex-col gap-1 text-2xs text-subtle md:col-span-2">
            Scenario (optional)
            <select value={scenario} onChange={(e) => setScenario(e.target.value)} className="h-8 rounded border border-border bg-elevated px-2 text-sm text-foreground">
              {SCENARIOS.map((s) => <option key={s.label} value={s.value}>{s.label}</option>)}
            </select>
          </label>
          <div className="flex items-end gap-2">
            <label className="flex items-center gap-2 text-xs text-muted">
              <input type="checkbox" checked={execute} onChange={(e) => setExecute(e.target.checked)} /> execute
            </label>
            <Button onClick={challenge} disabled={running} className="flex-1">{running ? "Reasoning…" : "Challenge"}</Button>
          </div>
        </div>
        {execute ? <p className="mt-2 text-2xs text-negative">Execution enabled — this will place a paper order on Alpaca.</p> : <p className="mt-2 text-2xs text-subtle">Dry-run: the agent reasons and runs risk gates but places no order.</p>}
      </Panel>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel>
          <PanelHeader title="Live reasoning trace" />
          {events.length === 0 && !running ? <EmptyHint /> : (
            <ul className="divide-y divide-border/50">
              {events.map((e, i) => <TraceRow key={i} evt={e} />)}
              {running ? <li className="px-3 py-2 text-xs text-subtle">…</li> : null}
            </ul>
          )}
        </Panel>
        <DecisionPanel decision={decision} />
      </div>
    </div>
  );
}

function EmptyHint() {
  return <div className="px-3 py-10 text-center text-xs text-subtle">The trace will appear here as the agent works through its decision.</div>;
}

function TraceRow({ evt }: { evt: StreamEvent }) {
  const label = { agent_analyzing: "analyzing", market_ready: "market context", signal_failed: "signal failed", strategy_built: "strategy built", risk_evaluated: "risk gates", agent_abstained: "abstained", agent_refused: "refused", agent_executed: "executed", decision: "final", error: "error" }[evt.type] ?? evt.type;
  const tone = evt.type === "agent_refused" || evt.type === "error" ? "negative" : evt.type === "agent_executed" ? "positive" : "accent";
  return (
    <li className="px-3 py-2">
      <Badge tone={tone as "negative" | "positive" | "accent"}>{label}</Badge>
      <span className="ml-2 text-xs text-muted">{summarize(evt)}</span>
    </li>
  );
}

function summarize(evt: StreamEvent): string {
  const p = evt.payload as Record<string, unknown>;
  if (evt.type === "market_ready") return `spot ${String(p.spot ?? "—")} · vol rank ${typeof p.vol_rank === "number" ? (p.vol_rank as number).toFixed(2) : "—"}`;
  if (evt.type === "strategy_built") return "deterministic defined-risk strategy constructed";
  if (evt.type === "agent_refused") return String(p.reason ?? "");
  if (evt.type === "agent_abstained") return String(p.reason ?? "");
  if (evt.type === "agent_executed") return `order ${String(p.order_id ?? "")}`;
  return "";
}

function DecisionPanel({ decision }: { decision: DecisionDto | null }) {
  if (!decision) return <Panel><PanelHeader title="Verdict" /><div className="px-3 py-10 text-center text-xs text-subtle">Awaiting a decision…</div></Panel>;
  const verdictTone = decision.status === "executed" ? "positive" : decision.status === "refused" ? "negative" : "neutral";
  return (
    <Panel>
      <PanelHeader title="Verdict" actions={<Badge tone={verdictTone}>{decision.status}</Badge>} />
      <div className="space-y-3 p-3">
        {decision.signal ? (
          <div>
            <p className="text-2xs uppercase tracking-wider text-subtle">Signal</p>
            <p className="mt-1 text-sm font-medium">{decision.signal.direction} · confidence {(decision.signal.confidence * 100).toFixed(0)}%</p>
            <p className="mt-1 text-xs text-muted">{decision.signal.thesis}</p>
          </div>
        ) : null}
        {decision.strategy ? (
          <div>
            <p className="text-2xs uppercase tracking-wider text-subtle">Strategy (code-decided)</p>
            <p className="mt-1 text-sm">{decision.strategy.name.replace(/_/g, " ")} · max loss {money(decision.strategy.max_loss)}</p>
          </div>
        ) : null}
        {decision.reason ? <p className="text-xs text-muted">{decision.reason}</p> : null}
        {decision.risk ? (
          <div>
            <p className="text-2xs uppercase tracking-wider text-subtle">Risk gates</p>
            <ul className="mt-1 space-y-1">
              {decision.risk.gates.map((g: GateDto) => (
                <li key={g.gate} className="flex items-center gap-2 text-xs">
                  <span className={cn("h-1.5 w-1.5 rounded-full", g.passed ? "bg-positive" : "bg-negative")} />
                  <span className="font-mono text-muted">{g.gate.replace(/_/g, " ")}</span>
                  {g.detail ? <span className="text-2xs text-subtle">{g.detail}</span> : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

function money(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}
