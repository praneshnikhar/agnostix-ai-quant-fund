"""Agent contracts — identity, capabilities, and tool permissions.

Every agent is defined by an AgentSpec: unique id + version + explicit
capability set + typed input/output schemas + least-privilege tool
permissions. Agents communicate through typed contracts only.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class AgentRole(StrEnum):
    RESEARCH = "research"
    SIGNAL = "signal"
    CRITIC = "critic"
    RISK = "risk"
    EXECUTION = "execution"
    PORTFOLIO = "portfolio"


class ToolPermission(StrEnum):
    """Least-privilege tool permissions (documents .clinerules §10)."""

    READ_MARKET_DATA = "read_market_data"
    READ_NEWS = "read_news"
    READ_SNAPSHOT = "read_snapshot"  # M1: normalized market snapshot access
    READ_PORTFOLIO = "read_portfolio"
    SUBMIT_PROPOSAL = "submit_proposal"
    EVALUATE_RISK_RULES = "evaluate_risk_rules"
    VERIFY_EVIDENCE = "verify_evidence"
    PLACE_ORDER = "place_order"  # execution role ONLY, after valid authorization


# Role → default permission mapping (least privilege by construction).
ROLE_PERMISSIONS: dict[AgentRole, frozenset[ToolPermission]] = {
    AgentRole.RESEARCH: frozenset(
        {
            ToolPermission.READ_MARKET_DATA,
            ToolPermission.READ_NEWS,
            ToolPermission.READ_SNAPSHOT,
        }
    ),
    AgentRole.SIGNAL: frozenset(
        {
            ToolPermission.READ_MARKET_DATA,
            ToolPermission.READ_NEWS,
            ToolPermission.SUBMIT_PROPOSAL,
        }
    ),
    AgentRole.CRITIC: frozenset(
        {
            ToolPermission.READ_MARKET_DATA,
            ToolPermission.EVALUATE_RISK_RULES,
            ToolPermission.VERIFY_EVIDENCE,
        }
    ),
    AgentRole.RISK: frozenset({ToolPermission.READ_PORTFOLIO, ToolPermission.EVALUATE_RISK_RULES}),
    # Execution permission is granted ONLY at runtime with a valid
    # authorization event; it is never part of a static default.
    AgentRole.EXECUTION: frozenset({ToolPermission.READ_PORTFOLIO}),
    AgentRole.PORTFOLIO: frozenset({ToolPermission.READ_PORTFOLIO}),
}


class AgentSpec(BaseModel):
    """Static definition of an agent."""

    agent_id: str  # e.g. "momentum_agent"
    version: str  # e.g. "v1"
    role: AgentRole
    description: str = ""
    input_schema_name: str  # registered contract name for inputs
    output_schema_name: str  # registered contract name for outputs
    model_class: str = "standard"  # gateway ModelClass hint
    prompt_version: str = "v0"
    tool_permissions: frozenset[ToolPermission] = Field(default_factory=frozenset)

    @property
    def qualified_id(self) -> str:
        return f"{self.agent_id}_{self.version}"


def spec_with_role_defaults(spec: AgentSpec) -> AgentSpec:
    """Return a copy of the spec with its role's default permissions applied."""
    defaults = ROLE_PERMISSIONS[spec.role]
    return spec.model_copy(update={"tool_permissions": defaults})
