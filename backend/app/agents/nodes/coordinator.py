"""
Research Coordinator Agent Node — final synthesis and report generation.

Responsibilities
----------------
- Validate that every requested ticker exists in the company universe.
- Collect structured findings from all specialist agents that ran.
- Detect cross-agent agreements and contradictions.
- Build a full markdown investment-research report with all required sections.
- Handle partial results (failed / skipped / unavailable agents) gracefully.
- Never override verified numerical data or fabricate conclusions from UNAVAILABLE agents.
"""

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


# ---------------------------------------------------------------------------
# Cross-agent synthesis helpers
# ---------------------------------------------------------------------------

def _extract_technical_bias(market_result: dict) -> str | None:
    """Return 'bullish' | 'bearish' | 'neutral' | None from market_analyst metrics."""
    metrics = market_result.get("supporting_metrics", {})
    for sym_data in metrics.values():
        if isinstance(sym_data, dict):
            trend = sym_data.get("trend_classification", "").lower()
            if trend:
                if "bullish" in trend:
                    return "bullish"
                if "bearish" in trend:
                    return "bearish"
                return "neutral"
    summary = market_result.get("summary", "").lower()
    if "bullish" in summary:
        return "bullish"
    if "bearish" in summary:
        return "bearish"
    return None


def _extract_fundamental_health(fundamental_result: dict) -> str | None:
    """Return 'strong' | 'weak' | 'mixed' | None from fundamental_analyst metrics."""
    metrics = fundamental_result.get("supporting_metrics", {})
    for sym_data in metrics.values():
        if isinstance(sym_data, dict):
            score = sym_data.get("fundamental_score")
            if score is not None:
                try:
                    s = float(score)
                    if s >= 60:
                        return "strong"
                    if s <= 40:
                        return "weak"
                    return "mixed"
                except (TypeError, ValueError):
                    pass
    summary = fundamental_result.get("summary", "").lower()
    if "strong" in summary or "solid" in summary or "healthy" in summary:
        return "strong"
    if "weak" in summary or "poor" in summary or "deteriorat" in summary:
        return "weak"
    return "mixed"


def _extract_news_sentiment(news_result: dict) -> str | None:
    """Return 'positive' | 'negative' | 'neutral' | None from news_analyst metrics."""
    metrics = news_result.get("supporting_metrics", {})
    for sym_data in metrics.values():
        if isinstance(sym_data, dict):
            bias = sym_data.get("sentiment_bias", "")
            if bias:
                return bias.lower()
            score = sym_data.get("avg_sentiment_score")
            if score is not None:
                try:
                    s = float(score)
                    if s > 0.1:
                        return "positive"
                    if s < -0.1:
                        return "negative"
                    return "neutral"
                except (TypeError, ValueError):
                    pass
    return None


