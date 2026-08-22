# 07 — AI Fund Vision: From Agentic Trading Desk to AI-Native Quantitative Investment Platform

> **Status:** Vision / Strategic Direction Document
> **Supersedes scope of:** `01_PRD.md` (hackathon-style MVP)
> **Builds upon:** `01_PRD.md`, `02_FRD.md`, `03_TechStack.md`, `04_Schemas.md`, `05_Development_Plan.md`, `06_RL_Improvement.md`

---

## 1. Executive Summary

The current documents describe an **Agentic Trading Desk**: multi-agent research → critic → human approval → execution → portfolio monitoring, with structured audit data and an RL roadmap. That is a strong foundation — effectively the MVP architecture.

This document defines the larger ambition built from that foundation: an **AI-native quantitative investment platform** — a virtual investment firm where multiple specialized AI agents behave like a research team, portfolio team, risk desk, and execution desk, while a higher-level allocation layer learns which strategies deserve capital.

### End-State Vision

> **An AI-native investment firm where specialized autonomous research and quantitative agents continuously analyze markets, debate investment opportunities, construct portfolios, execute within deterministic risk constraints, and learn from historical outcomes and human feedback.**

The key principle: **the fund itself becomes the learning system**.

Not:

```
LLM → BUY/SELL
```

But:

```
Data → Research → Signals → Debate → Risk → Allocation → Execution → Outcome → Learning → Better Allocation
```

---

## 2. The Fundamental Idea

Think of the system as an AI fund with **bands of agents** rather than one giant LLM.

```text
                         ┌─────────────────────────┐
                         │     FUND COMMANDER      │
                         │ Portfolio / Allocation  │
                         │ Risk / Capital Policy   │
                         └────────────┬────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
             RESEARCH BAND      SIGNAL BAND        RISK BAND
                    │                 │                 │
          ┌─────────┼───────┐   ┌─────┼─────┐     ┌─────┼─────┐
          ▼         ▼       ▼   ▼     ▼     ▼     ▼     ▼     ▼
       News AI  Fundamental Macro  Momentum MeanRev  Risk  Stress
       Agent    Agent       Agent   Agent    Agent    Agent  Agent
          │         │       │        │        │        │
          └─────────┴───────┴────────┴────────┴────────┘
                                      │
                                      ▼
                            ┌──────────────────┐
                            │  DEBATE / JURY   │
                            │ Agents challenge │
                            │ each hypothesis  │
                            └────────┬─────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │ PORTFOLIO MANAGER│
                            │ Capital allocation│
                            └────────┬─────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │ RISK GATE        │
                            │ Deterministic    │
                            │ constraints      │
                            └────────┬─────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │ EXECUTION        │
                            └────────┬─────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │ PORTFOLIO        │
                            │ MONITOR          │
                            └────────┬─────────┘
                                     │
                                     ▼
                         ┌────────────────────────┐
                         │ LEARNING / EVALUATION  │
                         │ Backtest + outcomes +  │
                         │ feedback + calibration │
                         └────────────────────────┘
```

### The Critical Architectural Principle

> **The LLM is not the trading system.**
> **LLMs are components inside a controlled quantitative architecture.**

---

## 3. Why This Is Larger Than the Current PRD

| Dimension | Current PRD (MVP) | AI Fund Vision |
|---|---|---|
| Agents | 3–4 strategy agents + critic | Six bands of specialized agents |
| Decision process | Signal → Critic → Human | Signals → Debate/Jury → Quantitative PM → Deterministic Risk Gate |
| Capital allocation | Per-trade sizing | Strategy-level allocation engine |
| Learning | RL roadmap (offline first) | Continuous learning loop + model registry + promotion gates |
| Data | Market + news via internal interface | Full data fabric: prices, fundamentals, news, macro, alternative data |
| Reproducibility | Audit trail | Immutable market snapshots — every prediction traceable to its information set |
| UX | Dashboard | Bloomberg Terminal × Palantir × quant fund cockpit |

---

## 4. Core Architectural Decisions (Summary)

These are elaborated in companion documents:

1. **Bands, not one giant agent** — see `08_Agent_Bands_Architecture.md`
2. **Signals, not orders** — strategy agents generate signals; only the PM/risk chain produces orders
3. **Debate before decision** — an AI Investment Committee challenges every hypothesis — see `09_Investment_Committee_Debate.md`
4. **The Portfolio Manager is NOT an LLM alone** — allocation is driven by quantitative models
5. **Three distinct learning mechanisms** — LLM reasoning, predictive models, and strategy allocation must not be conflated — see `10_Learning_System.md`
6. **Market snapshots for reproducibility** — every prediction traceable to its information set — see `11_Data_Fabric_Snapshots.md`
7. **Deterministic risk enforcement** — hard risk checks remain code-enforced, never delegated to the LLM (consistent with `02_FRD.md`)
8. **Model registry with explicit promotion gates** — models evolve like software releases, never self-promoting

---

## 5. Cost-Efficient Model Strategy

Given a preference for cost-efficient AI development:

> Keep the expensive frontier model concentrated on **research synthesis, debate, and high-value reasoning**, while numerical prediction, feature engineering, backtesting, scoring, risk, and routine agent work use cheaper/open-weight models and conventional ML.

That is both cheaper and architecturally cleaner.

| Workload | Model Class |
|---|---|
| Research synthesis, bull/bear debate, thesis generation | Frontier LLM |
| Routine agent work (classification, extraction) | Cheap / open-weight LLM |
| Numerical prediction (returns, probabilities) | XGBoost / LightGBM / NNs |
| Feature engineering, backtesting, scoring | Conventional ML / deterministic code |
| Risk checks | Deterministic code (never LLM) |
| Allocation optimization | Contextual bandits / Bayesian methods / convex optimization |

---

## 6. Companion Documents

| Document | Contents |
|---|---|
| `08_Agent_Bands_Architecture.md` | The six bands: Market Intelligence, Research, Strategy, Debate, Risk, Execution/Monitoring |
| `09_Investment_Committee_Debate.md` | Bull/Bear/Risk/Evidence/Jury debate protocol; quantitative Portfolio Manager & allocation engine |
| `10_Learning_System.md` | Learning loop, three learning types, model registry, promotion gates, anti-patterns |
| `11_Data_Fabric_Snapshots.md` | Investment Knowledge Graph / Market Data Lake; immutable market snapshot schema |
| `12_Portal_UX.md` | Fund overview, Agent Floor, Investment Thesis, Trade Decision Chain, Learning Dashboard, Model Registry screens |
| `13_Evolved_Architecture_Roadmap.md` | Evolved system pipeline, market regime detection, decision-dataset moat, Stage 1–4 build plan, anti-patterns |