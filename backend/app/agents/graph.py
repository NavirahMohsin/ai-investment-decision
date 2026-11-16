"""
LangGraph graph construction and compilation for ArthAI Phase 5.

Topology
--------

    [START]
        |
        v
    [validate_tickers]      <- resolves symbols against company universe, sets
        |                      validated_tickers / unknown_tickers in state
        v
    [router]                <- selects agents based on scope + explicit override
        |
        v
    [market_analyst]        <- skips itself if not selected
        |
        v
    [fundamental_analyst]   <- skips itself if not selected
        |
        v
    [news_analyst]          <- skips itself if not selected
        |
        v
    [risk_analyst]          <- skips itself if not selected
        |
        v
    [ml_analyst]            <- skips itself if not selected (DEEP scope only)
        |
        v
    [coordinator]           <- always runs; synthesises all findings
        |
        v
      [END]

Design decisions
----------------
- Sequential rather than parallel to keep SQLAlchemy sessions simple and
  predictable across LangGraph nodes.
- Each specialist node is responsible for self-skipping when not selected;
  this avoids complex conditional edges and prevents infinite loops.
- Coordinator always runs — even with partial results it must produce a report.
- Execution is bounded: LangGraph's default recursion limit (25) applies;
  our linear chain of 7 nodes is well within that bound.
- Ticker validation is a pure-DB node and never touches the LLM.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

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
# Ticker validation node
# ---------------------------------------------------------------------------

def _validate_tickers_node(state: GraphState) -> GraphState:
    """
    Resolve requested ticker symbols against the ArthAI company universe.

    Populates:
        state["validated_tickers"]  — symbols found in the DB
        state["unknown_tickers"]    — symbols NOT found in the DB (warnings added)

    Does not abort the graph if some tickers are unknown — the specialist
    agents will handle missing data gracefully for unrecognised symbols.
    Does NOT touch the LLM.
    """
    tickers: list[str] = state.get("tickers", [])
    if not tickers:
        logger.warning("No tickers supplied to validate.")
        return {
            **state,
            "validated_tickers": [],
            "unknown_tickers": [],
            "warnings": list(state.get("warnings", [])) + ["No tickers were supplied in the request."],
        }

    validated: list[str] = []
    unknown: list[str] = []

    try:
        from app.agents.dependencies import get_agent_db_session
        from app.db.models import Company

        with get_agent_db_session() as db:
            for symbol in tickers:
                company = (
                    db.query(Company)
                    .filter(Company.symbol == symbol.upper(), Company.is_active == True)  # noqa: E712
                    .first()
                )
                if company:
                    validated.append(symbol.upper())
                    logger.info("Ticker validated: %s -> %s (id=%d)", symbol, company.name, company.id)
                else:
                    unknown.append(symbol.upper())
                    logger.warning("Ticker not found in company universe: %s", symbol)

    except Exception as exc:
        logger.exception("Ticker validation DB query failed: %s", exc)
        # Non-fatal — treat all tickers as potentially valid and let agents handle it
        validated = [t.upper() for t in tickers]
        unknown = []
        new_warnings = list(state.get("warnings", [])) + [
            f"Ticker validation failed due to DB error: {exc}. "
            "Proceeding with all supplied tickers."
        ]
        return {
            **state,
            "validated_tickers": validated,
            "unknown_tickers": unknown,
            "warnings": new_warnings,
        }

    warnings = list(state.get("warnings", []))
    for sym in unknown:
        warnings.append(
            f"Ticker '{sym}' was not found in the ArthAI company universe "
            "and will be excluded from analysis."
        )

    logger.info(
        "Ticker validation complete. Validated: %s | Unknown: %s",
        validated, unknown,
    )

    return {
        **state,
        "validated_tickers": validated,
        "unknown_tickers": unknown,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Router node
# ---------------------------------------------------------------------------

def _router_node(state: GraphState) -> GraphState:
    """
    Determine which specialist agents to run based on scope and explicit
    caller overrides.  Does NOT touch the DB or LLM.

    Selection rules
    ---------------
    1. If the caller supplied ``selected_agents``, validate them against the
       registry and use that exact list.
    2. Otherwise, derive the agent list from the requested ``scope``.
    3. The coordinator is always appended last.
    4. Each agent's status is initialised to PENDING.
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

    # Honour explicit caller override (e.g. "just market_analyst")
    explicit = state.get("selected_agents", [])
    if explicit:
        selected = registry.validate_selection(
            [s for s in explicit if s != AgentName.COORDINATOR.value]
        )
        logger.info("Explicit agent selection override: %s", selected)

    # Coordinator always runs
    if AgentName.COORDINATOR.value not in selected:
        selected.append(AgentName.COORDINATOR.value)

    # Initialise statuses
    agent_results: dict = state.get("agent_results", {})
    agent_statuses: dict = state.get("agent_statuses", {})
    for name in selected:
        if name not in agent_statuses:
            agent_statuses[name] = ExecutionStatus.PENDING.value

    logger.info("Router selected agents: %s (scope=%s)", selected, scope.value)

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
    # Lazy imports to break circular import chains at module level
    from app.agents.nodes import (  # noqa: F401
        market_analyst_node,
        fundamental_analyst_node,
        news_analyst_node,
        ml_analyst_node,
        risk_analyst_node,
        coordinator_node,
    )

    sg = StateGraph(GraphState)

    # --- Infrastructure nodes ---
    sg.add_node("validate_tickers",     _validate_tickers_node)
    sg.add_node("router",               _router_node)

    # --- Specialist nodes ---
    sg.add_node("market_analyst",       market_analyst_node)
    sg.add_node("fundamental_analyst",  fundamental_analyst_node)
    sg.add_node("news_analyst",         news_analyst_node)
    sg.add_node("risk_analyst",         risk_analyst_node)
    sg.add_node("ml_analyst",           ml_analyst_node)

    # --- Synthesis node ---
    sg.add_node("coordinator",          coordinator_node)

    # --- Entry point ---
    sg.set_entry_point("validate_tickers")

    # --- Fixed sequential edges ---
    # Every specialist is responsible for self-skipping when not selected;
    # this avoids conditional edges and keeps the topology acyclic and simple.
    sg.add_edge("validate_tickers",    "router")
    sg.add_edge("router",              "market_analyst")
    sg.add_edge("market_analyst",      "fundamental_analyst")
    sg.add_edge("fundamental_analyst", "news_analyst")
    sg.add_edge("news_analyst",        "risk_analyst")
    sg.add_edge("risk_analyst",        "ml_analyst")
    sg.add_edge("ml_analyst",          "coordinator")
    sg.add_edge("coordinator",         END)

    return sg


def compile_graph():
    """
    Build and compile the graph.

    Returns a CompiledGraph ready for ``.invoke()`` or ``.stream()``.
    The graph is compiled fresh per call; cache the result yourself if needed.
    """
    sg = build_graph()
    return sg.compile()


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def create_initial_state(
    user_request: str,
    tickers: list[str],
    scope: str = AnalysisScope.STANDARD.value,
    selected_agents: Optional[list[str]] = None,
) -> GraphState:
    """
    Build a fresh, fully-initialised GraphState for a new run.

    Args:
        user_request:    Free-text question from the user.
        tickers:         NSE/BSE ticker symbols (will be validated against DB).
        scope:           AnalysisScope value string — 'quick', 'standard', 'deep'.
        selected_agents: Optional explicit override list of agent names.

    Returns:
        A GraphState dict ready to pass to ``compiled_graph.invoke()``.
    """
    return GraphState(
        user_request=user_request,
        tickers=[t.upper() for t in tickers],
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
        # Initialise validation keys — populated by validate_tickers node
        validated_tickers=[],
        unknown_tickers=[],
    )
