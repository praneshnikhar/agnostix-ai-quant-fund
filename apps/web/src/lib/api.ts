import type { HealthResponse } from "@agnostix/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Typed fetch helper for the FastAPI backend. */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!resp.ok) {
    throw new Error(`API ${resp.status}: ${await resp.text()}`);
  }
  return (await resp.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}

export interface AgentEvent {
  id: string;
  timestamp: string;
  agent_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  proposal_id: string | null;
}

export function getAgentEvents(limit = 20): Promise<AgentEvent[]> {
  return apiFetch<AgentEvent[]>(`/agent-events?limit=${limit}`);
}
