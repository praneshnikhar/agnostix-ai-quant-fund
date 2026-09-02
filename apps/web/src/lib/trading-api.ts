/**
 * Trading desk API client — typed against the /trading, /options, and
 * /playground backend contracts.
 */

import { apiFetch } from "./api";

export interface DeskAccount {
  equity: number;
  cash: number;
  buying_power: number;
  daily_pl: number;
  open_positions: number;
  defined_risk_committed: number;
  exposure_by_underlying: Record<string, number>;
}

export interface DeskStatus {
  kill_switch: boolean;
  started_at: string;
  execute: boolean;
  account: DeskAccount;
  open_strategies: DecisionDto[];
  journal_head: string;
  journal_verified: boolean;
}

export interface GateDto {
  gate: string;
  passed: boolean;
  hard: boolean;
  limit: number | null;
  actual: number | null;
  detail: string | null;
}

export interface RiskDto {
  verdict: string;
  gates: GateDto[];
}

export interface SignalDto {
  symbol: string;
  direction: string;
  confidence: number;
  thesis: string;
  catalyst: string | null;
  invalidation: string | null;
  model: string | null;
  provider: string | null;
}

export interface LegDto {
  contract: { symbol: string; strike: number; option_type: string; expiration: string };
  side: string;
  quantity: number;
  theoretical: number | null;
  delta: number | null;
}

export interface StrategyDto {
  strategy_id: string;
  name: string;
  underlying: string;
  legs: LegDto[];
  net_credit: number | null;
  max_loss: number | null;
  max_profit: number | null;
  probability_of_profit: number | null;
  days_to_expiration: number | null;
}

export interface DecisionDto {
  decision_id: string;
  symbol: string;
  timestamp: string;
  signal: SignalDto | null;
  strategy: StrategyDto | null;
  risk: RiskDto | null;
  status: string;
  order_id: string | null;
  reason: string | null;
  market_price: number | null;
  iv_rank: number | null;
}

export interface JournalEntry {
  seq: number;
  timestamp: string;
  kind: string;
  symbol: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  hash: string;
}

export interface JournalResponse {
  verified: boolean;
  count: number;
  entries: JournalEntry[];
}

export interface EquityPoint {
  timestamp: string;
  equity: number;
  cash: number;
  daily_pl: number | null;
}

export const getDeskStatus = () => apiFetch<DeskStatus>("/trading/status");
export const postDecide = (symbol: string, execute?: boolean) =>
  apiFetch<DecisionDto>("/trading/decide", {
    method: "POST",
    body: JSON.stringify({ symbol, execute }),
  });
export const postRun = (symbols: string[]) =>
  apiFetch<{ decisions: DecisionDto[] }>("/trading/run", {
    method: "POST",
    body: JSON.stringify({ symbols }),
  });
export const postKill = () => apiFetch<{ kill_switch: boolean }>("/trading/kill", { method: "POST" });
export const postResume = () => apiFetch<{ kill_switch: boolean }>("/trading/resume", { method: "POST" });
export const postSnapshot = () => apiFetch<{ recorded: boolean }>("/trading/snapshot", { method: "POST" });
export const getJournal = (limit = 200) => apiFetch<JournalResponse>(`/trading/journal?limit=${limit}`);
export const getEquity = () => apiFetch<EquityPoint[]>("/trading/equity");
