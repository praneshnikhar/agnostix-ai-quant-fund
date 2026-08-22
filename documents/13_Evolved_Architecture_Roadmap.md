# 13 — Evolved Architecture, Regime Detection, Moat & Staged Roadmap

> **Status:** Architecture / Roadmap Specification
> **Companion to:** `07_AIFund_Vision.md`
> **Extends:** `05_Development_Plan.md` (Phases 0–4), `06_RL_Improvement.md`

---

## 1. Evolving the Current Architecture

The current architecture is:

```text
Data → Signal → Critic → Human → Execution → Portfolio
```

That's excellent for the initial version. For the larger AI fund, evolve it into:

```text
                    DATA FABRIC
                         │
                         ▼
                 MARKET SNAPSHOT
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
      RESEARCH        STRATEGIES       MACRO
       BAND             BAND            BAND
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  SIGNAL AGGREGATOR
                         │
                         ▼
                  DEBATE / JURY
                         │
                         ▼
                PORTFOLIO MANAGER
                         │
                         ▼
                QUANT RISK ENGINE
                         │
                   ┌─────┴─────┐
                   ▼           ▼
                APPROVE       BLOCK
                   │
                   ▼
                EXECUTION
                   │
                   ▼
                 PORTFOLIO
                   │
                   ▼
             OUTCOME ENGINE
                   │
                   ▼
              LEARNING LOOP
                   │
       ┌───────────┼────────────┐
       ▼           ▼            ▼
   LLM tuning   Strategy      Allocator
                retraining
```

---

## 2. What NOT to Do (Anti-Patterns)

### ❌ One giant "AI trader"

Bad:

> "GPT, look at the market and decide what to buy."

You lose specialization, reproducibility, and quantitative control.

### ❌ Let the LLM calculate risk

Risk limits must remain deterministic. The existing FRD correctly specifies that hard risk checks should be code-enforced rather than delegated to the LLM.

### ❌ Train directly on P&L

The RL document correctly calls out why raw P&L is a poor reward signal.

### ❌ Constantly fine-tune the LLM

The model doesn't need to be retrained every time a trade loses. Often the correct response is:

> "The strategy performed poorly under this market regime."

not:

> "Retrain the LLM."

### ❌ Let the learning system automatically promote itself

Use the explicit promotion pipeline (`10_Learning_System.md`):

```text
Candidate Model
      ↓
Backtest
      ↓
Walk Forward
      ↓
Out-of-Sample
      ↓
Risk Evaluation
      ↓
Paper Trading
      ↓
Promotion
```

with explicit promotion criteria.

---

## 3. Market Regime Detection (Add Early)

This is one area to add early. The system should identify:

```text
REGIME

Trend:          Strong
Volatility:     Low
Liquidity:      High
Macro:          Risk-On
Correlation:    Medium
Rate Direction: Falling
```

Then strategy weights change by regime:

```text
                         NORMAL      HIGH VOL
Momentum                   30%          12%
Mean Reversion             15%          28%
Fundamental                30%          35%
News                        15%          15%
Macro                       10%          10%
```

Now the system isn't merely learning:

> "Momentum made money."

It's learning:

> "Momentum performs well under regime X."

That is considerably more interesting quantitatively — and it changes the learning target from global averages to **regime-conditional performance**.

### Regime Feature Set

| Dimension | Signals |
|---|---|
| Trend | Moving-average structure, breadth, momentum dispersion |
| Volatility | Realized vol, VIX, vol-of-vol |
| Liquidity | Spreads, depth, volume vs. ADV |
| Macro | Rates direction, curve, risk-on/off proxies |
| Correlation | Average pairwise correlation, factor concentration |

---

## 4. The Data Moat

The LLM itself probably won't be the strongest moat. The moat becomes the accumulated **decision dataset** (`11_Data_Fabric_Snapshots.md` §6):

```text
Historical Market Data
        +
News
        +
Fundamentals
        +
Agent Decisions
        +
Agent Disagreements
        +
Human Decisions
        +
Executed Trades
        +
Counterfactual Outcomes
        +
Market Regimes
        +
Model Versions
        +
Portfolio States
```

This dataset can answer:

- What did our agents believe?
- What evidence did they use?
- What did the PM approve?
- What actually happened?
- Which agent was correct?
- Under what market regime?
- Which signals were correlated?
- Which model version generated the decision?

Enormously more valuable than simply storing P&L.

---

## 5. Staged Build Plan

**Do not throw away the current six documents.** They are effectively the MVP architecture. Build in four stages:

### Stage 1 — Agentic Trading Desk (current scope)

Per the existing development plan (Phases 0–4):

- Alpaca paper trading
- 3–4 strategy agents
- Critic
- Human approval
- Portfolio
- Dashboard
- Audit trail

### Stage 2 — AI Fund

Add:

- Research Band
- Strategy Band (expanded)
- Investment Committee (debate/jury)
- Portfolio allocator (quantitative)
- Market regime engine
- Richer data fabric
- Model registry
- Agent performance analytics

### Stage 3 — Learning Fund

Add:

- Historical replay engine
- Walk-forward evaluation
- Strategy scoring
- Contextual bandits
- Preference optimization
- Offline RL
- Automated model evaluation
- Strategy allocation learning

### Stage 4 — Institutional Platform

Eventually:

- Multiple portfolios
- Multiple strategies
- Multi-asset
- Real-time risk
- Compliance
- Multi-user PM/Risk/Admin roles
- Institutional data providers
- Live execution
- OMS/EMS
- Advanced portfolio optimization

---

## 6. Cost-Efficient Model Placement (Reprise)

Keep the expensive frontier model concentrated on **research synthesis, debate, and high-value reasoning**; use cheaper/open-weight models and conventional ML for numerical prediction, feature engineering, backtesting, scoring, risk, and routine agent work.

Cheaper *and* architecturally cleaner.

---

## 7. Summary

The end-state vision:

> **An AI-native investment firm where specialized autonomous research and quantitative agents continuously analyze markets, debate investment opportunities, construct portfolios, execute within deterministic risk constraints, and learn from historical outcomes and human feedback.**

The key is that **the fund itself becomes the learning system**.

Not:

**LLM → BUY/SELL**

but:

**Data → Research → Signals → Debate → Risk → Allocation → Execution → Outcome → Learning → Better Allocation.**

That is a legitimate architecture for an AI quantitative fund, and the existing PRD/FRD/schema/RL documents already contain the first layer of it.