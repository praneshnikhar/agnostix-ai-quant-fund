"""Provider abstractions (M1).

All methods return INTERNAL domain schemas — never raw SDK objects.
Read-only market data only; no order code exists in this layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from market_data.schemas import Bar, NewsArticle, Quote, Security, Trade


class ProviderError(RuntimeError):
    """Raised when a provider fetch fails (network, auth, bad response)."""


class MarketDataProvider(ABC):
    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[Bar]: ...

    @abstractmethod
    def get_latest_quote(self, symbol: str) -> Quote | None: ...

    @abstractmethod
    def get_recent_trades(self, symbol: str, limit: int = 50) -> list[Trade]: ...

    @abstractmethod
    def get_security(self, symbol: str) -> Security | None: ...


class NewsProvider(ABC):
    @abstractmethod
    def get_news(self, symbols: list[str] | None = None, limit: int = 50) -> list[NewsArticle]: ...
