/**
 * M2 research UI tests — deterministic; API client mocked.
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/research-api", () => ({
  getLatestResearch: vi.fn(() =>
    Promise.resolve({
      id: "run-1",
      symbol: "ACME",
      status: "completed",
      created_at: "2026-08-01T00:00:00Z",
      completed_at: "2026-08-01T00:00:05Z",
      fundamental_view: "BULLISH",
      confidence: 0.7,
      critic_verdict: "PASS",
      agent_id: "fundamental_research_agent_v1",
      agent_version: "v1",
      prompt_version: "m2-fundamental-v1",
      model_provider: "mock",
      model_name: "mock-model-1",
      context_version: "m2-v1",
      research_output: {
        symbol: "ACME",
        research_timestamp: "2026-08-01T00:00:00Z",
        fundamental_view: "BULLISH",
        confidence: 0.7,
        investment_thesis: "Strong growth.",
        financial_assessment: { area: "financial", summary: "ok", statements: [], confidence: 0.5 },
        growth_assessment: {
          area: "growth",
          summary: "growing",
          statements: [
            { kind: "FACT", text: "Revenue was 115,200.0 in FY2025.", evidence_ids: ["ev1"] },
          ],
          confidence: 0.5,
        },
        profitability_assessment: { area: "profitability", summary: "ok", statements: [], confidence: 0.5 },
        cash_flow_assessment: { area: "cash_flow", summary: "ok", statements: [], confidence: 0.5 },
        balance_sheet_assessment: { area: "balance_sheet", summary: "ok", statements: [], confidence: 0.5 },
        valuation_assessment: { area: "valuation", summary: "ok", statements: [], confidence: 0.5 },
        catalysts: [],
        risks: [],
        bear_case: "",
        invalidation_conditions: [],
        evidence: [
          { evidence_id: "ev1", source: "acme-fy2025-10k", source_type: "document", claim_supported: "growth", relevant_period: null, url: null },
        ],
        data_quality: [],
        limitations: [],
      },
      critic_output: {
        verdict: "PASS",
        findings: [],
        claim_checks: [{ statement: "growth/FACT", status: "SUPPORTED", detail: null }],
        deterministic_checks_passed: true,
        notes: null,
      },
      error: null,
    })
  ),
  getResearchHistory: vi.fn(() => Promise.resolve([])),
  getFundamentals: vi.fn(() =>
    Promise.resolve([
      { metric: "revenue", value: 115200000000, period_type: "annual", period_end: "2025-09-30", fiscal_year: 2025, fiscal_quarter: null, currency: "USD", quality: "ok", provider: "fixture" },
      { metric: "gross_margin", value: null, period_type: "annual", period_end: "2025-09-30", fiscal_year: 2025, fiscal_quarter: null, currency: "USD", quality: "incomplete", provider: "fixture" },
    ])
  ),
  postRunResearch: vi.fn(),
}));

import ResearchSymbolPage from "@/app/research/[symbol]/page";

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("research symbol page", () => {
  it("renders view, thesis, evidence, critic and metadata", async () => {
    renderWithProviders(<ResearchSymbolPage params={{ symbol: "ACME" }} />);
    expect(await screen.findByText("BULLISH")).toBeTruthy();
    expect(screen.getByText("Strong growth.")).toBeTruthy();
    expect(screen.getByText(/Revenue was 115,200.0 in FY2025/)).toBeTruthy();
    expect(screen.getByText("acme-fy2025-10k")).toBeTruthy();
    expect(screen.getByText("PASS")).toBeTruthy();
    expect(screen.getByText("mock-model-1")).toBeTruthy();
    // deterministic-data disclaimer present
    expect(screen.getByText(/LLM never computes these/)).toBeTruthy();
  });

  it("renders unavailable metrics as unavailable — never fabricated", async () => {
    renderWithProviders(<ResearchSymbolPage params={{ symbol: "ACME" }} />);
    await screen.findByText("BULLISH");
    expect((await screen.findAllByText("unavailable")).length).toBeGreaterThan(0);
  });
});
