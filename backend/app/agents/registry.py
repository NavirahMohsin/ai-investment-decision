"""
Agent Registry - a central catalogue of every specialist agent.

Usage
-----
    from app.agents.registry import AgentRegistry, registry

    info = registry.get("market_analyst")
    agents = registry.list_for_scope(AnalysisScope.STANDARD)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.agents.state import AgentName, AnalysisScope, GraphState

logger = logging.getLogger(__name__)


@dataclass
class AgentInfo:
    """Metadata about a registered agent."""

    name: AgentName
    display_name: str
    description: str
    scopes: list[AnalysisScope] = field(default_factory=list)
    node_fn: Optional[Callable[[GraphState], GraphState]] = field(default=None, repr=False)
    requires_db: bool = True
    requires_llm: bool = True


class AgentRegistry:
    """Thread-safe registry of specialist agents."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentInfo] = {}

    def register(self, info: AgentInfo) -> None:
        """Register an AgentInfo entry. Raises if name is already registered."""
        key = info.name.value
        if key in self._agents:
            raise ValueError(f"Agent '{key}' is already registered.")
        self._agents[key] = info
        logger.debug("Registered agent: %s", key)

    def attach_node(self, name: AgentName, fn: Callable[[GraphState], GraphState]) -> None:
        """Attach the LangGraph node callable to a registered agent."""
        key = name.value
        if key not in self._agents:
            raise KeyError(f"Agent '{key}' not found in registry.")
        self._agents[key].node_fn = fn
        logger.debug("Attached node function to agent: %s", key)

    def get(self, name: str | AgentName) -> AgentInfo:
        key = name.value if isinstance(name, AgentName) else name
        if key not in self._agents:
            raise KeyError(f"Agent '{key}' not found in registry.")
        return self._agents[key]

    def all(self) -> list[AgentInfo]:
        return list(self._agents.values())

    def list_names(self) -> list[str]:
        return list(self._agents.keys())

    def list_for_scope(self, scope: AnalysisScope) -> list[AgentInfo]:
        """Return agents that participate in a given analysis scope."""
        return [a for a in self._agents.values() if scope in a.scopes]

    def validate_selection(self, selected: list[str]) -> list[str]:
        """Return only the agent names that are registered; log unknown ones."""
        valid = []
        for name in selected:
            if name in self._agents:
                valid.append(name)
            else:
                logger.warning("Unknown agent in selection: '%s' - ignoring.", name)
        return valid

    def __len__(self) -> int:
        return len(self._agents)

    def __contains__(self, name: str | AgentName) -> bool:
        key = name.value if isinstance(name, AgentName) else name
        return key in self._agents


# ---------------------------------------------------------------------------
# Global registry instance + default registrations
# ---------------------------------------------------------------------------

registry = AgentRegistry()

registry.register(AgentInfo(
    name=AgentName.MARKET_ANALYST,
    display_name="Market Analyst",
    description="Analyses price action, technical indicators, and market signals.",
    scopes=[AnalysisScope.QUICK, AnalysisScope.STANDARD, AnalysisScope.DEEP],
    requires_db=True,
    requires_llm=True,
))

registry.register(AgentInfo(
    name=AgentName.FUNDAMENTAL_ANALYST,
    display_name="Fundamental Analyst",
    description="Evaluates financial ratios, earnings quality, and balance-sheet health.",
    scopes=[AnalysisScope.STANDARD, AnalysisScope.DEEP],
    requires_db=True,
    requires_llm=True,
))

registry.register(AgentInfo(
    name=AgentName.NEWS_ANALYST,
    display_name="News Analyst",
    description="Processes recent news, sentiment signals, and event classifications.",
    scopes=[AnalysisScope.STANDARD, AnalysisScope.DEEP],
    requires_db=True,
    requires_llm=True,
))

registry.register(AgentInfo(
    name=AgentName.ML_ANALYST,
    display_name="ML Analyst",
    description="Surfaces ML-model predictions and feature-importance context.",
    scopes=[AnalysisScope.DEEP],
    requires_db=True,
    requires_llm=False,
))

registry.register(AgentInfo(
    name=AgentName.RISK_ANALYST,
    display_name="Risk Analyst",
    description="Assesses volatility, drawdown risk, and sector-level concentration.",
    scopes=[AnalysisScope.STANDARD, AnalysisScope.DEEP],
    requires_db=True,
    requires_llm=True,
))

registry.register(AgentInfo(
    name=AgentName.COORDINATOR,
    display_name="Research Coordinator",
    description="Synthesises specialist findings into a final investment-research report.",
    scopes=[AnalysisScope.QUICK, AnalysisScope.STANDARD, AnalysisScope.DEEP],
    requires_db=False,
    requires_llm=True,
))
