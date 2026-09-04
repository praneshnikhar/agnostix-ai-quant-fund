"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Panel, PanelHeader, EmptyState } from "@/components/ui";
import { CandleChart } from "@/components/markets/candle-chart";
import { FreshnessBadge } from "@/components/markets/freshness-badge";
import {
  getBars,
  getNews,
  getQuote,
  getSnapshot,
  getTrades,
} from "@/lib/markets-api";

export default function SymbolPage({
  params,
}: {
  params: { symbol: string };
}) {
  const rawSymbol = params.symbol;
  const symbol = rawSymbol.toUpperCase();

  const bars = useQuery({ queryKey: ["bars", symbol], queryFn: () => getBars(symbol) });
  const quote = useQuery({ queryKey: ["quote", symbol], queryFn: () => getQuote(symbol) });
  const trades = useQuery({ queryKey: ["trades", symbol], queryFn: () => getTrades(symbol) });
  const news = useQuery({ queryKey: ["news", symbol], queryFn: () => getNews(symbol) });
  const snapshot = useQuery({
    queryKey: ["snapshot", symbol],
    queryFn: () => getSnapshot(symbol),
  });

  // API returns bars newest-first; charts and last/prev need ascending order.
  const barList = [...(bars.data?.bars ?? [])].sort(
    (a, b) => new Date(a.event_time).getTime() - new Date(b.event_time).getTime()
  );
  const last = barList[barList.length - 1];
  const prev = barList[barList.length - 2];
  const change = last && prev ? last.close - prev.close : null;
  const changePct = change !== null && prev ? (change / prev.close) * 100 : null;
  const security = snapshot.data?.market.security as
    | { name?: string; exchange?: string }
    | undefined;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">{symbol}</h1>
          <p className="text-xs text-muted">
            {security?.name ?? "—"} · {security?.exchange ?? "—"}
          </p>
        </div>
        <Link href="/markets" className="text-xs text-muted hover:text-foreground">
          ← Back to markets
        </Link>
      </div>

      <Panel>
        <PanelHeader title="Price" actions={<span className="text-2xs text-muted">1Day bars</span>} />
        <div className="flex items-baseline gap-4 px-4 py-3">
          <span className="font-mono text-2xl tabular-nums text-foreground">
            {last ? last.close.toFixed(2) : "—"}
          </span>
          {change !== null && (
            <span
              className={`font-mono text-sm tabular-nums ${change >= 0 ? "text-positive" : "text-negative"}`}
            >
              {change >= 0 ? "+" : ""}
              {change.toFixed(2)} ({changePct?.toFixed(2)}%)
            </span>
          )}
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="Chart" />
        <div className="p-2">
          {bars.isLoading ? (
            <div className="flex h-[320px] items-center justify-center text-xs text-muted">
              Loading chart…
            </div>
          ) : bars.isError ? (
            <EmptyState title="Chart unavailable" description="Failed to load bars." />
          ) : barList.length === 0 ? (
            <EmptyState
              title="No chart data"
              description={`No ${symbol} bars ingested yet. Run the ingestion worker.`}
            />
          ) : (
            <CandleChart bars={barList} />
          )}
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Market Data" />
          <div className="space-y-2 p-3 text-xs">
            <div className="flex justify-between">
              <span className="text-muted">Bid / Ask</span>
              <span className="font-mono tabular-nums">
                {quote.data?.quote
                  ? `${quote.data.quote.bid_price?.toFixed(2) ?? "—"} / ${quote.data.quote.ask_price?.toFixed(2) ?? "—"}`
                  : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Volume (latest bar)</span>
              <span className="font-mono tabular-nums">{last?.volume ?? "—"}</span>
            </div>
            <div>
              <div className="mb-1 text-muted">Recent trades</div>
              {trades.data?.trades.length ? (
                <ul className="max-h-32 space-y-0.5 overflow-auto font-mono tabular-nums">
                  {trades.data.trades.slice(0, 10).map((t, i) => (
                    <li key={i} className="flex justify-between">
                      <span>{t.price.toFixed(2)}</span>
                      <span className="text-muted">×{t.size}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="text-muted">No trades ingested.</span>
              )}
            </div>
          </div>
        </Panel>

        <Panel>
          <PanelHeader title="News" />
          <div className="p-3">
            {news.isLoading ? (
              <div className="text-xs text-muted">Loading news…</div>
            ) : news.data?.articles.length ? (
              <ul className="space-y-2">
                {news.data.articles.slice(0, 8).map((a) => (
                  <li key={a.id} className="text-xs">
                    <a
                      href={a.url ?? "#"}
                      target="_blank"
                      rel="noreferrer"
                      className="text-foreground hover:text-positive"
                    >
                      {a.headline}
                    </a>
                    <div className="text-2xs text-muted">
                      {a.source ?? a.provider} ·{" "}
                      {new Date(a.published_at).toLocaleString()}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No news" description="No articles ingested for this symbol." />
            )}
          </div>
        </Panel>
      </div>

      <Panel>
        <PanelHeader title="Data Quality" />
        <div className="flex flex-wrap gap-2 p-3">
          {snapshot.data?.data_quality.map((d) => (
            <FreshnessBadge key={d.datatype} state={d.state} datatype={d.datatype} />
          ))}
          {!snapshot.data && (
            <span className="text-xs text-muted">Loading quality status…</span>
          )}
        </div>
      </Panel>
    </div>
  );
}