"""Autonomous options trading agent.

The safety architecture this module enforces:

    LLM proposes DIRECTION + THESIS (structured, bounded)
      → deterministic code builds a defined-risk strategy (strikes, size)
      → deterministic risk engine approves / refuses
      → (if approved) paper execution via the options broker
      → every decision, refusal, and order is hash-chained into the journal

An LLM never picks a strike, size, or strategy, and never touches the risk
decision. If no LLM is configured the agent abstains rather than guessing.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from execution.broker.options_base import (
    OptionOrderRequest,
    OptionsBroker,
)
from options.market import enrich_quote, realized_volatility, volatility_rank
from options.schemas import OptionChain, OptionQuote, OptionStrategy, OptionType
from options.strategies import build_strategy
from risk.engine import PortfolioState, RiskBudget, evaluate
from trading.journal import TradingJournal
from trading.schemas import AgentDecision, DecisionStatus, Signal, SignalDirection

DEFAULT_RISK_FREE_RATE = 0.04
MIN_SIGNAL_CONFIDENCE = 0.55
MIN_TRADEABLE_QUOTES = 3

Emitter = Callable[[str, dict[str, Any]], Awaitable[None]]


class SignalOutput(BaseModel):
    direction: str  # bullish | bearish | neutral | abstain
    confidence: float
    thesis: str
    catalyst: str | None = None
    invalidation: str | None = None


SIGNAL_SYSTEM_PROMPT = """You are a cautious options-trading signal analyst.

HARD RULES:
- You express ONLY a directional view and your conviction. You never choose
  strikes, quantities, leg structures, or strategies — deterministic code does.
- Default to "abstain" or "neutral" when the edge is unclear. Refusing is a
  valid and respected outcome.
- Use only the supplied market context. Do not invent prices, IV, or news.
- confidence is your conviction in the DIRECTION (0-1), NOT a probability of
  profit and NOT a bet size.
- Keep the thesis to one or two sentences and cite concrete facts from the
  context where possible.

