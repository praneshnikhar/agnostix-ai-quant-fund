"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getMarkets } from "@/lib/markets-api";
import { getResearchHistory, postRunResearch } from "@/lib/research-api";
import { Badge, EmptyState, ErrorState, LoadingState, Panel, PanelHeader, SectionHeader } from "@/components/ui";

const VIEW_STYLES: Record<string, string> = { BULLISH: "text-positive", BEARISH: "text-negative", NEUTRAL: "text-muted", INSUFFICIENT_DATA: "text-warning" };

export default function ResearchPage() {
  const qc = useQueryClient();
  const markets = useQuery({ queryKey: ["markets"], queryFn: getMarkets });
  const run = useMutation({ mutationFn: postRunResearch, onSuccess: (_d, symbol) => qc.invalidateQueries({ queryKey: ["research-history", symbol] }) });
  const coverage = markets.data?.watchlist ?? [];

  return <div className="space-y-5"><SectionHeader eyebrow="RESEARCH / WORKSPACE" title="Fundamental research" description="Evidence-backed AI research over deterministic market, news, and financial context. Research only — no trading capability exists here." actions={<Badge tone="info">M2 research</Badge>} /><Panel><PanelHeader title="Coverage" actions={<span className="text-2xs text-subtle">{markets.data ? `${coverage.length} symbols` : "backend coverage"}</span>} />{markets.isLoading ? <LoadingState label="Loading configured market coverage…" /> : markets.isError ? <ErrorState description="Market coverage is unavailable, so research symbols cannot be loaded." /> : coverage.length === 0 ? <EmptyState title="No research coverage" description="Configure the backend watchlist before starting a research run." /> : <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-xs"><thead><tr className="border-b border-border text-left text-2xs uppercase tracking-wider text-muted"><th className="px-3 py-2">Symbol</th><th className="px-3 py-2">Company</th><th className="px-3 py-2">View</th><th className="px-3 py-2">Confidence</th><th className="px-3 py-2">Critic</th><th className="px-3 py-2">Model</th><th className="px-3 py-2" /></tr></thead><tbody>{coverage.map((entry) => <HistoryRow key={entry.symbol} symbol={entry.symbol} name={entry.name} onRun={() => run.mutate(entry.symbol)} running={run.isPending && run.variables === entry.symbol} />)}</tbody></table></div>}</Panel>{run.isError ? <p role="alert" className="px-1 text-xs text-negative">Research run failed: {(run.error as Error)?.message ?? "unknown error"}</p> : null}</div>;
}

function HistoryRow({ symbol, name, onRun, running }: { symbol: string; name: string | null; onRun: () => void; running: boolean }) {
  const history = useQuery({ queryKey: ["research-history", symbol], queryFn: () => getResearchHistory(symbol, 1) });
  const latest = history.data?.[0];
  return <tr className="border-b border-border/50 transition-colors last:border-0 hover:bg-elevated/40"><td className="px-3 py-2"><Link href={`/research/${symbol}`} className="font-mono font-medium text-foreground hover:text-accent">{symbol}</Link></td><td className="px-3 py-2 text-muted">{name ?? "unavailable"}</td><td className={`px-3 py-2 ${latest?.fundamental_view ? VIEW_STYLES[latest.fundamental_view] : "text-muted"}`}>{history.isLoading ? "loading…" : latest?.fundamental_view ?? "no research"}</td><td className="px-3 py-2 font-mono tabular-nums text-muted">{latest?.confidence != null ? `${(latest.confidence * 100).toFixed(0)}%` : "unavailable"}</td><td className="px-3 py-2 text-muted">{latest?.critic_verdict ?? "unavailable"}</td><td className="px-3 py-2 text-muted">{latest?.model_provider && latest.model_name ? `${latest.model_provider} / ${latest.model_name}` : "unavailable"}</td><td className="px-3 py-2 text-right"><button onClick={onRun} disabled={running} className="rounded border border-border px-2 py-1 text-2xs text-muted transition-colors hover:border-border-strong hover:text-foreground disabled:opacity-50">{running ? "running…" : "run research"}</button></td></tr>;
}
