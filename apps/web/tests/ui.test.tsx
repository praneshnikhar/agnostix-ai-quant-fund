import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge, EmptyState, StatusDot } from "@/components/ui";

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
});