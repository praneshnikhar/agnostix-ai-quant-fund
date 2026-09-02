"""Interactive playground API — "challenge the agent" with live streaming.

POST /playground/challenge streams the agent's full decision process over
SSE: market context, LLM signal, deterministic strategy, every risk gate,
and the final verdict — all live, so a judge can watch the agent think.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services import trading_service

router = APIRouter(prefix="/playground", tags=["playground"])


class ChallengeRequest(BaseModel):
    symbol: str
    scenario: str | None = None
    execute: bool = False  # playground is dry-run by default; never real orders


@router.post("/challenge")
async def challenge(req: ChallengeRequest) -> StreamingResponse:
    queue: asyncio.Queue = asyncio.Queue()

    async def emitter(event_type: str, payload: dict) -> None:
        await queue.put({"type": event_type, "payload": payload})

    try:
        agent, refresh_account = trading_service.build_playground_agent(
            emitter, execute=req.execute
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"agent unavailable: {exc}") from exc

    async def run() -> None:
        try:
            await refresh_account()
            decision = await agent.decide(req.symbol.upper(), scenario=req.scenario)
            await queue.put({"type": "decision", "payload": decision.as_dict()})
        except Exception as exc:  # noqa: BLE001
            await queue.put({"type": "error", "payload": {"reason": repr(exc)[:500]}})
        finally:
            await queue.put(None)  # sentinel

    task = asyncio.create_task(run())

    async def stream():
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item, default=str)}\n\n"
        await task

    return StreamingResponse(stream(), media_type="text/event-stream")
