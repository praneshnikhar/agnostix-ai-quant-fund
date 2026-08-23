import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ProviderDetail } from "@/components/providers/provider-detail";
import { ProviderList } from "@/components/providers/provider-list";

describe("provider management UI", () => {
  it("renders provider catalog without claiming connection state", () => {
    render(<ProviderList />);
    expect(screen.getByText("OpenRouter")).toBeTruthy();
    expect(screen.getAllByText("not connected").length).toBeGreaterThan(0);
    expect(screen.getByText("Credential boundary")).toBeTruthy();
  });

  it("opens add flow and keeps save backend-disabled", () => {
      render(<ProviderList />);
      fireEvent.click(screen.getAllByRole("button", { name: "Add provider" })[0]);
      expect(screen.queryByRole("dialog", { name: "Global search" })).toBeNull();
      expect(screen.getByRole("dialog", { name: "Add AI provider" })).toBeTruthy();
      expect((screen.getByRole("button", { name: "Save provider" }) as HTMLButtonElement).disabled).toBe(true);
      fireEvent.click(screen.getByRole("button", { name: "Ollama local" }));
      expect(screen.queryByText("API key")).toBeNull();
  });

  it("masks credentials and exposes replacement only in memory", () => {
    render(<ProviderDetail providerId="openrouter" />);
      expect(screen.getByText("••••••••••••••••")).toBeTruthy();
      fireEvent.click(screen.getByRole("button", { name: "Replace" }));
      const input = screen.getByPlaceholderText("Enter replacement key");
      expect(input.getAttribute("type")).toBe("password");
    expect(screen.getByText(/never retrieved or shown/)).toBeTruthy();
  });
});
