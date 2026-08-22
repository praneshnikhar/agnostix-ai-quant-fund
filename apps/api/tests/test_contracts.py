"""Typed contract validation tests (documents/04_Schemas.md §2)."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.contracts import (
    CriticVerdict,
    DecisionType,
    Direction,
    ExecutionResult,
    ExecutionStatus,
    HumanDecisionContract,
    RuleCheck,
    RuleChecks,
    TradeProposal,
    Verdict,
    WSMessage,
    WSMessageType,
)


def test_trade_proposal_valid() -> None:
    p = TradeProposal(
        agent_id="momentum_agent_v1",
        symbol="AAPL",
        direction=Direction.LONG,
        thesis="Breakout with volume confirmation.",
        confidence=0.82,
        size_pct_portfolio=0.03,
    )
    assert p.proposal_id
    assert p.direction.value == "long"


def test_trade_proposal_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        TradeProposal(
            agent_id="x",
            symbol="AAPL",
            direction=Direction.LONG,
            thesis="t",
            confidence=1.5,  # out of [0, 1]
        )


def test_critic_verdict_roundtrip() -> None:
    v = CriticVerdict(
        proposal_id=uuid.uuid4(),
        verdict=Verdict.PASS_WITH_WARNING,
        rule_checks=RuleChecks(
            max_position_size=RuleCheck(passed=True, limit=0.05, actual=0.03),
            daily_loss_budget=RuleCheck(passed=True, remaining=500.0),
        ),
        llm_notes="Thesis is plausible; valuation is stretched.",
    )
    data = v.model_dump(mode="json")
    assert CriticVerdict.model_validate(data) == v


def test_human_decision_contract() -> None:
    d = HumanDecisionContract(
        proposal_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        decision=DecisionType.REVISE,
        revised_fields={"size_pct_portfolio": 0.02},
        notes="Too large for current drawdown budget.",
    )
    assert d.decision.value == "revise"


def test_execution_result_contract() -> None:
    e = ExecutionResult(
        proposal_id=uuid.uuid4(),
        alpaca_order_id="abc-123",
        status=ExecutionStatus.FILLED,
        filled_price=181.42,
        filled_qty=10,
    )
    assert e.status.value == "filled"


def test_ws_envelope() -> None:
    m = WSMessage(type=WSMessageType.NEW_PROPOSAL, payload={"symbol": "NVDA"})
    assert m.type.value == "new_proposal"
    assert WSMessage.model_validate(m.model_dump(mode="json")) == m
