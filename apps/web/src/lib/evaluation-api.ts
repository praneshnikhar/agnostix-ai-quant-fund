/**
 * Frontend contracts for the M2.2 evaluation domain.
 *
 * The backend persists these records but does not currently expose an
 * evaluation read route. Keep the types here so the Models UI can adopt the
 * eventual API without inventing browser-side provider calls or responses.
 */
export type EvaluationStatus = "pending" | "running" | "completed" | "failed";

export interface EvaluationModelRecord {
  provider: string;
  model: string;
  status: EvaluationStatus;
  context_version: string | null;
  context_hash: string | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  estimated_cost_usd: number | null;
  grounding_passed: boolean | null;
  evidence_coverage: number | null;
  critic_verdict: string | null;
  structured_output: boolean | null;
  error: string | null;
}

export interface EvaluationRunRecord {
  id: string;
  symbol: string;
  status: EvaluationStatus;
  created_at: string;
  completed_at: string | null;
  context_version: string;
  context_hash: string;
  models: EvaluationModelRecord[];
  error: string | null;
}
