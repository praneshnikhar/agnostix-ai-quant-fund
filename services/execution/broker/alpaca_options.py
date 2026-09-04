"""Alpaca options adapter (paper trading ONLY).

Thin adapter over alpaca-py. All imports are lazy so the module (and the
whole app) imports cleanly without alpaca-py installed. Clients are
injectable for deterministic testing. Live (real-money) endpoints are
hard-refused at construction.

Data sources:
  - option contracts (reference metadata)  → TradingClient.get_option_contracts
  - option quotes / snapshots (bid/ask/greeks) → OptionHistoricalDataClient
  - underlying price                         → StockHistoricalDataClient
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from execution.broker.options_base import (
    OptionOrderRequest,
    OptionOrderStatus,
    OptionsBroker,
)
from options.schemas import OptionContract, OptionQuote, OptionType

PROVIDER = "alpaca_options"


class OptionsBrokerNotConfiguredError(RuntimeError):
    """Raised when Alpaca credentials are missing or unset."""


class LiveTradingRefusedError(RuntimeError):
    """Raised when a live-money client is requested."""


def _settings() -> Any:
    from app.core.config import get_settings

    return get_settings()


def _build_clients():
    """Build (trading_client, option_data_client, stock_data_client)."""
    s = _settings()
    if not s.alpaca_api_key or not s.alpaca_secret_key:
        raise OptionsBrokerNotConfiguredError("ALPACA_API_KEY / ALPACA_SECRET_KEY are not set")
    if not s.alpaca_paper:
        raise LiveTradingRefusedError("ALPACA_PAPER=false refused: paper trading only")

    from alpaca.trading.client import TradingClient

    trading = TradingClient(api_key=s.alpaca_api_key, secret_key=s.alpaca_secret_key, paper=True)

    option_data: Any = None
    stock_data: Any = None
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient

        option_data = OptionHistoricalDataClient(
            api_key=s.alpaca_api_key, secret_key=s.alpaca_secret_key
        )
    except ImportError:
        option_data = None
    try:
        from alpaca.data.historical import StockHistoricalDataClient

        stock_data = StockHistoricalDataClient(
            api_key=s.alpaca_api_key, secret_key=s.alpaca_secret_key
        )
    except ImportError:
        stock_data = None

    return trading, option_data, stock_data


def _contract_type(raw: Any) -> OptionType:
    value = str(getattr(raw, "type", "")).lower()
    if "put" in value:
        return OptionType.PUT
    return OptionType.CALL


def _expiry_naive(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        # Keep it tz-aware; downstream DTE/price math subtracts an aware now.
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    try:
        # expiration_date is a date (naive); combine with ~16:00 ET market
        # close, expressed as UTC so datetime arithmetic is consistent.
        d = value
        if hasattr(value, "date"):
            d = value.date()
        return datetime(d.year, d.month, d.day, 20, 0, tzinfo=UTC)
    except Exception:  # noqa: BLE001
        return None


class AlpacaOptionsBroker(OptionsBroker):
    """Paper options broker over alpaca-py."""

    name = "alpaca_options"

    def __init__(self, *, trading=None, option_data=None, stock_data=None) -> None:
        if trading is not None or option_data is not None or stock_data is not None:
            self._trading, self._option_data, self._stock_data = trading, option_data, stock_data
        else:
            self._trading, self._option_data, self._stock_data = _build_clients()

    # -- reference data -----------------------------------------------------

    async def get_option_contracts(
        self,
        underlying: str,
        *,
        expiration: datetime | None = None,
        min_dte: int = 0,
        max_dte: int = 60,
    ) -> list[OptionContract]:
        from alpaca.trading.enums import AssetStatus
        from alpaca.trading.requests import GetOptionContractsRequest

        kwargs: dict[str, Any] = {
            "underlying_symbols": [underlying.upper()],
            "status": AssetStatus.ACTIVE,
            "limit": 9999,
        }
        if expiration is not None:
            kwargs["expiration_date"] = expiration.date()
        elif min_dte or max_dte:
            # Alpaca returns only near-term contracts by default; constrain the
            # request to the DTE window so the agent's expiry selection works.
            today = _now().date()
            kwargs["expiration_date_gte"] = today + timedelta(days=min_dte)
            kwargs["expiration_date_lte"] = today + timedelta(days=max_dte)

        def _fetch() -> list[OptionContract]:
            req = GetOptionContractsRequest(**kwargs)
            resp = self._trading.get_option_contracts(req)
            contracts = getattr(resp, "option_contracts", []) or []
            out: list[OptionContract] = []
            for c in contracts:
                strike = getattr(c, "strike_price", None)
                if strike is None:
                    continue
                out.append(
                    OptionContract(
                        symbol=str(getattr(c, "symbol", "")),
                        underlying=underlying.upper(),
                        option_type=_contract_type(c),
                        strike=float(strike),
                        expiration=_expiry_naive(getattr(c, "expiration_date", None)) or _now(),
                        root=str(getattr(c, "root_symbol", "") or ""),
                    )
                )
            return out

        return await asyncio.to_thread(_fetch)

    # -- quotes -------------------------------------------------------------

    async def get_option_quotes(self, symbols: list[str]) -> dict[str, OptionQuote]:
        if not symbols:
            return {}
        if self._option_data is None:
            return {}
        from alpaca.data.requests import OptionSnapshotRequest

        BATCH = 100  # Alpaca option snapshot API limits each request to 100 symbols

        def _fetch_batch(batch: list[str]) -> dict[str, OptionQuote]:
            req = OptionSnapshotRequest(symbol_or_symbols=batch)
            resp = self._option_data.get_option_snapshot(req)
            out: dict[str, OptionQuote] = {}
            for sym in batch:
                snap = self._snapshot_for(resp, sym)
                if snap is None:
                    continue
                quote = self._snapshot_to_quote(sym, snap)
                if quote is not None:
                    out[sym] = quote
            return out

        def _fetch() -> dict[str, OptionQuote]:
            out: dict[str, OptionQuote] = {}
            for i in range(0, len(symbols), BATCH):
                out.update(_fetch_batch(symbols[i : i + BATCH]))
            return out

        return await asyncio.to_thread(_fetch)

    @staticmethod
    def _snapshot_for(resp: Any, symbol: str) -> Any:
        if isinstance(resp, dict):
            return resp.get(symbol)
        return None

    @staticmethod
    def _occ_strike(symbol: str) -> float | None:
        """Parse the strike (×1000, 8 digits) from an OCC option symbol.

        e.g. "SPY260903C00420000" -> 420.0. Returns None for malformed symbols.
        """
        digits = symbol[-8:]
        if not digits.isdigit():
            return None
        return float(int(digits)) / 1000.0

    def _snapshot_to_quote(self, symbol: str, snap: Any) -> OptionQuote | None:
        quote = getattr(snap, "latest_quote", None)
        bid = getattr(quote, "bid_price", None)
        ask = getattr(quote, "ask_price", None)
        if bid is None and ask is None:
            trade = getattr(snap, "latest_trade", None)
            last = getattr(trade, "price", None) if trade else None
        else:
            last = None
        greeks = getattr(snap, "greeks", None)
        strike = self._occ_strike(symbol)
        if strike is None:
            return None
        return OptionQuote(
            symbol=symbol,
            strike=strike,
            bid=float(bid) if bid is not None else None,
            ask=float(ask) if ask is not None else None,
            last=float(last) if last is not None else None,
            implied_volatility=float(getattr(snap, "implied_volatility", 0) or 0) or None,
            delta=float(greeks.delta)
            if greeks and getattr(greeks, "delta", None) is not None
            else None,
            gamma=float(greeks.gamma)
            if greeks and getattr(greeks, "gamma", None) is not None
            else None,
            theta=float(greeks.theta)
            if greeks and getattr(greeks, "theta", None) is not None
            else None,
            vega=float(greeks.vega)
            if greeks and getattr(greeks, "vega", None) is not None
            else None,
        )

    # -- orders -------------------------------------------------------------

    async def submit_option_order(self, request: OptionOrderRequest) -> OptionOrderStatus:
        from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest, OptionLegRequest

        def _submit() -> OptionOrderStatus:
            if request.mleg and request.num_legs > 1:
                # Alpaca MLEG requires relatively-prime leg ratios: leg qty is
                # expressed as a ratio (1:1 for spreads) and the order `qty` is
                # the number of multi-leg units. Reduce by the GCD so equal legs
                # submit as 1:1 rather than the raw (non-prime) contract count.
                import math

                gcd = math.gcd(*request.quantities) or 1
                ratios = [int(q // gcd) for q in request.quantities]
                legs = [
                    OptionLegRequest(
                        symbol=leg.symbol,
                        side=OrderSide.BUY if side.value.startswith("buy") else OrderSide.SELL,
                        ratio_qty=ratio,
                    )
                    for leg, side, ratio in zip(
                        request.legs, request.sides, ratios, strict=False
                    )
                ]
                order = MarketOrderRequest(
                    qty=gcd,
                    order_class=OrderClass.MLEG,
                    time_in_force=TimeInForce.DAY,
                    legs=legs,
                    client_order_id=request.client_order_id,
                )
            else:
                leg = request.legs[0]
                side = request.sides[0]
                order = MarketOrderRequest(
                    symbol=leg.symbol,
                    qty=request.quantities[0],
                    side=OrderSide.BUY if side.value.startswith("buy") else OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                    client_order_id=request.client_order_id,
                )
            result = self._trading.submit_order(order)
            return OptionOrderStatus(
                order_id=str(result.id),
                status=str(result.status),
                raw={"alpaca_order_id": str(result.id)},
            )

        return await asyncio.to_thread(_submit)

    async def close_option_position(self, symbol: str, qty: float) -> OptionOrderStatus:
        from alpaca.trading.requests import ClosePositionRequest

        def _close() -> OptionOrderStatus:
            result = self._trading.close_position(
                symbol_or_asset_id=symbol, close_options=ClosePositionRequest(qty=str(abs(qty)))
            )
            return OptionOrderStatus(order_id=str(result.id), status=str(result.status))

        return await asyncio.to_thread(_close)

    # -- underlying ---------------------------------------------------------

    async def get_underlying_price(self, symbol: str) -> float | None:
        if self._stock_data is None:
            return None
        from alpaca.data.requests import StockLatestQuoteRequest

        def _fetch() -> float | None:
            req = StockLatestQuoteRequest(symbol_or_symbols=[symbol.upper()])
            resp = self._stock_data.get_stock_latest_quote(req)
            data = resp.get(symbol.upper()) if isinstance(resp, dict) else None
            if data is None:
                return None
            price = getattr(data, "ask_price", None) or getattr(data, "bid_price", None)
            return float(price) if price is not None else None

        return await asyncio.to_thread(_fetch)


def _now() -> datetime:
    return datetime.now(UTC)
