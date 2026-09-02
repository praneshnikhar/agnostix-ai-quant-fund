"""Alpaca adapters — Broker + MarketDataProvider (paper trading ONLY).

Uses alpaca-py when credentials are configured; raises
BrokerNotConfiguredError otherwise so the app can run without Alpaca.
Live (real-money) endpoints are hard-refused at construction time.

Alpaca MCP is NOT used here: MCP is a separate integration boundary
(see mcp_boundary.py) used as a development accelerator. This adapter is
the durable SDK/API fallback path.
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from execution.broker.base import (
    AccountInfo,
    Bar,
    Broker,
    MarketDataProvider,
    NewsItem,
    OrderRequest,
    OrderStatusInfo,
    PositionInfo,
)


class BrokerNotConfiguredError(RuntimeError):
    """Raised when Alpaca credentials are missing."""


class LiveTradingRefusedError(RuntimeError):
    """Raised if any code attempts to construct a live-money client."""


def _load_clients() -> tuple[Any, Any]:
    """Build (trading_client, data_client) or raise if unconfigured."""
    from app.core.config import get_settings

    s = get_settings()
    if not s.alpaca_api_key or not s.alpaca_secret_key:
        raise BrokerNotConfiguredError("ALPACA_API_KEY / ALPACA_SECRET_KEY are not set")
    if not s.alpaca_paper:
        # Hard safety refusal — M0/M1+ development is paper-only.
        raise LiveTradingRefusedError(
            "ALPACA_PAPER=false refused: this platform is paper-trading only "
            "until live execution is explicitly authorized in a future milestone."
        )

    from alpaca.trading.client import TradingClient

    trading = TradingClient(
        api_key=s.alpaca_api_key,
        secret_key=s.alpaca_secret_key,
        paper=True,  # always True in M0
    )

    try:
        from alpaca.data.historical import StockHistoricalDataClient

        data_client: Any = StockHistoricalDataClient(
            api_key=s.alpaca_api_key, secret_key=s.alpaca_secret_key
        )
    except ImportError:
        data_client = None

    return trading, data_client


class AlpacaBroker(Broker):
    """Paper-trading broker adapter (alpaca-py)."""

    name = "alpaca_paper"

    def __init__(self) -> None:
        self._trading, self._data = _load_clients()

    async def get_account(self) -> AccountInfo:
        import asyncio

        account = await asyncio.to_thread(self._trading.get_account)
        last_equity = getattr(account, "last_equity", None)
        return AccountInfo(
            equity=float(account.equity),
            cash=float(account.cash),
            buying_power=float(account.buying_power),
            raw={
                "account_number": str(getattr(account, "account_number", "")),
                "last_equity": float(last_equity) if last_equity is not None else None,
            },
        )

    async def get_positions(self) -> list[PositionInfo]:
        import asyncio

        positions = await asyncio.to_thread(self._trading.get_all_positions)
        return [
            PositionInfo(
                symbol=p.symbol,
                qty=float(p.qty),
                avg_entry_price=float(p.avg_entry_price),
                current_price=(float(p.current_price) if p.current_price else None),
                unrealized_pl=(float(p.unrealized_pl) if p.unrealized_pl else None),
            )
            for p in positions
        ]

    async def submit_order(self, request: OrderRequest) -> OrderStatusInfo:
        """Submit a paper order. Authorization provenance must be present."""
        import asyncio

        if not request.authorization_event_id or not request.authorized_by_user_id:
            raise PermissionError(
                "submit_order requires authorization_event_id and "
                "authorized_by_user_id (human approval provenance)."
            )

        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        order = MarketOrderRequest(
            symbol=request.symbol,
            qty=request.quantity,
            side=OrderSide.BUY if request.side.value == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            client_order_id=request.client_order_id,
        )
        result = await asyncio.to_thread(self._trading.submit_order, order)
        return OrderStatusInfo(
            order_id=str(result.id),
            status=str(result.status),
            raw={"alpaca_order_id": str(result.id)},
        )

    async def get_order(self, order_id: str) -> OrderStatusInfo:
        import asyncio

        result = await asyncio.to_thread(self._trading.get_order_by_id, order_id)
        return OrderStatusInfo(
            order_id=str(result.id),
            status=str(result.status),
            filled_qty=float(result.filled_qty or 0),
            filled_avg_price=(float(result.filled_avg_price) if result.filled_avg_price else None),
        )


class AlpacaMarketDataProvider(MarketDataProvider):
    """Read-only market data adapter (bars/quotes/news)."""

    name = "alpaca_market_data"

    def __init__(self) -> None:
        _, self._data = _load_clients()

    async def get_bars(self, symbol: str, timeframe: str = "1Day", limit: int = 100) -> list[Bar]:
        if self._data is None:
            raise BrokerNotConfiguredError("Alpaca data client unavailable")
        import asyncio
        from datetime import datetime, timedelta

        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        unit_map = {
            "Minute": TimeFrameUnit.Minute,
            "Hour": TimeFrameUnit.Hour,
            "Day": TimeFrameUnit.Day,
        }
        key = timeframe.split("Day")[0] if timeframe.endswith("Day") else timeframe
        tf_unit = unit_map.get(key, TimeFrameUnit.Day)
        tf = TimeFrame(1, tf_unit)

        end = datetime.now(UTC)
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=end - timedelta(days=limit),
            limit=limit,
            feed=DataFeed.IEX,
        )
        bars = await asyncio.to_thread(self._data.get_stock_bars, req)
        out: list[Bar] = []
        for bar in bars[symbol]:
            out.append(
                Bar(
                    symbol=symbol,
                    timestamp=bar.timestamp,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=float(bar.volume),
                )
            )
        return out

    async def get_quote(self, symbol: str) -> dict[str, Any]:
        # Minimal quote via latest bar until the market-data milestone lands.
        bars = await self.get_bars(symbol, limit=1)
        if not bars:
            return {"symbol": symbol, "available": False}
        last = bars[-1]
        return {
            "symbol": symbol,
            "available": True,
            "last_close": last.close,
            "as_of": last.timestamp.isoformat(),
        }

    async def get_news(self, symbol: str, limit: int = 10) -> list[NewsItem]:
        # News ingestion arrives with the M1 market-intelligence milestone;
        # the interface exists now so callers can depend on it immediately.
        return []
