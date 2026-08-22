# 08 — Agent Bands Architecture

> **Status:** Architecture Specification
> **Companion to:** `07_AIFund_Vision.md`
> **Extends:** `02_FRD.md` (data interface requirements), `04_Schemas.md`

---

## 1. Overview

The AI fund is organized into approximately **six bands** of specialized agents. Each band has a distinct responsibility, and agents within a band produce structured outputs consumed by downstream bands. No agent "does everything."

```text
Band 1: Market Intelligence   (sensory system)
Band 2: Research Agents       (AI research department)
Band 3: Strategy Agents       (quant strategies → signals, not orders)
Band 4: Debate / Jury         (investment committee)
Band 5: Risk                  (deterministic + analytical risk)
Band 6: Execution & Monitoring (order lifecycle + portfolio monitor)
```

---

## 2. Band 1 — Market Intelligence

This is the **sensory system** of the fund.

Agents in this band continuously consume and normalize:

- Price / OHLCV
- Intraday trades
- Volume
- Volatility
- Market breadth
- News
- SEC / company filings
- Earnings
- Analyst revisions
- Macroeconomic data
- Interest rates
- Sector data
- Company fundamentals
- Alternative data (later)

### Requirements

The current FRD already requires normalized/cached market and news data and explicitly requires downstream agents to use an internal data interface rather than hitting external APIs directly. This band expands that considerably:

| Requirement | Description |
|---|---|
| Normalization | All sources normalized into canonical schemas (`04_Schemas.md`) |
| Caching | Layered cache with TTL per data type |
| Internal-only access | Downstream agents MUST use the internal data interface — no direct external API calls |
| Point-in-time correctness | Data must be retrievable as-of any timestamp `T` for replay/backtest |
| Provenance | Every record carries source, retrieval time, and license metadata |

---

## 3. Band 2 — Research Agents

This is effectively the **AI research department**. Each agent produces structured research — never trades directly.

### Agent Roster

#### Fundamental Analyst
> *"Is Microsoft undervalued relative to its expected future cash generation?"*

Outputs: valuation assessment, earnings quality, FCF trends, ROIC, margin trajectory, debt profile.

#### News Analyst
> *"What information has changed about NVDA during the last 24 hours?"*

Outputs: material event detection, sentiment scoring, importance ranking, novelty vs. prior knowledge.

#### Earnings Analyst
> *"Did the earnings release materially change the company's outlook?"*

Outputs: surprise magnitude, guidance changes, revision direction, transcript tone analysis.

#### Macro Analyst
> *"How does the current rate environment affect growth equities?"*

Outputs: regime classification, rate sensitivity mapping, sector rotation implications.

#### Competitive Analyst
> *"Is AMD gaining or losing competitive position?"*

Outputs: market share signals, product cycle positioning, pricing power assessment.

#### Market Structure Analyst
> *"What is the current liquidity/volume/volatility regime?"*

Outputs: liquidity depth, volatility regime, breadth indicators, microstructure health.

### Output Contract

Every research agent emits a structured research object:

```json
{
  "agent_id": "fundamental_analyst",
  "symbol": "MSFT",
  "timestamp": "...",
  "snapshot_id": "...",
  "findings": [ ... ],
  "confidence": 0.0,
  "evidence_refs": [ ... ],
  "dissent_notes": null
}
```

---

## 4. Band 3 — Strategy Agents

This is where the actual quant strategies live. **Each strategy agent generates a signal, not an order.** That distinction is critical.

You don't want every agent trying to do everything.

### Momentum Agent

Looks for:

- Trend persistence
- Breakouts
- Relative strength
- Volume confirmation
- Momentum regimes

### Mean Reversion Agent

Looks for:

- Statistical deviation
- Z-score
- RSI
- Bollinger bands
- Short-term reversals

### Fundamental Agent

Looks for:

- Valuation
- Earnings growth
- Free cash flow
- ROIC
- Margins
- Debt
- Revenue quality

### News/Event Agent

Looks for:

- Earnings surprises
- Guidance changes
- M&A
- Regulatory events
- Geopolitical events
- Product announcements

### Statistical/Quant Agent

Looks for:

- Factor relationships
- Correlations
- Statistical anomalies
- Cross-sectional opportunities

### Macro Agent

Looks for:

- Rates
- Inflation
- Employment
- Commodities
- FX
- Liquidity
- Economic cycles

### Signal Contract

```json
{
  "signal_id": "...",
  "strategy_agent": "momentum",
  "symbol": "NVDA",
  "direction": "BUY | SELL | HOLD",
  "strength": 0.91,
  "confidence": 0.87,
  "horizon_days": 5,
  "regime_context": { ... },
  "evidence_refs": [ ... ],
  "snapshot_id": "...",
  "model_version": "momentum-v1.2"
}
```

---

## 5. Band 4 — Debate / Jury (Investment Committee)

Described fully in `09_Investment_Committee_Debate.md`. Signals from Band 3 are aggregated and then challenged by Bull, Bear, Risk, Evidence, and Judge agents before reaching the Portfolio Manager.

---

## 6. Band 5 — Risk

Two layers:

1. **Analytical Risk Agents**
   - Risk Agent: portfolio impact analysis, VaR, concentration, correlation
   - Stress Agent: scenario analysis, drawdown simulation, tail-risk assessment

2. **Deterministic Risk Gate** (code-enforced, never LLM-decided)
   - Position limits
   - Sector concentration limits
   - Drawdown circuit breakers
   - Exposure caps
   - Liquidity minimums

Consistent with `02_FRD.md`: hard risk checks are code-enforced rather than delegated to the LLM.

---

## 7. Band 6 — Execution & Monitoring

- **Execution Desk:** order construction, routing (Alpaca paper trading in Stage 1), fill tracking, slippage measurement
- **Portfolio Monitor:** live positions, exposure, P&L attribution, drift detection
- **Outcome Engine:** records realized outcomes against original signals for the learning loop (`10_Learning_System.md`)

---

## 8. Cross-Band Rules

| Rule | Rationale |
|---|---|
| Agents communicate only through structured artifacts | Reproducibility, auditability |
| Every artifact references a `snapshot_id` | Point-in-time reproducibility |
| Strategy agents never place orders | Separation of signal generation and capital deployment |
| LLM agents never compute risk limits | Deterministic enforcement |
| Frontier LLM reserved for synthesis/debate; cheap models elsewhere | Cost efficiency |
| Human approval gate retained (Stage 1) before execution | Safety |