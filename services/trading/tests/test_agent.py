"""End-to-end tests for the trading agent with a fake broker + gateway."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from execution.broker.options_base import (
    OptionOrderRequest,
    OptionOrderStatus,
    OptionsBroker,
)
from options.schemas import OptionContract, OptionQuote, OptionType
from trading.agent import AccountSnapshot, TradingAgent
from trading.schemas import DecisionStatus


class FakeOptionsBroker(OptionsBroker):
    name = "fake_options"

    def __init__(self, *, spot: float = 100.0) -> None:
        self._spot = spot
        self.orders: list[OptionOrderRequest] = []
        self._expiry = datetime.now(UTC) + timedelta(days=30)

    async def get_option_contracts(self, underlying, *, expiration=None, min_dte=0, max_dte=60):
        contracts = []
        for strike in [95.0, 97.0, 100.0, 102.0, 105.0]:
            contracts.append(
                OptionContract(
                    symbol=f"{underlying}P{strike:.0f}",
                    underlying=underlying,
                    option_type=OptionType.PUT,
                    strike=strike,
                    expiration=self._expiry,
                )
            )
        for strike in [100.0, 102.0, 105.0]:
            contracts.append(
                OptionContract(
                    symbol=f"{underlying}C{strike:.0f}",
                    underlying=underlying,
                    option_type=OptionType.CALL,
                    strike=strike,
                    expiration=self._expiry,
                )
            )
        return contracts

    async def get_option_quotes(self, symbols):
        out = {}
        for s in symbols:
            out[s] = OptionQuote(symbol=s, strike=_strike_from(s), bid=1.0, ask=1.2)
        return out

    async def submit_option_order(self, request):
        self.orders.append(request)
        return OptionOrderStatus(order_id="o-123", status="accepted")

    async def close_option_position(self, symbol, qty):
        return OptionOrderStatus(order_id="o-close", status="accepted")

    async def get_underlying_price(self, symbol):
        return self._spot


def _strike_from(symbol: str) -> float:
    num = ""
    for ch in reversed(symbol):
        if ch.isdigit():
            num = ch + num
        elif num:
            break
    return float(num) if num else 0.0


class FakeGateway:
    def __init__(self, direction: str = "bullish", confidence: float = 0.7) -> None:
        self._direction = direction
        self._confidence = confidence

    async def run(self, **kwargs):
        return {
            "structured": {
                "direction": self._direction,
                "confidence": self._confidence,
                "thesis": "fake thesis",
                "catalyst": None,
                "invalidation": None,
            },
            "provider": "fake",
            "model": "fake-model",
            "content": None,
        }


def _closes(n: int = 200, start: float = 100.0) -> list[float]:
    import random

    rng = random.Random(42)
    out = [start]
    for _ in range(n):
        out.append(out[-1] * (1 + rng.gauss(0, 0.01)))
    return out


def _account(**kw) -> AccountSnapshot:
    return AccountSnapshot(equity=100_000.0, cash=100_000.0, buying_power=200_000.0, **kw)


def _make_agent(direction="bullish", confidence=0.7, execute=True):
    broker = FakeOptionsBroker()
    agent = TradingAgent(
        gateway=FakeGateway(direction, confidence),
        options_broker=broker,
        account=_account(),
        history_provider=lambda s: _async_closes(),
        execute=execute,
    )
    return agent, broker


async def _async_closes() -> list[float]:
    return _closes()


@pytest.mark.asyncio
async def test_executes_approved_trade():
    agent, broker = _make_agent("bullish", 0.8)
    decision = await agent.decide("AAPL")
    assert decision.status == DecisionStatus.EXECUTED
    assert decision.order_id is not None
    assert broker.orders
    assert agent.journal.verify()


@pytest.mark.asyncio
async def test_abstains_on_low_confidence():
    agent, _ = _make_agent("bullish", 0.3)
    decision = await agent.decide("AAPL")
    assert decision.status == DecisionStatus.ABSTAINED
    assert agent.journal.verify()


@pytest.mark.asyncio
async def test_abstains_on_abstain_signal():
    agent, _ = _make_agent("abstain", 0.8)
    decision = await agent.decide("AAPL")
    assert decision.status == DecisionStatus.ABSTAINED
    assert agent.journal.verify()


@pytest.mark.asyncio
async def test_dry_run_does_not_execute():
    agent, broker = _make_agent("bullish", 0.8, execute=False)
    decision = await agent.decide("AAPL")
    assert decision.status == DecisionStatus.ABSTAINED
    assert decision.reason and "dry-run" in decision.reason
    assert not broker.orders


@pytest.mark.asyncio
async def test_no_gateway_abstains():
    broker = FakeOptionsBroker()
    agent = TradingAgent(
        gateway=None,
        options_broker=broker,
        account=_account(),
        history_provider=lambda s: _async_closes(),
    )
    decision = await agent.decide("AAPL")
    assert decision.status == DecisionStatus.ABSTAINED
