"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Panel, PanelHeader, EmptyState } from "@/components/ui";
import {
  getFundamentals,
  getLatestResearch,
  getResearchHistory,
  postRunResearch,
} from "@/lib/research-api";
import type { Assessment, Thesis } from "@/lib/research-api";

const VIEW_STYLES: Record<string, string> = {
  BULLISH: "text-positive",
  BEARISH: "text-negative",
  NEUTRAL: "text-muted",
  INSUFFICIENT_DATA: "text-warning",
};

const VERDICT_STYLES: Record<string, string> = {
  PASS: "text-positive",
  REVISE: "text-warning",
  REJECT: "text-negative",
};

const METRIC_LABELS: Record<string, string> = {
  revenue: "Revenue",
  revenue_growth: "Revenue Growth (YoY)",
  gross_profit: "Gross Profit",
  gross_margin: "Gross Margin",
  operating_income: "Operating Income",
  operating_margin: "Operating Margin",
  net_income: "Net Income",
  net_margin: "Net Margin",
  eps: "EPS",
  free_cash_flow: "Free Cash Flow",
  operating_cash_flow: "Operating Cash Flow",
  capital_expenditure: "CapEx",
  cash_and_equivalents: "Cash",
  total_debt: "Total Debt",
  net_debt: "Net Debt",
  shares_outstanding: "Shares Outstanding",
};

function fmtMetric(m: string, v: number | null, currency: string): string {
  if (v === null) return "unavailable";
  if (m.endsWith("_margin") || m === "revenue_growth" || m === "fcf_yield") {
    return `${(v * 100).toFixed(1)}%`;
  }
  const abs = Math.abs(v);
  const suffix = abs >= 1e9 ? "B" : abs >= 1e6 ? "M" : abs >= 1e3 ? "K" : "";
  const scaled = suffix ? v / Number(`1e${suffix === "B" ? 9 : suffix === "M" ? 6 : 3}`) : v;
  return `${currency === "USD" ? "$" : ""}${scaled.toFixed(2)}${suffix}`;
}

