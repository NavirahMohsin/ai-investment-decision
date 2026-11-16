"""Export all agent node callables and attach them to the registry."""

from app.agents.nodes.market_analyst import market_analyst_node
from app.agents.nodes.fundamental_analyst import fundamental_analyst_node
from app.agents.nodes.news_analyst import news_analyst_node
from app.agents.nodes.ml_analyst import ml_analyst_node
from app.agents.nodes.risk_analyst import risk_analyst_node
from app.agents.nodes.coordinator import coordinator_node
from app.agents.registry import registry
from app.agents.state import AgentName

# Attach node callables to global registry
registry.attach_node(AgentName.MARKET_ANALYST, market_analyst_node)
registry.attach_node(AgentName.FUNDAMENTAL_ANALYST, fundamental_analyst_node)
registry.attach_node(AgentName.NEWS_ANALYST, news_analyst_node)
registry.attach_node(AgentName.ML_ANALYST, ml_analyst_node)
registry.attach_node(AgentName.RISK_ANALYST, risk_analyst_node)
registry.attach_node(AgentName.COORDINATOR, coordinator_node)

__all__ = [
    "market_analyst_node",
    "fundamental_analyst_node",
    "news_analyst_node",
    "ml_analyst_node",
    "risk_analyst_node",
    "coordinator_node",
]
