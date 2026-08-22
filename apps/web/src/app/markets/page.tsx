"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Panel, PanelHeader, EmptyState } from "@/components/ui";
import { getMarkets } from "@/lib/markets-api";

export default function MarketsPage() {
  const [search, setSearch] = useState("");
  const { data, isLoading, isError } = useQuery({
    queryKey: ["markets"],
    queryFn: getMarkets,
    refetchInterval: 60_000,
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toUpperCase();
    return q
      ? data.watchlist.filter(
          (e) => e.symbol.includes(q) || (e.name ?? "").toUpperCase().includes(q)
        )
      : data.watchlist;
  }, [data, search]);

  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader
          title="Markets — Development Watchlist"
          actions={
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search symbol…"
              aria-label="Search symbols"
              className="h-7 w-48 rounded border border-border bg-elevated px-2 text-xs text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
            />
          }
        />
        {isLoading ? (
          <div className="p-4 text-xs text-muted">Loading watchlist…</div>
        ) : isError ? (
          <div className="p-4 text-xs text-negative">
            Failed to load market data. Backend may be unreachable.
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No symbols match"
            description="Adjust the search or configure MARKET_WATCHLIST on the backend."
          />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-2xs uppercase tracking-wider text-muted">
                <th className="px-3 py-2 font-medium">Symbol</th>
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Exchange</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((entry) => (
                <tr
                  key={entry.symbol}
                  className="border-b border-border/50 hover:bg-elevated/60"
                >
                  <td className="px-3 py-2">
                    <Link
                      href={`/markets/${entry.symbol.toLowerCase()}`}
                      className="font-medium text-foreground hover:text-positive"
                    >
                      {entry.symbol}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-muted">{entry.name ?? "—"}</td>
                  <td className="px-3 py-2 text-muted">{entry.exchange ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
      <p className="text-2xs text-muted">
        M1 market intelligence — read-only. No trading functionality is available
        in this milestone. Data shown only where ingested; missing data is
        labeled as missing.
      </p>
    </div>
  );
}