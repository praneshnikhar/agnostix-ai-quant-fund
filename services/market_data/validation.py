"""Deterministic data-quality validation (M1).

Pure functions returning lists of human-readable problems. Empty list =
valid. No exceptions for invalid data — validation is a quality gate that
feeds provenance/observability, not a crash path.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from market_data.schemas import (
    CLOCK_SKEW_TOLERANCE_SECONDS,
    Bar,
    NewsArticle,
    Quote,
    Trade,
)


def _future_check(event_time: datetime, problems: list[str], label: str) -> None:
    now = datetime.now(UTC)
    if event_time > now + timedelta(seconds=CLOCK_SKEW_TOLERANCE_SECONDS):
        problems.append(f"{label}: event_time is in the future beyond clock-skew tolerance")


def validate_bar(b: Bar) -> list[str]:
    problems: list[str] = []
    if b.high < b.low:
        problems.append("bar: high < low")
    if b.high < max(b.open, b.close):
        problems.append("bar: high < max(open, close)")
    if b.low > min(b.open, b.close):
        problems.append("bar: low > min(open, close)")
    if b.volume < 0:
        problems.append("bar: negative volume")
    if b.close <= 0:
        problems.append("bar: non-positive close")
    _future_check(b.event_time, problems, "bar")
    return problems


def validate_quote(q: Quote) -> list[str]:
    problems: list[str] = []
    if q.bid_price is not None and q.ask_price is not None:
        if q.bid_price <= 0 or q.ask_price <= 0:
            problems.append("quote: non-positive bid/ask price")
        elif q.bid_price > q.ask_price:
            problems.append("quote: crossed book (bid > ask)")
    _future_check(q.event_time, problems, "quote")
    return problems


def validate_trade(t: Trade) -> list[str]:
    problems: list[str] = []
    if t.price <= 0:
        problems.append("trade: non-positive price")
    if t.size <= 0:
        problems.append("trade: non-positive size")
    _future_check(t.event_time, problems, "trade")
    return problems


def validate_news(n: NewsArticle) -> list[str]:
    problems: list[str] = []
    if not n.headline.strip():
        problems.append("news: empty headline")
    if n.url is not None and not n.url.lower().startswith(("http://", "https://")):
        problems.append("news: url scheme must be http/https")
    _future_check(n.published_at, problems, "news")
    return problems


def validate_batch[T](
    items: list[T], validator: Callable[[T], list[str]]
) -> tuple[list[T], list[tuple[int, list[str]]]]:
    """Split a batch into (valid_items, [(index, problems), ...])."""
    valid: list[T] = []
    invalid: list[tuple[int, list[str]]] = []
    for i, item in enumerate(items):
        problems = validator(item)
        if problems:
            invalid.append((i, problems))
        else:
            valid.append(item)
    return valid, invalid


__all__ = [
    "validate_bar",
    "validate_batch",
    "validate_news",
    "validate_quote",
    "validate_trade",
]
