"""
Shared typed state for the ArthAI multi-agent LangGraph graph.

Design rules
------------
- All values must be JSON-serialisable (no SQLAlchemy sessions, no DB objects).
- Agents receive a *copy* of the relevant slice; they write back to named keys.
- TypedDict (not Pydantic) is used so LangGraph can merge sub-dicts natively.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional, TypedDict

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentName(str, Enum):
    """Canonical names for every specialist agent."""
    MARKET_ANALYST      = "market_analyst"
    FUNDAMENTAL_ANALYST = "fundamental_analyst"
    NEWS_ANALYST        = "news_analyst"
    ML_ANALYST          = "ml_analyst"
    RISK_ANALYST        = "risk_analyst"
    COORDINATOR         = "coordinator"


class ExecutionStatus(str, Enum):
    """Lifecycle status of a single agent execution."""
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    SKIPPED   = "skipped"


class AnalysisScope(str, Enum):
    """Requested depth of analysis."""
    QUICK    = "quick"     # single agent, fast answer
    STANDARD = "standard"  # 3-4 agents
    DEEP     = "deep"      # all agents


# ---------------------------------------------------------------------------
# Per-agent structured result  (Pydantic - richer validation)
# ---------------------------------------------------------------------------

class AgentResult(BaseModel):
    """Structured result produced by every specialist agent."""

    agent_name: AgentName = Field(..., description="Which agent produced this result")
    status: ExecutionStatus = Field(default=ExecutionStatus.PENDING)

    # Core content
    summary: str = Field(default="", description="One-paragraph human-readable summary")
    key_findings: list[str] = Field(
        default_factory=list,
        description="Bullet-point key findings (no invented metrics)",
    )
    supporting_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw numeric / categorical metrics backing the findings",
    )

    # Provenance
    evidence_sources: list[str] = Field(
        default_factory=list,
        description="Data sources accessed (table names, API endpoints, service names)",
    )
    data_timestamps: dict[str, str] = Field(
        default_factory=dict,
        description="ISO-8601 timestamps keyed by data source name",
    )

    # Quality signals
    confidence: str = Field(
        default="low",
        description="Overall reliability: low | medium | high",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Data that was unavailable or could not be retrieved",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Limitations, caveats, or data quality issues",
    )

    # Timing
    started_at: Optional[str] = Field(None, description="ISO-8601 execution start time")
    completed_at: Optional[str] = Field(None, description="ISO-8601 execution end time")
    error_message: Optional[str] = Field(None, description="Error detail on failure")

    def mark_running(self) -> "AgentResult":
        self.status = ExecutionStatus.RUNNING
        self.started_at = datetime.utcnow().isoformat()
        return self

    def mark_completed(self) -> "AgentResult":
        self.status = ExecutionStatus.COMPLETED
        self.completed_at = datetime.utcnow().isoformat()
        return self

    def mark_failed(self, error: str) -> "AgentResult":
        self.status = ExecutionStatus.FAILED
        self.error_message = error
        self.completed_at = datetime.utcnow().isoformat()
        return self

    def mark_skipped(self, reason: str) -> "AgentResult":
        self.status = ExecutionStatus.SKIPPED
        self.warnings.append(f"Skipped: {reason}")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for graph state."""
        return self.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Top-level graph state  (TypedDict so LangGraph can do channel-based merging)
# ---------------------------------------------------------------------------

class GraphState(TypedDict, total=False):
    """
    Shared state threaded through every node in the LangGraph graph.

    Keys are intentionally optional (total=False) so each node only needs to
    update the keys it owns.
    """

    # Request metadata
    user_request: str
    tickers: list[str]
    scope: str
    selected_agents: list[str]

    # Per-agent results (plain dicts - JSON-safe)
    agent_results: dict[str, dict[str, Any]]
    agent_statuses: dict[str, str]

    # Errors / warnings
    errors: list[str]
    warnings: list[str]

    # Synthesis
    final_report: Optional[str]
    evidence_sources: list[str]

    # Execution metadata
    run_id: str
    started_at: str
    completed_at: Optional[str]
    llm_provider_used: Optional[str]
