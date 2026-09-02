"""Options broker abstraction.

Business logic (trading agent, risk engine) depends ONLY on these
interfaces. The Alpaca implementation is confined to alpaca_options.py.
Paper trading only — live money is hard-refused at adapter construction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field

from options.schemas import OptionContract, OptionQuote, OptionSide


class OptionOrderRequest(BaseModel):
    """A sized, risk-approved options order (single-leg or multi-leg)."""

    strategy_id: str
    underlying: str
    legs: list[OptionContract]
    sides: list[OptionSide]
    quantities: list[int]
    # Multi-leg orders fill atomically (MLEG); single legs are plain orders.
    mleg: bool = False
    order_type: str = "market"
    limit_price: float | None = None
    time_in_force: str = "day"
    client_order_id: str | None = None

    @property
    def num_legs(self) -> int:
        return len(self.legs)


class OptionOrderStatus(BaseModel):
    order_id: str
    status: str
    filled_qty: float = 0.0
    filled_avg_price: float | None = None
    legs: list[dict] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)


class OptionsBroker(ABC):
    """Options order-placement + reference-data boundary (paper only)."""

    name: str

    @abstractmethod
    async def get_option_contracts(
        self, underlying: str, *, expiration: datetime | None = None
    ) -> list[OptionContract]: ...

    @abstractmethod
    async def get_option_quotes(self, symbols: list[str]) -> dict[str, OptionQuote]: ...

    @abstractmethod
    async def submit_option_order(self, request: OptionOrderRequest) -> OptionOrderStatus: ...

    @abstractmethod
    async def close_option_position(self, symbol: str, qty: float) -> OptionOrderStatus: ...

    @abstractmethod
    async def get_underlying_price(self, symbol: str) -> float | None: ...