Respond with a single JSON object matching the requested schema."""


async def _noop_emit(event_type: str, payload: dict[str, Any]) -> None:
    return None


async def _empty_history(symbol: str) -> list[float]:
    return []


@dataclass
class AccountSnapshot:
    equity: float
    cash: float
    buying_power: float = 0.0
    daily_pl: float = 0.0
    open_positions: int = 0
    defined_risk_committed: float = 0.0
    exposure_by_underlying: dict[str, float] = field(default_factory=dict)


def _now() -> datetime:
    return datetime.now(UTC)


def _to_direction(raw: str) -> SignalDirection:
    value = (raw or "").strip().lower()
    if value in ("bull", "bullish", "long"):
        return SignalDirection.BULLISH
    if value in ("bear", "bearish", "short"):
        return SignalDirection.BEARISH
    if value in ("neutral", "sideways", "range"):
        return SignalDirection.NEUTRAL
    return SignalDirection.ABSTAIN


def select_expiration(contracts, min_dte: int, max_dte: int) -> datetime | None:
    """Pick the nearest expiry within [min_dte, max_dte] days from now."""
    now = _now()
    candidates: list[datetime] = []
    seen: set[str] = set()
    for c in contracts:
        dte = (c.expiration - now).days
        if min_dte <= dte <= max_dte:
            key = c.expiration.isoformat()
            if key not in seen:
                seen.add(key)
                candidates.append(c.expiration)
    if not candidates:
        return None
    return sorted(candidates)[0]


def scale_strategy(strategy: OptionStrategy, quantity: int) -> OptionStrategy:
    """Scale a qty=1 strategy to `quantity` contracts, preserving ratios."""
    if quantity == 1:
        return strategy
    return strategy.model_copy(
        update={
            "legs": [leg.model_copy(update={"quantity": quantity}) for leg in strategy.legs],
            "max_loss": (strategy.max_loss or 0.0) * quantity,
            "max_profit": (strategy.max_profit or 0.0) * quantity,
            "net_credit": (strategy.net_credit or 0.0) * quantity,
        }
    )


class TradingAgent:
    """The autonomous loop. Paper execution only."""

    def __init__(
        self,
        *,
        gateway: Any = None,
        options_broker: OptionsBroker,
        account: AccountSnapshot,
        history_provider: Callable[[str], Awaitable[list[float]]] | None = None,
        budget: RiskBudget | None = None,
        emitter: Emitter | None = None,
        journal: TradingJournal | None = None,
        risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
        min_confidence: float = MIN_SIGNAL_CONFIDENCE,
        min_dte: int = 7,
        max_dte: int = 45,
        execute: bool = True,
        max_contracts: int = 10,
    ) -> None:
        self._gateway = gateway
        self._broker = options_broker
        self._account = account
        self._history = history_provider or _empty_history
        self._budget = budget or RiskBudget()
        self._emitter = emitter or _noop_emit
        self._journal = journal or TradingJournal()
        self._rate = risk_free_rate
        self._min_confidence = min_confidence
        self._min_dte = min_dte
        self._max_dte = max_dte
        self._execute = execute
        self._max_contracts = max_contracts

    @property
    def journal(self) -> TradingJournal:
        return self._journal

    # -- market context -----------------------------------------------------

    async def _market_context(self, symbol: str) -> dict[str, Any]:
        spot = await self._broker.get_underlying_price(symbol)
        history = await self._history(symbol)
        if spot is None and history:
            spot = history[-1]
        rv = realized_volatility(history)
        vrank = volatility_rank(rv, history)
        contracts = await self._broker.get_option_contracts(
            symbol, min_dte=self._min_dte, max_dte=self._max_dte
        )
        expiration = select_expiration(contracts, self._min_dte, self._max_dte)
        chain = await self._build_chain(symbol, spot, contracts, expiration)
        return {
            "spot": spot,
            "realized_vol": rv,
            "vol_rank": vrank,
            "expiration": expiration,
            "chain": chain,
            "history": history,
        }

    async def _build_chain(
        self,
        symbol: str,
        spot: float | None,
        contracts,
        expiration: datetime | None,
    ) -> OptionChain | None:
        if expiration is None or spot is None:
            return None
        selected = [c for c in contracts if c.expiration == expiration]
        calls_syms = [c.symbol for c in selected if c.option_type == OptionType.CALL]
        puts_syms = [c.symbol for c in selected if c.option_type == OptionType.PUT]
        raw_quotes = await self._broker.get_option_quotes(calls_syms + puts_syms)
        calls: list[OptionQuote] = []
        puts: list[OptionQuote] = []
        for c in selected:
            q = raw_quotes.get(c.symbol)
            if q is None:
                continue
            q = enrich_quote(q, spot, c.strike, c.expiration, c.option_type, rate=self._rate)
            if c.option_type == OptionType.CALL:
                calls.append(q)
            else:
                puts.append(q)
        if len(calls) + len(puts) < MIN_TRADEABLE_QUOTES:
            return None
        return OptionChain(
            underlying=symbol,
            underlying_price=spot,
            expiration=expiration,
            calls=calls,
            puts=puts,
        )

    # -- signal -------------------------------------------------------------

    async def _signal(
        self, symbol: str, ctx: dict[str, Any], scenario: str | None = None
    ) -> Signal | None:
        if self._gateway is None:
            await self._emitter("signal_skipped", {"symbol": symbol, "reason": "no LLM configured"})
            return None
        chain = ctx.get("chain")
        chain_summary = (
            {
                "underlying_price": chain.underlying_price,
                "expiration": chain.expiration.isoformat(),
                "n_calls": len(chain.calls),
                "n_puts": len(chain.puts),
                "atm_iv_puts": [
                    round(q.implied_volatility, 4) for q in chain.puts[:5] if q.implied_volatility
                ],
            }
            if chain
            else None
        )
        context_text = {
            "symbol": symbol.upper(),
            "underlying_price": ctx.get("spot"),
            "realized_volatility_30d": round(ctx["realized_vol"], 4)
            if ctx.get("realized_vol")
            else None,
            "vol_rank": round(ctx["vol_rank"], 3) if ctx.get("vol_rank") is not None else None,
            "option_chain_summary": chain_summary,
            "recent_closes": [round(c, 2) for c in ctx.get("history", [])[-10:]],
            "user_injected_scenario": scenario,
        }
        import json as _json

        try:
            response = await self._gateway.run(
                task="options_signal",
                model_class="reasoning",
                messages=[
                    {"role": "system", "content": SIGNAL_SYSTEM_PROMPT},
                    {"role": "user", "content": _json.dumps(context_text, default=str)},
                ],
                caller_agent_id="options_signal_agent",
                prompt_version="options-signal-v1",
                temperature=0.2,
                response_schema=SignalOutput.model_json_schema(),
            )
        except Exception as exc:  # noqa: BLE001 — LLM failure → abstain, never guess
            await self._emitter("signal_failed", {"symbol": symbol, "error": repr(exc)[:300]})
            return None

        structured = (
            response.get("structured")
            if isinstance(response, dict)
            else getattr(response, "structured", None)
        )
        content = (
            response.get("content")
            if isinstance(response, dict)
            else getattr(response, "content", None)
        )
        payload = structured if isinstance(structured, dict) else _parse_json(content)
        if payload is None:
            await self._emitter(
                "signal_failed", {"symbol": symbol, "error": "unparseable model output"}
            )
            return None
        try:
            out = SignalOutput.model_validate(payload)
        except Exception:  # noqa: BLE001
            await self._emitter("signal_failed", {"symbol": symbol, "error": "schema violation"})
            return None

        provider = (
            response.get("provider")
            if isinstance(response, dict)
            else getattr(response, "provider", "unknown")
        )
        model = (
            response.get("model")
            if isinstance(response, dict)
            else getattr(response, "model", "unknown")
        )
        return Signal(
            symbol=symbol.upper(),
            direction=_to_direction(out.direction),
            confidence=out.confidence,
            thesis=out.thesis,
            catalyst=out.catalyst,
            invalidation=out.invalidation,
            model=str(model),
            provider=str(provider),
        )

    # -- decision -----------------------------------------------------------

    async def decide(
        self,
        symbol: str,
        *,
        execute: bool | None = None,
        scenario: str | None = None,
    ) -> AgentDecision:
        decision_id = f"d-{uuid.uuid4().hex[:12]}"
        should_execute = self._execute if execute is None else execute
        base: dict[str, Any] = {
            "decision_id": decision_id,
            "symbol": symbol.upper(),
        }
        await self._emitter("agent_analyzing", {**base, "symbol": symbol.upper()})

        try:
            ctx = await self._market_context(symbol)
        except Exception as exc:  # noqa: BLE001
            decision = AgentDecision(
                **base, status=DecisionStatus.ERROR, reason=f"market context: {exc!r}"[:500]
            )
            self._journal.append("error", symbol, {"reason": repr(exc)[:500]})
            await self._emitter("agent_error", {**base, "reason": repr(exc)[:300]})
            return decision

        await self._emitter(
            "market_ready",
            {
                **base,
                "spot": ctx.get("spot"),
                "realized_vol": ctx.get("realized_vol"),
                "vol_rank": ctx.get("vol_rank"),
            },
        )

        signal = await self._signal(symbol, ctx, scenario=scenario)

        decision = AgentDecision(
            **base,
            signal=signal,
            market_price=ctx.get("spot"),
            iv_rank=ctx.get("vol_rank"),
        )

        if signal is None or signal.direction == SignalDirection.ABSTAIN:
            decision.status = DecisionStatus.ABSTAINED
            decision.reason = "abstained: no signal" if signal is None else "abstained: no edge"
            self._journal.append("abstain", symbol, {"reason": decision.reason})
            await self._emitter("agent_abstained", {**base, "reason": decision.reason})
            return decision

        if signal.confidence < self._min_confidence:
            decision.status = DecisionStatus.ABSTAINED
            decision.reason = (
                f"confidence {signal.confidence:.2f} below threshold {self._min_confidence:.2f}"
            )
            self._journal.append(
                "abstain", symbol, {"reason": decision.reason, "confidence": signal.confidence}
            )
            await self._emitter("agent_abstained", {**base, "reason": decision.reason})
            return decision

        chain = ctx.get("chain")
        if chain is None or ctx.get("spot") is None:
            decision.status = DecisionStatus.ABSTAINED
            decision.reason = "no tradeable option chain or underlying price"
            self._journal.append("abstain", symbol, {"reason": decision.reason})
            await self._emitter("agent_abstained", {**base, "reason": decision.reason})
            return decision

        strategy = build_strategy(
            signal.direction.value,
            symbol.upper(),
            ctx["spot"],
            chain.expiration,
            chain.calls,
            chain.puts,
        )
        if strategy is None:
            decision.status = DecisionStatus.ABSTAINED
            decision.reason = "strategy builder could not construct a defined-risk trade"
            self._journal.append("abstain", symbol, {"reason": decision.reason})
            await self._emitter("agent_abstained", {**base, "reason": decision.reason})
            return decision
        decision.strategy = strategy

        # Deterministic sizing: max contracts such that per-trade loss ≤ budget.
        limit = self._budget.max_loss_per_trade_pct * max(self._account.equity, 1.0)
        max_qty = int(limit / (strategy.max_loss or 0.0)) if strategy.max_loss else 0
        quantity = max(1, min(max_qty, self._max_contracts))
        if max_qty < 1:
            quantity = 1
        strategy = scale_strategy(strategy, quantity)
        decision.strategy = strategy

        await self._emitter(
            "strategy_built", {**base, "strategy": strategy.model_dump(mode="json")}
        )

        portfolio = PortfolioState(
            equity=self._account.equity,
            cash=self._account.cash,
            daily_pl=self._account.daily_pl,
            open_positions=self._account.open_positions,
            defined_risk_committed=self._account.defined_risk_committed,
            exposure_by_underlying=self._account.exposure_by_underlying,
        )
        risk = evaluate(strategy, portfolio, self._budget, iv_rank=ctx.get("vol_rank"))
        decision.risk = risk
        await self._emitter("risk_evaluated", {**base, "risk": risk.as_dict()})

        if not risk.passed:
            decision.status = DecisionStatus.REFUSED
            decision.reason = f"risk gates: {[g.gate.value for g in risk.gates if not g.passed]}"
            # Publish every refusal with full gate detail (the differentiator).
            self._journal.append(
                "refusal",
                symbol,
                {"risk": risk.as_dict(), "signal": signal.model_dump(mode="json")},
            )
            await self._emitter(
                "agent_refused", {**base, "reason": decision.reason, "risk": risk.as_dict()}
            )
            return decision

        if not should_execute:
            decision.status = DecisionStatus.ABSTAINED
            decision.reason = "risk-approved but execution disabled (paper/dry-run)"
            self._journal.append(
                "dry_run",
                symbol,
                {"strategy": strategy.model_dump(mode="json"), "risk": risk.as_dict()},
            )
            await self._emitter("agent_dry_run", {**base, "reason": decision.reason})
            return decision

        order = OptionOrderRequest(
            strategy_id=strategy.strategy_id,
            underlying=symbol.upper(),
            legs=[leg.contract for leg in strategy.legs],
            sides=[leg.side for leg in strategy.legs],
            quantities=[leg.quantity for leg in strategy.legs],
            mleg=len(strategy.legs) > 1,
            client_order_id=f"agnostix-{decision_id}",
        )
        try:
            result = await self._broker.submit_option_order(order)
        except Exception as exc:  # noqa: BLE001
            decision.status = DecisionStatus.ERROR
            decision.reason = f"order rejected: {exc!r}"[:500]
            self._journal.append("error", symbol, {"reason": repr(exc)[:500]})
            await self._emitter("order_failed", {**base, "reason": repr(exc)[:300]})
            return decision

        decision.status = DecisionStatus.EXECUTED
        decision.order_id = result.order_id
        self._journal.append(
            "execution",
            symbol,
            {
                "order_id": result.order_id,
                "status": result.status,
                "strategy": strategy.model_dump(mode="json"),
            },
        )
        await self._emitter(
            "agent_executed", {**base, "order_id": result.order_id, "status": result.status}
        )
        return decision

    # -- cycle --------------------------------------------------------------

    async def run_cycle(self, symbols: list[str]) -> list[AgentDecision]:
        """Run one full decision pass over the watchlist."""
        decisions: list[AgentDecision] = []
        for symbol in symbols:
            decision = await self.decide(symbol)
            decisions.append(decision)
        return decisions


def _parse_json(text: str | None) -> dict | None:
    if not text:
        return None
    import json

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None
