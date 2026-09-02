"""Trading service — wires the TradingDesk to Alpaca, DB, and WebSocket.

This module owns the process-wide desk singleton and adapts the real Alpaca
adapters into the desk's injected dependencies (account getter, history
provider, options broker). It also persists hash-chained journal entries to
Postgres and broadcasts live agent events over the existing WebSocket hub.

Graceful degradation: if Alpaca credentials are absent the desk is not built
and callers receive a clear "not configured" signal — the platform stays
operational (research still works) but never fabricates a paper account.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from execution.broker.alpaca import AlpacaBroker, AlpacaMarketDataProvider, BrokerNotConfiguredError
from execution.broker.alpaca_options import AlpacaOptionsBroker
from trading.agent import AccountSnapshot
from trading.desk import TradingDesk

_desk: TradingDesk | None = None
_desk_error: str | None = None
_last_persisted_seq: int = -1


def _gateway() -> Any:
    from model_gateway.gateway import ModelGateway

    return ModelGateway.from_settings()


async def _account_getter() -> AccountSnapshot:
    broker = AlpacaBroker()
    info = await broker.get_account()
    last_equity = info.raw.get("last_equity")
    daily_pl = (info.equity - last_equity) if last_equity is not None else 0.0
    return AccountSnapshot(
        equity=info.equity,
        cash=info.cash,
        buying_power=info.buying_power,
        daily_pl=float(daily_pl),
    )


async def _history_provider(symbol: str) -> list[float]:
    provider = AlpacaMarketDataProvider()
    bars = await provider.get_bars(symbol, "1Day", limit=365)
    return [b.close for b in bars if b.close is not None]


def _build_desk(*, execute: bool = True) -> TradingDesk:
    options_broker = AlpacaOptionsBroker()

    async def emitter(event_type: str, payload: dict[str, Any]) -> None:
        from app.api.routes.ws import manager
        from app.schemas.contracts import WSMessage

        msg_type = _ws_type(event_type)
        await manager.broadcast(WSMessage(type=msg_type, payload={"event": event_type, **payload}))

    return TradingDesk(
        options_broker=options_broker,
        account_getter=_account_getter,
        history_provider=_history_provider,
        gateway=_gateway(),
        emitter=emitter,
        execute=execute,
    )


def _ws_type(event_type: str):
    from app.schemas.contracts import WSMessageType

    if event_type in ("agent_executed", "order_failed"):
        return WSMessageType.ORDER_UPDATE
    if event_type == "kill_switch":
        return WSMessageType.KILL_SWITCH
    if event_type in ("agent_refused", "agent_abstained", "strategy_built"):
        return WSMessageType.NEW_PROPOSAL
    return WSMessageType.HEARTBEAT


def get_desk(*, execute: bool = True) -> TradingDesk:
    """Return the process-wide desk, building it on first use.

    Raises BrokerNotConfiguredError if Alpaca credentials are missing.
    """
    global _desk, _desk_error
    if _desk is None and _desk_error is None:
        try:
            _desk = _build_desk(execute=execute)
        except BrokerNotConfiguredError as exc:
            _desk_error = str(exc)
            raise
    if _desk is None:
        raise BrokerNotConfiguredError(_desk_error or "trading desk unavailable")
    return _desk


def desk_ready() -> bool:
    return _desk is not None


async def sync_journal(session) -> int:
    """Persist any not-yet-persisted journal entries to trading_journal.

    Returns the number of entries written. Idempotent across calls.
    """
    global _last_persisted_seq
    if _desk is None:
        return 0
    from app.db.models import TradingJournalEntry

    entries = _desk.journal.entries
    new = [e for e in entries if e.seq > _last_persisted_seq]
    for e in new:
        session.add(
            TradingJournalEntry(
                seq=e.seq,
                kind=e.kind,
                symbol=e.symbol,
                payload=e.payload,
                prev_hash=e.prev_hash,
                hash=e.hash,
            )
        )
    if new:
        await session.commit()
        _last_persisted_seq = new[-1].seq
    return len(new)


def reset_desk_for_tests() -> None:
    global _desk, _desk_error, _last_persisted_seq
    _desk = None
    _desk_error = None
    _last_persisted_seq = -1


def build_playground_agent(emitter, *, execute: bool = True):
    """Build a standalone TradingAgent for the interactive playground.

    Uses the real Alpaca adapters but a caller-supplied emitter so events
    can be streamed per-request (SSE) instead of broadcast over WebSocket.
    """
    from trading.agent import TradingAgent

    agent = TradingAgent(
        gateway=_gateway(),
        options_broker=AlpacaOptionsBroker(),
        account=AccountSnapshot(equity=100_000.0, cash=100_000.0, buying_power=200_000.0),
        history_provider=_history_provider,
        emitter=emitter,
        execute=execute,
    )

    async def refresh_account() -> None:
        agent._account = await _account_getter()  # noqa: SLF001

    return agent, refresh_account


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
