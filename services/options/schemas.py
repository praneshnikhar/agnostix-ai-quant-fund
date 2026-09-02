"""Options domain schemas.

All values are internal, provider-agnostic. Execution adapters convert
Alpaca (or any broker) shapes into these contracts; strategy and risk code
depend only on these types.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class OptionType(StrEnum):
    CALL = "call"
    PUT = "put"


class OptionSide(StrEnum):
    """Trade side: BUY_TO_OPEN / SELL_TO_OPEN / BUY_TO_CLOSE / SELL_TO_CLOSE."""

    BUY_TO_OPEN = "buy_to_open"
    SELL_TO_OPEN = "sell_to_open"
    BUY_TO_CLOSE = "buy_to_close"
    SELL_TO_CLOSE = "sell_to_close"


class Greeks(BaseModel):
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


class OptionContract(BaseModel):
    """A single option contract, as returned by a chain provider."""

    symbol: str  # OCC symbol, e.g. "AAPL250919C00225000"
    underlying: str
    option_type: OptionType
    strike: float = Field(gt=0)
    expiration: datetime
    root: str | None = None


class OptionQuote(BaseModel):
    """Last/implied-volatility snapshot for one contract."""

    symbol: str
    strike: float = Field(gt=0)
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    open_interest: int | None = None
    volume: int | None = None


class OptionChain(BaseModel):
    """Ordered option chain for one underlying at one expiry."""

    underlying: str
    underlying_price: float | None = None
    expiration: datetime
    calls: list[OptionQuote] = Field(default_factory=list)
    puts: list[OptionQuote] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OptionLeg(BaseModel):
    """One leg of a multi-leg strategy, before execution."""

    contract: OptionContract
    side: OptionSide
    quantity: int = Field(gt=0)
    limit_price: float | None = None
    theoretical: float | None = None
    delta: float | None = None

    @property
    def net_delta(self) -> float:
        sign = 1.0 if self.side in (OptionSide.BUY_TO_OPEN, OptionSide.BUY_TO_CLOSE) else -1.0
        return sign * self.quantity * (self.delta or 0.0)


class OptionStrategy(BaseModel):
    """A complete, sized, defined-risk options strategy ready for risk gates."""

    strategy_id: str
    name: str  # e.g. "bull_put_spread", "iron_condor", "cash_secured_put"
    underlying: str
    legs: list[OptionLeg] = Field(default_factory=list)
    net_credit: float | None = None
    net_debit: float | None = None
    max_loss: float | None = None
    max_profit: float | None = None
    break_even: list[float] = Field(default_factory=list)
    probability_of_profit: float | None = None
    days_to_expiration: int | None = None
    notes: list[str] = Field(default_factory=list)

    @property
    def defined_risk(self) -> bool:
        return self.max_loss is not None and self.max_loss >= 0
