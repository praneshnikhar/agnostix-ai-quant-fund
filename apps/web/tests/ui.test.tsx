import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge, EmptyState, ErrorState, LoadingState, ModelBadge, StatusDot } from "@/components/ui";

describe("design-system primitives", () => {
  it("renders a badge with tone styling", () => {
    render(<Badge tone="positive">PASS</Badge>);
    const badge = screen.getByText("PASS");
    expect(badge.className).toContain("text-positive");
  });

  it("renders a status dot with an accessible label", () => {
    render(<StatusDot status="ok" />);
    const dot = screen.getByRole("status");
    expect(dot.getAttribute("aria-label")).toBe("status: ok");
  });

  it("renders empty state copy", () => {
    render(
      <EmptyState title="No data" description="Awaiting first milestone." />
    );
    expect(screen.getByText("No data")).toBeTruthy();
    expect(screen.getByText(/Awaiting first milestone/)).toBeTruthy();
  });

  it("renders explicit loading and error states", () => {
    render(<><LoadingState label="Loading market data" /><ErrorState description="Market API unavailable" /></>);
    expect(screen.getByText("Loading market data")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("Market API unavailable");
  });

  it("does not fabricate model metadata", () => {
    render(<ModelBadge />);
    expect(screen.getByText("not connected")).toBeTruthy();
  });
});
