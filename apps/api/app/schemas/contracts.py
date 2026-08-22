"""Pydantic v2 schemas — API contracts and typed agent-to-agent contracts.

The four core JSON object schemas follow `documents/04_Schemas.md` §2 exactly:
TradeProposal, CriticVerdict, HumanDecision, ExecutionResult.
These are the canonical typed contracts; agents must exchange these
structures rather than free-form text.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Health / system
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    environment: str
    database: bool
    redis: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Evidence (part of TradeProposal)
# ---------------------------------------------------------------------------


class Evidence(BaseModel):
    type: str  # e.g. price_action | news | fundamental
    detail: str
    value: float | None = None
    source_url: str | None = None


# ---------------------------------------------------------------------------
# Core agent-to-agent contracts (documents/04_Schemas.md §2)
# ---------------------------------------------------------------------------


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"


class TradeProposal(BaseModel):
    """Signal Agent → Critic."""

    proposal_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    agent_id: str
    symbol: str
    direction: Direction
    thesis: str
    evidence: list[Evidence] = Field(default_factory=list)
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    size_pct_portfolio: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RuleCheck(BaseModel):
    passed: bool
    limit: float | None = None
    actual: float | None = None
    remaining: float | None = None
    detail: str | None = None


class RuleChecks(BaseModel):
    max_position_size: RuleCheck | None = None
    sector_concentration: RuleCheck | None = None
    daily_loss_budget: RuleCheck | None = None
    leverage: RuleCheck | None = None

    model_config = {"extra": "allow"}


class Verdict(StrEnum):
    PASS = "pass"
    PASS_WITH_WARNING = "pass_with_warning"
    REJECT = "reject"


class CriticVerdict(BaseModel):
    """Critic → Human Gate."""

    proposal_id: uuid.UUID
    verdict: Verdict
    rule_checks: RuleChecks
    llm_notes: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DecisionType(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REVISE = "revise"


class HumanDecisionContract(BaseModel):
    """Human Gate → Execution."""

    proposal_id: uuid.UUID
    user_id: uuid.UUID
    decision: DecisionType
    revised_fields: dict[str, Any] | None = None
    notes: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ExecutionStatus(StrEnum):
    ACCEPTED = "accepted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    REJECTED = "rejected"
    CANCELED = "canceled"


class ExecutionResult(BaseModel):
    """Execution → Portfolio Monitor / Dashboard."""

    proposal_id: uuid.UUID
    alpaca_order_id: str
    status: ExecutionStatus
    filled_price: float | None = None
    filled_qty: float | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Audit events (append-only trail)
# ---------------------------------------------------------------------------


class EventType(StrEnum):
    DATA_PULL = "data_pull"
    PROPOSAL_CREATED = "proposal_created"
    CRITIC_REVIEWED = "critic_reviewed"
    RISK_CHECKED = "risk_checked"
    HUMAN_DECISION = "human_decision"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    POSITION_CHANGED = "position_changed"
    KILL_SWITCH_TRIGGERED = "kill_switch_triggered"
    EVALUATION_COMPLETED = "evaluation_completed"
    MODEL_PROMOTED = "model_promoted"


class AgentEventIn(BaseModel):
    """Payload accepted by POST /agent-events (append-only)."""

    agent_id: str
    event_type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    proposal_id: uuid.UUID | None = None


class AgentEventOut(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    agent_id: str
    event_type: str
    payload: dict[str, Any]
    proposal_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# WebSocket envelope (server → dashboard)
# ---------------------------------------------------------------------------


class WSMessageType(StrEnum):
    NEW_PROPOSAL = "new_proposal"
    POSITION_UPDATE = "position_update"
    ORDER_UPDATE = "order_update"
    KILL_SWITCH = "kill_switch"
    HEARTBEAT = "heartbeat"


class WSMessage(BaseModel):
    """Envelope for all server→client WebSocket messages."""

    type: WSMessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
