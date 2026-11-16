"""
LangGraph graph construction and compilation for ArthAI Phase 5.

The graph is compiled once at module level and invoked once per user request.

Topology (STANDARD scope)
--------------------------

    [START]
        |
        v
    [router]
        |
        v
    [market_analyst]
        |
        v
    [fundamental_analyst]
        |
        v
    [news_analyst]
        |
        v
    [risk_analyst]
        |
        v
    [ml_analyst]      <- DEEP scope only (skips itself if not selected)
        |
        v
    [coordinator]
        |
        v
      [END]
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from langgraph.graph import StateGraph, END

from app.agents.state import (
    AgentName,
    AnalysisScope,
    ExecutionStatus,
    GraphState,
)
from app.agents.registry import registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Router node
# ---------------------------------------------------------------------------

def _router_node(state: GraphState) -> GraphState:
    """
    Inspect scope + user_request and populate selected_agents.
    Does NOT touch the DB or LLM.
    """
    scope_str = state.get("scope", AnalysisScope.STANDARD.value)
    try:
        scope = AnalysisScope(scope_str)
    except ValueError:
        logger.warning("Unknown scope '%s'; defaulting to STANDARD.", scope_str)
        scope = AnalysisScope.STANDARD

    scope_agents = registry.list_for_scope(scope)
    selected = [
        a.name.value
        for a in scope_agents
        if a.name != AgentName.COORDINATOR
    ]

    # Honour explicit override from the caller
    explicit = state.get("selected_agents", [])
    if explicit:
        selected = registry.validate_selection(explicit)

    # Coordinator always runs last
    if AgentName.COORDINATOR.value not in selected:
        selected.append(AgentName.COORDINATOR.value)

    agent_results: dict = state.get("agent_results", {})
    agent_statuses: dict = state.get("agent_statuses", {})
    for name in selected:
        if name not in agent_statuses:
            agent_statuses[name] = ExecutionStatus.PENDING.value

    logger.info("Router selected agents: %s", selected)

    return {
        **state,
        "selected_agents": selected,
        "agent_results": agent_results,
        "agent_statuses": agent_statuses,
        "run_id": state.get("run_id", str(uuid.uuid4())),
        "started_at": state.get("started_at", datetime.utcnow().isoformat()),
        "errors": state.get("errors", []),
        "warnings": state.get("warnings", []),
        "evidence_sources": state.get("evidence_sources", []),
    }


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Construct but do NOT compile the LangGraph StateGraph."""
    # Lazy import to avoid circular imports at module level
    from app.agents.nodes import (  # noqa: F401
        market_analyst_node,
        fundamental_analyst_node,
        news_analyst_node,
        ml_analyst_node,
        risk_analyst_node,
        coordinator_node,
    )

    sg = StateGraph(GraphState)

    sg.add_node("router",               _router_node)
    sg.add_node("market_analyst",       market_analyst_node)
    sg.add_node("fundamental_analyst",  fundamental_analyst_node)
    sg.add_node("news_analyst",         news_analyst_node)
    sg.add_node("risk_analyst",         risk_analyst_node)
    sg.add_node("ml_analyst",           ml_analyst_node)
    sg.add_node("coordinator",          coordinator_node)

    sg.set_entry_point("router")

    sg.add_edge("router",              "market_analyst")
    sg.add_edge("market_analyst",      "fundamental_analyst")
    sg.add_edge("fundamental_analyst", "news_analyst")
    sg.add_edge("news_analyst",        "risk_analyst")
    sg.add_edge("risk_analyst",        "ml_analyst")
    sg.add_edge("ml_analyst",          "coordinator")
    sg.add_edge("coordinator",         END)

    return sg


def compile_graph():
    """Build and compile the graph. Returns a CompiledGraph ready for .invoke()."""
    sg = build_graph()
    return sg.compile()


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def create_initial_state(
    user_request: str,
    tickers: list[str],
    scope: str = AnalysisScope.STANDARD.value,
    selected_agents: list[str] | None = None,
) -> GraphState:
    """
    Build a fresh, fully-initialised GraphState for a new run.

    Args:
        user_request: Free-text question from the user.
        tickers: NSE/BSE ticker symbols.
        scope: AnalysisScope value string.
        selected_agents: Optional explicit list of agent names.

    Returns:
        A GraphState dict ready to pass to compiled_graph.invoke().
    """
    return GraphState(
        user_request=user_request,
        tickers=tickers,
        scope=scope,
        selected_agents=selected_agents or [],
        agent_results={},
        agent_statuses={},
        errors=[],
        warnings=[],
        evidence_sources=[],
        final_report=None,
        run_id=str(uuid.uuid4()),
        started_at=datetime.utcnow().isoformat(),
        completed_at=None,
        llm_provider_used=None,
    )
