# Schemas Document
## Agentic Trading Desk

**Version:** 0.1
Covers: relational DB schema, core JSON object schemas exchanged between agents, and key API/WebSocket contracts.

---

## 1. Relational Database Schema (PostgreSQL)

### `proposals`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| created_at | timestamptz | |
| agent_id | text | Which signal agent generated it (e.g., `momentum_agent_v1`) |
| symbol | text | |
| direction | text | `long` \| `short` |
| thesis | text | Natural-language rationale |
| evidence | jsonb | Structured list of supporting data points |
| entry_price | numeric | |
| stop_loss | numeric | |
| take_profit | numeric | |
| size | numeric | Shares/contracts or % of portfolio |
| confidence | numeric | 0–1 |
| status | text | `pending_critic` \| `critic_pass` \| `critic_pass_warning` \| `critic_reject` \| `pending_human` \| `approved` \| `rejected` \| `revised` \| `executed` \| `expired` |

### `critic_reviews`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| proposal_id | UUID FK → proposals.id | |
| verdict | text | `pass` \| `pass_with_warning` \| `reject` |
| rule_checks | jsonb | Per-rule pass/fail results (position size, concentration, drawdown budget, leverage) |
| llm_notes | text | Qualitative assessment (kept separate from rule_checks, which are code-enforced) |
| created_at | timestamptz | |

### `human_decisions`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| proposal_id | UUID FK → proposals.id | |
| user_id | UUID FK → users.id | |
| decision | text | `approve` \| `reject` \| `revise` |
| revised_fields | jsonb | Nullable; only set if `revise` |
| notes | text | Optional human rationale — valuable training signal |
| decided_at | timestamptz | |

### `orders`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| proposal_id | UUID FK → proposals.id | |
| alpaca_order_id | text | External reference |
| status | text | Mirrors Alpaca order status enum |
| filled_price | numeric | |
| filled_qty | numeric | |
| submitted_at | timestamptz | |
| updated_at | timestamptz | |

### `positions` (synced snapshot, not source of truth — Alpaca is)
| Column | Type | Notes |
|---|---|---|
| symbol | text PK | |
| qty | numeric | |
| avg_entry_price | numeric | |
| current_price | numeric | |
| unrealized_pl | numeric | |
| updated_at | timestamptz | |

### `portfolio_snapshots`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| timestamp | timestamptz | |
| equity | numeric | |
| cash | numeric | |
| daily_pl | numeric | |
| drawdown_pct | numeric | |
| benchmark_return_pct | numeric | For SPY comparison |

### `agent_events` (audit log — append-only)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| timestamp | timestamptz | |
| agent_id | text | |
| event_type | text | `data_pull` \| `proposal_created` \| `critic_verdict` \| `human_decision` \| `order_placed` \| `order_filled` \| `kill_switch_triggered` |
| payload | jsonb | Full structured event data |
| proposal_id | UUID nullable FK | Links related events together |

### `users`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | text | |
| role | text | `pm` \| `admin` \| `viewer` |

---

## 2. Core JSON Object Schemas (agent-to-agent contracts)

### TradeProposal (Signal Agent → Critic)
```json
{
  "proposal_id": "uuid",
  "agent_id": "momentum_agent_v1",
  "symbol": "AAPL",
  "direction": "long",
  "thesis": "string",
  "evidence": [
    {"type": "price_action", "detail": "string", "value": 0.0},
    {"type": "news", "detail": "string", "source_url": "string"}
  ],
  "entry_price": 0.0,
  "stop_loss": 0.0,
  "take_profit": 0.0,
  "size_pct_portfolio": 0.0,
  "confidence": 0.0,
  "timestamp": "iso8601"
}
```

### CriticVerdict (Critic → Human Gate)
```json
{
  "proposal_id": "uuid",
  "verdict": "pass | pass_with_warning | reject",
  "rule_checks": {
    "max_position_size": {"pass": true, "limit": 0.05, "actual": 0.03},
    "sector_concentration": {"pass": true, "limit": 0.25, "actual": 0.10},
    "daily_loss_budget": {"pass": true, "remaining": 500.0},
    "leverage": {"pass": true, "limit": 1.0, "actual": 1.0}
  },
  "llm_notes": "string",
  "timestamp": "iso8601"
}
```

### HumanDecision (Human Gate → Execution)
```json
{
  "proposal_id": "uuid",
  "user_id": "uuid",
  "decision": "approve | reject | revise",
  "revised_fields": {"size_pct_portfolio": 0.02},
  "notes": "string",
  "timestamp": "iso8601"
}
```

### ExecutionResult (Execution → Portfolio Monitor / Dashboard)
```json
{
  "proposal_id": "uuid",
  "alpaca_order_id": "string",
  "status": "accepted | filled | partially_filled | rejected | canceled",
  "filled_price": 0.0,
  "filled_qty": 0.0,
  "timestamp": "iso8601"
}
```

---

## 3. API Contract Summary (FastAPI)

| Endpoint | Method | Purpose |
|---|---|---|
| `/proposals` | GET | List proposals (filterable by status, symbol, date) |
| `/proposals/{id}` | GET | Full proposal detail incl. critic review |
| `/proposals/{id}/decision` | POST | Submit human decision (approve/reject/revise) |
| `/portfolio` | GET | Current positions, equity, P&L |
| `/portfolio/history` | GET | Equity curve / snapshots over time |
| `/agent-events` | GET | Queryable audit log |
| `/kill-switch` | POST | Trigger/reset the global halt |
| `/ws/updates` | WS | Push channel: new proposals, position changes, order fills |

---

## 4. WebSocket Event Types (server → dashboard)

```json
{"type": "new_proposal", "payload": { ...TradeProposal, "critic": {...CriticVerdict} } }
{"type": "position_update", "payload": { ...positions row } }
{"type": "order_update", "payload": { ...ExecutionResult } }
{"type": "kill_switch", "payload": {"active": true, "triggered_by": "uuid", "timestamp": "iso8601"} }
```