def _detect_conflicts(agent_results: dict[str, dict]) -> list[str]:
    """
    Identify meaningful contradictions between specialist agent findings.
    Returns a list of human-readable conflict descriptions.
    """
    conflicts: list[str] = []

    market = agent_results.get("market_analyst")
    fundamental = agent_results.get("fundamental_analyst")
    news = agent_results.get("news_analyst")
    ml = agent_results.get("ml_analyst")

    def _status_ok(r: dict | None) -> bool:
        return r is not None and r.get("status") == ExecutionStatus.COMPLETED.value

    tech_bias = _extract_technical_bias(market) if _status_ok(market) else None
    fund_health = _extract_fundamental_health(fundamental) if _status_ok(fundamental) else None
    news_sent = _extract_news_sentiment(news) if _status_ok(news) else None

    # Technical vs Fundamental conflict
    if tech_bias == "bullish" and fund_health == "weak":
        conflicts.append(
            "⚠️ Technical signals are bullish while fundamental analysis indicates weak financial health. "
            "Price momentum may not be supported by earnings quality or balance-sheet strength."
        )
    elif tech_bias == "bearish" and fund_health == "strong":
        conflicts.append(
            "⚠️ Technical signals are bearish despite strong fundamentals. "
            "The price decline may represent a temporary market dislocation or sector-wide pressure."
        )

    # Technical vs News conflict
    if tech_bias == "bullish" and news_sent == "negative":
        conflicts.append(
            "⚠️ Bullish price action conflicts with negative recent news sentiment. "
            "If negative news catalysts are material, the technical trend may reverse."
        )
    elif tech_bias == "bearish" and news_sent == "positive":
        conflicts.append(
            "⚠️ Bearish technical trend despite positive news sentiment. "
            "Positive news may already be priced in, or broader market conditions may be overriding."
        )

    # ML vs Technical conflict
    if _status_ok(ml):
        ml_metrics = ml.get("supporting_metrics", {})
        for sym_data in ml_metrics.values():
            if isinstance(sym_data, dict) and sym_data.get("status") != "UNAVAILABLE":
                ml_direction = sym_data.get("predicted_direction", "").lower()
                if ml_direction == "positive" and tech_bias == "bearish":
                    conflicts.append(
                        "⚠️ ML model predicts positive direction but technical indicators are bearish. "
                        "Models may be using historical feature regimes that differ from current conditions."
                    )
                elif ml_direction == "negative" and tech_bias == "bullish":
                    conflicts.append(
                        "⚠️ ML model predicts negative direction despite bullish technical signals. "
                        "Consider that ML predictions reflect probability estimates, not certainties."
                    )
                break

    return conflicts


