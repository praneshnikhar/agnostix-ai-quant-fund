import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import ModelsPage from "@/app/models/page";

describe("model evaluation center", () => {
  it("renders explicit registry and unavailable states", () => {
    render(<ModelsPage />);
    expect(screen.getByText("Model registry")).toBeTruthy();
    expect(screen.getByText("OpenRouter")).toBeTruthy();
    expect(screen.getAllByText("not connected").length).toBeGreaterThan(0);
  });

  it("switches to comparison without inventing metrics", () => {
    render(<ModelsPage />);
    const comparisonTabs = screen.getAllByRole("tab", { name: "Model comparison" });
    fireEvent.click(comparisonTabs[comparisonTabs.length - 1]);
    expect(screen.getByText("Grounding")).toBeTruthy();
    expect(screen.getByText("no benchmark data")).toBeTruthy();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});
