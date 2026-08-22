"""Celery application (M1 ingestion).

Beat schedule is OFF by default (env-gated) so no uncontrolled loops run.
Rate limits are conservative to respect provider quotas. Paper trading
only — no order tasks exist or will exist here in M1.
"""

from __future__ import annotations

import os

from celery import Celery

broker_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "agnostix_m1",
    broker=broker_url,
    backend=broker_url,
    include=["app.workers.tasks_ingestion"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Conservative rate limits (provider courtesy).
    task_annotations={
        "app.workers.tasks_ingestion.*": {"rate_limit": "30/m"},
    },
    task_routes={
        "ingest_bars": {"queue": "market_data"},
        "ingest_quotes": {"queue": "market_data"},
        "ingest_trades": {"queue": "market_data"},
        "ingest_news": {"queue": "news"},
        "ingest_security_metadata": {"queue": "metadata"},
    },
)

# Beat schedule: opt-in only.
if os.environ.get("MARKET_INGESTION_SCHEDULE_ENABLED", "").lower() == "true":
    watchlist = os.environ.get("MARKET_WATCHLIST", "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,AMD").split(
        ","
    )
    celery_app.conf.beat_schedule = {
        f"ingest-bars-{sym.strip().lower()}": {
            "task": "ingest_bars",
            "schedule": 3600.0,
            "args": [sym.strip()],
        }
        for sym in watchlist
    } | {
        "ingest-news": {
            "task": "ingest_news",
            "schedule": 900.0,
            "args": [],
        }
    }
else:
    celery_app.conf.beat_schedule = {}
