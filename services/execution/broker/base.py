"""Broker and MarketDataProvider abstractions.

Business logic depends ONLY on these interfaces. Alpaca-specific code is
confined to the alpaca_* adapters. The system must remain operational if
Alpaca MCP is unavailable (SDK/API fallback).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class TimeInForce(StrEnum):
    DAY = "day"
    GTC = "gtc"


class OrderRequest(BaseModel):
    """Typed order request. Execution requires a prior authorization event
    (enforced by the execution service in M7 — never by the broker alone)."""

    symbol: str
    side: OrderSide
    quantity: float = Field(gt=0)
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    time_in_force: TimeInForce = TimeInForce.DAY
    client_order_id: str | None = None
    # Authorization provenance — required for auditability.
    proposal_id: str | None = None
    authorized_by_user_id: str | None = None
    authorization_event_id: str | None = None


class OrderStatusInfo(BaseModel):
    order_id: str
    status: str
    filled_qty: float = 0.0
    filled_avg_price: float | None = None
    submitted_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class AccountInfo(BaseModel):
    equity: float
    cash: float
    buying_power: float
    raw: dict[str, Any] = Field(default_factory=dict)


class PositionInfo(BaseModel):
    symbol: str
    qty: float
    avg_entry_price: float
    current_price: float | None = None
    unrealized_pl: float | None = None


class Bar(BaseModel):
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class NewsItem(BaseModel):
    headline: str
    source: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    symbols: list[str] = Field(default_factory=list)


class Broker(ABC):
    """Order-placement boundary. Implementations must be paper-only in M0."""

    name: str

    @abstractmethod
    async def get_account(self) -> AccountInfo: ...

    @abstractmethod
    async def get_positions(self) -> list[PositionInfo]: ...

    @abstractmethod
    async def submit_order(self, request: OrderRequest) -> OrderStatusInfo: ...

    @abstractmethod
    async def get_order(self, order_id: str) -> OrderStatusInfo: ...


class MarketDataProvider(ABC):
    """Read-only market data boundary."""

    name: str

    @abstractmethod
    async def get_bars(
        self, symbol: str, timeframe: str = "1Day", limit: int = 100
    ) -> list[Bar]: ...

    @abstractmethod
    async def get_quote(self, symbol: str) -> dict[str, Any]: ...

    @abstractmethod
    async def get_news(self, symbol: str, limit: int = 10) -> list[NewsItem]: ...
