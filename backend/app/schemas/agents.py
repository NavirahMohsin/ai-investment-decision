"""
Pydantic schemas for the Multi-Agent Financial Intelligence API.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class AgentMetadataSchema(BaseModel):
    """Metadata describing a registered specialist agent."""
    name: str = Field(..., description="Canonical agent identifier")
    display_name: str = Field(..., description="Human-readable agent name")
    description: str = Field(..., description="Summary of responsibilities and capabilities")
    scopes: list[str] = Field(default_factory=list, description="Supported analysis scopes")
    requires_db: bool = Field(default=True, description="Whether this agent accesses the database")
    requires_llm: bool = Field(default=True, description="Whether this agent invokes an LLM")
    is_available: bool = Field(default=True, description="Whether the agent is currently available")


class AgentsListResponse(BaseModel):
    """Response containing all registered agents."""
    agents: list[AgentMetadataSchema] = Field(default_factory=list)
    total: int = Field(..., description="Total number of registered agents")


class AgentsHealthResponse(BaseModel):
    """Health status of the multi-agent orchestration and LLM providers."""
    status: str = Field(..., description="Overall health: healthy | degraded | unhealthy")
    orchestration_available: bool = Field(..., description="Whether LangGraph workflow is compilable")
    registered_agents: list[str] = Field(default_factory=list, description="List of registered agent names")
    total_agents: int = Field(..., description="Count of registered agents")
    gemini_available: bool = Field(..., description="Gemini LLM provider availability")
    groq_available: bool = Field(..., description="Groq LLM provider availability")
    active_providers: list[str] = Field(default_factory=list, description="Available LLM providers")
    message: str = Field(..., description="Status summary message")
    timestamp: str = Field(..., description="ISO-8601 timestamp of health evaluation")


class AgentResultDetailSchema(BaseModel):
    """Structured result returned by an individual specialist agent."""
    agent_name: str = Field(..., description="Agent name identifier")
    status: str = Field(..., description="Execution status: pending | running | completed | failed | skipped")
    summary: str = Field(default="", description="Executive summary of findings")
    key_findings: list[str] = Field(default_factory=list, description="Grounded bullet points")
    supporting_metrics: dict[str, Any] = Field(default_factory=dict, description="Raw numeric/structured metrics")
    evidence_sources: list[str] = Field(default_factory=list, description="Data sources accessed")
    data_timestamps: dict[str, str] = Field(default_factory=dict, description="Source data timestamps")
    confidence: str = Field(default="low", description="Confidence level: low | medium | high")
    missing_information: list[str] = Field(default_factory=list, description="Identified data gaps")
    warnings: list[str] = Field(default_factory=list, description="Caveats and limitations")
    started_at: Optional[str] = Field(None, description="Start timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    error_message: Optional[str] = Field(None, description="Error detail if execution failed")


class AgentResearchRequest(BaseModel):
    """Request payload for research on a specific stock ticker."""
    ticker: str = Field(..., min_length=1, max_length=50, description="Stock ticker symbol (e.g. INFY, RELIANCE)")
    question: Optional[str] = Field(None, max_length=1000, description="Optional specific research question")
    scope: Optional[str] = Field("standard", description="Analysis scope: quick | standard | deep")
    selected_agents: Optional[list[str]] = Field(None, description="Optional explicit list of agent names to execute")

    @field_validator("ticker")
    @classmethod
    def normalise_ticker(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("Ticker cannot be empty")
        return cleaned

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: Optional[str]) -> str:
        if v is None:
            return "standard"
        norm = v.strip().lower()
        if norm not in ("quick", "standard", "deep"):
            raise ValueError(f"Invalid scope '{v}'. Allowed scopes are: quick, standard, deep")
        return norm


class AgentAnalyzeRequest(BaseModel):
    """Request payload for natural language research across one or more stocks."""
    request: str = Field(..., min_length=2, max_length=2000, description="Natural language research prompt")
    tickers: Optional[list[str]] = Field(None, description="Optional explicit ticker symbols")
    scope: Optional[str] = Field(None, description="Optional explicit analysis scope: quick | standard | deep")
    selected_agents: Optional[list[str]] = Field(None, description="Optional explicit list of agents")

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        norm = v.strip().lower()
        if norm not in ("quick", "standard", "deep"):
            raise ValueError(f"Invalid scope '{v}'. Allowed scopes are: quick, standard, deep")
        return norm


class AgentExecutionResponse(BaseModel):
    """Consolidated response returned by the multi-agent workflow."""
    run_id: str = Field(..., description="Unique execution UUID")
    status: str = Field(..., description="Execution result: completed | partial_failure | failed")
    user_request: str = Field(..., description="Original user prompt or generated query")
    tickers: list[str] = Field(default_factory=list, description="Validated stock tickers analysed")
    scope: str = Field(..., description="Effective analysis scope")
    selected_agents: list[str] = Field(default_factory=list, description="Agents selected for this run")
    execution_statuses: dict[str, str] = Field(default_factory=dict, description="Statuses per agent")
    final_report: Optional[str] = Field(None, description="Consolidated markdown report generated by coordinator")
    agent_results: dict[str, AgentResultDetailSchema] = Field(
        default_factory=dict, description="Structured findings keyed by agent name"
    )
    evidence_sources: list[str] = Field(default_factory=list, description="Aggregated data sources")
    warnings: list[str] = Field(default_factory=list, description="System-wide or agent warnings")
    errors: list[str] = Field(default_factory=list, description="Errors encountered during execution")
    started_at: str = Field(..., description="ISO-8601 execution start timestamp")
    completed_at: Optional[str] = Field(None, description="ISO-8601 execution completion timestamp")
    execution_time_seconds: Optional[float] = Field(None, description="Elapsed execution duration in seconds")
    llm_provider_used: Optional[str] = Field(None, description="LLM provider utilised for synthesis")
