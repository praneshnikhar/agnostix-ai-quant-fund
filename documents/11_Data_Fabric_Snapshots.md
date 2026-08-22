# 11 — Data Fabric & Market Snapshots

> **Status:** Architecture / Data Specification
> **Companion to:** `07_AIFund_Vision.md`
> **Extends:** `04_Schemas.md` (existing data schemas)

---

## 1. Overview

The user requirement "News, Trades and Company fundamentals" expands into an **Investment Knowledge Graph / Market Data Lake**. The key principle:

> **Every prediction should be traceable back to its information set.**

---

## 2. Information Architecture

```text
                        MARKET DATA
                            │
       ┌────────────────────┼────────────────────┐
       ▼                    ▼                    ▼
    Prices               Trades               Volume
       │                    │                    │
       └────────────────────┼────────────────────┘
                            │
                         FEATURES
                            │
      ┌─────────────────────┼─────────────────────┐
      ▼                     ▼                     ▼
   Technical             Statistical          Market Regime
      │                     │                     │
      └─────────────────────┼─────────────────────┘
                            │
                            ▼
                      COMPANY DATA
                            │
       ┌────────────────────┼────────────────────┐
       ▼                    ▼                    ▼
   Financials           Earnings              Filings
       │                    │                    │
       └────────────────────┼────────────────────┘
                            │
                         NEWS
                            │
       ┌────────────────────┼────────────────────┐
       ▼                    ▼                    ▼
   Headlines           Sentiment             Events
                            │
                            ▼
                     MACRO / ALTERNATIVE
                            │
                            ▼
                       AI RESEARCH
                            │
                            ▼
                     INVESTMENT SIGNAL
```

### Layers

| Layer | Contents |
|---|---|
| Market Data | Prices, trades, volume, OHLCV, volatility, breadth |
| Features | Technical indicators, statistical features, regime labels |
| Company Data | Financials, earnings, filings, analyst revisions |
| News | Headlines, sentiment, material events |
| Macro / Alternative | Rates, inflation, employment, commodities, FX, liquidity; alt-data later |
| AI Research | Agent findings, theses, debates (outputs become first-class data) |
| Investment Signal | Final structured signals and decisions |

---

## 3. Market Snapshots

This is a key addition to the current schemas (`04_Schemas.md`).

At time `T`, each agent receives a complete, immutable **market snapshot**:

```json
{
  "symbol": "NVDA",
  "timestamp": "...",

  "market": {
    "price": 181.42,
    "volume": 12400000,
    "volatility": 0.31,
    "relative_strength": 0.87
  },

  "fundamentals": {
    "revenue_growth": 0.42,
    "eps_growth": 0.38,
    "pe": 41.2,
    "fcf_margin": 0.28
  },

  "news": [
    {
      "headline": "...",
      "sentiment": 0.74,
      "importance": 0.91
    }
  ],

  "macro": {
    "fed_rate": 0.043,
    "vix": 18.4
  },

  "portfolio": {
    "current_exposure": 0.07,
    "sector_exposure": 0.21
  }
}
```

Then:

```text
Prediction = function(snapshot)
```

### Why Snapshots Matter: Reproducibility

Six months later you can ask:

> *"What information did the model actually see when it made this decision?"*

And answer it exactly. This is extremely important for research and debugging.

### Snapshot Properties

| Property | Requirement |
|---|---|
| Immutability | Snapshots are write-once; never mutated after creation |
| Completeness | Contains everything the agent saw — no hidden context |
| Addressability | Every artifact references its `snapshot_id` |
| As-of correctness | Reconstructed from point-in-time-correct source data (no look-ahead) |
| Compactness | Feature-level representation suitable for replay at scale |

---

## 4. Point-in-Time Correctness Rules

- Fundamentals must reflect **as-reported** values (restatements handled via effective-date versioning)
- News items timestamped by publication time, not ingestion time
- Analyst estimates versioned with revision dates
- Corporate actions (splits, dividends) applied as-of their ex-dates
- Backtests/replays may only consume data published before simulation time `T`

---

## 5. Storage Strategy

| Data | Store | Notes |
|---|---|---|
| Raw market data | Time-series store (columnar) | Partitioned by symbol/date |
| Features | Feature store with online/offline parity | Same code path for live + backtest |
| News/events | Document store + embeddings index | For RAG and event retrieval |
| Snapshots | Immutable object storage / append-only tables | Content-addressed by hash |
| Agent artifacts (research, signals, theses) | Append-only decision log | Feeds audit trail + learning loop |
| Outcomes | Time-series joined to signal IDs | Attribution queries |

---

## 6. The Decision Dataset (Emergent Moat)

Over time the fabric accumulates a proprietary **decision dataset**:

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

That dataset can answer:

- What did our agents believe?
- What evidence did they use?
- What did the PM approve?
- What actually happened?
- Which agent was correct?
- Under what market regime?
- Which signals were correlated?
- Which model version generated the decision?

> This is enormously more valuable than simply storing P&L.

See `13_Evolved_Architecture_Roadmap.md` §5 for how this becomes the moat.