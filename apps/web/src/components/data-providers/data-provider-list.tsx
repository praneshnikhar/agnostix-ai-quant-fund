"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  Badge,
  Button,
  EmptyState,
  Panel,
  PanelHeader,
  SectionHeader,
} from "@/components/ui";
import {
  DATA_PROVIDER_CATEGORY_LABELS,
  DATA_PROVIDER_CATALOG,
  type DataProviderCategory,
} from "@/lib/data-provider-management-api";

const categories: { id: DataProviderCategory | "all"; label: string }[] = [
  { id: "all", label: "All data providers" },
  ...Object.entries(DATA_PROVIDER_CATEGORY_LABELS).map(([id, label]) => ({
    id: id as DataProviderCategory,
    label,
  })),
];

export function DataProviderList() {
  const [category, setCategory] = useState<DataProviderCategory | "all">("all");
  const visible = useMemo(
    () =>
      category === "all"
        ? DATA_PROVIDER_CATALOG
        : DATA_PROVIDER_CATALOG.filter((provider) =>
            provider.categories.includes(category),
          ),
    [category],
  );

  return (
    <div className="space-y-5">
      <SectionHeader
        eyebrow="SETTINGS / DATA PROVIDERS"
        title="Data providers"
        description="Configure the financial data infrastructure that feeds adapters, normalization, validation, freshness, and MarketSnapshot."
        actions={<Button disabled>Add data provider</Button>}
      />

      <Panel>
        <div className="flex gap-1 overflow-x-auto border-b border-border px-3 pt-2">
          {categories.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setCategory(item.id)}
              className={`whitespace-nowrap border-b-2 px-3 py-2 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${category === item.id ? "border-accent text-foreground" : "border-transparent text-muted hover:text-foreground"}`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="divide-y divide-border/50">
          {visible.map((provider) => (
            <DataProviderRow key={provider.id} provider={provider} />
          ))}
        </div>
        {visible.length === 0 ? (
          <EmptyState
            title="No providers in this category"
            description="Future market-data, news, fundamentals, macro, and custom adapters can be added without changing this page architecture."
          />
        ) : null}
      </Panel>

      <Panel>
        <PanelHeader title="Data infrastructure boundary" />
        <p className="px-4 py-3 text-xs leading-relaxed text-muted">
          Data providers are separate from AI providers and never route through
          ModelGateway. The backend currently exposes no provider-management
          routes, so connection and ingestion state remain unavailable.
        </p>
      </Panel>
    </div>
  );
}

function DataProviderRow({
  provider,
}: {
  provider: (typeof DATA_PROVIDER_CATALOG)[number];
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 transition-colors hover:bg-elevated/30">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded border border-border bg-elevated font-mono text-sm text-accent">
          {provider.name.slice(0, 1)}
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/settings/data-providers/${provider.id}`}
              className="text-sm font-medium text-foreground hover:text-accent"
            >
              {provider.name}
            </Link>
            <Badge>data provider</Badge>
            <Badge tone="neutral">backend unavailable</Badge>
          </div>
          <p className="mt-1 text-xs text-muted">{provider.description}</p>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <div className="hidden text-right sm:block">
          <p className="text-2xs text-subtle">Freshness / feeds</p>
          <p className="mt-1 font-mono text-xs text-muted">— / —</p>
        </div>
        <Link
          href={`/settings/data-providers/${provider.id}`}
          className="rounded border border-border px-2.5 py-1.5 text-2xs text-muted hover:border-border-strong hover:text-foreground"
        >
          Manage
        </Link>
      </div>
    </div>
  );
}

