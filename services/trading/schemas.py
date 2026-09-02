"""Trading domain schemas — signal, decision, and audit records."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from options.schemas import OptionStrategy
from risk.engine import RiskResult


class SignalDirection(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    ABSTAIN = "abstain"


class Signal(BaseModel):
    """LLM output — direction + thesis ONLY. Strikes/size are code-decided."""

    symbol: str
    direction: SignalDirection
    confidence: float = Field(ge=0.0, le=1.0)
    thesis: str
    catalyst: str | None = None
    invalidation: str | None = None
    model: str | None = None
    provider: str | None = None


class DecisionStatus(StrEnum):
    EXECUTED = "executed"
    REFUSED = "refused"
    ABSTAINED = "abstained"
    ERROR = "error"


class AgentDecision(BaseModel):
    """One full cycle of the agent: signal → strategy → risk → (execute)."""

    decision_id: str
    symbol: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    signal: Signal | None = None
    strategy: OptionStrategy | None = None
    risk: RiskResult | None = None
    status: DecisionStatus = DecisionStatus.ABSTAINED
    order_id: str | None = None
    reason: str | None = None
    market_price: float | None = None
    iv_rank: float | None = None

    def as_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "signal": self.signal.model_dump(mode="json") if self.signal else None,
            "strategy": self.strategy.model_dump(mode="json") if self.strategy else None,
            "risk": self.risk.as_dict() if self.risk else None,
            "status": self.status.value,
            "order_id": self.order_id,
            "reason": self.reason,
            "market_price": self.market_price,
            "iv_rank": self.iv_rank,
        }
