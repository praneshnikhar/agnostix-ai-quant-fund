# 12 — Portal UX: The AI Fund Cockpit

> **Status:** Product / UX Specification
> **Companion to:** `07_AIFund_Vision.md`
> **Extends:** `01_PRD.md` (dashboard requirements)

---

## 1. Design Philosophy

The portal should feel like an **actual AI hedge fund** — not a generic SaaS dashboard.

Design reference:

> **Bloomberg Terminal × Palantir × modern quant fund cockpit.**

Invest heavily in UX. The interface is a major differentiator: it makes the autonomous fund legible, trustworthy, and auditable to its human overseers.

---

## 2. Screen Inventory

| # | Screen | Purpose |
|---|---|---|
| 1 | Home / Fund Overview | Fund-level health at a glance |
| 2 | Agent Floor | Live view of the AI fund working |
| 3 | Investment Thesis | Debate output and evidence per idea |
| 4 | Trade Decision Chain | "Why did we trade?" — full decision audit |
| 5 | Learning Dashboard | Agent/strategy performance and allocation |
| 6 | Model Registry | Model versions, metrics, promotion history |

---

## 3. Screen 1 — Home / Fund Overview

```text
┌───────────────────────────────────────────────────────────┐
│ AI FUND                                MARKET OPEN ●       │
├───────────────────────────────────────────────────────────┤
│                                                           │
│ AUM              TODAY             YTD             SHARPE  │
│ $10.42M          +1.84%            +17.2%           2.14  │
│                                                           │
├──────────────────────────┬────────────────────────────────┤
│ EQUITY CURVE              │ CURRENT EXPOSURE              │
│                          │                                │
│      ╱──────             │ Tech        ████████  42%      │
│  ───╯                    │ Healthcare  ███      16%       │
│                          │ Finance     ██       11%       │
│                          │ Cash        █████    25%       │
├──────────────────────────┴────────────────────────────────┤
│ AI INVESTMENT ACTIVITY                                    │
│                                                           │
│ 🟢 Momentum Agent      NVDA     BUY       91%             │
│ 🟢 Fundamental Agent   MSFT     BUY       84%             │
│ 🟡 Macro Agent         TSLA     HOLD      61%             │
│ 🔴 Risk Agent          AMD      BLOCK     —               │
└───────────────────────────────────────────────────────────┘
```

### Components

- KPI strip: AUM, daily P&L, YTD return, Sharpe
- Equity curve (intraday + since inception)
- Current exposure by sector / strategy / single-name concentration
- Live AI investment activity feed (signals, blocks, approvals)

---

## 4. Screen 2 — Agent Floor

The really interesting screen: **you should be able to see the AI fund working.**

```text
RESEARCH FLOOR

NEWS AGENT
● Processing 1,284 articles
● 38 material events
● 12 new signals

FUNDAMENTAL AGENT
● Analyzing 2,481 companies
● 143 valuation anomalies

MOMENTUM AGENT
● Scanning 6,420 securities
● 27 breakout candidates

MACRO AGENT
● Regime: Risk-On
● Confidence: 72%

RISK AGENT
● Portfolio VaR: 2.4%
● Concentration: NORMAL
● Drawdown: -1.2%
```

Click an agent and see its **current hypotheses**, workload, confidence levels, and recent outputs.

This becomes a major differentiator — transparency into agent cognition in real time.

---

## 5. Screen 3 — Investment Thesis

Per-idea view of the Investment Committee debate (`09_Investment_Committee_Debate.md`):

### NVDA — LONG

```text
AI INVESTMENT COMMITTEE

                 BULL        BEAR
Fundamental       88          32
Momentum          91          41
News              79          36
Macro             63          57
Risk              —           HIGH

CONSENSUS                         78%

Expected Return                  +8.4%
Expected Volatility              22%
Suggested Allocation             2.8%

┌─────────────────────────────────────────┐
│ WHY?                                    │
│                                         │
│ ✓ Revenue growth accelerating            │
│ ✓ Positive earnings revision             │
│ ✓ Strong price momentum                  │
│ ✓ AI infrastructure demand               │
│                                         │
│ RISKS                                   │
│                                         │
│ ! Elevated valuation                    │
│ ! Semiconductor cyclicality              │
│ ! High portfolio correlation             │
└─────────────────────────────────────────┘
```

**Crucially: show the evidence.** Every claim links to its underlying data source (headline, filing, price series). Not just "the AI thinks NVDA is bullish."

---

## 6. Screen 4 — "Why did we trade?" (Trade Decision Chain)

The most valuable page may actually be this one. For every position:

```text
TRADE #84721

NVDA LONG
Entered: 181.42
Size: 2.8%

DECISION CHAIN

News Agent
     ↓
Positive AI infrastructure announcement

Fundamental Agent
     ↓
Forward earnings estimate revised +7%

Momentum Agent
     ↓
Breakout + volume confirmation

Bear Agent
     ↓
Valuation risk identified

Risk Agent
     ↓
Portfolio concentration acceptable

Portfolio Manager
     ↓
APPROVED

Execution
     ↓
Filled @ 181.47
```

This directly extends the audit-trail architecture already specified in the current system (`02_FRD.md`, `04_Schemas.md`).

---

## 7. Screen 5 — Learning Dashboard

A first-class part of the product. Instead of just "Portfolio up 17%", show:

### AI Performance

| Agent          | Signals | Win Rate | Sharpe | Avg Return | Calibration |
| -------------- | ------: | -------: | -----: | ---------: | ----------: |
| Momentum       |     482 |      61% |   1.72 |      +1.8% |         82% |
| Fundamental    |     317 |      67% |   2.04 |      +2.4% |         89% |
| News           |     529 |      55% |   1.31 |      +1.2% |         74% |
| Mean Reversion |     394 |      49% |   0.91 |      +0.6% |         68% |

### Strategy Allocation

```text
Fundamental       31%
Momentum          27%
Macro             17%
News              15%
Mean Reversion     6%
Cash               4%
```

And the allocator can explain:

> *"Fundamental allocation increased from 22% → 31% after 40 consecutive out-of-sample observations improved its risk-adjusted performance."*

That is much more compelling than saying "our LLM learned."

---

## 8. Screen 6 — Model Registry

Treat models like software releases (`10_Learning_System.md`):

```text
MODEL REGISTRY

Fundamental-Agent
────────────────────────────────
v1.0   Sharpe 1.42
v1.1   Sharpe 1.67
v1.2   Sharpe 1.91   ← CURRENT

Training period:
2022-01 → 2025-12

Validation:
2026-01 → 2026-04

Out-of-sample:
2026-05 → 2026-07

Status:
● Production

Promoted because:
+12.4% relative Sharpe
-8.1% drawdown
+6.7% calibration
```

Now you have an **AI research platform**, rather than merely an AI trading bot.

---

## 9. UX Principles

| Principle | Application |
|---|---|
| Show reasoning, not just outcomes | Every decision exposes its chain |
| Evidence-first | Claims link to data; no unexplained assertions |
| Disagreement is visible | Bull/bear scores shown side-by-side |
| Calibration over confidence theater | Display calibration scores prominently |
| Determinism visible | Risk blocks show which deterministic rule fired |
| Human gate explicit | Approval queue states are first-class UI states |