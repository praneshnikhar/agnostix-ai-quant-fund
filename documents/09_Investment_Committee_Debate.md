# 09 — Investment Committee: Debate, Jury & Quantitative Portfolio Manager

> **Status:** Architecture Specification
> **Companion to:** `07_AIFund_Vision.md`, `08_Agent_Bands_Architecture.md`
> **Extends:** `04_Schemas.md` (signal/critic schemas)

---

## 1. Overview

When multiple strategy agents produce conflicting signals for the same symbol, the system must not simply average them. Instead, it convenes an **AI Investment Committee** — a structured debate in which agents challenge each hypothesis before a quantitative Portfolio Manager allocates capital.

This resembles an investment committee rather than a chatbot.

---

## 2. The Problem: Conflicting Signals

Example signal set for NVDA:

```text
NVDA

Fundamental Agent:       BUY  82%
Momentum Agent:          BUY  91%
News Agent:              BUY  73%
Macro Agent:             HOLD 58%
Mean Reversion Agent:    SELL 61%
```

**Don't simply average those numbers.** Averaging hides the reasoning, the evidence quality, and the disagreement structure. Instead, create a **debate layer**.

---

## 3. Debate Roles

### Bull Agent
> Build the strongest possible case for buying NVDA.

- Assembles the best evidence from all supporting signals
- Constructs a coherent investment thesis
- Quantifies expected return and upside scenarios

### Bear Agent
> Attempt to falsify the investment thesis.

- Actively argues against the trade
- Identifies weaknesses in the bull case
- Surfaces contrary evidence and failure modes

### Risk Agent
> Identify ways this trade could damage the portfolio.

- Correlation with existing holdings
- Concentration impact
- Drawdown scenarios
- Liquidity and exit risk

### Evidence Agent
> Verify every factual claim against the underlying dataset.

- Checks each claim against the data fabric (`11_Data_Fabric_Snapshots.md`)
- Flags unsupported or stale claims
- Assigns evidence quality scores

### Judge Agent
> Evaluate the competing arguments and produce a structured investment recommendation.

- Weighs arguments by evidence quality, not rhetoric
- Produces consensus score, expected return/volatility, and suggested allocation
- Records dissent explicitly

---

## 4. Debate Output: Investment Thesis

Example rendered thesis:

```text
NVDA — LONG

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

**Crucially: show the evidence.** Not just "the AI thinks NVDA is bullish" — every claim links back to its underlying data via `evidence_refs`.

---

## 5. Thesis Schema

```json
{
  "thesis_id": "...",
  "symbol": "NVDA",
  "direction": "LONG",
  "snapshot_id": "...",
  "debate": {
    "bull_case": { "arguments": [ ... ], "score": 88 },
    "bear_case": { "arguments": [ ... ], "score": 32 },
    "risk_case": { "concerns": [ ... ], "severity": "MEDIUM" },
    "evidence_audit": { "claims_verified": 14, "claims_flagged": 1 },
    "judge_verdict": {
      "consensus": 0.78,
      "expected_return": 0.084,
      "expected_volatility": 0.22,
      "suggested_allocation": 0.028,
      "dissent": [ ... ]
    }
  },
  "model_versions": { ... }
}
```

---

## 6. The Portfolio Manager Is NOT an LLM Alone

This is one of the most important architectural decisions.

The PM layer is a **Capital Allocation Engine** driven by quantitative inputs:

```text
Expected Return
      +
Signal Confidence
      +
Historical Strategy Performance
      +
Market Regime
      +
Correlation
      +
Portfolio Exposure
      +
Risk Budget
      +
Liquidity
      ↓
Capital Allocation Engine
```

The system might conclude:

```text
Momentum strategy       → 24% allocation
Fundamental strategy    → 31%
News strategy           → 12%
Mean reversion          → 8%
Macro                   → 15%
Cash                    → 10%
```

That allocation must be supported by **quantitative models**, not merely an LLM saying "I feel bullish."

### Allocation Engine Inputs

| Input | Source |
|---|---|
| Expected return | Judge verdict + predictive models |
| Signal confidence | Strategy agent outputs |
| Historical strategy performance | Outcome Engine / learning loop |
| Market regime | Regime Detection Engine (`13_Evolved_Architecture_Roadmap.md`) |
| Correlation | Covariance estimation over portfolio |
| Portfolio exposure | Portfolio Monitor |
| Risk budget | Deterministic risk policy |
| Liquidity | Market structure data |

### Allocation Methods (by stage)

- Stage 1: rule-based sizing (fixed fractions, volatility targeting)
- Stage 2: Bayesian shrinkage toward strategy-level Sharpe estimates
- Stage 3: contextual bandits / offline RL over allocation policy

---

## 7. Pipeline Summary

```text
Strategy Signals (Band 3)
        │
        ▼
Signal Aggregator (group by symbol, detect conflicts)
        │
        ▼
Debate / Jury (Bull → Bear → Risk → Evidence → Judge)
        │
        ▼
Investment Thesis (structured, evidence-linked)
        │
        ▼
Capital Allocation Engine (quantitative)
        │
        ▼
Deterministic Risk Gate (approve / block)
        │
        ▼
Execution
```

---

## 8. Design Rules

| Rule | Rationale |
|---|---|
| Never average raw signal scores | Averaging destroys reasoning and disagreement structure |
| Bear agent must be genuinely adversarial | Prevents groupthink / sycophancy |
| Evidence agent audits all factual claims | Grounding; prevents hallucinated theses |
| Judge weighs by evidence quality | Rhetoric must not beat data |
| PM allocation is quantitative | Reproducible, backtestable, explainable |
| All debate artifacts persisted | Audit trail + training data for future learning |