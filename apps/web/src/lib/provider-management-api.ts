/**
 * Safe provider-management contracts.
 *
 * There are no provider-management HTTP routes yet. These types deliberately
 * model credential presence rather than credential values so the future API
 * cannot require secrets to be returned to the browser.
 */
export type ProviderCategory = "cloud" | "local" | "custom";
export type ProviderStatus = "connected" | "testing" | "disconnected" | "error" | "disabled" | "not_configured" | "backend_unavailable";

export interface ManagedModel {
  provider: string;
  model: string;
  display_name?: string | null;
  status?: "enabled" | "disabled" | "unavailable";
  capabilities?: string[] | null;
  context_window?: number | null;
  is_default?: boolean;
  enabled?: boolean;
}

export interface ManagedProvider {
  id: string;
  name: string;
  category: ProviderCategory;
  status: ProviderStatus;
  enabled: boolean;
  base_url?: string | null;
  has_credentials: boolean;
  configured_models: number;
  default_model?: string | null;
  last_connection_test?: string | null;
  models: ManagedModel[];
}

export interface ProviderConnectionResult {
  status: "connected" | "failed";
  provider: string;
  model?: string | null;
  latency_ms?: number | null;
  error?: string | null;
}

export const PROVIDER_CATALOG: ReadonlyArray<{ id: string; name: string; category: ProviderCategory; description: string; supportsDiscovery: boolean }> = [
  { id: "openrouter", name: "OpenRouter", category: "cloud", description: "Cloud model routing and provider aggregation.", supportsDiscovery: true },
  { id: "openai", name: "OpenAI", category: "cloud", description: "Direct OpenAI-compatible cloud models.", supportsDiscovery: false },
  { id: "anthropic", name: "Anthropic", category: "cloud", description: "Direct Claude model access.", supportsDiscovery: false },
  { id: "google", name: "Google / Gemini", category: "cloud", description: "Gemini models when a backend adapter is available.", supportsDiscovery: false },
  { id: "deepseek", name: "DeepSeek", category: "cloud", description: "DeepSeek models through a configured adapter.", supportsDiscovery: false },
  { id: "ollama", name: "Ollama", category: "local", description: "Local inference served from an Ollama host.", supportsDiscovery: true },
  { id: "custom", name: "Custom / OpenAI-compatible", category: "custom", description: "vLLM, TGI, private inference, or other compatible endpoints.", supportsDiscovery: false },
];

export function providerCatalogEntry(id: string) {
  return PROVIDER_CATALOG.find((provider) => provider.id === id) ?? PROVIDER_CATALOG.find((provider) => provider.id === "custom")!;
}