export default function ResearchSymbolPage({
  params,
}: {
  params: { symbol: string };
}) {
  const symbol = params.symbol.toUpperCase();
  const qc = useQueryClient();

  const research = useQuery({
    queryKey: ["research", symbol],
    queryFn: () => getLatestResearch(symbol),
    retry: false,
  });
  const fundamentals = useQuery({
    queryKey: ["fundamentals", symbol],
    queryFn: () => getFundamentals(symbol),
  });
  const history = useQuery({
    queryKey: ["research-history", symbol],
    queryFn: () => getResearchHistory(symbol),
  });

  const run = useMutation({
    mutationFn: () => postRunResearch(symbol),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["research", symbol] });
      qc.invalidateQueries({ queryKey: ["research-history", symbol] });
    },
  });

  const thesis: Thesis | null = research.data?.research_output ?? null;
  const critic = research.data?.critic_output ?? null;

  return (
    <div className="space-y-4">
      {/* HEADER */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-mono text-lg font-semibold text-foreground">
            {symbol}
          </h1>
          <p className="text-xs text-muted">
            status: {research.data?.status ?? (research.isLoading ? "loading…" : "no research")}{" "}
            · last run:{" "}
            {research.data?.created_at
              ? new Date(research.data.created_at).toLocaleString()
              : "—"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/research" className="text-xs text-muted hover:text-foreground">
            ← All research
          </Link>
          <button
            onClick={() => run.mutate()}
            disabled={run.isPending}
            className="rounded border border-border px-2 py-1 text-2xs text-muted hover:text-foreground disabled:opacity-50"
          >
            {run.isPending ? "running…" : "run research"}
          </button>
        </div>
      </div>

      {run.isError && (
        <p className="px-1 text-xs text-negative">
          Run failed: {(run.error as Error)?.message}
        </p>
      )}

      {research.isLoading && (
        <Panel>
          <EmptyState title="Loading research…" description="Fetching latest research run." />
        </Panel>
      )}

      {research.isError && !research.isLoading && (
        <Panel>
          <EmptyState
            title="No research yet"
            description={`No completed research run for ${symbol}. Trigger a run to generate one.`}
          />
        </Panel>
      )}

      {thesis && (
        <>
          {/* FUNDAMENTAL VIEW */}
          <Panel>
            <PanelHeader title="Fundamental View" />
            <div className="flex items-center gap-6 px-4 py-3">
              <span className={`font-mono text-xl ${VIEW_STYLES[thesis.fundamental_view]}`}>
                {thesis.fundamental_view}
              </span>
              <div>
                <p className="text-2xs text-muted">Confidence</p>
                <p className="font-mono text-sm tabular-nums text-foreground">
                  {(thesis.confidence * 100).toFixed(0)}%
                </p>
                <p className="text-2xs text-muted">
                  confidence in research quality — not a probability of return
                </p>
              </div>
              {critic && (
                <div>
                  <p className="text-2xs text-muted">Critic</p>
                  <p className={`font-mono text-sm ${VERDICT_STYLES[critic.verdict]}`}>
                    {critic.verdict}
                  </p>
                </div>
              )}
            </div>
          </Panel>

          {/* THESIS + FACT/INTERPRETATION/CONCLUSION */}
          <Panel>
            <PanelHeader title="Investment Thesis" />
            <p className="px-4 py-3 text-sm leading-relaxed text-foreground">
              {thesis.investment_thesis}
            </p>
            <StatementsGrid assessments={[
              thesis.growth_assessment,
              thesis.profitability_assessment,
              thesis.cash_flow_assessment,
              thesis.balance_sheet_assessment,
              thesis.valuation_assessment,
            ]} />
          </Panel>

          {/* FINANCIALS */}
          <Panel>
            <PanelHeader
              title="Financials"
              actions={
                <span className="text-2xs text-muted">
                  deterministic data · LLM never computes these
                </span>
              }
            />
            <FinancialTable metrics={fundamentals.data ?? []} loading={fundamentals.isLoading} />
          </Panel>

          {/* CATALYSTS / RISKS / BEAR CASE / INVALIDATION */}
          <div className="grid grid-cols-2 gap-4">
            <Panel>
              <PanelHeader title="Catalysts" />
              <ListItems items={thesis.catalysts.map((c) => c.description)} empty="No catalysts identified." />
            </Panel>
            <Panel>
              <PanelHeader title="Risks" />
              <ListItems items={thesis.risks.map((r) => `[${r.severity}] ${r.description}`)} empty="No risks identified." />
            </Panel>
            <Panel>
              <PanelHeader title="Bear Case" />
              <p className="px-4 py-3 text-xs leading-relaxed text-muted">
                {thesis.bear_case || "Not provided."}
              </p>
            </Panel>
            <Panel>
              <PanelHeader title="Invalidation Conditions" />
              <ListItems
                items={thesis.invalidation_conditions.map(
                  (c) => `${c.condition} → watch: ${c.observable_signal}`
                )}
                empty="None specified."
              />
            </Panel>
          </div>

          {/* EVIDENCE */}
          <Panel>
            <PanelHeader title="Evidence" actions={<span className="text-2xs text-muted">sources supporting the thesis</span>} />
            {thesis.evidence.length === 0 ? (
              <EmptyState title="No evidence" description="The agent cited no evidence." />
            ) : (
              <ul className="divide-y divide-border/50">
                {thesis.evidence.map((e) => (
                  <li key={e.evidence_id} className="px-4 py-2 text-xs">
                    <span className="font-mono text-accent">{e.evidence_id}</span>{" "}
                    <span className="text-muted">via</span>{" "}
                    <span className="text-foreground">{e.source}</span>{" "}
                    <span className="rounded bg-surface px-1.5 py-0.5 text-2xs text-muted">
                      {e.source_type}
                    </span>
                    <p className="mt-0.5 text-muted">{e.claim_supported}</p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          {/* CRITIC */}
          {critic && (
            <Panel>
              <PanelHeader
                title="Critic Review"
                actions={
                  <span className={`font-mono text-2xs ${VERDICT_STYLES[critic.verdict]}`}>
                    {critic.verdict} · deterministic checks{" "}
                    {critic.deterministic_checks_passed ? "passed" : "FAILED"}
                  </span>
                }
              />
              {critic.findings.length === 0 && critic.claim_checks.length === 0 ? (
                <EmptyState title="Clean review" description="No findings reported." />
              ) : (
                <ul className="divide-y divide-border/50">
                  {critic.findings.map((f, i) => (
                    <li key={i} className="px-4 py-2 text-xs">
                      <span className={f.severity === "critical" ? "text-negative" : f.severity === "warning" ? "text-warning" : "text-muted"}>
                        [{f.severity}]
                      </span>{" "}
                      <span className="text-muted">{f.category}:</span>{" "}
                      <span className="text-foreground">{f.detail}</span>
                    </li>
                  ))}
                  {critic.claim_checks
                    .filter((c) => c.status !== "SUPPORTED")
                    .map((c, i) => (
                      <li key={`c-${i}`} className="px-4 py-2 text-xs">
                        <span className={c.status === "CONTRADICTED" ? "text-negative" : "text-warning"}>
                          [{c.status}]
                        </span>{" "}
                        <span className="text-muted">{c.statement}</span>
                      </li>
                    ))}
                </ul>
              )}
            </Panel>
          )}

          {/* MODEL METADATA */}
          <Panel>
            <PanelHeader title="Model Metadata" />
            <dl className="grid grid-cols-4 gap-x-4 gap-y-2 px-4 py-3 text-xs">
              <Meta label="Provider" value={research.data?.model_provider} />
              <Meta label="Model" value={research.data?.model_name} />
              <Meta label="Agent" value={research.data?.agent_id} />
              <Meta label="Prompt version" value={research.data?.prompt_version} />
              <Meta label="Context version" value={research.data?.context_version} />
              <Meta label="Run id" value={research.data?.id.slice(0, 8)} />
            </dl>
            {thesis.limitations.length > 0 && (
              <p className="border-t border-border/50 px-4 py-2 text-2xs text-warning">
                Limitations: {thesis.limitations.join("; ")}
              </p>
            )}
          </Panel>

          {/* HISTORY */}
          <Panel>
            <PanelHeader title="Research History" />
            <HistoryTable entries={history.data ?? []} loading={history.isLoading} />
          </Panel>
        </>
      )}
    </div>
  );
}

function Meta({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-2xs text-muted">{label}</dt>
      <dd className="font-mono text-foreground">{value ?? "—"}</dd>
    </div>
  );
}

function StatementsGrid({ assessments }: { assessments: Assessment[] }) {
  return (
    <div className="grid grid-cols-2 gap-x-6 gap-y-3 border-t border-border/50 px-4 py-3">
      {assessments.map((a) => (
        <div key={a.area}>
          <p className="text-2xs uppercase tracking-wide text-muted">{a.area}</p>
          <p className="text-xs text-foreground">{a.summary}</p>
          {a.statements.map((s, i) => (
            <p key={i} className="mt-1 text-2xs">
              <span
                className={
                  s.kind === "FACT"
                    ? "text-accent"
                    : s.kind === "INTERPRETATION"
                      ? "text-warning"
                      : "text-positive"
                }
              >
                {s.kind}:
              </span>{" "}
              <span className="text-muted">{s.text}</span>
              {s.evidence_ids.length > 0 && (
                <span className="ml-1 font-mono text-2xs text-muted">
                  [{s.evidence_ids.join(", ")}]
                </span>
              )}
            </p>
          ))}
        </div>
      ))}
    </div>
  );
}

function FinancialTable({
  metrics,
  loading,
}: {
  metrics: { metric: string; value: number | null; period_type: string; period_end: string; currency: string; quality: string }[];
  loading: boolean;
}) {
  if (loading) return <p className="px-4 py-3 text-xs text-muted">Loading…</p>;
  if (metrics.length === 0)
    return <EmptyState title="No financial data" description="Fundamental data unavailable for this symbol." />;
  return (
    <table className="w-full text-xs">
      <tbody>
        {metrics.map((m) => (
          <tr key={`${m.metric}-${m.period_end}`} className="border-b border-border/40 last:border-0">
            <td className="px-4 py-1.5 text-muted">
              {METRIC_LABELS[m.metric] ?? m.metric}
            </td>
            <td className="px-4 py-1.5 font-mono tabular-nums text-foreground">
              {fmtMetric(m.metric, m.value, m.currency)}
            </td>
            <td className="px-4 py-1.5 text-2xs text-muted">
              {m.period_type} · {m.period_end}
            </td>
            <td className="px-4 py-1.5 text-right">
              {m.quality !== "ok" && (
                <span className="rounded bg-surface px-1.5 py-0.5 text-2xs text-warning">
                  {m.quality}
                </span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ListItems({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0)
    return <p className="px-4 py-3 text-xs text-muted">{empty}</p>;
  return (
    <ul className="list-inside list-disc px-4 py-3 text-xs text-foreground">
      {items.map((t, i) => (
        <li key={i}>{t}</li>
      ))}
    </ul>
  );
}

function HistoryTable({
  entries,
  loading,
}: {
  entries: { id: string; created_at: string; fundamental_view: string | null; confidence: number | null; critic_verdict: string | null; model_provider: string | null; model_name: string | null }[];
  loading: boolean;
}) {
  if (loading) return <p className="px-4 py-3 text-xs text-muted">Loading…</p>;
  if (entries.length === 0)
    return <EmptyState title="No history" description="No previous runs." />;
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="border-b border-border text-left text-muted">
          <th className="px-4 py-2 font-medium">Timestamp</th>
          <th className="px-4 py-2 font-medium">View</th>
          <th className="px-4 py-2 font-medium">Confidence</th>
          <th className="px-4 py-2 font-medium">Critic</th>
          <th className="px-4 py-2 font-medium">Model</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((h) => (
          <tr key={h.id} className="border-b border-border/40 last:border-0">
            <td className="px-4 py-1.5 text-muted">
              {new Date(h.created_at).toLocaleString()}
            </td>
            <td className={`px-4 py-1.5 ${h.fundamental_view ? VIEW_STYLES[h.fundamental_view] : ""}`}>
              {h.fundamental_view ?? "—"}
            </td>
            <td className="px-4 py-1.5 font-mono tabular-nums text-muted">
              {h.confidence != null ? h.confidence.toFixed(2) : "—"}
            </td>
            <td className={`px-4 py-1.5 ${h.critic_verdict ? VERDICT_STYLES[h.critic_verdict] : "text-muted"}`}>
              {h.critic_verdict ?? "—"}
            </td>
            <td className="px-4 py-1.5 text-muted">
              {h.model_provider}/{h.model_name}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}