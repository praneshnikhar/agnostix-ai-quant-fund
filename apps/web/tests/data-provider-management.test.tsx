import { beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { DataProviderDetail } from "@/components/data-providers/data-provider-detail";
import { DataProviderList } from "@/components/data-providers/data-provider-list";

describe("data provider management UI", () => {
  beforeEach(() => cleanup());

  it("keeps data providers separate from AI providers", () => {
    render(<DataProviderList />);
    expect(screen.getByText("Alpaca")).toBeTruthy();
    expect(screen.getByText("Data infrastructure boundary")).toBeTruthy();
    expect(screen.queryByText("OpenRouter")).toBeNull();
  });

  it("exposes only the supported Alpaca credential and feed fields", () => {
    render(<DataProviderDetail providerId="alpaca" />);
    expect(screen.getByText("Market data feed")).toBeTruthy();
    expect(screen.queryByText("Market Data Base URL")).toBeNull();
    expect(screen.queryByText("Trading Base URL")).toBeNull();
    expect(screen.getByText(/Trading is shown as a separate capability/)).toBeTruthy();
  });

  it("keeps test and save disabled while masking replacement credentials", () => {
    render(<DataProviderDetail providerId="alpaca" />);
    expect((screen.getAllByRole("button", { name: "Test connection" })[0] as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getAllByRole("button", { name: "Save provider" })[0] as HTMLButtonElement).disabled).toBe(true);
    const alpacaReplaceButtons = screen.getAllByRole("button", { name: "Replace Alpaca credentials" });
    fireEvent.click(alpacaReplaceButtons[alpacaReplaceButtons.length - 1]);
    expect(screen.getByPlaceholderText("Enter replacement api key").getAttribute("type")).toBe("password");
    expect(screen.getByText(/never returned/)).toBeTruthy();
  });
});
