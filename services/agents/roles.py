"""Role-level agent abstractions (M0: interfaces only, no intelligence).

Each role enforces its permission boundary at the type level. Concrete
agents arrive in M1+ (research), M2 (fundamental analyst), M3 (strategy
band), M4 (committee), M5 (risk), M7 (execution).
"""

from __future__ import annotations

from abc import abstractmethod

from pydantic import BaseModel

from agents.base import BaseAgent
from agents.contracts import AgentSpec, ToolPermission
from agents.events import EventEmitter


class ResearchAgent(BaseAgent):
    """Read-only research over market/news data. NO execution."""

    def __init__(self, spec: AgentSpec, emitter: EventEmitter) -> None:
        super().__init__(spec, emitter)
        self.require_permission(ToolPermission.READ_MARKET_DATA)

    @abstractmethod
    async def run(self, input_data: BaseModel) -> BaseModel: ...


class SignalAgent(ResearchAgent):
    """Research + submit proposals. Still NO execution."""

    def __init__(self, spec: AgentSpec, emitter: EventEmitter) -> None:
        super().__init__(spec, emitter)
        self.require_permission(ToolPermission.SUBMIT_PROPOSAL)


class CriticAgent(BaseAgent):
    """Verifies evidence and evaluates deterministic risk rules. NO execution."""

    def __init__(self, spec: AgentSpec, emitter: EventEmitter) -> None:
        super().__init__(spec, emitter)
        self.require_permission(ToolPermission.EVALUATE_RISK_RULES)
        self.require_permission(ToolPermission.VERIFY_EVIDENCE)

    @abstractmethod
    async def run(self, input_data: BaseModel) -> BaseModel: ...


class RiskAgent(BaseAgent):
    """Portfolio-aware risk evaluation. Deterministic rules; NO execution."""

    def __init__(self, spec: AgentSpec, emitter: EventEmitter) -> None:
        super().__init__(spec, emitter)
        self.require_permission(ToolPermission.READ_PORTFOLIO)

    @abstractmethod
    async def run(self, input_data: BaseModel) -> BaseModel: ...


class ExecutionAgent(BaseAgent):
    """The ONLY role that may place orders — and only after a valid
    human-authorization event is presented at runtime."""

    def __init__(self, spec: AgentSpec, emitter: EventEmitter) -> None:
        super().__init__(spec, emitter)
        # PLACE_ORDER is never a static default; it must be granted with an
        # authorization event per order. Enforced in later milestones.

    @abstractmethod
    async def run(self, input_data: BaseModel) -> BaseModel: ...


class PortfolioAgent(BaseAgent):
    """Syncs positions/equity snapshots. Read-only."""

    def __init__(self, spec: AgentSpec, emitter: EventEmitter) -> None:
        super().__init__(spec, emitter)
        self.require_permission(ToolPermission.READ_PORTFOLIO)

    @abstractmethod
    async def run(self, input_data: BaseModel) -> BaseModel: ...
