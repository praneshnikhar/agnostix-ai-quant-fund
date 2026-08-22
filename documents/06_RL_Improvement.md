# Improving the Agents & Models — Reinforcement Learning Approach
## Agentic Trading Desk

**Version:** 0.1

This document covers how to actually make the agents *get better over time*, not just run. It's written assuming the pipeline in the other docs is already producing logged proposals, critic verdicts, human decisions, and execution outcomes — that log is your training data.

---

## 1. Why RL Is Hard Here (Read This First)

Before reaching for RL, be clear-eyed about the constraints:

- **You can't trial-and-error on live markets.** Real RL (agent acts, environment responds, agent updates) implies exploration — placing bad trades on purpose to learn. Even in paper trading this is slow (one trading day = one data point) and market non-stationarity means old episodes go stale.
- **Reward is delayed and noisy.** A trade's "correctness" isn't known until it closes, and even then, a good decision can lose money (variance) while a bad one can win (luck). Naively training on realized P&L teaches the model to chase noise.
- **Sample efficiency is brutal.** Markets don't repeat. You won't get millions of transitions the way a game-playing RL agent would.

Given this, the practical path for a hackathon-to-early-product timeline is **not** "train a PPO agent live on the market." It's a layered approach: start with the human feedback you're already collecting, use offline/simulated RL for tighter feedback loops, and treat full online RL as a long-term stretch goal, not a hackathon deliverable.

---

## 2. Layer 1 — Use the Human Approval Signal (Available Immediately)

Every `human_decisions` row is a preference label: the PM looked at a proposal and said approve/reject/revise. This is exactly the kind of data used in **RLHF-style preference optimization**, and you already have it from Day 1 of the product, no extra instrumentation needed.

**Approach: Direct Preference Optimization (DPO) style fine-tuning, or simpler — prompt-level few-shot conditioning**

- **Cheapest version (no training):** periodically build a few-shot prompt for the Signal Agent that includes recent examples of *approved* proposals (as positive exemplars) and *rejected* proposals with the human's stated reason (as negative exemplars). This alone measurably shifts LLM output quality and requires no ML infra — just a prompt-construction step reading from `human_decisions`.
- **Next step (light training):** if using an open-weight model for a signal agent, collect (proposal, human_label) pairs and run DPO or a reward-model + PPO fine-tune. This requires enough volume (hundreds of labeled proposals minimum) to be worthwhile — unlikely during the hackathon itself, but design your logging now so you can do this post-hackathon.
- **Critic agent specifically:** since critic decisions should stay largely rule-based/deterministic (per the FRD), don't RL-tune the rule engine. Do use human overrides of critic warnings (human approves despite a `pass_with_warning`) as a signal for *recalibrating thresholds*, not for retraining an LLM to ignore rules.

---

## 3. Layer 2 — Reward Design for Outcome-Based Learning

Once trades close, you have a second, delayed signal: did it make money, risk-adjusted. Design reward carefully — this is the single biggest failure point in trading RL.

**Don't use raw P&L as reward.** It teaches the model to take on hidden risk (a strategy can look great on raw P&L while quietly increasing tail risk).

**Better reward components (combine, don't use one alone):**

| Component | Why |
|---|---|
| Risk-adjusted return (Sharpe or Sortino over the trade/period) | Penalizes volatility, not just direction |
| Max drawdown penalty | Punishes strategies that occasionally blow up even if average return is fine |
| Transaction cost / slippage penalty | Keeps the agent from overtrading |
| Human agreement bonus | Small reward for proposals that got approved (keeps the model aligned with the human's risk appetite, not just backtest performance) |
| Calibration penalty | Penalize confidence scores that don't match realized outcomes (a model saying "90% confidence" should be right ~90% of the time — score this with something like Brier score) |

A reasonable composite: `reward = risk_adjusted_return - λ1*drawdown_penalty - λ2*cost_penalty + λ3*human_agreement_bonus`, tuned via backtesting, not guessed.

---

## 4. Layer 3 — Offline / Simulated RL (The Realistic "Real RL" Path)

Instead of learning live, train in a **replay environment** built from your own logged data + historical market data:

- Build a **gym-style environment** (OpenAI Gym / Gymnasium interface) where the "episode" replays historical price data for your watchlist, and the agent's action space is: propose a trade (symbol, direction, size) or pass.
- Reward is computed using the composite function from Section 3, calculated against what *actually* happened historically after that point in time (careful: strict walk-forward — never let the model see future data).
- Algorithms that fit this setting:
  - **Contextual bandits** (e.g., LinUCB, or a simple neural bandit) for a lighter-weight starting point — good fit if you're mainly deciding *which* signal/strategy to trust more at a given time, not full sequential decision-making.
  - **PPO** if you want the agent making sequential position-sizing/hold-duration decisions, not just single-shot proposals.
  - **Offline RL algorithms (CQL, IQL)** if you specifically want to learn from the logged human-approved trajectory data without further live interaction — these are designed for exactly the "you can't explore live" constraint you have.

**Critical practice: walk-forward evaluation.** Train on data up to time T, evaluate strictly on T+1 onward, roll forward. A single train/test split will overstate performance due to regime dependence.

---

## 5. Layer 4 — Multi-Agent Credit Assignment

With multiple signal agents (momentum, mean-reversion, sentiment), you eventually want to learn **which agent to trust when**, not just improve each agent in isolation.

- Track a rolling performance score per agent (e.g., realized Sharpe of their approved-and-executed proposals over trailing 20 trades).
- Use this as input to a lightweight **meta-agent / allocator** that weights how much capital or attention each signal agent gets — this can literally start as a bandit problem (each signal agent = an "arm", reward = risk-adjusted P&L of trades taken on its proposals).
- This is a natural, demo-friendly stretch goal: "our system doesn't just generate signals, it learns which of its own strategies to trust."

---

## 6. Practical Guardrails Against Common RL-in-Trading Failure Modes

- **Reward hacking:** watch for the agent learning to propose only trivially safe/small trades to farm the "human agreement bonus" — cap how much that term can dominate the composite reward.
- **Overfitting to backtest:** always hold out a final out-of-sample period never touched during any tuning, and report performance on it honestly (including to judges — this builds credibility).
- **Regime shift:** a model tuned on a trending market will misbehave in a choppy one. If time allows, backtest across at least two visibly different historical regimes.
- **Non-stationarity of "correct" behavior:** periodically retrain/recalibrate rather than treating the model as done — set up your logging (per the Schemas doc) so re-training is a data query away, not a re-instrumentation project.

---

## 7. What's Realistic for the Hackathon Itself

Given time constraints, aim for:

1. **Working now:** the few-shot conditioning approach from Layer 1 (approved/rejected examples in the prompt) — cheap, visible, demoable.
2. **Built but not fully trained:** the offline RL environment/reward function from Layer 3 — show the architecture and a toy training run on historical data, even if it's not powering live proposals yet.
3. **Roadmap slide, not a demo:** full offline RL (CQL/IQL) and the multi-agent allocator — present these as "what we'd build next" with the data pipeline already in place to support them. Judges respond well to "we designed the system so this is a straightforward next step," backed by the fact that your schema already logs everything needed.
