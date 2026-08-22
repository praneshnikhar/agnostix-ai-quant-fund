"""LangGraph pipeline skeleton — propose → critique → human gate.

M0 establishes the graph SHAPE only. Nodes are stubs that raise
NotImplementedError; the real implementations arrive in M2–M7.

The graph encodes the mandatory execution chain:

    Signal → Critic → Risk → Human Approval → Execution

The human-gate node is a LangGraph interrupt point: the graph pauses until
an external approval event resumes it. No edge bypasses the gate.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


class PipelineState(TypedDict, total=False):
    """Shared state flowing through the proposal pipeline."""

    proposal: dict[str, Any]          # TradeProposal (serialized)
    critic_verdict: dict[str, Any] | None
    risk_assessment: dict[str, Any] | None
    human_decision: dict[str, Any] | None   # present ONLY after approval gate
    execution_result: dict[str, Any] | None
    halted: bool                       # kill switch / rejection short-circuit


def signal_node(state: PipelineState) -> PipelineState:
    """M3+: strategy agents produce TradeProposal objects."""
    raise NotImplementedError("Signal agents are implemented in M3")


def critic_node(state: PipelineState) -> PipelineState:
    """M2/M4+: deterministic rule checks + evidence verification."""
    raise NotImplementedError("Critic logic is implemented in M2+")


def risk_node(state: PipelineState) -> PipelineState:
    """M5: deterministic quant risk engine. LLM never decides here."""
    raise NotImplementedError("Risk engine is implemented in M5")


def human_gate_node(state: PipelineState) -> PipelineState:
    """Interrupt point — waits for an explicit human decision event."""
    raise NotImplementedError("Human gate wiring is implemented in M4/M7")


def execution_node(state: PipelineState) -> PipelineState:
    """M7: paper execution via Broker abstraction, authorization required."""
    raise NotImplementedError("Execution is implemented in M7")


def build_pipeline_graph() -> StateGraph:
    """Construct the (unexecuted in M0) proposal pipeline graph."""
    graph = StateGraph(PipelineState)
    graph.add_node("signal", signal_node)
    graph.add_node("critic", critic_node)
    graph.add_node("risk", risk_node)
    graph.add_node("human_gate", human_gate_node)
    graph.add_node("execution", execution_node)

    graph.set_entry_point("signal")
    graph.add_edge("signal", "critic")
    graph.add_edge("critic", "risk")
    graph.add_edge("risk", "human_gate")
    # Execution is reachable ONLY through the human gate.
    graph.add_edge("human_gate", "execution")
    graph.add_edge("execution", END)

    return graph
