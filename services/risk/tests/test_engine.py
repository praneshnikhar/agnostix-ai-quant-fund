"""Unit tests for the deterministic risk engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from options.schemas import OptionContract, OptionLeg, OptionSide, OptionStrategy, OptionType
from risk.engine import Gate, GateVerdict, PortfolioState, RiskBudget, evaluate


def _strategy(
    max_loss: float, *, dte: int = 30, pop: float = 0.75, underlying: str = "AAPL"
) -> OptionStrategy:
    expiry = datetime.now(UTC) + timedelta(days=dte)
    leg = OptionLeg(
        contract=OptionContract(
            symbol="P100",
            underlying=underlying,
            option_type=OptionType.PUT,
            strike=100.0,
            expiration=expiry,
        ),
        side=OptionSide.SELL_TO_OPEN,
        quantity=1,
        delta=-0.30,
    )
    return OptionStrategy(
        strategy_id="test",
        name="bull_put_spread",
        underlying=underlying,
        legs=[leg],
        max_loss=max_loss,
        max_profit=100.0,
        days_to_expiration=dte,
        probability_of_profit=pop,
    )


def _portfolio(
    equity: float = 100_000.0,
    cash: float = 100_000.0,
    daily_pl: float = 0.0,
    open_positions: int = 0,
    committed: float = 0.0,
    exposure_by_underlying: dict[str, float] | None = None,
) -> PortfolioState:
    return PortfolioState(
        equity=equity,
        cash=cash,
        daily_pl=daily_pl,
        open_positions=open_positions,
        defined_risk_committed=committed,
        exposure_by_underlying=exposure_by_underlying or {},
    )


def _evaluate(strategy: OptionStrategy, portfolio: PortfolioState):
    return evaluate(strategy, portfolio, RiskBudget())


def test_approve_healthy_trade() -> None:
    result = _evaluate(_strategy(500.0), _portfolio())
    assert result.verdict == GateVerdict.APPROVE
    assert result.passed


def test_refuse_max_loss_per_trade() -> None:
    # 5% of equity = $5,000; a $6,000 loss trade must be refused.
    result = _evaluate(_strategy(6000.0), _portfolio())
    assert result.verdict == GateVerdict.REFUSE
    failed = next(g for g in result.gates if g.gate == Gate.MAX_LOSS_PER_TRADE)
    assert failed.passed is False


def test_refuse_undefined_risk() -> None:
    s = _strategy(500.0)
    s.max_loss = None
    result = _evaluate(s, _portfolio())
    assert result.verdict == GateVerdict.REFUSE


def test_circuit_breaker_stops_desk() -> None:
    # Daily P&L of -$5,000 on $100k = -5% → breaker trips (limit 3%).
    result = _evaluate(_strategy(500.0), _portfolio(daily_pl=-5000.0))
    assert result.verdict == GateVerdict.REFUSE
    failed = next(g for g in result.gates if g.gate == Gate.DAILY_LOSS_CIRCUIT_BREAKER)
    assert failed.passed is False


def test_soft_failure_reduces_not_refuses() -> None:
    # PoP below floor (soft) but everything else healthy → REDUCE.
    result = _evaluate(_strategy(500.0, pop=0.40), _portfolio())
    assert result.verdict == GateVerdict.REDUCE


def test_concentration_gate() -> None:
    # $9,900 already committed in AAPL + new $500 → $10,400 > 10% ($10k) limit.
    result = _evaluate(
        _strategy(500.0), _portfolio(committed=0.0, exposure_by_underlying={"AAPL": 9900.0})
    )
    assert result.verdict == GateVerdict.REFUSE
    failed = next(g for g in result.gates if g.gate == Gate.CONCENTRATION)
    assert failed.passed is False


def test_cash_collateral_gate() -> None:
    result = _evaluate(_strategy(500.0), _portfolio(cash=100.0))
    assert result.verdict == GateVerdict.REFUSE
    failed = next(g for g in result.gates if g.gate == Gate.CASH_COLLATERAL)
    assert failed.passed is False


def test_dte_window_gate() -> None:
    result = _evaluate(_strategy(500.0, dte=1), _portfolio())
    assert result.verdict == GateVerdict.REFUSE
    failed = next(g for g in result.gates if g.gate == Gate.DTE_WINDOW)
    assert failed.passed is False
