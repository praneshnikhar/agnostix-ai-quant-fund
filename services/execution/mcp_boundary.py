"""Alpaca MCP integration boundary.

Alpaca MCP is a one-month development accelerator. This boundary lets the
system call MCP tools WITHOUT making the application dependent on MCP:

    Agent / Service
          ↓
    Tool Gateway (this module)
          ↓
    Alpaca MCP

If MCP is unavailable, callers fall back to the SDK/API adapters in
broker/alpaca.py. The application's domain model never depends on MCP.

Permission model (least privilege — enforced here, not by convention):

    signal agents : market/news read-only tools
    critic        : market data + risk-rule evaluation
    execution     : order placement ONLY with valid authorization provenance

Research/signal agents can NEVER reach an order-placement tool through
this boundary.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import httpx


class McpTool(StrEnum):
    """Tool names exposed by the Alpaca MCP server."""

    GET_ACCOUNT = "get_account"
    GET_POSITIONS = "get_positions"
    GET_BARS = "get_bars"
    GET_NEWS = "get_news"
    SUBMIT_ORDER = "submit_order"


class AgentRole(StrEnum):
    SIGNAL = "signal"
    CRITIC = "critic"
    EXECUTION = "execution"


# Role → allowed MCP tools. Order placement is deliberately absent from
# every role except execution.
ROLE_TOOLS: dict[AgentRole, frozenset[McpTool]] = {
    AgentRole.SIGNAL: frozenset({McpTool.GET_BARS, McpTool.GET_NEWS}),
    AgentRole.CRITIC: frozenset({McpTool.GET_BARS, McpTool.GET_NEWS}),
    # Execution is granted at runtime only with authorization provenance;
    # see ToolGateway.call() enforcement below.
    AgentRole.EXECUTION: frozenset({McpTool.GET_ACCOUNT, McpTool.GET_POSITIONS}),
}


class McpUnavailableError(RuntimeError):
    """Raised when the MCP server cannot be reached — callers should fall
    back to the SDK/API adapter path."""


class ToolGateway:
    """The single entry point for MCP tool calls, with permission checks."""

    def __init__(self, mcp_url: str | None) -> None:
        self._mcp_url = mcp_url

    @property
    def available(self) -> bool:
        return bool(self._mcp_url)

    async def call(
        self,
        role: AgentRole,
        tool: McpTool,
        params: dict[str, Any] | None = None,
        *,
        authorization_event_id: str | None = None,
        authorized_by_user_id: str | None = None,
    ) -> dict[str, Any]:
        """Invoke an MCP tool after enforcing the permission model."""
        allowed = ROLE_TOOLS.get(role, frozenset())
        if tool not in allowed:
            raise PermissionError(f"role={role.value} is not permitted to use tool={tool.value}")

        if tool == McpTool.SUBMIT_ORDER:
            if not authorization_event_id or not authorized_by_user_id:
                raise PermissionError(
                    "submit_order requires human-authorization provenance "
                    "(authorization_event_id + authorized_by_user_id)."
                )

        if not self.available:
            raise McpUnavailableError(
                "ALPACA_MCP_URL is not configured; fall back to the SDK/API broker adapter."
            )

        payload = {
            "tool": tool.value,
            "arguments": params or {},
            "context": {
                "role": role.value,
                "authorization_event_id": authorization_event_id,
            },
        }
        if self._mcp_url is None:  # defensive; availability checked above
            raise McpUnavailableError("MCP URL disappeared mid-call")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self._mcp_url, json=payload)
            resp.raise_for_status()
            return resp.json()
