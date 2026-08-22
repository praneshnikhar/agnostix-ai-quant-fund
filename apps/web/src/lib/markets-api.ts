/**
 * M1 market intelligence API client — typed against internal backend schemas.
 * No provider-specific shapes leak into the UI.
 */

import { apiFetch } from "./api";

export interface WatchlistEntry {
  symbol: string;
  name: string | null;
  exchange: string | null;
}

export interface MarketsResponse {
  watchlist: WatchlistEntry[];
  generated_at: string;
}

export interface Bar {
  symbol: string;
  timeframe: string;
  event_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  trade_count: number | null;
  vwap: number | null;
  provider: string;
  received_at: string;
}

export interface Quote {
  event_time: string;
  bid_price: number | null;
  bid_size: number | null;
  ask_price: number | null;
  ask_size: number | null;
  last_price: number | null;
  provider: string;
  received_at: string;
}

export interface Trade {
  event_time: string;
  price: number;
  size: number;
  conditions: string[] | null;
  provider: string;
  provider_trade_id: string | null;
  received_at: string;
}

export interface NewsArticleDto {
  id: string;
  headline: string;
  summary: string | null;
  source: string | null;
  url: string | null;
  symbols: string[];
  published_at: string;
  received_at: string;
  provider: string;
}

export type FreshnessState = "fresh" | "stale" | "missing" | "invalid";

export interface DataQualityStatus {
  datatype: string;
  symbol: string;
  state: FreshnessState;
  as_of: string | null;
  age_seconds: number | null;
  threshold_seconds: number | null;
  detail: string | null;
}

export interface SnapshotResponse {
  symbol: string;
  generated_at: string;
  market: Record<string, unknown>;
  news: NewsArticleDto[];
  fundamentals: Record<string, unknown>;
  macro: Record<string, unknown>;
  data_quality: DataQualityStatus[];
}

export const getMarkets = () => apiFetch<MarketsResponse>("/markets");
export const getBars = (symbol: string, timeframe = "1Day", limit = 300) =>
  apiFetch<{ bars: Bar[] }>(
    `/markets/${symbol}/bars?timeframe=${timeframe}&limit=${limit}`
  );
export const getQuote = (symbol: string) =>
  apiFetch<{ quote: Quote | null }>(`/markets/${symbol}/quotes`);
export const getTrades = (symbol: string) =>
  apiFetch<{ trades: Trade[] }>(`/markets/${symbol}/trades`);
export const getNews = (symbol: string) =>
  apiFetch<{ articles: NewsArticleDto[] }>(`/markets/${symbol}/news`);
export const getSnapshot = (symbol: string) =>
  apiFetch<SnapshotResponse>(`/markets/${symbol}/snapshot`);

/** Deterministic fixture data for tests/storybook — NEVER shown as live. */
export const FIXTURE_BARS: Bar[] = [
  ...Array.from({ length: 30 }, (_, i) => ({
    symbol: "AAPL",
    timeframe: "1Day",
    event_time: new Date(Date.UTC(2024, 5, 3 + i, 14, 30)).toISOString(),
    open: 100 + i,
    high: 105 + i,
    low: 98 + i,
    close: 103 + i,
    volume: 1000 + i * 10,
    trade_count: 100 + i,
    vwap: 102 + i,
    provider: "fixture",
    received_at: new Date(Date.UTC(2024, 5, 4 + i)).toISOString(),
  })),
];