def _detect_agreements(agent_results: dict[str, dict]) -> list[str]:
    """Identify signals where multiple agents agree, increasing conviction."""
    agreements: list[str] = []

    market = agent_results.get("market_analyst")
    fundamental = agent_results.get("fundamental_analyst")
    news = agent_results.get("news_analyst")

    def _status_ok(r: dict | None) -> bool:
        return r is not None and r.get("status") == ExecutionStatus.COMPLETED.value

    tech_bias = _extract_technical_bias(market) if _status_ok(market) else None
    fund_health = _extract_fundamental_health(fundamental) if _status_ok(fundamental) else None
    news_sent = _extract_news_sentiment(news) if _status_ok(news) else None

    if tech_bias == "bullish" and fund_health == "strong" and news_sent == "positive":
        agreements.append(
            "✅ All three primary signals agree: bullish technicals + strong fundamentals + positive news. "
            "This multi-signal alignment may indicate higher-conviction opportunity, subject to risk considerations."
        )
    elif tech_bias == "bearish" and fund_health == "weak" and news_sent == "negative":
        agreements.append(
            "✅ All three primary signals converge negatively: bearish technicals + weak fundamentals + negative news. "
            "Multi-agent alignment on the downside warrants careful risk management."
        )
    elif tech_bias == "bullish" and fund_health == "strong":
        agreements.append("✅ Bullish technicals supported by strong fundamentals — positive technical-fundamental alignment.")
    elif tech_bias == "bearish" and news_sent == "negative":
        agreements.append("✅ Bearish technical trend aligned with negative news sentiment.")
    elif fund_health == "strong" and news_sent == "positive":
        agreements.append("✅ Strong fundamental health aligned with positive news sentiment.")

    return agreements


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def _build_report_sections(
    state: GraphState,
    agent_results: dict[str, dict],
    conflicts: list[str],
    agreements: list[str],
) -> str:
    """
    Build the full markdown report from structured agent findings.
    Does NOT call the LLM — uses agent-verified data only for metrics.
    The LLM is called separately for the Executive Summary section.
    """
    tickers = state.get("tickers", [])
    user_request = state.get("user_request", "")
    run_id = state.get("run_id", "")
    scope = state.get("scope", "standard")
    started_at = state.get("started_at", "")
    all_sources: list[str] = state.get("evidence_sources", [])
    all_warnings: list[str] = state.get("warnings", [])

    # Identify which companies were validated
    validated_tickers = state.get("validated_tickers", tickers)
    unknown_tickers = state.get("unknown_tickers", [])

    lines: list[str] = []

    # Header
    lines.append("# 🔍 ArthAI Multi-Agent Research Report")
    lines.append(f"\n**Request:** {user_request}")
    lines.append(f"**Tickers:** {', '.join(tickers)}")
    lines.append(f"**Analysis scope:** {scope.upper()}")
    lines.append(f"**Run ID:** `{run_id}`")
    lines.append(f"**Generated:** {started_at[:19].replace('T', ' ')} UTC\n")
    lines.append("---\n")

    # 1. Company identification / ticker validation
    lines.append("## 1. Company Identification")
    if validated_tickers:
        lines.append(f"The following ticker(s) were found in the ArthAI company universe: **{', '.join(validated_tickers)}**.")
    if unknown_tickers:
        lines.append(
            f"\n> ⚠️ **Unknown tickers:** {', '.join(unknown_tickers)} — not found in the company database. "
            "Analysis for these tickers was skipped."
        )
    lines.append("")

    # 2. Market & Technical Analysis
    lines.append("## 2. Market & Technical Analysis")
    _append_agent_section(lines, agent_results, "market_analyst", "Market Analyst")
    lines.append("")

    # 3. Fundamental Analysis
    lines.append("## 3. Fundamental Analysis")
    _append_agent_section(lines, agent_results, "fundamental_analyst", "Fundamental Analyst")
    lines.append("")

    # 4. News & Event Analysis
    lines.append("## 4. News & Event Analysis")
    _append_agent_section(lines, agent_results, "news_analyst", "News Analyst")
    lines.append("")

    # 5. ML Predictions
    lines.append("## 5. ML Predictions")
    _append_agent_section(lines, agent_results, "ml_analyst", "ML Analyst")
    lines.append("")

    # 6. Risk Assessment
    lines.append("## 6. Risk Assessment")
    _append_agent_section(lines, agent_results, "risk_analyst", "Risk Analyst")
    lines.append("")

    # 7. Cross-Agent Synthesis
    lines.append("## 7. Cross-Agent Synthesis")

    if agreements:
        lines.append("\n### Areas of Agreement")
        for a in agreements:
            lines.append(f"\n{a}")

    if conflicts:
        lines.append("\n### Conflicting Findings")
        for c in conflicts:
            lines.append(f"\n{c}")

    if not agreements and not conflicts:
        lines.append(
            "_Insufficient agent results to perform cross-agent synthesis. "
            "Run with STANDARD or DEEP scope for comprehensive analysis._"
        )
    lines.append("")

    # 8. Missing Information
    all_missing: list[str] = []
    for ar_dict in agent_results.values():
        all_missing.extend(ar_dict.get("missing_information", []))

    lines.append("## 8. Missing Information & Data Gaps")
    if all_missing:
        for m in sorted(set(all_missing)):
            lines.append(f"- {m}")
    else:
        lines.append("_No significant data gaps identified by specialist agents._")
    lines.append("")

    # 9. Data Sources & Timestamps
    lines.append("## 9. Data Sources & Timestamps")
    if all_sources:
        for src in sorted(set(all_sources)):
            lines.append(f"- `{src}`")
    else:
        lines.append("_No explicit sources recorded._")
    lines.append("")

    # 10. Overall Confidence & Limitations
    lines.append("## 10. Overall Confidence & Limitations")
    confidence_scores = {
        "high": 3, "medium": 2, "low": 1
    }
    confidences = [
        ar_dict.get("confidence", "low")
        for ar_dict in agent_results.values()
        if ar_dict.get("status") == ExecutionStatus.COMPLETED.value
    ]
    if confidences:
        avg = sum(confidence_scores.get(c, 1) for c in confidences) / len(confidences)
        overall = "high" if avg >= 2.5 else ("medium" if avg >= 1.5 else "low")
        lines.append(f"**Overall report confidence:** `{overall}`\n")
        lines.append(f"Based on {len(confidences)} completed specialist agent(s).")
    else:
        lines.append("**Overall report confidence:** `low` — no agents completed successfully.")

    if all_warnings:
        lines.append("\n**Warnings & Caveats:**")
        for w in sorted(set(all_warnings)):
            lines.append(f"- {w}")
    lines.append("")

    # 11. Disclaimer
    lines.append("## 11. Financial Disclaimer")
    lines.append(
        "> This report is generated by an AI system (ArthAI) and does not constitute investment advice, "
        "financial guidance, or a recommendation to buy, sell, or hold any security. "
        "All data is sourced from the ArthAI database and is subject to the limitations of the underlying data providers. "
        "Past performance, technical signals, and ML predictions are not guarantees of future results. "
        "Always verify with official sources and consult a qualified financial professional before making investment decisions."
    )

    return "\n".join(lines)


