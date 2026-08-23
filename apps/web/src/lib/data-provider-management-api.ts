/**
 * Typed boundary for financial/data-provider management.
 *
 * The API currently exposes no provider-management routes. These contracts
 * intentionally describe credential presence and health metadata only; the
 * browser must never receive provider secrets.
 */
export type DataProviderCategory =
  | "market_data"
  | "news"
  | "fundamentals"
  | "earnings"
  | "macro"
  | "alternative_data"
  | "custom";

export type DataProviderStatus =
  | "connected"
  | "testing"
  | "disconnected"
  | "error"
  | "not_configured"
  | "backend_unavailable";

export type FreshnessState = "fresh" | "stale" | "missing" | "invalid";

export type DataCapability =
  | "market_data"
  | "news"
  | "security_metadata"
  | "trading";

export interface DataProviderCapability {
  capability: DataCapability;
  status: DataProviderStatus;
}

export interface DataProviderHealth {
  last_successful_ingestion?: string | null;
  freshness?: FreshnessState | null;
  provider_latency_ms?: number | null;
  data_quality?: FreshnessState | null;
  last_error?: string | null;
  available_feeds?: string[] | null;
  symbols_covered?: number | null;
}

export interface ManagedDataProvider {
  id: string;
  name: string;
  categories: DataProviderCategory[];
  status: DataProviderStatus;
  enabled: boolean;
  has_credentials: boolean;
  health?: DataProviderHealth | null;
  capabilities: DataProviderCapability[];
}

export interface DataProviderConnectionResult {
  status: "connected" | "failed";
  provider: string;
  capabilities?: DataProviderCapability[] | null;
  latency_ms?: number | null;
  error?: string | null;
}

export const DATA_PROVIDER_CATALOG: ReadonlyArray<{
  id: string;
  name: string;
  categories: DataProviderCategory[];
  description: string;
  supportsFeed: boolean;
}> = [
  {
    id: "alpaca",
    name: "Alpaca",
    categories: ["market_data", "news"],
    description: "Market data and news adapter for the M1 ingestion pipeline.",
    supportsFeed: true,
  },
];

export const DATA_PROVIDER_CATEGORY_LABELS: Record<DataProviderCategory, string> = {
  market_data: "Market Data",
  news: "News",
  fundamentals: "Fundamentals",
  earnings: "Earnings",
  macro: "Macro",
  alternative_data: "Alternative Data",
  custom: "Custom Data Source",
};

export const ALPACA_FEEDS = ["iex", "sip"] as const;

export function dataProviderCatalogEntry(id: string) {
  return (
    DATA_PROVIDER_CATALOG.find((provider) => provider.id === id) ??
    DATA_PROVIDER_CATALOG[0]
  );
}

