"""Freshness evaluation (M1).

Explicit data-quality states: FRESH / STALE / MISSING / INVALID.
Thresholds are configurable per datatype; defaults are documented and
deliberate — never silently invented.

Default rationale:
- bars: 24h — daily bars are the primary M1 granularity; a daily bar is
  considered fresh until roughly one trading day has passed.
- quotes: 60s — quotes are near-realtime; anything older than a minute
  during evaluation should be surfaced as stale.
- trades: 300s — trade prints age quickly but slightly slower than quotes.
- news: 6h — news relevance decays over hours, not seconds.
- security_metadata: 7d — reference data changes rarely.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from market_data.schemas import FreshnessState, MarketDataStatus


class FreshnessThresholds(BaseModel):
    """Per-datatype freshness thresholds in seconds. Fully configurable."""

    bars_seconds: float = Field(default=24 * 3600)
    quotes_seconds: float = Field(default=60)
    trades_seconds: float = Field(default=300)
    news_seconds: float = Field(default=6 * 3600)
    security_metadata_seconds: float = Field(default=7 * 24 * 3600)

    def for_datatype(self, datatype: str) -> timedelta:
        mapping = {
            "bars": self.bars_seconds,
            "quotes": self.quotes_seconds,
            "trades": self.trades_seconds,
            "news": self.news_seconds,
            "security_metadata": self.security_metadata_seconds,
        }
        try:
            return timedelta(seconds=mapping[datatype])
        except KeyError as exc:
            raise ValueError(f"unknown datatype: {datatype}") from exc


def load_thresholds_from_settings(raw: dict[str, float] | None) -> FreshnessThresholds:
    """Build thresholds from an optional settings dict (e.g. env-derived).

    Unknown keys are ignored; absent keys keep documented defaults.
    """
    if not raw:
        return FreshnessThresholds()
    allowed = {
        "bars_seconds",
        "quotes_seconds",
        "trades_seconds",
        "news_seconds",
        "security_metadata_seconds",
    }
    return FreshnessThresholds(**{k: v for k, v in raw.items() if k in allowed})


def evaluate_freshness(
    newest_event_time: datetime | None,
    now: datetime,
    threshold: timedelta,
    *,
    symbol: str = "",
    datatype: str = "",
) -> tuple[FreshnessState, MarketDataStatus]:
    """Classify freshness of the newest record of a datatype.

    - None record          -> MISSING
    - naive event_time     -> INVALID (never guess a timezone)
    - age <= threshold     -> FRESH
    - otherwise            -> STALE
    """
    threshold_seconds = threshold.total_seconds()
    if newest_event_time is None:
        return FreshnessState.MISSING, MarketDataStatus(
            datatype=datatype,
            symbol=symbol,
            state=FreshnessState.MISSING,
            as_of=None,
            age_seconds=None,
            threshold_seconds=threshold_seconds,
            detail="no records available",
        )

    if newest_event_time.tzinfo is None:
        return FreshnessState.INVALID, MarketDataStatus(
            datatype=datatype,
            symbol=symbol,
            state=FreshnessState.INVALID,
            as_of=None,
            age_seconds=None,
            threshold_seconds=threshold_seconds,
            detail="event_time is timezone-naive",
        )

    now_aware = now if now.tzinfo is not None else now.replace(tzinfo=newest_event_time.tzinfo)
    age = (now_aware - newest_event_time).total_seconds()
    state = FreshnessState.FRESH if age <= threshold_seconds else FreshnessState.STALE
    return state, MarketDataStatus(
        datatype=datatype,
        symbol=symbol,
        state=state,
        as_of=newest_event_time,
        age_seconds=max(age, 0.0),
        threshold_seconds=threshold_seconds,
    )


__all__ = [
    "FreshnessThresholds",
    "evaluate_freshness",
    "load_thresholds_from_settings",
]
