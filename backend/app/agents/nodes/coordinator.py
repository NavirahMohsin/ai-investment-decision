"""Research Coordinator agent node - final synthesis."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from app.agents.state import AgentName, AgentResult, ExecutionStatus, GraphState
from app.agents.prompts import COORDINATOR_SYSTEM
from app.agents.nodes.base import merge_agent_result
from app.agents.dependencies import get_agent_llm_service

logger = logging.getLogger(__name__)


def coordinator_node(state: GraphState) -> GraphState:
    """
    Coordinator: synthesise all specialist agent findings into a markdown report.

    Reads agent_results from state, builds a summary prompt, calls the LLM,
    and stores the final report in state["final_report"].
    """
    result = AgentResult(agent_name=AgentName.COORDINATOR)
    result.mark_running()

    agent_results: dict[str, Any] = state.get("agent_results", {})

    # Build a compact summary of each agent's findings for the prompt
    summaries: list[str] = []
    for agent_name, ar_dict in agent_results.items():
        status = ar_dict.get("status", "unknown")
        if status not in (ExecutionStatus.COMPLETED.value, ExecutionStatus.SKIPPED.value):
            summaries.append(f"## {agent_name.upper()}\nStatus: {status} - no findings.")
            continue

        findings_text = "\n".join(
            f"- {f}" for f in ar_dict.get("key_findings", [])
        ) or "None reported."

        summaries.append(
            f"## {agent_name.upper()}\n"
            f"Status: {status}\n"
            f"Summary: {ar_dict.get('summary', 'N/A')}\n"
            f"Key findings:\n{findings_text}\n"
            f"Metrics: {json.dumps(ar_dict.get('supporting_metrics', {}), default=str)}\n"
            f"Confidence: {ar_dict.get('confidence', 'unknown')}\n"
            f"Warnings: {'; '.join(ar_dict.get('warnings', []))}\n"
            f"Missing: {'; '.join(ar_dict.get('missing_information', []))}"
        )

    agent_summary_text = (
        "\n\n".join(summaries) if summaries else "No agent results available."
    )

    prompt = (
        f"User request: {state.get('user_request', '')}\n\n"
        f"Tickers analysed: {', '.join(state.get('tickers', []))}\n\n"
        f"Specialist agent findings:\n\n{agent_summary_text}\n\n"
        "Synthesise all findings into a coherent investment research report in Markdown."
    )

    llm_provider_used = None
    final_report = None

    try:
        llm = get_agent_llm_service()
        response = llm.generate(
            prompt=prompt,
            system_prompt=COORDINATOR_SYSTEM,
            temperature=0.3,
            max_tokens=4096,
        )
        final_report = response.content
        llm_provider_used = response.provider.value
        result.summary = "Synthesis report generated successfully."
        result.key_findings = ["Final report produced by coordinator."]
        result.evidence_sources = list(state.get("evidence_sources", []))
        result.confidence = "medium"
        result.mark_completed()

    except Exception as exc:
        logger.exception("Coordinator LLM call failed: %s", exc)
        result.mark_failed(str(exc))
        final_report = (
            "# ArthAI Research Report\n\n"
            "**Error:** The coordinator could not generate a synthesis report.\n\n"
            f"Reason: {exc}\n\n"
            "Please review the individual agent results."
        )

    new_state = merge_agent_result(state, result)
    new_state["final_report"] = final_report
    new_state["completed_at"] = datetime.utcnow().isoformat()
    if llm_provider_used:
        new_state["llm_provider_used"] = llm_provider_used

    return new_state
