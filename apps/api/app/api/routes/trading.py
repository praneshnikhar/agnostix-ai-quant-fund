"""Trading desk API — account, decisions, journal, kill switch (paper only)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services import trading_service

router = APIRouter(prefix="/trading", tags=["trading"])


class DecideRequest(BaseModel):
    symbol: str
    execute: bool | None = None


class RunRequest(BaseModel):
    symbols: list[str]


class SnapshotRequest(BaseModel):
    equity: float | None = None


def _desk():
    try:
        return trading_service.get_desk()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"trading desk unavailable: {exc}") from exc


@router.get("/status")
async def status() -> dict:
    desk = _desk()
    return await desk.status()


@router.post("/decide")
async def decide(req: DecideRequest, session: AsyncSession = Depends(get_session)) -> dict:
    desk = _desk()
    decision = await desk.decide(req.symbol.upper(), execute=req.execute)
    await trading_service.sync_journal(session)
    return decision.as_dict()


@router.post("/run")
async def run(req: RunRequest, session: AsyncSession = Depends(get_session)) -> dict:
    desk = _desk()
    decisions = await desk.run_cycle([s.upper() for s in req.symbols])
    await trading_service.sync_journal(session)
    return {"decisions": [d.as_dict() for d in decisions]}


@router.post("/kill")
async def kill() -> dict:
    desk = _desk()
    desk.trigger_kill()
    return {"kill_switch": True}


@router.post("/resume")
async def resume() -> dict:
    desk = _desk()
    desk.resume()
    return {"kill_switch": False}


@router.get("/journal")
async def journal(
    limit: int = 200,
    session: AsyncSession = Depends(get_session),
) -> dict:
    from sqlalchemy import select

    from app.db.models import TradingJournalEntry

    stmt = select(TradingJournalEntry).order_by(TradingJournalEntry.seq.desc()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    entries: list[dict[str, Any]] = [
        {
            "seq": r.seq,
            "timestamp": r.timestamp.isoformat(),
            "kind": r.kind,
            "symbol": r.symbol,
            "payload": r.payload,
            "prev_hash": r.prev_hash,
            "hash": r.hash,
        }
        for r in rows
    ]
    # Recompute chain integrity from the persisted rows (oldest → newest).
    ordered = sorted(entries, key=lambda e: int(e["seq"]))
    verified = _verify_chain(ordered)
    return {"verified": verified, "count": len(entries), "entries": entries}


def _verify_chain(entries: list[dict]) -> bool:
    import hashlib
    import json

    prev = "0" * 64
    for e in entries:
        if e["prev_hash"] != prev:
            return False
        body = {
            "seq": e["seq"],
            "kind": e["kind"],
            "symbol": e["symbol"],
            "payload": e["payload"],
            "ts": e["timestamp"],
        }
        canonical = json.dumps(body, sort_keys=True, default=str, separators=(",", ":"))
        digest = hashlib.sha256((prev + canonical).encode("utf-8")).hexdigest()
        if digest != e["hash"]:
            return False
        prev = e["hash"]
    return True


@router.get("/equity")
async def equity(session: AsyncSession = Depends(get_session)) -> list[dict]:
    from sqlalchemy import select

    from app.db.models import PortfolioSnapshot

    stmt = select(PortfolioSnapshot).order_by(PortfolioSnapshot.timestamp.asc()).limit(500)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "timestamp": r.timestamp.isoformat(),
            "equity": float(r.equity),
            "cash": float(r.cash),
            "daily_pl": float(r.daily_pl) if r.daily_pl is not None else None,
        }
        for r in rows
    ]


@router.post("/snapshot")
async def snapshot(session: AsyncSession = Depends(get_session)) -> dict:
    desk = _desk()
    status = await desk.status()
    from app.db.models import PortfolioSnapshot

    account = status["account"]
    row = PortfolioSnapshot(
        equity=account["equity"], cash=account["cash"], daily_pl=account["daily_pl"]
    )
    session.add(row)
    await session.commit()
    return {"recorded": True, "equity": account["equity"], "daily_pl": account["daily_pl"]}
