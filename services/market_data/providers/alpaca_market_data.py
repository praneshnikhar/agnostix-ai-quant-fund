"""Alpaca market-data provider (M1).

Thin adapter over alpaca-py. The SDK is imported lazily so the module
(and the whole app) works without the package installed. All SDK responses
are converted through market_data.normalization into internal schemas.
The SDK client is injectable for deterministic testing.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from market_data.normalization import (
    NormalizationError,
    normalize_bar,
    normalize_quote,
    normalize_security,
    normalize_trade,
)
from market_data.providers.base import MarketDataProvider, ProviderError
from market_data.schemas import Bar, Quote, Security, Trade

PROVIDER = "alpaca_market_data"


def _now() -> datetime:
    return datetime.now(UTC)


class AlpacaMarketDataProvider(MarketDataProvider):
    """client: an alpaca-py StockHistoricalClient-compatible object."""

    def __init__(
        self,
        client: object | None = None,
        *,
        api_key: str | None = None,
        secret_key: str | None = None,
        feed: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._feed = feed
        if client is not None:
            self._client = client
        else:
            self._client = self._build_default_client(
                api_key=self._api_key,
                secret_key=self._secret_key,
                feed=self._feed,
            )

    @staticmethod
    def _build_default_client(
        *, api_key: str | None = None, secret_key: str | None = None, feed: str | None = None
    ) -> object:
        try:
            from alpaca.data.historical.stock import StockHistoricalDataClient
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise ProviderError(
                "alpaca-py is not installed; install it or inject a client"
            ) from exc
        key = api_key or os.environ.get("ALPACA_API_KEY_ID")
        secret = secret_key or os.environ.get("ALPACA_API_SECRET_KEY")
        if not key or not secret:
            raise ProviderError("ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY not set")
        # alpaca-py >= 0.44 sets the data feed per-request (see _request /
        # get_latest_quote), not on the client constructor.
        return StockHistoricalDataClient(api_key=key, secret_key=secret)

    # -- bars ---------------------------------------------------------------

    def get_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[Bar]:
        received = _now()
        end = end or received
        start = start or end - timedelta(days=30)
        try:
            resp = self._client.get_stock_bars(  # type: ignore[attr-defined]
                self._request(symbol, timeframe, start, end, limit)
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"bars fetch failed for {symbol}: {exc}") from exc
        raw_bars = self._extract(resp, symbol)
        bars: list[Bar] = []
        for raw in raw_bars:
            raw.setdefault("S", symbol)
            try:
                bars.append(normalize_bar(raw, provider=PROVIDER, received_at=received))
            except NormalizationError:
                continue  # invalid records are dropped and counted upstream
        return bars

    # -- quotes -------------------------------------------------------------

    def get_latest_quote(self, symbol: str) -> Quote | None:
        received = _now()
        feed = self._feed or os.environ.get("ALPACA_DATA_FEED", "iex")
        try:
            from alpaca.data.requests import StockLatestQuoteRequest

            resp = self._client.get_stock_latest_quote(  # type: ignore[attr-defined]
                StockLatestQuoteRequest(symbol_or_symbols=[symbol.upper()], feed=feed)
            )
        except Exception as exc:
            raise ProviderError(f"quote fetch failed for {symbol}: {exc}") from exc
        quote = self._single(resp, symbol)
        if quote is None:
            return None
        first = self._as_dict(quote)
        first.setdefault("S", symbol)
        return normalize_quote(first, provider=PROVIDER, received_at=received)

    # -- trades -------------------------------------------------------------

    def get_recent_trades(self, symbol: str, limit: int = 50) -> list[Trade]:
        received = _now()
        end = received
        start = end - timedelta(days=1)
        feed = self._feed or os.environ.get("ALPACA_DATA_FEED", "iex")
        try:
            from alpaca.data.requests import StockTradesRequest

            resp = self._client.get_stock_trades(  # type: ignore[attr-defined]
                StockTradesRequest(
                    symbol_or_symbols=symbol.upper(), start=start, end=end, limit=limit, feed=feed
                )
            )
        except Exception as exc:
            raise ProviderError(f"trades fetch failed for {symbol}: {exc}") from exc
        trades: list[Trade] = []
        for raw in self._extract(resp, symbol)[-limit:]:
            raw = dict(raw)
            # alpaca's `id` is a per-response sequence number, not a stable
            # trade identifier — treating it as a provider_trade_id would
            # collide across symbols.
            raw.pop("id", None)
            raw.setdefault("S", symbol)
            trades.append(normalize_trade(raw, provider=PROVIDER, received_at=received))
        return trades

    # -- security metadata --------------------------------------------------

    def get_security(self, symbol: str) -> Security | None:
        received = _now()
        try:
            # Prefer an injected client exposing get_asset (test fakes);
            # otherwise lazily build a PAPER-ONLY TradingClient.
            asset = None
            injected = getattr(self._client, "get_asset", None)
            if callable(injected):
                asset = injected(symbol.upper())
            else:
                client = getattr(self, "_trading_client", None)
                if client is None:
                    from alpaca.trading.client import TradingClient

                    key = self._api_key or os.environ.get("ALPACA_API_KEY_ID")
                    secret = self._secret_key or os.environ.get("ALPACA_API_SECRET_KEY")
                    if not key or not secret:
                        raise ProviderError("credentials required for security metadata")
                    client = TradingClient(api_key=key, secret_key=secret, paper=True)
                    self._trading_client = client
                asset = client.get_asset(symbol.upper())
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"security fetch failed for {symbol}: {exc}") from exc
        raw = {
            "symbol": getattr(asset, "symbol", symbol),
            "name": getattr(asset, "name", None),
            "exchange": str(getattr(asset, "exchange", "") or "") or None,
            "status": "active" if getattr(asset, "status", "active") == "active" else "inactive",
            "asset_class": str(getattr(asset, "asset_class", "us_equity")),
        }
        return normalize_security(raw, provider=PROVIDER, received_at=received)

    # -- helpers -------------------------------------------------------------

    def _request(
        self, symbol: str, timeframe: str, start: datetime, end: datetime, limit: int
    ) -> dict:
        tf_map = {"1Min": "1Min", "1Hour": "1Hour", "1Day": "1Day"}
        try:
            from typing import Any, cast

            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame

            tf = cast(
                Any,
                TimeFrame.Minute
                if timeframe == "1Min"
                else (TimeFrame.Hour if timeframe == "1Hour" else TimeFrame.Day),
            )
            from alpaca.data.enums import DataFeed

            req = StockBarsRequest(
                symbol_or_symbols=symbol.upper(),
                timeframe=tf,
                start=start,
                end=end,
                limit=limit,
                feed=cast(DataFeed | None, self._feed or os.environ.get("ALPACA_DATA_FEED", "iex")),
            )
            return req  # type: ignore[return-value]
        except ImportError:
            return {
                "symbol_or_symbols": symbol.upper(),
                "timeframe": tf_map.get(timeframe, "1Day"),
                "start": start,
                "end": end,
                "limit": limit,
            }

    @staticmethod
    def _extract(resp: object, symbol: str) -> list[dict]:
        """Normalize alpaca-py response shapes ({sym: [...]}, BarSet, dicts)."""
        from typing import Any

        if isinstance(resp, dict):
            data: Any = resp.get(symbol.upper(), resp)
        else:
            data = getattr(resp, "data", resp)
        if isinstance(data, dict):  # mapping of symbol -> rows
            rows = data.get(symbol.upper(), [])
        elif isinstance(data, list):
            rows = data
        else:
            rows = []
        out: list[dict] = []
        for row in rows:
            out.append(AlpacaMarketDataProvider._as_dict(row))
        return out

    @staticmethod
    def _as_dict(row: object) -> dict:
        """Convert an alpaca-py model (or dict) to a plain dict."""
        if isinstance(row, dict):
            return dict(row)
        dump = getattr(row, "model_dump", None)
        if callable(dump):
            return dump()
        return {k: v for k, v in vars(row).items() if not k.startswith("_") and v is not None}

    @staticmethod
    def _single(resp: object, symbol: str) -> object | None:
        """Extract the single per-symbol model from a {symbol: model} response.

        Some SDK shapes wrap the model in a one-element list; unwrap it.
        """
        if isinstance(resp, dict):
            data = resp
        else:
            data = getattr(resp, "data", resp)
        if isinstance(data, dict):
            item = data.get(symbol.upper())
            if isinstance(item, list):
                return item[0] if item else None
            return item
        return None
