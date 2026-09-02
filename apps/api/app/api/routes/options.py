"""Options chain API — live, Greeks-enriched chains (paper data)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.services.options_service import fetch_chain

router = APIRouter(prefix="/options", tags=["options"])


@router.get("/chain/{symbol}")
async def chain(
    symbol: str,
    expiration: datetime | None = None,
    min_dte: int = Query(default=0, ge=0, le=180),
    max_dte: int = Query(default=60, ge=0, le=365),
) -> dict:
    """Return an enriched option chain (contracts, quotes, IV, Greeks)."""
    try:
        result = await fetch_chain(
            symbol.upper(),
            expiration=expiration,
            min_dte=min_dte,
            max_dte=max_dte,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"options data unavailable: {exc}") from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"no tradeable chain for {symbol.upper()}")
    return result.model_dump(mode="json")
