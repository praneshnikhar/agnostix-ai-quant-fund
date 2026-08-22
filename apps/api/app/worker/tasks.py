"""Celery task definitions (M0).

Only the connectivity-proving `ping` task exists. Milestone-specific
workers (market data, news, research, signals, backtest, evaluation,
execution, portfolio) are added in later milestones.
"""

from __future__ import annotations

from app.worker.celery_app import celery_app


@celery_app.task(name="ping")
def ping() -> dict[str, str]:
    """Round-trip proof that broker + backend (Redis) are operational."""
    return {"status": "pong"}
