# 14 — Evolved Tech Stack & Model Strategy

> **Status:** Architecture / Technology Decision Document
> **Supersedes portions of:** `03_TechStack.md`
> **Companion to:** `07_AIFund_Vision.md`

---

## 1. Guiding Principle

Start this as a **real product architecture**, not as a hackathon prototype that we later have to rewrite.

The existing documents are a useful MVP baseline, but the original stack is deliberately evolved where it improves **cost, maintainability, or the eventual AI-fund architecture**.

---

## 2. Recommended Stack Overview

```text
Next.js (web)
     │
     ▼
FastAPI (api)
     │
 ┌───┼─────────┐
 ▼   ▼         ▼
PG  Redis    Workers (Celery)
               │
               ▼
            LangGraph
               │
       ┌───────┼───────┐
       ▼       ▼       ▼
     Agents  Risk   Execution
```

That's enough. Do not start with Kubernetes, Kafka, Spark, Flink, ClickHouse, Airflow, Ray, Milvus, or K8s GPU clusters. Add them only when there is evidence we need them.

---

## 3. Frontend — Premium Trading Terminal

**Next.js + TypeScript + Tailwind CSS + shadcn/ui**

| Choice | Role |
|---|---|
| Next.js App Router | Complex dashboard: nested layouts, streaming, modern React |
| TypeScript | End-to-end type safety |
| Tailwind CSS | Styling foundation |
| shadcn/ui + Radix primitives | Coherent design system from day one |
| Lucide icons | Icon set |
| TanStack Query | Server state / data fetching |
| Zustand | Local application state |
| TradingView Lightweight Charts | Price/equity charts |
| Recharts | Only where TradingView isn't appropriate |
| Framer Motion | Used sparingly |
| WebSocket/SSE | Live events |

> Do **not** build the UI from scratch with generic Tailwind components. We want a coherent design system from day one.

---

## 4. Backend — Python

**FastAPI + Python 3.12+**

FastAPI fits because we need:

- Async APIs
- WebSockets (directly suited to the real-time trading dashboard)
- Pydantic validation
- Background processing
- Strong Python quant/ML ecosystem

---

## 5. Agent Orchestration — LangGraph

Retained almost exactly from the original stack. The fund will eventually have:

- Hierarchical agents
- Stateful workflows
- Human approval
- Persistent execution
- Branching
- Retries
- Agent interruption
- Replay

LangGraph is specifically designed for stateful, long-running agent workflows and human-in-the-loop control.

---

## 6. Database — PostgreSQL as Central Data Platform

Make PostgreSQL the central data platform rather than introducing five databases immediately:

```text
PostgreSQL
├── relational trading data
├── agent events
├── market metadata
├── research data
├── model metadata
├── training datasets
└── vector embeddings (pgvector)
```

Use **pgvector** for the initial semantic retrieval layer.

Do not introduce Pinecone, Weaviate, ClickHouse, MongoDB, etc. until there is an actual scaling reason.

### Change from original TechStack (`03_TechStack.md`)

Original suggestion was TimescaleDB or plain PostgreSQL. Decision: start with **PostgreSQL + appropriate time-series indexing/partitioning**, and introduce Timescale-specific infrastructure only if the actual market-data workload justifies it. Keeps the initial system cheap and considerably easier to operate.

---

## 7. Cache / Queue — Redis

Use Redis for:

- Job queues
- Short-lived cache
- Distributed locks
- Rate limiting
- Real-time coordination

For the first version, **do not add Kafka**.

---

## 8. Background Jobs — Celery + Redis

Rather than making FastAPI itself perform long-running trading/AI jobs.

Eventual worker fleet:

```text
Market data workers
News workers
Research workers
Signal workers
Backtest workers
Evaluation workers
Execution worker
Portfolio worker
```

---

## 9. Quant / ML — Python Ecosystem

```text
NumPy
Pandas
Polars
SciPy
scikit-learn
XGBoost
LightGBM
PyTorch
vectorbt
statsmodels
```

Rules of thumb:

- Use **Polars** for large data transformations.
- Use **PyTorch** only when neural models are actually needed.
- Don't automatically turn every prediction problem into an LLM problem.

---

## 10. AI Model Strategy — Provider-Agnostic Model Gateway

### Change from original TechStack

Original document suggests Claude Sonnet/Haiku as the LLM provider. Decision: **do not hard-code that choice into the architecture.** Use Claude as one provider if it performs best for a particular agent, but put it behind the model gateway.

### The Model Gateway

```text
                   AI MODEL GATEWAY
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       OpenAI         Anthropic       Local
                                      Models
```

Every agent calls:

```python
model_gateway.generate(...)
```

rather than directly calling OpenAI/Anthropic. This means we can later switch:

```text
Claude → GPT → Gemini → Qwen → DeepSeek → local Ollama model
```

without rewriting agents.

### Gateway Service Structure

```text
backend/
    ai/
        gateway.py
        providers/
            anthropic.py
            openai.py
            ollama.py
        routing.py
        schemas.py
        costs.py
        telemetry.py
```

Agent usage:

```python
result = await model_gateway.run(
    task="fundamental_analysis",
    model_class="reasoning",
    context=market_snapshot,
)
```

The gateway decides which model to use, and records:

- model
- tokens
- latency
- cost
- prompt version
- response
- agent
- task
- success/failure

This telemetry becomes extremely valuable later when optimizing the fund's economics.

---

## 11. Workload-to-Model Mapping

Don't use expensive LLMs for everything:

| Work | Model |
|---|---|
| Simple classification | Small/local model |
| News extraction | Small/cheap LLM |
| Sentiment | Small model |
| Financial document extraction | Cheap LLM |
| Fundamental analysis | Strong reasoning model |
| Investment committee | Strong reasoning model |
| Bull/Bear debate | Strong reasoning model |
| Risk explanation | Cheap/medium model |
| Numerical prediction | XGBoost/LightGBM/PyTorch |
| Portfolio optimization | Quant algorithms |
| Risk limits | Pure Python |
| Backtesting | Python |
| Market regime | ML model |
| Embeddings | Local embedding model |

This prevents spending $0.50–$5 every time a trivial agent needs to classify an article.

### Cost Philosophy

Optimize for **cost per useful decision**, not simply lowest infrastructure bill:

| Tier | Example |
|---|---|
| Cheap/local | News: 1,000 articles → local/cheap extraction model |
| Medium | Research: 10 companies → medium reasoning model |
| Expensive | Investment Committee: 3 serious candidates → strongest reasoning model |
| No LLM | Risk: Python |
| No LLM | Portfolio optimization: quantitative optimizer |

### Provider-Agnostic Composition Example

```text
Fundamental Agent → Claude
News extraction   → Qwen local
Sentiment         → FinBERT
Prediction        → LightGBM
Committee         → Claude/GPT
Embeddings        → local BGE model
```

A much more rational AI stack than choosing one LLM and putting everything through it.