"""Deterministic options risk engine.

The ONE place a trade is allowed or refused. Every gate is pure math — an
LLM never participates in risk decisions (design principle #3). The engine
takes a proposed `OptionStrategy`, current portfolio state, and a risk
budget, and returns an ordered list of gate checks plus a final verdict.

Verdict semantics:
    APPROVE  — all gates passed, strategy may execute (subject to sizing below)
    REFUSE   — a hard gate failed; the strategy must NOT execute
    REDUCE   — strategy would be acceptable at a smaller size; caller may
               re-submit with a reduced quantity

This module is dependency-free and fully unit-testable with a fake
portfolio state — no broker, no DB, no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from options.schemas import OptionStrategy


class GateVerdict(StrEnum):
    APPROVE = "approve"
    REFUSE = "refuse"
    REDUCE = "reduce"


class Gate(StrEnum):
    DEFINED_RISK = "defined_risk"
    MAX_LOSS_PER_TRADE = "max_loss_per_trade"
    MAX_LOSS_TOTAL = "max_loss_total"
    CONCENTRATION = "concentration"
    IV_RANK_BAND = "iv_rank_band"
    DTE_WINDOW = "dte_window"
    PROBABILITY_OF_PROFIT = "probability_of_profit"
    DAILY_LOSS_CIRCUIT_BREAKER = "daily_loss_circuit_breaker"
    OPEN_POSITIONS_LIMIT = "open_positions_limit"
    CASH_COLLATERAL = "cash_collateral"


@dataclass
class GateResult:
    gate: Gate
    passed: bool
    hard: bool  # hard gates REFUSE the trade; soft gates only REDUCE/warn
    limit: float | None = None
    actual: float | None = None
    detail: str | None = None

    def as_dict(self) -> dict:
        return {
            "gate": self.gate.value,
            "passed": self.passed,
            "hard": self.hard,
            "limit": self.limit,
            "actual": self.actual,
            "detail": self.detail,
        }


@dataclass
class RiskResult:
    verdict: GateVerdict
    gates: list[GateResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.verdict != GateVerdict.REFUSE

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "gates": [g.as_dict() for g in self.gates],
        }


@dataclass
class RiskBudget:
    """Tunable risk parameters (one config for the whole desk)."""

    max_loss_per_trade_pct: float = 0.02  # 2% of equity per trade
    max_total_defined_risk_pct: float = 0.25  # 25% of equity in defined risk
    max_concentration_pct: float = 0.10  # 10% of equity per underlying
    min_iv_rank: float = 0.20  # only sell premium when IV rank ≥ 20
    max_iv_rank: float = 0.95
    min_dte: int = 7
    max_dte: int = 45
    min_probability_of_profit: float = 0.60
    daily_loss_limit_pct: float = 0.03  # circuit breaker at 3% daily loss
    max_open_positions: int = 10


@dataclass
class PortfolioState:
    """The subset of portfolio state risk decisions need (broker-agnostic)."""

    equity: float
    cash: float
    daily_pl: float = 0.0
    open_positions: int = 0
    defined_risk_committed: float = 0.0  # sum of open max_loss across book
    exposure_by_underlying: dict[str, float] = field(default_factory=dict)


def _clamp(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


def evaluate(
    strategy: OptionStrategy,
    portfolio: PortfolioState,
    budget: RiskBudget,
    *,
    iv_rank: float | None = None,
) -> RiskResult:
    """Run every gate against a proposed strategy. Pure and deterministic."""
    gates: list[GateResult] = []
    equity = max(portfolio.equity, 1e-6)

    # 1. Defined risk — a strategy without a finite max loss is refused, hard.
    if not strategy.defined_risk:
        gates.append(
            GateResult(
                Gate.DEFINED_RISK, passed=False, hard=True, detail="strategy has no finite max_loss"
            )
        )
        return RiskResult(GateVerdict.REFUSE, gates)
    gates.append(GateResult(Gate.DEFINED_RISK, passed=True, hard=True, actual=strategy.max_loss))

    max_loss = strategy.max_loss or 0.0

    # 2. Max loss per trade.
    limit = budget.max_loss_per_trade_pct * equity
    ok = max_loss <= limit
    gates.append(
        GateResult(
            Gate.MAX_LOSS_PER_TRADE,
            ok,
            hard=True,
            limit=limit,
            actual=max_loss,
            detail=f"max_loss ${max_loss:,.0f} vs ${limit:,.0f} limit",
        )
    )

    # 3. Max total defined risk across the book.
    total_after = portfolio.defined_risk_committed + max_loss
    total_limit = budget.max_total_defined_risk_pct * equity
    ok_total = total_after <= total_limit
    gates.append(
        GateResult(
            Gate.MAX_LOSS_TOTAL,
            ok_total,
            hard=True,
            limit=total_limit,
            actual=total_after,
            detail=f"committed ${total_after:,.0f} vs ${total_limit:,.0f}",
        )
    )

    # 4. Concentration per underlying.
    current = portfolio.exposure_by_underlying.get(strategy.underlying, 0.0)
    conc_limit = budget.max_concentration_pct * equity
    conc_after = current + max_loss
    ok_conc = conc_after <= conc_limit
    gates.append(
        GateResult(
            Gate.CONCENTRATION,
            ok_conc,
            hard=True,
            limit=conc_limit,
            actual=conc_after,
            detail=f"{strategy.underlying} risk ${conc_after:,.0f} vs ${conc_limit:,.0f}",
        )
    )

    # 5. IV rank band (soft: out-of-band only reduces, it doesn't refuse).
    if iv_rank is None:
        gates.append(
            GateResult(
                Gate.IV_RANK_BAND,
                passed=True,
                hard=False,
                detail="iv_rank unavailable — treated as pass",
            )
        )
    else:
        ok_iv = budget.min_iv_rank <= iv_rank <= budget.max_iv_rank
        gates.append(
            GateResult(
                Gate.IV_RANK_BAND,
                ok_iv,
                hard=False,
                limit=budget.min_iv_rank,
                actual=iv_rank,
                detail=(
                    f"iv_rank {iv_rank:.2f} vs "
                    f"[{budget.min_iv_rank:.2f}, {budget.max_iv_rank:.2f}]"
                ),
            )
        )

    # 6. DTE window (hard).
    dte = strategy.days_to_expiration
    if dte is None:
        ok_dte = True
    else:
        ok_dte = budget.min_dte <= dte <= budget.max_dte
    gates.append(
        GateResult(
            Gate.DTE_WINDOW,
            ok_dte,
            hard=True,
            limit=budget.min_dte,
            actual=dte,
            detail=f"dte {dte} vs [{budget.min_dte}, {budget.max_dte}]",
        )
    )

    # 7. Probability of profit floor (soft).
    pop = strategy.probability_of_profit
    if pop is None:
        ok_pop = True
    else:
        ok_pop = pop >= budget.min_probability_of_profit
    gates.append(
        GateResult(
            Gate.PROBABILITY_OF_PROFIT,
            ok_pop,
            hard=False,
            limit=budget.min_probability_of_profit,
            actual=pop,
            detail=f"PoP {pop} vs {budget.min_probability_of_profit}",
        )
    )

    # 8. Daily loss circuit breaker (hard — halts the whole desk).
    daily_limit = budget.daily_loss_limit_pct * equity
    breaker_ok = portfolio.daily_pl > -daily_limit
    gates.append(
        GateResult(
            Gate.DAILY_LOSS_CIRCUIT_BREAKER,
            breaker_ok,
            hard=True,
            limit=daily_limit,
            actual=portfolio.daily_pl,
            detail=f"daily P&L ${portfolio.daily_pl:,.0f} vs ${-daily_limit:,.0f} floor",
        )
    )

    # 9. Open positions limit.
    ok_open = portfolio.open_positions < budget.max_open_positions
    gates.append(
        GateResult(
            Gate.OPEN_POSITIONS_LIMIT,
            ok_open,
            hard=True,
            limit=budget.max_open_positions,
            actual=portfolio.open_positions,
            detail=f"{portfolio.open_positions} open vs {budget.max_open_positions} max",
        )
    )

    # 10. Cash collateral (defined-risk trades need margin; cash-secured needs full cover).
    #     Use a conservative requirement: available cash must cover max_loss.
    ok_cash = portfolio.cash >= max_loss
    gates.append(
        GateResult(
            Gate.CASH_COLLATERAL,
            ok_cash,
            hard=True,
            limit=max_loss,
            actual=portfolio.cash,
            detail=f"cash ${portfolio.cash:,.0f} vs ${max_loss:,.0f} collateral",
        )
    )

    hard_failures = [g for g in gates if not g.passed and g.hard]
    soft_failures = [g for g in gates if not g.passed and not g.hard]

    if hard_failures:
        return RiskResult(GateVerdict.REFUSE, gates)
    if soft_failures:
        return RiskResult(GateVerdict.REDUCE, gates)
    return RiskResult(GateVerdict.APPROVE, gates)
