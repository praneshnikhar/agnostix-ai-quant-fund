"""Options chain service — fetch and deterministically enrich a live chain."""

from __future__ import annotations

from datetime import datetime

from execution.broker.alpaca_options import AlpacaOptionsBroker
from options.market import enrich_quote
from options.schemas import OptionChain, OptionQuote, OptionType
from trading.agent import select_expiration


async def fetch_chain(
    symbol: str,
    *,
    expiration: datetime | None = None,
    min_dte: int = 0,
    max_dte: int = 60,
) -> OptionChain | None:
    """Fetch + enrich a live option chain for one underlying."""
    broker = AlpacaOptionsBroker()
    spot = await broker.get_underlying_price(symbol)
    if spot is None:
        return None
    contracts = await broker.get_option_contracts(symbol)
    if not contracts:
        return None

    if expiration is None:
        expiration = select_expiration(contracts, min_dte, max_dte)
    if expiration is None:
        return None

    selected = [c for c in contracts if c.expiration == expiration]
    symbols = [c.symbol for c in selected]
    raw_quotes = await broker.get_option_quotes(symbols)

    calls: list[OptionQuote] = []
    puts: list[OptionQuote] = []
    for c in selected:
        q = raw_quotes.get(c.symbol)
        if q is None:
            continue
        q = enrich_quote(q, spot, c.strike, c.expiration, c.option_type)
        if c.option_type == OptionType.CALL:
            calls.append(q)
        else:
            puts.append(q)

    return OptionChain(
        underlying=symbol.upper(),
        underlying_price=spot,
        expiration=expiration,
        calls=calls,
        puts=puts,
    )
