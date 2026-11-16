"""
Base helper for all specialist agent nodes.

Provides:
- ``BaseAgentNode``:  wraps error handling, status tracking, and state merging.
- ``merge_agent_result``: utility to fold an AgentResult back into GraphState.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.agents.state import AgentName, AgentResult, ExecutionStatus, GraphState
from app.agents.prompts import AGENT_RESULT_JSON_SCHEMA
from app.agents.dependencies import get_agent_llm_service

logger = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def merge_agent_result(state: GraphState, result: AgentResult) -> GraphState:
    """
    Merge a completed AgentResult into the graph state immutably.

    - Writes the serialised result to state["agent_results"][agent_name].
    - Updates state["agent_statuses"][agent_name].
    - Extends state["evidence_sources"] with any new sources.
    - Appends any errors/warnings to their respective lists.
    """
    agent_key = result.agent_name.value

    agent_results = dict(state.get("agent_results", {}))
    agent_results[agent_key] = result.to_dict()

    agent_statuses = dict(state.get("agent_statuses", {}))
    agent_statuses[agent_key] = result.status.value

    # Deduplicate evidence sources
    existing_sources = list(state.get("evidence_sources", []))
    new_sources = [s for s in result.evidence_sources if s not in existing_sources]
    evidence_sources = existing_sources + new_sources

    errors = list(state.get("errors", []))
    if result.error_message:
        errors.append(f"[{agent_key}] {result.error_message}")

    warnings = list(state.get("warnings", []))
    for w in result.warnings:
        warnings.append(f"[{agent_key}] {w}")

    return {
        **state,
        "agent_results": agent_results,
        "agent_statuses": agent_statuses,
        "evidence_sources": evidence_sources,
        "errors": errors,
        "warnings": warnings,
    }


def _parse_llm_json(raw: str) -> dict[str, Any]:
    """
    Extract the first JSON object from an LLM response string.
    Handles both bare JSON and markdown code-fenced JSON.
    """
    m = _JSON_BLOCK_RE.search(raw)
    if m:
        raw = m.group(1)

    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start : end + 1]

    return json.loads(raw)


class BaseAgentNode:
    """
    Reusable base for specialist agent nodes.

    Subclasses implement ``_gather_data`` and ``_build_prompt``.
    The ``__call__`` method orchestrates the full node lifecycle.
    """

    agent_name: AgentName
    system_prompt: str

    def __call__(self, state: GraphState) -> GraphState:
        result = AgentResult(agent_name=self.agent_name)

        # Skip if not selected
        selected = state.get("selected_agents", [])
        if self.agent_name.value not in selected:
            result.mark_skipped("Not selected for this run.")
            return merge_agent_result(state, result)

        result.mark_running()
        logger.info("Agent [%s] starting.", self.agent_name.value)

        try:
            data = self._gather_data(state)
            prompt = self._build_prompt(state, data)
            llm_response = self._call_llm(prompt)
            self._populate_result(result, llm_response, data)
            result.mark_completed()
            logger.info("Agent [%s] completed.", self.agent_name.value)

        except Exception as exc:
            logger.exception("Agent [%s] failed: %s", self.agent_name.value, exc)
            result.mark_failed(str(exc))

        return merge_agent_result(state, result)

    # ------------------------------------------------------------------
    # Overridable hooks
    # ------------------------------------------------------------------

    def _gather_data(self, state: GraphState) -> dict[str, Any]:
        """Retrieve domain data from DB / services. Must NOT store a Session in state."""
        raise NotImplementedError

    def _build_prompt(self, state: GraphState, data: dict[str, Any]) -> str:
        """Construct the user-turn prompt from state + gathered data."""
        raise NotImplementedError

    def _populate_result(
        self,
        result: AgentResult,
        llm_response: str,
        data: dict[str, Any],
    ) -> None:
        """Parse LLM output and fill result fields."""
        try:
            parsed = _parse_llm_json(llm_response)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Agent [%s]: could not parse LLM JSON (%s). Storing raw text.",
                self.agent_name.value, exc,
            )
            result.summary = llm_response[:2000]
            result.warnings.append("LLM response was not valid JSON.")
            return

        result.summary = parsed.get("summary", "")
        result.key_findings = parsed.get("key_findings", [])
        result.supporting_metrics = parsed.get("supporting_metrics", {})
        result.evidence_sources = parsed.get("evidence_sources", [])
        result.data_timestamps = parsed.get("data_timestamps", {})
        result.confidence = parsed.get("confidence", "low")
        result.missing_information = parsed.get("missing_information", [])
        result.warnings = parsed.get("warnings", [])

    # ------------------------------------------------------------------
    # LLM helper
    # ------------------------------------------------------------------

    def _call_llm(self, prompt: str) -> str:
        llm = get_agent_llm_service()
        response = llm.generate(
            prompt=prompt,
            system_prompt=self.system_prompt + "\n\n" + AGENT_RESULT_JSON_SCHEMA,
            temperature=0.2,
            max_tokens=2048,
        )
        return response.content
