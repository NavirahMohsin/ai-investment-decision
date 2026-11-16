"""
API routes for the Multi-Agent Financial Intelligence System.

Endpoints:
- GET  /api/v1/agents/health     - Orchestration and LLM provider health check
- GET  /api/v1/agents            - Catalogue of registered specialist agents
- POST /api/v1/agents/research   - Ticker-specific multi-agent research
- POST /api/v1/agents/analyze    - Natural-language multi-agent analysis
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Company
from app.agents.state import AgentName, AnalysisScope, ExecutionStatus
from app.agents.registry import registry
from app.agents.graph import compile_graph, create_initial_state
from app.services.llm_service import get_llm_service
from app.schemas.agents import (
    AgentAnalyzeRequest,
    AgentExecutionResponse,
    AgentMetadataSchema,
    AgentResearchRequest,
    AgentResultDetailSchema,
    AgentsHealthResponse,
    AgentsListResponse,
)

logger = logging.getLogger(__name__)

agents_router = APIRouter(
    prefix="/api/v1/agents",
    tags=["Multi-Agent Intelligence"],
    responses={
        400: {"description": "Validation or bad request error"},
        404: {"description": "Resource not found"},
        500: {"description": "Internal processing error"},
    },
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _extract_tickers_from_text(text: str, db: Session) -> list[str]:
    """
    Extract recognized company symbols from text by matching active symbols
    and company names.
    """
    companies = (
        db.query(Company.symbol, Company.name)
        .filter(Company.is_active == True)  # noqa: E712
        .all()
    )

    found_symbols: list[str] = []
    text_upper = text.upper()

    # 1. Exact symbol match on word boundaries
    for sym, _ in companies:
        pattern = r"\b" + re.escape(sym.upper()) + r"\b"
        if re.search(pattern, text_upper):
            if sym.upper() not in found_symbols:
                found_symbols.append(sym.upper())

    # 2. Company name substring match if no symbol found yet
    if not found_symbols:
        for sym, name in companies:
            clean_name = re.sub(r"\b(ltd|limited|inc|corp|industries|technologies|services)\b", "", name, flags=re.IGNORECASE).strip()
            if len(clean_name) >= 3 and clean_name.lower() in text.lower():
                if sym.upper() not in found_symbols:
                    found_symbols.append(sym.upper())

    return found_symbols


def _infer_scope_from_query(query: str) -> str:
    """Infer analysis scope from keywords in the prompt."""
    q_lower = query.lower()
    if any(k in q_lower for k in ["deep", "comprehensive", "full", "all models", "deep-dive"]):
        return AnalysisScope.DEEP.value
    if any(k in q_lower for k in ["quick", "brief", "fast", "snapshot", "technical only"]):
        return AnalysisScope.QUICK.value
    return AnalysisScope.STANDARD.value


def _build_execution_response(
    final_state: dict[str, Any],
    elapsed_seconds: float,
) -> AgentExecutionResponse:
    """Transform GraphState into an AgentExecutionResponse."""
    raw_results = final_state.get("agent_results", {})
    agent_results_detail: dict[str, AgentResultDetailSchema] = {}
    for agent_key, r_dict in raw_results.items():
        try:
            agent_results_detail[agent_key] = AgentResultDetailSchema(**r_dict)
        except Exception as exc:
            logger.warning("Could not parse AgentResult for %s: %s", agent_key, exc)
            agent_results_detail[agent_key] = AgentResultDetailSchema(
                agent_name=agent_key,
                status=r_dict.get("status", "unknown"),
                summary=r_dict.get("summary", ""),
                key_findings=r_dict.get("key_findings", []),
                error_message=str(exc),
            )

    statuses = final_state.get("agent_statuses", {})
    errors = final_state.get("errors", [])

    if not statuses:
        overall_status = "failed" if errors else "completed"
    else:
        failed_count = sum(1 for s in statuses.values() if s == ExecutionStatus.FAILED.value)
        completed_count = sum(1 for s in statuses.values() if s == ExecutionStatus.COMPLETED.value)
        if completed_count == 0 and failed_count > 0:
            overall_status = "failed"
        elif failed_count > 0:
            overall_status = "partial_failure"
        else:
            overall_status = "completed"

    return AgentExecutionResponse(
        run_id=final_state.get("run_id", ""),
        status=overall_status,
        user_request=final_state.get("user_request", ""),
        tickers=final_state.get("validated_tickers", final_state.get("tickers", [])),
        scope=final_state.get("scope", AnalysisScope.STANDARD.value),
        selected_agents=final_state.get("selected_agents", []),
        execution_statuses=statuses,
        final_report=final_state.get("final_report"),
        agent_results=agent_results_detail,
        evidence_sources=final_state.get("evidence_sources", []),
        warnings=final_state.get("warnings", []),
        errors=errors,
        started_at=final_state.get("started_at", datetime.now(timezone.utc).isoformat()),
        completed_at=final_state.get("completed_at"),
        execution_time_seconds=elapsed_seconds,
        llm_provider_used=final_state.get("llm_provider_used"),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@agents_router.get(
    "/health",
    response_model=AgentsHealthResponse,
    summary="Check multi-agent system health",
    description="Inspect LangGraph workflow availability, registered agents, and configured LLM providers.",
)
async def get_agents_health():
    """
    Check the operational health of the multi-agent system.
    Returns:
    - Orchestration readiness
    - Registered specialist agents
    - Availability of LLM providers without revealing credentials
    """
    orchestration_available = True
    try:
        # Verify graph compiles without error
        compile_graph()
    except Exception as exc:
        logger.error("Graph compilation check failed: %s", exc)
        orchestration_available = False

    active_providers: list[str] = []
    gemini_ok = False
    groq_ok = False

    try:
        llm_svc = get_llm_service()
        gemini_ok = bool(llm_svc.gemini_available)
        groq_ok = bool(llm_svc.groq_available)
        if gemini_ok:
            active_providers.append("gemini")
        if groq_ok:
            active_providers.append("groq")
    except Exception as exc:
        logger.warning("LLM service check failed: %s", exc)

    registered_names = registry.list_names()

    if not orchestration_available:
        status_val = "unhealthy"
        msg = "Orchestration graph compilation failed"
    elif not active_providers:
        status_val = "degraded"
        msg = "Orchestrator ready, but no LLM providers configured (deterministic logic active)"
    elif len(active_providers) == 1:
        status_val = "healthy"
        msg = f"Orchestrator ready with {active_providers[0].title()} provider"
    else:
        status_val = "healthy"
        msg = "All specialist agents and LLM providers operational"

    return AgentsHealthResponse(
        status=status_val,
        orchestration_available=orchestration_available,
        registered_agents=registered_names,
        total_agents=len(registered_names),
        gemini_available=gemini_ok,
        groq_available=groq_ok,
        active_providers=active_providers,
        message=msg,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@agents_router.get(
    "",
    response_model=AgentsListResponse,
    summary="List registered specialist agents",
    description="Retrieve all registered analyst agents, their descriptions, scopes, and resource requirements.",
)
async def list_agents():
    """List all registered agents and their capabilities in ArthAI."""
    agent_info_list = registry.all()
    metadata = [
        AgentMetadataSchema(
            name=a.name.value,
            display_name=a.display_name,
            description=a.description,
            scopes=[s.value for s in a.scopes],
            requires_db=a.requires_db,
            requires_llm=a.requires_llm,
            is_available=True,
        )
        for a in agent_info_list
    ]
    return AgentsListResponse(agents=metadata, total=len(metadata))


@agents_router.post(
    "/research",
    response_model=AgentExecutionResponse,
    summary="Run targeted company research",
    description="Execute the multi-agent workflow for a specific stock ticker with optional custom question and scope.",
)
async def run_ticker_research(
    request: AgentResearchRequest,
    db: Session = Depends(get_db),
):
    """
    Perform multi-agent financial research for a specific ticker.
    - Validates ticker against the existing company universe.
    - Validates optional agent names.
    - Runs the LangGraph workflow.
    - Returns individual agent findings and a consolidated report.
    """
    sym = request.ticker.strip().upper()

    # 1. Validate ticker against company universe
    company = (
        db.query(Company)
        .filter(Company.symbol == sym, Company.is_active == True)  # noqa: E712
        .first()
    )
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ticker '{sym}' not found in the company universe.",
        )

    # 2. Validate selected agents if explicitly provided
    if request.selected_agents:
        valid_names = set(registry.list_names())
        invalid_agents = [a for a in request.selected_agents if a not in valid_names]
        if invalid_agents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid agent name(s): {invalid_agents}. Valid agents are: {sorted(list(valid_names))}",
            )

    user_query = request.question.strip() if request.question else f"Comprehensive investment analysis of {sym} ({company.name})"
    scope_val = request.scope or AnalysisScope.STANDARD.value

    # 3. Execute LangGraph workflow
    try:
        graph = compile_graph()
        initial_state = create_initial_state(
            user_request=user_query,
            tickers=[sym],
            scope=scope_val,
            selected_agents=request.selected_agents,
        )

        start_time = time.perf_counter()
        final_state = graph.invoke(initial_state)
        elapsed = round(time.perf_counter() - start_time, 3)

        return _build_execution_response(final_state, elapsed)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error executing research workflow for ticker %s: %s", sym, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete research workflow: {str(exc)}",
        )


@agents_router.post(
    "/analyze",
    response_model=AgentExecutionResponse,
    summary="Natural language multi-agent analysis",
    description="Accepts a natural-language research request, identifies tickers and scopes, and executes the multi-agent graph.",
)
async def run_natural_language_analysis(
    request: AgentAnalyzeRequest,
    db: Session = Depends(get_db),
):
    """
    Analyze natural-language investment requests using the multi-agent system.
    - Extracts or validates ticker symbols.
    - Determines or validates the appropriate analysis scope and agents.
    - Executes the LangGraph workflow and returns consolidated intelligence.
    """
    raw_query = request.request.strip()

    # 1. Identify tickers (either explicitly provided or extracted from prompt)
    tickers: list[str] = []
    if request.tickers:
        for t in request.tickers:
            norm = t.strip().upper()
            comp = db.query(Company).filter(Company.symbol == norm, Company.is_active == True).first()  # noqa: E712
            if not comp:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Company with ticker '{norm}' not found in the company universe.",
                )
            if norm not in tickers:
                tickers.append(norm)
    else:
        tickers = _extract_tickers_from_text(raw_query, db)

    if not tickers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not detect any valid company ticker from your request. Please specify the 'tickers' list explicitly.",
        )

    # 2. Validate selected agents if explicitly provided
    if request.selected_agents:
        valid_names = set(registry.list_names())
        invalid_agents = [a for a in request.selected_agents if a not in valid_names]
        if invalid_agents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid agent name(s): {invalid_agents}. Valid agents are: {sorted(list(valid_names))}",
            )

    # 3. Determine analysis scope
    effective_scope = request.scope or _infer_scope_from_query(raw_query)

    # 4. Execute workflow
    try:
        graph = compile_graph()
        initial_state = create_initial_state(
            user_request=raw_query,
            tickers=tickers,
            scope=effective_scope,
            selected_agents=request.selected_agents,
        )

        start_time = time.perf_counter()
        final_state = graph.invoke(initial_state)
        elapsed = round(time.perf_counter() - start_time, 3)

        return _build_execution_response(final_state, elapsed)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error executing analyze workflow: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute analysis workflow: {str(exc)}",
        )
