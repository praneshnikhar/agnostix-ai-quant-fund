# 10 — Learning System: Continuous Loop, Model Registry & Promotion Gates

> **Status:** Architecture Specification
> **Companion to:** `07_AIFund_Vision.md`
> **Extends:** `06_RL_Improvement.md` (offline-first RL roadmap)

---

## 1. Overview

The uploaded RL document (`06_RL_Improvement.md`) is directionally correct: **don't start with online PPO trading against live markets**. The market is too noisy, rewards are delayed, and sample efficiency is terrible.

Instead, create a **continuous learning loop** that gives you model evolution without blindly letting the model rewrite itself.

---

## 2. The Continuous Learning Loop

```text
                Historical Data
                      │
                      ▼
                 Backtesting
                      │
                      ▼
                Agent Signals
                      │
                      ▼
              Simulated Portfolio
                      │
                      ▼
             Performance Outcomes
                      │
                      ▼
              Evaluation Engine
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
    Strategy Score          Model Score
          │                       │
          └───────────┬───────────┘
                      ▼
               Model Registry
                      │
                      ▼
              New Agent Version
                      │
                      ▼
             Walk-forward test
                      │
                      ▼
                Promotion Gate
                      │
                      ▼
                 Production
```

---

## 3. Three Distinct Learning Mechanisms

This is a critical distinction. There are **three different things that can learn**, and they must not be conflated.

### A. LLM Reasoning

Example: *understanding an earnings call.*

Can improve through:

- Better prompts
- RAG
- Domain-specific datasets
- Fine-tuning
- Preference optimization

### B. Predictive Models

Example: *probability that a stock will outperform SPY over the next 5 days.*

Can use:

- XGBoost
- LightGBM
- Neural networks
- Temporal models
- Transformers
- Ensembles

### C. Strategy Allocation

Example: *how much capital should the momentum strategy receive today?*

Can use:

- Contextual bandits
- Bayesian allocation
- Reinforcement learning
- Portfolio optimization

### Division of Labor

> **The LLM is particularly useful for unstructured information and reasoning.**
> **The quantitative models should handle numerical prediction and optimization.**

---

## 4. Don't Make "Training the LLM" the Primary Learning Mechanism

The model doesn't need to be retrained every time a trade loses.

Often the correct response is:

> "The strategy performed poorly under this market regime."

not:

> "Retrain the LLM."

| Situation | Correct Response |
|---|---|
| Strategy underperforms in high-vol regime | Adjust regime-conditional weights |
| Signal calibration drifts | Retrain predictive model (B) |
| Reasoning quality degrades on new data types | Improve prompts / RAG (A) |
| Allocation persistently suboptimal | Update allocation policy (C) |
| Single losing trade | Usually: nothing. Record outcome, move on. |

---

## 5. Model Registry

Treat models like **software releases**.

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

### Registry Record Schema

```json
{
  "model_id": "fundamental-agent",
  "version": "v1.2",
  "status": "production | candidate | retired",
  "training_window": { "start": "2022-01", "end": "2025-12" },
  "validation_window": { "start": "2026-01", "end": "2026-04" },
  "out_of_sample_window": { "start": "2026-05", "end": "2026-07" },
  "metrics": {
    "sharpe": 1.91,
    "max_drawdown": -0.081,
    "calibration": 0.89,
    "win_rate": 0.67
  },
  "promotion_reason": {
    "relative_sharpe_delta": 0.124,
    "drawdown_delta": -0.081,
    "calibration_delta": 0.067
  },
  "parent_version": "v1.1",
  "promoted_at": "...",
  "promoted_by": "promotion-gate-v1"
}
```

---

## 6. Promotion Gate

The learning system must **never automatically promote itself**. Every candidate passes an explicit, human-auditable pipeline:

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

### Example Promotion Criteria

| Criterion | Threshold |
|---|---|
| Relative Sharpe improvement | ≥ +10% vs. current production |
| Max drawdown | No worse than production − 2pp |
| Calibration | ≥ production calibration |
| Out-of-sample window | ≥ 3 months, unseen data |
| Paper trading | ≥ 4 weeks, no risk-gate violations |
| Capacity / turnover | Within policy limits |

---

## 7. Evaluation Engine Metrics

Per strategy and per model version:

- **Win rate** (directional accuracy)
- **Sharpe / Sortino** (risk-adjusted return)
- **Average return per signal**
- **Calibration** (does 70% confidence mean 70% frequency?)
- **Regime-conditional performance** (see `13_Evolved_Architecture_Roadmap.md`)
- **Turnover and capacity**
- **Correlation with other strategies**

---

## 8. Learning Loop Outputs

The learning loop feeds three consumers:

1. **Strategy Scores** → Capital Allocation Engine (which strategies deserve capital)
2. **Model Scores** → Model Registry (which model versions to promote/retire)
3. **Calibration Data** → Agent prompts and predictive models (confidence correction)

---

## 9. Design Rules

| Rule | Rationale |
|---|---|
| Never train directly on raw P&L | Raw P&L is a poor reward signal (per `06_RL_Improvement.md`) |
| Never auto-promote models | Explicit gates prevent silent regression |
| Keep the three learning types separate | Conflating them destroys attribution |
| Prefer regime-conditional analysis over global averages | "Momentum works in regime X" ≫ "momentum works" |
| Persist every outcome against its original signal | Enables counterfactual and attribution research |
| Human sign-off on production promotion | Safety and accountability |