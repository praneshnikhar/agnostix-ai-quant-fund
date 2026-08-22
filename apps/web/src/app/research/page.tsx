"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Panel, PanelHeader, EmptyState } from "@/components/ui";
import {
  getResearchHistory,
  postRunResearch,
} from "@/lib/research-api";

const UNIVERSE = ["ACME", "GLOBEX", "INITECH"];

const VIEW_STYLES: Record<string, string> = {
  BULLISH: "text-positive",
  BEARISH: "text-negative",
  NEUTRAL: "text-muted",
  INSUFFICIENT_DATA: "text-warning",
};

export default function ResearchPage() {
  const qc = useQueryClient();
  const run = useMutation({
    mutationFn: postRunResearch,
    onSuccess: (_d, symbol) => {
      qc.invalidateQueries({ queryKey: ["research-history", symbol] });
    },
  });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-foreground">
          Fundamental Research
        </h1>
        <p className="text-xs text-muted">
          Evidence-backed AI research over deterministic financial data.
          Research only — no trading capability exists at this stage.
        </p>
      </div>

      <Panel>
        <PanelHeader title="Coverage" />
        {UNIVERSE.length === 0 ? (
          <EmptyState title="No coverage" description="No companies under coverage yet." />
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th className="px-4 py-2 font-medium">Symbol</th>
                <th className="px-4 py-2 font-medium">Latest View</th>
                <th className="px-4 py-2 font-medium">Confidence</th>
                <th className="px-4 py-2 font-medium">Critic</th>
                <th className="px-4 py-2 font-medium">Model</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {UNIVERSE.map((symbol) => (
                <HistoryRow key={symbol} symbol={symbol} onRun={() => run.mutate(symbol)} running={run.isPending && run.variables === symbol} />
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {run.isError && (
        <p className="px-1 text-xs text-negative">
          Research run failed: {(run.error as Error)?.message ?? "unknown error"}
        </p>
      )}
    </div>
  );
}

function HistoryRow({
  symbol,
  onRun,
  running,
}: {
  symbol: string;
  onRun: () => void;
  running: boolean;
}) {
  const history = useQuery({
    queryKey: ["research-history", symbol],
    queryFn: () => getResearchHistory(symbol, 1),
  });
  const latest = history.data?.[0];
  return (
    <tr className="border-b border-border/50 last:border-0">
      <td className="px-4 py-2">
        <Link
          href={`/research/${symbol}`}
          className="font-mono text-foreground hover:text-accent"
        >
          {symbol}
        </Link>
      </td>
      <td className={`px-4 py-2 ${latest?.fundamental_view ? VIEW_STYLES[latest.fundamental_view] : "text-muted"}`}>
        {history.isLoading ? "…" : latest?.fundamental_view ?? "no research"}
      </td>
      <td className="px-4 py-2 tabular-nums text-muted">
        {latest?.confidence != null ? latest.confidence.toFixed(2) : "—"}
      </td>
      <td className="px-4 py-2 text-muted">{latest?.critic_verdict ?? "—"}</td>
      <td className="px-4 py-2 text-muted">
        {latest ? `${latest.model_provider}/${latest.model_name}` : "—"}
      </td>
      <td className="px-4 py-2 text-right">
        <button
          onClick={onRun}
          disabled={running}
          className="rounded border border-border px-2 py-1 text-2xs text-muted hover:text-foreground disabled:opacity-50"
        >
          {running ? "running…" : "run research"}
        </button>
      </td>
    </tr>
  );
}