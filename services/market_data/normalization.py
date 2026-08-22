"""Provider-agnostic normalization (M1).

Pure functions converting loosely-typed provider-shaped dicts into internal
domain models. Deterministic code only — NO LLM calls for OHLCV parsing,
timestamp normalization, or basic news metadata extraction (.clinerules §32).

Accepted key aliases cover Alpaca-style short keys (t/o/h/l/c/v) and
verbose keys (timestamp/open/high/...). Unknown/garbage values raise
NormalizationError rather than being silently coerced.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from market_data.schemas import Bar, NewsArticle, ProviderInfo, Quote, Security, Trade


class NormalizationError(ValueError):
    """Raised when a provider record cannot be normalized."""


def _get(raw: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in raw and raw[k] is not None:
            return raw[k]
    return None


def _require(raw: dict[str, Any], *keys: str) -> Any:
    value = _get(raw, *keys)
    if value is None:
        raise NormalizationError(f"missing required field(s) {keys} in {raw!r}")
    return value


def _to_float(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise NormalizationError(f"{field}: not a number: {value!r}") from exc
    if result != result or result in (float("inf"), float("-inf")):
        raise NormalizationError(f"{field}: non-finite value: {value!r}")
    return result


def _to_int(value: Any, field: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise NormalizationError(f"{field}: not an integer: {value!r}") from exc


def parse_timestamp(value: Any) -> datetime:
    """Parse ISO strings / epoch seconds / epoch millis to tz-aware UTC.

    Never fabricates a time: unparseable input raises NormalizationError.
    """
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        # Heuristic by magnitude: ns -> ms -> s.
        magnitude = abs(value)
        if magnitude >= 1e17:
            seconds = value / 1e9  # nanoseconds
        elif magnitude >= 1e11:
            seconds = value / 1000.0  # milliseconds
        else:
            seconds = float(value)
        try:
            dt = datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise NormalizationError(f"unparseable epoch timestamp: {value!r}") from exc
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError as exc:
            raise NormalizationError(f"unparseable timestamp: {value!r}") from exc
    else:
        raise NormalizationError(f"unsupported timestamp type: {type(value).__name__}")

    if dt.tzinfo is None:
        raise NormalizationError(
            f"timestamp is timezone-naive; refusing to guess timezone: {value!r}"
        )
    return dt.astimezone(UTC)


def normalize_bar(raw: dict[str, Any], provider: str, received_at: datetime) -> Bar:
    event_time = parse_timestamp(_require(raw, "t", "timestamp", "time"))
    return Bar(
        symbol=str(_require(raw, "S", "symbol")).upper(),
        event_time=event_time,
        open=_to_float(_require(raw, "o", "open"), "open"),
        high=_to_float(_require(raw, "h", "high"), "high"),
        low=_to_float(_require(raw, "l", "low"), "low"),
        close=_to_float(_require(raw, "c", "close"), "close"),
        volume=_to_float(_require(raw, "v", "volume"), "volume"),
        trade_count=(
            _to_int(v, "trade_count") if (v := _get(raw, "n", "trade_count")) is not None else None
        ),
        vwap=(_to_float(v, "vwap") if (v := _get(raw, "vw", "vwap")) is not None else None),
        provider_info=ProviderInfo(provider=provider),
        received_at=received_at,
    )


def normalize_quote(raw: dict[str, Any], provider: str, received_at: datetime) -> Quote:
    return Quote(
        symbol=str(_require(raw, "S", "symbol")).upper(),
        event_time=parse_timestamp(_require(raw, "t", "timestamp", "time")),
        # Alpaca convention: ap/as = ask price/size, bp/bs = bid price/size.
        ask_price=(
            _to_float(v, "ask_price")
            if (v := _get(raw, "ap", "apx", "ask_price")) is not None
            else None
        ),
        ask_size=(
            _to_float(v, "ask_size") if (v := _get(raw, "as", "ask_size")) is not None else None
        ),
        bid_price=(
            _to_float(v, "bid_price")
            if (v := _get(raw, "bp", "bpx", "bid_price")) is not None
            else None
        ),
        bid_size=(
            _to_float(v, "bid_size") if (v := _get(raw, "bs", "bid_size")) is not None else None
        ),
        last_price=(
            _to_float(v, "last_price") if (v := _get(raw, "last_price", "px")) is not None else None
        ),
        provider_info=ProviderInfo(provider=provider),
        received_at=received_at,
    )


def normalize_trade(raw: dict[str, Any], provider: str, received_at: datetime) -> Trade:
    conditions_raw = _get(raw, "c", "conditions")
    conditions = (
        [str(c) for c in conditions_raw]
        if isinstance(conditions_raw, list)
        else ([str(conditions_raw)] if conditions_raw is not None else [])
    )
    return Trade(
        symbol=str(_require(raw, "S", "symbol")).upper(),
        event_time=parse_timestamp(_require(raw, "t", "timestamp", "time")),
        price=_to_float(_require(raw, "p", "price"), "price"),
        size=_to_float(_require(raw, "s", "size"), "size"),
        conditions=conditions,
        provider_trade_id=(str(v) if (v := _get(raw, "i", "id", "trade_id")) is not None else None),
        provider_info=ProviderInfo(provider=provider),
        received_at=received_at,
    )


def normalize_news(raw: dict[str, Any], provider: str, received_at: datetime) -> NewsArticle:
    symbols_raw = _get(raw, "symbols", "ticker_symbols")
    symbols = [str(s).upper() for s in symbols_raw] if isinstance(symbols_raw, list) else []
    return NewsArticle(
        provider_article_id=str(_require(raw, "id", "article_id")),
        headline=str(_require(raw, "headline", "title")),
        summary=(str(v) if (v := _get(raw, "summary", "content")) is not None else None),
        source=(str(v) if (v := _get(raw, "source")) is not None else None),
        url=(str(v) if (v := _get(raw, "url", "article_url")) is not None else None),
        symbols=symbols,
        published_at=parse_timestamp(_require(raw, "created_at", "published_at", "published_utc")),
        provider_info=ProviderInfo(provider=provider),
        received_at=received_at,
    )


def normalize_security(raw: dict[str, Any], provider: str, received_at: datetime) -> Security:
    status = str(_get(raw, "status") or "active").lower()
    if status not in ("active", "inactive"):
        raise NormalizationError(f"invalid security status: {status!r}")
    return Security(
        symbol=str(_require(raw, "symbol", "S")).upper(),
        name=(str(v) if (v := _get(raw, "name")) is not None else None),
        exchange=(str(v) if (v := _get(raw, "exchange")) is not None else None),
        asset_class=(
            str(v) if (v := _get(raw, "asset_class", "class")) is not None else "us_equity"
        ),
        status=status,
        provider_info=ProviderInfo(provider=provider),
        received_at=received_at,
    )


__all__ = [
    "NormalizationError",
    "normalize_bar",
    "normalize_news",
    "normalize_quote",
    "normalize_security",
    "normalize_trade",
    "parse_timestamp",
]
