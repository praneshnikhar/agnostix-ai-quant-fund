/**
 * M1 market explorer tests — deterministic fixture data only.
 * Fixture data is clearly labeled; never presented as live market data.
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import MarketsPage from "@/app/markets/page";
import { FIXTURE_BARS } from "@/lib/markets-api";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(async (path: string) => {
    if (path === "/markets") {
      return {
        watchlist: [
          { symbol: "AAPL", name: "Apple Inc.", exchange: "NASDAQ" },
          { symbol: "MSFT", name: "Microsoft", exchange: "NASDAQ" },
        ],
        generated_at: new Date().toISOString(),
      };
    }
    throw new Error(`unexpected ${path}`);
  }),
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("Markets page", () => {
  it("renders watchlist symbols from the API", async () => {
    renderWithClient(<MarketsPage />);
    expect(await screen.findByText("AAPL")).toBeTruthy();
    expect(screen.getByText("MSFT")).toBeTruthy();
  });

  it("fixture bars are labeled as fixture provider (never live)", () => {
    for (const bar of FIXTURE_BARS) {
      expect(bar.provider).toBe("fixture");
    }
  });
});