"""Freshness evaluation tests: boundaries, missing, invalid, configurability."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from market_data.freshness import (
    FreshnessThresholds,
    evaluate_freshness,
    load_thresholds_from_settings,
)
from market_data.schemas import FreshnessState

T0 = datetime(2024, 6, 3, 14, 30, tzinfo=UTC)


def test_missing_when_no_records() -> None:
    state, status = evaluate_freshness(
        None, T0, timedelta(seconds=60), symbol="AAPL", datatype="quotes"
    )
    assert state == FreshnessState.MISSING
    assert status.as_of is None


def test_fresh_at_exact_threshold() -> None:
    state, _ = evaluate_freshness(T0, T0 + timedelta(seconds=60), timedelta(seconds=60))
    assert state == FreshnessState.FRESH


def test_stale_just_over_threshold() -> None:
    state, status = evaluate_freshness(T0, T0 + timedelta(seconds=61), timedelta(seconds=60))
    assert state == FreshnessState.STALE
    assert status.age_seconds == 61.0


def test_naive_event_time_is_invalid() -> None:
    naive = datetime(2024, 6, 3, 14, 30)  # noqa: DTZ001 — intentional
    state, status = evaluate_freshness(naive, T0, timedelta(seconds=60))
    assert state == FreshnessState.INVALID
    assert "naive" in (status.detail or "")


def test_default_thresholds_documented_values() -> None:
    t = FreshnessThresholds()
    assert t.bars_seconds == 24 * 3600
    assert t.quotes_seconds == 60
    assert t.trades_seconds == 300
    assert t.news_seconds == 6 * 3600
    assert t.security_metadata_seconds == 7 * 24 * 3600


def test_thresholds_configurable() -> None:
    t = load_thresholds_from_settings({"quotes_seconds": 5})
    assert t.quotes_seconds == 5
    assert t.bars_seconds == 24 * 3600  # untouched default


def test_unknown_datatype_raises() -> None:
    import pytest

    with pytest.raises(ValueError):
        FreshnessThresholds().for_datatype("options")