def _append_agent_section(
    lines: list[str],
    agent_results: dict[str, dict],
    agent_key: str,
    display_name: str,
) -> None:
    """Append a formatted section for a single agent to the lines list."""
    ar_dict = agent_results.get(agent_key)
    if ar_dict is None:
        lines.append(f"_No result recorded for {display_name} — agent may not have been selected._")
        return

    status = ar_dict.get("status", "unknown")
    confidence = ar_dict.get("confidence", "unknown")
    summary = ar_dict.get("summary", "")
    key_findings = ar_dict.get("key_findings", [])
    warnings = ar_dict.get("warnings", [])
    missing = ar_dict.get("missing_information", [])

    if status == ExecutionStatus.SKIPPED.value:
        lines.append(f"_⏭️ {display_name} was not selected for this analysis scope._")
        return

    if status == ExecutionStatus.FAILED.value:
        err = ar_dict.get("error_message", "Unknown error")
        lines.append(f"_❌ {display_name} failed: {err}_")
        return

    # Completed or partial
    status_icon = "✅" if status == ExecutionStatus.COMPLETED.value else "⚠️"
    lines.append(f"{status_icon} **Status:** {status.capitalize()} | **Confidence:** {confidence}\n")

    if summary:
        lines.append(f"**Summary:** {summary}\n")

    if key_findings:
        lines.append("**Key Findings:**")
        for finding in key_findings:
            lines.append(f"- {finding}")
        lines.append("")

    if missing:
        lines.append("**Data Gaps:**")
        for m in missing:
            lines.append(f"- _{m}_")
        lines.append("")

    if warnings:
        lines.append("**Warnings:**")
        for w in warnings:
            lines.append(f"- _{w}_")


# ---------------------------------------------------------------------------
# Main coordinator node
# ---------------------------------------------------------------------------

