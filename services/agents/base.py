"""BaseAgent — lifecycle and permission guard for all agents.

M0 establishes the interface and lifecycle only. Actual intelligence
(research, signals, critique, risk, execution) is implemented in later
milestones against these contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from agents.contracts import AgentSpec, ToolPermission, spec_with_role_defaults
from agents.events import EventEmitter


class PermissionDeniedError(PermissionError):
    """Raised when an agent attempts a tool it has no permission for."""


class BaseAgent(ABC):
    """Lifecycle: initialize → run → shutdown, with permission enforcement."""

    def __init__(
        self,
        spec: AgentSpec,
        emitter: EventEmitter,
    ) -> None:
        self.spec = spec_with_role_defaults(spec)
        self.emitter = emitter

    @property
    def qualified_id(self) -> str:
        return self.spec.qualified_id

    def require_permission(self, permission: ToolPermission) -> None:
        """Least-privilege guard. Raises PermissionDeniedError if absent."""
        if permission not in self.spec.tool_permissions:
            raise PermissionDeniedError(
                f"agent={self.qualified_id} lacks permission={permission.value}"
            )

    async def initialize(self) -> None:
        """Hook for setup (connections, prompt loading)."""
        await self.emitter.emit(
            agent_id=self.qualified_id,
            event_type="agent_initialized",
            payload={"role": self.spec.role.value},
        )

    @abstractmethod
    async def run(self, input_data: BaseModel) -> BaseModel:
        """Execute one unit of work with typed input/output."""
        ...

    async def shutdown(self) -> None:
        await self.emitter.emit(
            agent_id=self.qualified_id,
            event_type="agent_stopped",
            payload={},
        )

    # -- convenience -------------------------------------------------------

    def describe(self) -> dict[str, Any]:
        return {
            "agent_id": self.spec.agent_id,
            "version": self.spec.version,
            "role": self.spec.role.value,
            "permissions": sorted(p.value for p in self.spec.tool_permissions),
            "input_schema": self.spec.input_schema_name,
            "output_schema": self.spec.output_schema_name,
            "model_class": self.spec.model_class,
            "prompt_version": self.spec.prompt_version,
        }
