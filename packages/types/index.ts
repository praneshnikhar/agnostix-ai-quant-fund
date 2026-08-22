/**
 * Shared TypeScript API contracts — single source of truth for
 * frontend/backend message shapes. Mirrors apps/api/app/schemas/contracts.py.
 * Never duplicate these types elsewhere.
 */

export type WSMessageType =
  | "new_proposal"
  | "position_update"
  | "order_update"
  | "kill_switch"
  | "heartbeat";

export interface WSMessage {
  type: WSMessageType;
  payload: Record<string, unknown>;
  timestamp: string;
}

export interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy";
  version: string;
  environment: string;
  database: boolean;
  redis: boolean;
  timestamp: string;
}

export interface AgentEvent {
  id: string;
  timestamp: string;
  agent_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  proposal_id: string | null;
}