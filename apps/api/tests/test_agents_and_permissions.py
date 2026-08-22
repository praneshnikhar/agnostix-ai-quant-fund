"""Agent permission-boundary and MCP tool-gateway tests.

These encode the least-privilege rules from .clinerules §10:
signal agents can never place orders; execution requires authorization.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from agents.base import PermissionDeniedError
from agents.contracts import AgentRole, AgentSpec, ToolPermission, spec_with_role_defaults
from agents.events import EventSinkRegistry, RegistryEmitter
from agents.roles import SignalAgent
from execution.mcp_boundary import AgentRole as McpRole
from execution.mcp_boundary import McpTool, ToolGateway


class _In(BaseModel):
    x: int = 0


class _Out(BaseModel):
    y: int = 0


class _StubSignalAgent(SignalAgent):
    async def run(self, input_data: BaseModel) -> BaseModel:
        return _Out()


def _spec(role: AgentRole = AgentRole.SIGNAL) -> AgentSpec:
    return AgentSpec(
        agent_id="momentum_agent",
        version="v1",
        role=role,
        input_schema_name="_In",
        output_schema_name="_Out",
    )


def test_signal_agent_cannot_place_orders() -> None:
    agent = _StubSignalAgent(_spec(), RegistryEmitter(EventSinkRegistry()))
    with pytest.raises(PermissionDeniedError):
        agent.require_permission(ToolPermission.PLACE_ORDER)


def test_signal_agent_has_read_and_submit() -> None:
    spec = spec_with_role_defaults(_spec())
    assert ToolPermission.READ_MARKET_DATA in spec.tool_permissions
    assert ToolPermission.SUBMIT_PROPOSAL in spec.tool_permissions
    assert ToolPermission.PLACE_ORDER not in spec.tool_permissions


async def test_agent_lifecycle_emits_events() -> None:
    registry = EventSinkRegistry()
    emitter = RegistryEmitter(registry)
    agent = _StubSignalAgent(_spec(), emitter)
    await agent.initialize()
    await agent.shutdown()
    types = [e.event_type for e in registry.snapshot()]
    assert "agent_initialized" in types
    assert "agent_stopped" in types


# ---------------------------------------------------------------------------
# MCP tool gateway permission model
# ---------------------------------------------------------------------------


async def test_mcp_signal_role_cannot_submit_order() -> None:
    gateway = ToolGateway(mcp_url="http://localhost:9999")
    with pytest.raises(PermissionError):
        await gateway.call(McpRole.SIGNAL, McpTool.SUBMIT_ORDER)


async def test_mcp_execution_requires_authorization_provenance() -> None:
    gateway = ToolGateway(mcp_url=None)  # unavailable; permission check first
    with pytest.raises(PermissionError):
        await gateway.call(
            McpRole.EXECUTION,
            McpTool.SUBMIT_ORDER,
            # no authorization_event_id / authorized_by_user_id
        )


async def test_mcp_unavailable_raises_fallback_error() -> None:
    gateway = ToolGateway(mcp_url=None)
    with pytest.raises(RuntimeError, match="fall back"):
        await gateway.call(McpRole.SIGNAL, McpTool.GET_BARS)
