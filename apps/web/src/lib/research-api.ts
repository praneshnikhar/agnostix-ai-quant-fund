/**
 * M2 fundamental research API client — typed against internal backend schemas.
 * No provider-specific shapes leak into the UI.
 */

import { apiFetch } from "./api";

export type FundamentalView =
  | "BULLISH"
  | "NEUTRAL"
  | "BEARISH"
  | "INSUFFICIENT_DATA";

export type CriticVerdict = "PASS" | "REVISE" | "REJECT";

export interface EvidenceRef {
  evidence_id: string;
  source: string;
  source_type: string;
  claim_supported: string;
  relevant_period: string | null;
  url: string | null;
}

export interface ResearchStatement {
  kind: "FACT" | "INTERPRETATION" | "CONCLUSION";
  text: string;
  evidence_ids: string[];
}

export interface Assessment {
  area: string;
  summary: string;
  statements: ResearchStatement[];
  confidence: number;
}

export interface Catalyst {
  description: string;
  expected_timeframe: string | null;
  evidence_ids: string[];
}

export interface RiskItem {
  description: string;
  severity: string;
  evidence_ids: string[];
}

export interface InvalidationCondition {
  condition: string;
  observable_signal: string;
}

export interface Thesis {
  symbol: string;
  research_timestamp: string;
  fundamental_view: FundamentalView;
  confidence: number;
  investment_thesis: string;
  financial_assessment: Assessment;
  growth_assessment: Assessment;
  profitability_assessment: Assessment;
  cash_flow_assessment: Assessment;
  balance_sheet_assessment: Assessment;
  valuation_assessment: Assessment;
  catalysts: Catalyst[];
  risks: RiskItem[];
  bear_case: string;
  invalidation_conditions: InvalidationCondition[];
  evidence: EvidenceRef[];
  data_quality: { area: string; quality: string; detail: string | null }[];
  limitations: string[];
}

export interface ClaimCheck {
  statement: string;
  status: "SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED" | "MISSING_EVIDENCE";
  detail: string | null;
}

export interface CriticFinding {
  category: string;
  severity: string;
  detail: string;
}

export interface CriticOutput {
  verdict: CriticVerdict;
  findings: CriticFinding[];
  claim_checks: ClaimCheck[];
  deterministic_checks_passed: boolean;
  notes: string | null;
}

export interface ResearchRun {
  id: string;
  symbol: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  fundamental_view: FundamentalView | null;
  confidence: number | null;
  critic_verdict: CriticVerdict | null;
  agent_id: string | null;
  agent_version: string | null;
  prompt_version: string | null;
  model_provider: string | null;
  model_name: string | null;
  model_requested?: string | null;
  latency_ms?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  estimated_cost_usd?: number | null;
  context_version: string | null;
  research_output: Thesis | null;
  critic_output: CriticOutput | null;
  error: string | null;
}

export interface HistoryEntry {
  id: string;
  created_at: string;
  fundamental_view: FundamentalView | null;
  confidence: number | null;
  critic_verdict: CriticVerdict | null;
  model_provider: string | null;
  model_name: string | null;
  prompt_version: string | null;
}

export interface ResearchRunMetadata {
  provider: string | null;
  requestedModel: string | null;
  servedModel: string | null;
  agent: string | null;
  agentVersion: string | null;
  promptVersion: string | null;
  contextVersion: string | null;
  contextHash: string | null;
  latencyMs: number | null;
  inputTokens: number | null;
  outputTokens: number | null;
  totalTokens: number | null;
  estimatedCostUsd: number | null;
}

export interface MetricDto {
  metric: string;
  value: number | null;
  period_type: string;
  period_end: string;
  fiscal_year: number | null;
  fiscal_quarter: number | null;
  currency: string;
  quality: string;
  provider: string;
}

export interface DocumentDto {
  document_id: string;
  title: string;
  document_type: string;
  source: string | null;
  url: string | null;
  published_at: string | null;
  retrieved_at: string;
}

export const getLatestResearch = (symbol: string) =>
  apiFetch<ResearchRun>(`/research/${symbol}`);

export const getResearchHistory = (symbol: string, limit = 50) =>
  apiFetch<HistoryEntry[]>(`/research/${symbol}/history?limit=${limit}`);

export const getFundamentals = (symbol: string) =>
  apiFetch<MetricDto[]>(`/research/${symbol}/fundamentals`);

export const getEvidence = (symbol: string) =>
  apiFetch<EvidenceRef[]>(`/research/${symbol}/evidence`);

export const getResearchDocuments = (symbol: string) =>
  apiFetch<DocumentDto[]>(`/research/${symbol}/documents`);

export const getRun = (runId: string) =>
  apiFetch<ResearchRun>(`/research/runs/${runId}`);

export const postRunResearch = (symbol: string) =>
  apiFetch<{ run_id: string; status: string }>(`/research/${symbol}/run`, {
    method: "POST",
  });

export const postFeedback = (
  runId: string,
  decision: "APPROVE" | "REJECT" | "REQUEST_REVISION",
  notes?: string
) =>
  apiFetch<{ status: string }>(`/research/runs/${runId}/feedback`, {
    method: "POST",
    body: JSON.stringify({ decision, notes }),
    headers: { "Content-Type": "application/json" },
  });
