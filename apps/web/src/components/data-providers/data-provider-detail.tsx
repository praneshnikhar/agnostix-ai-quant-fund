"use client";

import Link from "next/link";
import { useState } from "react";
import {
  Badge,
  Button,
  EmptyState,
  Panel,
  PanelHeader,
  SectionHeader,
} from "@/components/ui";
import {
  ALPACA_FEEDS,
  DATA_PROVIDER_CATEGORY_LABELS,
  dataProviderCatalogEntry,
  type DataCapability,
} from "@/lib/data-provider-management-api";

const capabilityLabels: Record<DataCapability, string> = {
  market_data: "Market Data",
  news: "News",
  security_metadata: "Security Metadata",
  trading: "Trading",
};

export function DataProviderDetail({ providerId }: { providerId: string }) {
  const provider = dataProviderCatalogEntry(providerId);
  const [apiKey, setApiKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [replacing, setReplacing] = useState(false);
  const [showSecrets, setShowSecrets] = useState(false);
  const [feed, setFeed] = useState<(typeof ALPACA_FEEDS)[number]>("iex");

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 text-xs text-muted">
        <Link href="/settings/data-providers" className="hover:text-foreground">
          Data providers
        </Link>
        <span>/</span>
        <span className="text-foreground">{provider.name}</span>
      </div>

      <SectionHeader
        eyebrow="FINANCIAL DATA INFRASTRUCTURE"
        title={provider.name}
        description={provider.description}
        actions={
          <div className="flex items-center gap-2">
            <Badge tone="neutral">backend unavailable</Badge>
            <Button disabled>Test connection</Button>
          </div>
        }
      />

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(300px,0.7fr)]">
        <Panel>
          <PanelHeader title="Data-provider configuration" />
          <div className="space-y-4 p-4">
            <div className="rounded border border-warning/30 bg-warning/5 px-3 py-2 text-xs leading-relaxed text-warning">
              Backend integration pending. These values stay in component memory
              and cannot be saved from this screen.
            </div>
            <fieldset className="space-y-3">
              <legend className="text-2xs uppercase tracking-wider text-subtle">
                Alpaca credentials
              </legend>
              {replacing ? (
                <>
                  <SecretField
                    label="API key"
                    value={apiKey}
                    onChange={setApiKey}
                    visible={showSecrets}
                  />
                  <SecretField
                    label="Secret key"
                    value={secretKey}
                    onChange={setSecretKey}
                    visible={showSecrets}
                  />
                  <button
                    type="button"
                    onClick={() => setShowSecrets((value) => !value)}
                    className="text-2xs text-accent hover:underline"
                  >
                    {showSecrets ? "Hide secrets" : "Show secrets"}
                  </button>
                </>
              ) : (
                <div className="flex items-center justify-between rounded border border-border bg-elevated px-2.5 py-2">
                  <span className="font-mono text-xs tracking-widest text-muted">
                    •••••••••••••••• / ••••••••••••••••
                  </span>
                  <button
                    type="button"
                    onClick={() => setReplacing(true)}
                    aria-label="Replace Alpaca credentials"
                    className="text-2xs text-accent hover:underline"
                  >
                    Replace
                  </button>
                </div>
              )}
              <p className="text-2xs text-subtle">
                The existing backend contract uses API key and secret key
                environment credentials. Original secrets are never returned.
              </p>
            </fieldset>

            <label className="block text-xs text-muted">
              Market data feed
              <select
                value={feed}
                onChange={(event) => setFeed(event.target.value as (typeof ALPACA_FEEDS)[number])}
                className="mt-1 h-9 w-full rounded border border-border bg-elevated px-2.5 text-xs text-foreground outline-none focus:border-accent focus:ring-1 focus:ring-accent"
              >
                {ALPACA_FEEDS.map((item) => (
                  <option key={item} value={item}>
                    {item.toUpperCase()}
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-2xs text-subtle">
                The adapter supports IEX and SIP feed values. Base URLs are not
                exposed because the current backend has no data-provider URL
                contract.
              </span>
            </label>

            <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-4">
              <Button variant="ghost" disabled>
                Test connection
              </Button>
              <Button disabled>Save provider</Button>
            </div>
          </div>
        </Panel>

        <Panel>
          <PanelHeader title="Capability status" />
          <div className="space-y-3 px-4 py-4">
            {(["market_data", "news", "security_metadata", "trading"] as DataCapability[]).map(
              (capability) => (
                <div
                  key={capability}
                  className="flex items-center justify-between gap-3 border-b border-border/40 pb-2 last:border-0"
                >
                  <span className="text-xs text-muted">{capabilityLabels[capability]}</span>
                  <Badge tone="neutral">backend unavailable</Badge>
                </div>
              ),
            )}
            <p className="pt-1 text-2xs leading-relaxed text-subtle">
              Trading is shown as a separate capability. Data credentials do not
              imply trading authorization, and no trading status is claimed.
            </p>
          </div>
        </Panel>
      </div>

      <Panel>
        <PanelHeader title="Data-source health" />
        <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            "Last successful ingestion",
            "Freshness",
            "Provider latency",
            "Data quality",
            "Last error",
            "Available feeds",
            "Symbols covered",
          ].map((label) => (
            <div key={label} className="rounded border border-border/60 bg-elevated/40 p-3">
              <p className="text-2xs uppercase tracking-wider text-subtle">{label}</p>
              <p className="mt-2 font-mono text-xs text-muted">unavailable</p>
            </div>
          ))}
        </div>
        <p className="border-t border-border/50 px-4 py-3 text-2xs text-subtle">
          Freshness uses the M1 vocabulary: Fresh, Stale, Missing, Invalid.
          Values remain unavailable until a backend health contract exists.
        </p>
      </Panel>

      <Panel>
        <PanelHeader title="Ingestion architecture" />
        <p className="px-4 py-3 text-xs leading-relaxed text-muted">
          Alpaca → provider adapter → normalization → validation → freshness /
          quality → Redis / PostgreSQL → MarketSnapshot → Research. This UI
          does not bypass that pipeline or route data through ModelGateway.
        </p>
      </Panel>

      <Panel>
        <PanelHeader title="Security boundary" />
        <p className="px-4 py-3 text-xs leading-relaxed text-muted">
          Credentials are never placed in localStorage, sessionStorage, URLs, or
          client-side analytics. The browser only shows masked placeholders and
          does not make direct provider calls.
        </p>
      </Panel>
    </div>
  );
}

function SecretField({
  label,
  value,
  onChange,
  visible,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  visible: boolean;
}) {
  return (
    <label className="block text-xs text-muted">
      {label}
      <input
        type={visible ? "text" : "password"}
        autoComplete="new-password"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={`Enter replacement ${label.toLowerCase()}`}
        className="mt-1 h-9 w-full rounded border border-border bg-elevated px-2.5 text-xs text-foreground outline-none placeholder:text-subtle focus:border-accent focus:ring-1 focus:ring-accent"
      />
    </label>
  );
}
