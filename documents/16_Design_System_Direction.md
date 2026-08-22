# 16 — UI Design Language & Dashboard Information Architecture

> **Status:** Design System Direction
> **Companion to:** `12_Portal_UX.md`, `15_Monorepo_Structure.md`
> **Feeds:** `DESIGN_SYSTEM.md` (repo root)

---

## 1. Visual Direction

**Institutional dark terminal + modern AI workspace.**

### What it is NOT

- Neon crypto UI
- Excessive gradients
- Generic SaaS cards
- Giant rounded rectangles everywhere
- "AI sparkle" everywhere

### What it IS

- Dark graphite background
- Near-black panels
- Restrained borders
- High information density
- Excellent typography
- Compact metrics
- Subtle status colors
- Precise charts
- Strong hierarchy
- Excellent spacing
- Keyboard navigation
- Responsive layouts

Design reference:

> **Bloomberg + Linear + Palantir + modern institutional trading software.**

---

## 2. The Dashboard Must Immediately Answer Five Questions

When you open the dashboard:

### 1. How is the fund doing?

```text
NAV
Daily P&L
MTD
YTD
Sharpe
Sortino
Drawdown
```

### 2. What is the AI doing?

```text
Agents active
Signals generated
Research completed
Investment theses
Debates underway
```

### 3. What does it want to trade?

```text
NVDA   LONG   87%
MSFT   LONG   81%
AMD    SHORT  73%
```

### 4. Why?

Evidence + thesis + disagreement.

### 5. How risky is it?

```text
Gross exposure
Net exposure
Sector exposure
VaR
Drawdown
Concentration
Liquidity
Correlation
```

That is the primary experience.

---

## 3. Design Tokens (Foundation)

| Token | Direction |
|---|---|
| Background | Dark graphite (`#0A0C10` range) |
| Panel | Near-black elevated surfaces |
| Border | Restrained, low-contrast hairlines |
| Text primary | High-contrast off-white |
| Text secondary | Muted gray, still legible at density |
| Positive | Muted green (status, not decoration) |
| Negative | Muted red |
| Warning | Amber |
| Accent | Single restrained accent for interactive elements |
| Font | Inter or similar for UI; tabular numerals for metrics; monospace for prices/tickers |
| Density | Compact rows, tight metric clusters — information-dense over airy |
| Radius | Small radii; no giant rounded rectangles |
| Motion | Framer Motion sparingly — state transitions only |

---

## 4. Component Priorities (shadcn/ui base + custom)

Custom components needed beyond shadcn defaults:

- Metric tile / KPI strip
- Ticker / price cell (tabular numerals)
- Equity curve panel (TradingView Lightweight Charts)
- Exposure bar chart
- Signal row (agent, symbol, direction, confidence)
- Debate scorecard (bull/bear columns)
- Decision chain timeline
- Agent status card (live workload)
- Risk limit gauge with deterministic-rule annotations
- Event log table (virtualized)
- Approval queue item

---

## 5. Interaction Principles

| Principle | Application |
|---|---|
| Keyboard navigation | Command palette, j/k list navigation, hotkeys for approval actions |
| Live by default | WebSocket/SSE-driven updates; no manual refresh |
| Evidence one click away | Every claim/number links to its source artifact |
| Determinism visible | Risk blocks show which rule fired and its threshold |
| Status colors are semantic | Green/red/amber mean something specific everywhere |
| Density with hierarchy | Dense but scannable: size/weight/color establish reading order |

---

## 6. Deliverable in M0

M0 establishes:

- Theme tokens wired into Tailwind config
- Base layout shell: sidebar navigation (workspace routes), topbar (market status, clock), content area
- Core primitives: MetricTile, Panel, DataTable shell, StatusDot
- Dashboard placeholder answering the five questions structurally (with empty/skeleton states)