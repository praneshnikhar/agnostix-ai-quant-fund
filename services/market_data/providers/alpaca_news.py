"""Alpaca news provider (M1). Deterministic metadata extraction only —
no LLM sentiment analysis (that belongs to a later AI milestone)."""

from __future__ import annotations

import os

from market_data.normalization import NormalizationError, normalize_news
from market_data.providers.base import NewsProvider, ProviderError
from market_data.schemas import NewsArticle

PROVIDER = "alpaca_news"


class AlpacaNewsProvider(NewsProvider):
    """client: alpaca-py news-capable client (injectable for tests)."""

    def __init__(self, client: object | None = None) -> None:
        if client is not None:
            self._client = client
        else:
            try:
                from alpaca.data.historical.news import NewsClient
            except ImportError as exc:
                raise ProviderError(
                    "alpaca-py is not installed; install it or inject a client"
                ) from exc
            key = os.environ.get("ALPACA_API_KEY_ID")
            secret = os.environ.get("ALPACA_API_SECRET_KEY")
            if not key or not secret:
                raise ProviderError("ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY not set")
            self._client = NewsClient(api_key=key, secret_key=secret)

    def get_news(self, symbols: list[str] | None = None, limit: int = 50) -> list[NewsArticle]:
        from datetime import UTC, datetime, timedelta

        received = datetime.now(UTC)
        params: dict = {"limit": limit}
        if symbols:
            params["symbols"] = [s.upper() for s in symbols]
            params["start"] = received - timedelta(days=7)
        try:
            resp = self._client.get_news(params)  # type: ignore[attr-defined]
        except Exception as exc:
            raise ProviderError(f"news fetch failed: {exc}") from exc
        rows = getattr(resp, "news", None)
        if rows is None and isinstance(resp, dict):
            rows = resp.get("news", [])
        articles: list[NewsArticle] = []
        for row in rows or []:
            raw = (
                dict(row)
                if isinstance(row, dict)
                else {
                    k: v
                    for k, v in vars(row).items()
                    if not k.startswith("_") and v is not None
                }
            )
            # alpaca-py uses ticker_symbols + published_at naming.
            if "symbols" not in raw and "ticker_symbols" in raw:
                raw["symbols"] = raw["ticker_symbols"]
            if "published_at" in raw and "created_at" not in raw:
                raw["created_at"] = raw["published_at"]
            try:
                articles.append(
                    normalize_news(raw, provider=PROVIDER, received_at=received)
                )
            except NormalizationError:
                continue
        return articles
