"""Market-data domain layer (M1).

Pure domain contracts + normalization + validation + freshness.
No database, no provider SDKs, no I/O. Provider adapters live in
``market_data.providers``; persistence lives in ``app.db.repositories``.
"""

from market_data.freshness import FreshnessThresholds, evaluate_freshness
from market_data.normalization import (
    NormalizationError,
    normalize_bar,
    normalize_news,
    normalize_quote,
    normalize_security,
    normalize_trade,
    parse_timestamp,
)
from market_data.schemas import (
    Bar,
    FreshnessState,
    MarketDataStatus,
    MarketSnapshot,
    NewsArticle,
    ProviderInfo,
    Quote,
    Security,
    Trade,
)
from market_data.validation import (
    validate_bar,
    validate_batch,
    validate_news,
    validate_quote,
    validate_trade,
)

__all__ = [
    "Bar",
    "FreshnessState",
    "FreshnessThresholds",
    "MarketDataStatus",
    "MarketSnapshot",
    "NewsArticle",
    "NormalizationError",
    "ProviderInfo",
    "Quote",
    "Security",
    "Trade",
    "evaluate_freshness",
    "normalize_bar",
    "normalize_news",
    "normalize_quote",
    "normalize_security",
    "normalize_trade",
    "parse_timestamp",
    "validate_bar",
    "validate_batch",
    "validate_news",
    "validate_quote",
    "validate_trade",
]
