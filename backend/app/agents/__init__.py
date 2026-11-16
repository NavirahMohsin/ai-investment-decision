"""
ArthAI Phase 5 - Multi-Agent Financial Intelligence System.

Public surface area
-------------------
    from app.agents import compile_graph, create_initial_state, registry

    graph  = compile_graph()
    state  = create_initial_state("Analyse INFY for me", tickers=["INFY"])
    result = graph.invoke(state)
"""

from app.agents.state import (
    AgentName,
    AgentResult,
    AnalysisScope,
    ExecutionStatus,
    GraphState,
)
from app.agents.registry import registry
from app.agents.graph import (
    compile_graph,
    create_initial_state,
    build_graph,
    _validate_tickers_node,
    _router_node,
)

__all__ = [
    "AgentName",
    "AgentResult",
    "AnalysisScope",
    "ExecutionStatus",
    "GraphState",
    "registry",
    "compile_graph",
    "create_initial_state",
    "build_graph",
    "_validate_tickers_node",
    "_router_node",
]
