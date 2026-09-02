"""TradingDesk — the autonomous options desk facade.

Owns the live agent, the open-strategies book, the kill switch, and the
hash-chained journal. It is broker- and persistence-agnostic: account data,
history, and the options broker are injected by the API layer, so the desk
itself has no FastAPI/DB imports and is unit-testable in isolation.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from execution.broker.options_base import OptionsBroker
from risk.engine import RiskBudget
from trading.agent import AccountSnapshot, TradingAgent
from trading.journal import TradingJournal
from trading.schemas import AgentDecision, DecisionStatus

Emitter = Callable[[str, dict[str, Any]], Awaitable[None]]
AccountGetter = Callable[[], Awaitable[AccountSnapshot]]


class TradingDesk:
    """One desk = one agent + one book + one journal. Paper only."""

    def __init__(
        self,
        *,
        options_broker: OptionsBroker,
        account_getter: AccountGetter,
        history_provider: Callable[[str], Awaitable[list[float]]],
        gateway: Any = None,
        budget: RiskBudget | None = None,
        emitter: Emitter | None = None,
        execute: bool = True,
    ) -> None:
        self._account_getter = account_getter
        self._emitter = emitter
        self._execute = execute
        self._kill_switch = False
        self._open: dict[str, AgentDecision] = {}
        self._last_decisions: list[AgentDecision] = []
        self._started_at = datetime.now(UTC)

        async def _noop(e: str, p: dict) -> None:
            return None

        self._journal = TradingJournal()
        self._agent = TradingAgent(
            gateway=gateway,
            options_broker=options_broker,
            account=AccountSnapshot(equity=0.0, cash=0.0),
            history_provider=history_provider,
            budget=budget,
            emitter=emitter or _noop,
            journal=self._journal,
            execute=execute,
        )

    # -- state --------------------------------------------------------------

    @property
    def kill_switch(self) -> bool:
        return self._kill_switch

    @property
    def journal(self) -> TradingJournal:
        return self._journal

    @property
    def started_at(self) -> datetime:
        return self._started_at

    def open_strategies(self) -> list[AgentDecision]:
        return list(self._open.values())

    def last_decisions(self, limit: int = 20) -> list[AgentDecision]:
        return self._last_decisions[-limit:]

    def trigger_kill(self) -> None:
        self._kill_switch = True
        if self._emitter:
            import asyncio

            asyncio.ensure_future(self._emitter("kill_switch", {"state": True}))

    def resume(self) -> None:
        self._kill_switch = False
        if self._emitter:
            import asyncio

            asyncio.ensure_future(self._emitter("kill_switch", {"state": False}))

    # -- account ------------------------------------------------------------

    async def _account_snapshot(self) -> AccountSnapshot:
        base = await self._account_getter()
        committed = sum(
            (d.strategy.max_loss or 0.0) for d in self._open.values() if d.strategy is not None
        )
        exposure: dict[str, float] = {}
        for d in self._open.values():
            if d.strategy is None:
                continue
            exposure[d.symbol] = exposure.get(d.symbol, 0.0) + (d.strategy.max_loss or 0.0)
        return AccountSnapshot(
            equity=base.equity,
            cash=base.cash,
            buying_power=base.buying_power,
            daily_pl=base.daily_pl,
            open_positions=len(self._open),
            defined_risk_committed=committed,
            exposure_by_underlying=exposure,
        )

    async def status(self) -> dict[str, Any]:
        account = await self._account_snapshot()
        return {
            "kill_switch": self._kill_switch,
            "started_at": self._started_at.isoformat(),
            "execute": self._execute,
            "account": {
                "equity": account.equity,
                "cash": account.cash,
                "buying_power": account.buying_power,
                "daily_pl": account.daily_pl,
                "open_positions": account.open_positions,
                "defined_risk_committed": account.defined_risk_committed,
                "exposure_by_underlying": account.exposure_by_underlying,
            },
            "open_strategies": [d.as_dict() for d in self._open.values()],
            "journal_head": self._journal.head_hash,
            "journal_verified": self._journal.verify(),
        }

    # -- decisions ----------------------------------------------------------

    async def decide(
        self,
        symbol: str,
        *,
        execute: bool | None = None,
        scenario: str | None = None,
    ) -> AgentDecision:
        if self._kill_switch:
            return AgentDecision(
                decision_id=f"d-kill-{len(self._last_decisions)}",
                symbol=symbol.upper(),
                status=DecisionStatus.ABSTAINED,
                reason="kill switch engaged",
            )
        # Refresh the account snapshot before each decision so the risk engine
        # sees live equity/cash and the current book.
        account = await self._account_snapshot()
        self._agent._account = account  # noqa: SLF001 — desk owns agent state
        decision = await self._agent.decide(symbol, execute=execute, scenario=scenario)
        self._record(decision)
        return decision

    async def run_cycle(self, symbols: list[str]) -> list[AgentDecision]:
        results: list[AgentDecision] = []
        for symbol in symbols:
            if self._kill_switch:
                break
            results.append(await self.decide(symbol))
        return results

    def _record(self, decision: AgentDecision) -> None:
        self._last_decisions.append(decision)
        if decision.status.value == "executed":
            self._open[decision.decision_id] = decision
        elif decision.status.value == "error" and decision.order_id:
            pass

    def mark_closed(self, decision_id: str) -> None:
        self._open.pop(decision_id, None)