def coordinator_node(state: GraphState) -> GraphState:
    """
    Research Coordinator: synthesise all specialist agent findings into a full
    markdown investment-research report.

    Steps:
    1. Collect all completed/failed/skipped agent results.
    2. Detect cross-agent agreements and contradictions.
    3. Build structured markdown report from verified data.
    4. Call LLM to generate a concise Executive Summary section.
    5. Prepend Executive Summary to the report and store in state.
    """
    result = AgentResult(agent_name=AgentName.COORDINATOR)
    result.mark_running()

    agent_results: dict[str, Any] = state.get("agent_results", {})

    # ------------------------------------------------------------------
    # Step 1: Cross-agent analysis (fully deterministic — no LLM)
    # ------------------------------------------------------------------
    conflicts = _detect_conflicts(agent_results)
    agreements = _detect_agreements(agent_results)
    logger.info(
        "Coordinator: %d agreements, %d conflicts detected.",
        len(agreements), len(conflicts),
    )

    # ------------------------------------------------------------------
    # Step 2: Build structured markdown report (data-grounded, no LLM)
    # ------------------------------------------------------------------
    structured_report = _build_report_sections(state, agent_results, conflicts, agreements)

    # ------------------------------------------------------------------
    # Step 3: LLM — generate Executive Summary only
    # ------------------------------------------------------------------
    summaries_for_llm: list[str] = []
    for agent_key, ar_dict in agent_results.items():
        status = ar_dict.get("status", "unknown")
        if status not in (ExecutionStatus.COMPLETED.value, ExecutionStatus.SKIPPED.value):
            summaries_for_llm.append(
                f"## {agent_key.upper()}\nStatus: {status} — no findings available."
            )
            continue
        if status == ExecutionStatus.SKIPPED.value:
            continue

        findings_text = "\n".join(
            f"- {f}" for f in ar_dict.get("key_findings", [])
        ) or "None reported."
        summaries_for_llm.append(
            f"## {agent_key.upper()}\n"
            f"Summary: {ar_dict.get('summary', 'N/A')}\n"
            f"Confidence: {ar_dict.get('confidence', 'unknown')}\n"
            f"Key findings:\n{findings_text}\n"
            f"Warnings: {'; '.join(ar_dict.get('warnings', []))}\n"
            f"Missing: {'; '.join(ar_dict.get('missing_information', []))}"
        )

    conflict_text = "\n".join(conflicts) if conflicts else "None identified."
    agreement_text = "\n".join(agreements) if agreements else "None identified."

    exec_summary_prompt = (
        f"User research request: {state.get('user_request', '')}\n"
        f"Tickers: {', '.join(state.get('tickers', []))}\n\n"
        f"Agent findings:\n\n{''.join(summaries_for_llm)}\n\n"
        f"Cross-agent agreements:\n{agreement_text}\n\n"
        f"Cross-agent conflicts:\n{conflict_text}\n\n"
        "Write a concise Executive Summary (3-5 sentences) for an investment research report. "
        "Integrate ONLY the information the agents reported — do not introduce new data, estimates, or opinions. "
        "Acknowledge conflicts if present. Do not make buy/sell recommendations. "
        "Output only the summary paragraph — no headings, no JSON."
    )

    exec_summary = ""
    llm_provider_used = None

    try:
        llm = get_agent_llm_service()
        response = llm.generate(
            prompt=exec_summary_prompt,
            system_prompt=COORDINATOR_SYSTEM,
            temperature=0.2,
            max_tokens=512,
        )
        exec_summary = response.content.strip()
        llm_provider_used = response.provider.value
        logger.info("Coordinator: Executive Summary generated via %s.", llm_provider_used)

    except Exception as exc:
        logger.warning("Coordinator: LLM call failed for Executive Summary: %s", exc)
        exec_summary = (
            "Executive Summary could not be generated due to an LLM service error. "
            "Please refer to the individual agent sections below for verified findings."
        )
        result.warnings.append(f"Executive Summary LLM call failed: {exc}")

    # ------------------------------------------------------------------
    # Step 4: Compose final report — Executive Summary first, then sections
    # ------------------------------------------------------------------
    exec_section = (
        "## Executive Summary\n\n"
        f"{exec_summary}\n\n"
        "---\n"
    )
    final_report = exec_section + "\n" + structured_report

    # ------------------------------------------------------------------
    # Step 5: Populate coordinator AgentResult
    # ------------------------------------------------------------------
    completed_agents = [
        k for k, v in agent_results.items()
        if v.get("status") == ExecutionStatus.COMPLETED.value
    ]
    result.summary = f"Research report synthesised from {len(completed_agents)} completed agent(s)."
    result.key_findings = [
        f"Completed agents: {', '.join(completed_agents) or 'none'}",
        f"Agreements detected: {len(agreements)}",
        f"Conflicts detected: {len(conflicts)}",
    ]
    result.evidence_sources = list(state.get("evidence_sources", []))
    result.confidence = "medium" if completed_agents else "low"
    result.mark_completed()

    new_state = merge_agent_result(state, result)
    new_state["final_report"] = final_report
    new_state["completed_at"] = datetime.utcnow().isoformat()
    if llm_provider_used:
        new_state["llm_provider_used"] = llm_provider_used

    return new_state
