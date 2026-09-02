"""Implied-volatility analytics: IV rank and IV percentile.

Used by the risk engine and strategy builder to decide whether a stock's
option premium is worth selling (high IV rank) or buying (low IV rank).
Deterministic — takes a list of implied vol observations and returns a
rank/percentile. Pure functions only.
"""

from __future__ import annotations


def _clean(values: list[float] | None) -> list[float]:
    if not values:
        return []
    return [v for v in values if v is not None and v > 0]


def iv_rank(current_iv: float | None, iv_history: list[float] | None) -> float | None:
    """IV rank: where current IV sits in the min–max range of history.

    Returns 0.0–1.0, or None when current IV or a usable history range is
    unavailable (never fabricate a rank from a single observation).
    """
    if current_iv is None or current_iv <= 0:
        return None
    hist = _clean(iv_history)
    if len(hist) < 2:
        return None
    low, high = min(hist), max(hist)
    if high - low <= 1e-9:
        return 0.5
    return max(0.0, min(1.0, (current_iv - low) / (high - low)))


def iv_percentile(current_iv: float | None, iv_history: list[float] | None) -> float | None:
    """IV percentile: fraction of historical IV observations below current."""
    if current_iv is None or current_iv <= 0:
        return None
    hist = _clean(iv_history)
    if not hist:
        return None
    below = sum(1 for v in hist if v < current_iv)
    return below / len(hist)
