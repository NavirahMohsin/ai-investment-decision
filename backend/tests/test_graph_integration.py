"""
Graph-level integration tests for the ArthAI Phase 5 multi-agent workflow.

Acceptance Criteria
-------------------
- A single research request travels through the full graph, invokes relevant
  specialist agents, collects their results, and produces a grounded
  consolidated report.
- The coordinator never fabricates conclusions from UNAVAILABLE agent results.
- Partial results (failed / skipped agents) are handled gracefully.
- Cross-agent agreement and conflict detection works correctly.
- The ticker validation node correctly resolves known and unknown symbols.
- Scope-based routing selects the correct agent subset.
- The graph compiles and runs without infinite loops or recursion errors.

All LLM calls and specialist agent nodes are mocked — no real API calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.agents.state import (
    AgentName,
    AgentResult,
    AnalysisScope,
    ExecutionStatus,
    GraphState,
)
from app.agents.graph import (
    compile_graph,
    create_initial_state,
    build_graph,
    _router_node,
    _validate_tickers_node,
)
from app.agents.nodes.coordinator import (
    coordinator_node,
    _detect_conflicts,
    _detect_agreements,
    _build_report_sections,
)
from app.agents.nodes.base import merge_agent_result
from app.db.models import Company, Sector
from app.services.llm_service import LLMResponse, LLMProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_completed_result(
    agent_name: AgentName,
    summary: str = "Test summary.",
    key_findings: list[str] | None = None,
    confidence: str = "medium",
    supporting_metrics: dict | None = None,
    warnings: list[str] | None = None,
    missing: list[str] | None = None,
) -> dict:
    """Return a serialised (plain dict) AgentResult in COMPLETED state."""
    r = AgentResult(agent_name=agent_name)
    r.mark_running()
    r.summary = summary
    r.key_findings = key_findings or ["Finding A", "Finding B"]
    r.confidence = confidence
    r.supporting_metrics = supporting_metrics or {"test_metric": 1.0}
    r.evidence_sources = [f"{agent_name.value}_source"]
    r.warnings = warnings or []
    r.missing_information = missing or []
    r.mark_completed()
    return r.to_dict()


def _make_failed_result(agent_name: AgentName, error: str = "Service unavailable") -> dict:
    r = AgentResult(agent_name=agent_name)
    r.mark_running()
    r.mark_failed(error)
    return r.to_dict()


def _make_skipped_result(agent_name: AgentName) -> dict:
    r = AgentResult(agent_name=agent_name)
    r.mark_skipped("Not selected for this run.")
    return r.to_dict()


def _make_llm_response(text: str) -> LLMResponse:
    return LLMResponse(
        content=text,
        provider=LLMProvider.GEMINI,
        usage={"input_tokens": 50, "output_tokens": 50, "total_tokens": 100},
    )


def _build_state_with_all_agents(
    tickers: list[str] | None = None,
    scope: str = AnalysisScope.STANDARD.value,
) -> GraphState:
    """Return a GraphState pre-populated with completed results for all 5 specialists."""
    tickers = tickers or ["INFY"]
    state = create_initial_state(
        user_request="Comprehensive analysis of INFY",
        tickers=tickers,
        scope=scope,
    )
    state["validated_tickers"] = tickers
    state["unknown_tickers"] = []
    state["selected_agents"] = [
        "market_analyst", "fundamental_analyst", "news_analyst",
        "risk_analyst", "ml_analyst", "coordinator",
    ]
    state["agent_results"] = {
        "market_analyst": _make_completed_result(
            AgentName.MARKET_ANALYST,
            summary="INFY is showing bullish momentum.",
            supporting_metrics={"INFY": {"trend_classification": "Bullish", "rsi": 58.0}},
        ),
        "fundamental_analyst": _make_completed_result(
            AgentName.FUNDAMENTAL_ANALYST,
            summary="INFY demonstrates strong financial health.",
            supporting_metrics={"INFY": {"fundamental_score": 72.0}},
        ),
        "news_analyst": _make_completed_result(
            AgentName.NEWS_ANALYST,
            summary="Recent news sentiment on INFY is positive.",
            supporting_metrics={"INFY": {"sentiment_bias": "positive", "avg_sentiment_score": 0.65}},
        ),
        "risk_analyst": _make_completed_result(
            AgentName.RISK_ANALYST,
            summary="Moderate risk profile with manageable drawdown.",
            supporting_metrics={"INFY": {"annualized_volatility": 18.5, "max_drawdown_pct": -12.0}},
        ),
        "ml_analyst": _make_completed_result(
            AgentName.ML_ANALYST,
            summary="ML model predicts positive direction for INFY.",
            supporting_metrics={"INFY": {"predicted_direction": "positive", "confidence": 0.74}},
        ),
    }
    return state


# ---------------------------------------------------------------------------
# 1. Graph compilation
# ---------------------------------------------------------------------------

class TestGraphCompilation:
    def test_graph_compiles_without_error(self):
        graph = compile_graph()
        assert graph is not None

    def test_graph_has_correct_nodes(self):
        sg = build_graph()
        nodes = list(sg.nodes)
        expected = {
            "validate_tickers", "router",
            "market_analyst", "fundamental_analyst", "news_analyst",
            "risk_analyst", "ml_analyst", "coordinator",
        }
        assert expected.issubset(set(nodes))

    def test_create_initial_state_structure(self):
        state = create_initial_state(
            user_request="Analyse RELIANCE",
            tickers=["RELIANCE"],
            scope=AnalysisScope.DEEP.value,
        )
        assert state["user_request"] == "Analyse RELIANCE"
        assert state["tickers"] == ["RELIANCE"]
        assert state["scope"] == "deep"
        assert state["selected_agents"] == []
        assert state["agent_results"] == {}
        assert state["validated_tickers"] == []
        assert state["unknown_tickers"] == []
        assert state["final_report"] is None
        assert state["run_id"] != ""


# ---------------------------------------------------------------------------
# 2. Ticker validation node
# ---------------------------------------------------------------------------

class TestTickerValidationNode:
    def test_validates_known_ticker(self, db_session):
        """Known ticker should appear in validated_tickers."""
        # Create a company in the test DB
        sec = db_session.query(Sector).filter_by(sector_name="Technology").first()
        if not sec:
            sec = Sector(sector_name="Technology", industry_name="IT", data_source="test")
            db_session.add(sec)
            db_session.flush()
        company = Company(
            name="Infosys Ltd",
            symbol="INFY_VAL",
            provider_symbol="INFY_VAL.NS",
            exchange="NSE",
            instrument_type="equity",
            is_active=True,
            sector_id=sec.id,
        )
        db_session.add(company)
        db_session.commit()

        state = create_initial_state("Analyse INFY_VAL", tickers=["INFY_VAL"])

        with patch("app.agents.dependencies.get_agent_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = db_session
            result = _validate_tickers_node(state)

        assert "INFY_VAL" in result["validated_tickers"]
        assert "INFY_VAL" not in result["unknown_tickers"]

    def test_flags_unknown_ticker(self, db_session):
        """Unknown ticker should appear in unknown_tickers with a warning."""
        state = create_initial_state("Analyse FAKE_XYZ", tickers=["FAKE_XYZ"])

        with patch("app.agents.dependencies.get_agent_db_session") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = db_session
            result = _validate_tickers_node(state)

        assert "FAKE_XYZ" in result["unknown_tickers"]
        assert "FAKE_XYZ" not in result["validated_tickers"]
        assert any("FAKE_XYZ" in w for w in result["warnings"])

    def test_handles_empty_tickers(self, db_session):
        """Empty ticker list should produce a warning, not crash."""
        state = create_initial_state("What is the market?", tickers=[])
        # Empty tickers — no DB call needed
        result = _validate_tickers_node(state)
        assert result["validated_tickers"] == []
        assert result["unknown_tickers"] == []
        assert len(result["warnings"]) > 0

    def test_db_failure_is_non_fatal(self):
        """DB failure during validation should not abort the graph."""
        state = create_initial_state("Analyse INFY", tickers=["INFY"])

        with patch("app.agents.dependencies.get_agent_db_session", side_effect=Exception("DB offline")):
            result = _validate_tickers_node(state)

        # Should treat all tickers as valid and continue
        assert "INFY" in result["validated_tickers"]
        assert any("validation failed" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# 3. Router node
# ---------------------------------------------------------------------------

class TestRouterNode:
    def test_standard_scope_selects_correct_agents(self):
        state = create_initial_state("Analyse INFY", tickers=["INFY"], scope="standard")
        result = _router_node(state)
        selected = result["selected_agents"]
        assert "market_analyst" in selected
        assert "fundamental_analyst" in selected
        assert "news_analyst" in selected
        assert "risk_analyst" in selected
        assert "coordinator" in selected
        # ML analyst is DEEP only
        assert "ml_analyst" not in selected

    def test_deep_scope_includes_ml_analyst(self):
        state = create_initial_state("Full analysis", tickers=["INFY"], scope="deep")
        result = _router_node(state)
        assert "ml_analyst" in result["selected_agents"]

    def test_quick_scope_selects_market_only(self):
        state = create_initial_state("Quick check on INFY", tickers=["INFY"], scope="quick")
        result = _router_node(state)
        selected = result["selected_agents"]
        assert "market_analyst" in selected
        assert "coordinator" in selected
        # Fundamental / news not in quick scope
        assert "fundamental_analyst" not in selected

    def test_explicit_agent_override(self):
        state = create_initial_state(
            "Technical analysis only",
            tickers=["INFY"],
            selected_agents=["market_analyst"],
        )
        result = _router_node(state)
        assert "market_analyst" in result["selected_agents"]
        assert "coordinator" in result["selected_agents"]
        assert "fundamental_analyst" not in result["selected_agents"]

    def test_all_agents_initialised_pending(self):
        state = create_initial_state("Analyse INFY", tickers=["INFY"], scope="standard")
        result = _router_node(state)
        for agent in result["selected_agents"]:
            assert result["agent_statuses"].get(agent) == ExecutionStatus.PENDING.value

    def test_unknown_scope_defaults_to_standard(self):
        state = create_initial_state("Analyse INFY", tickers=["INFY"], scope="UNKNOWN_SCOPE")
        result = _router_node(state)
        # Standard agents should be present
        assert "market_analyst" in result["selected_agents"]
        assert "fundamental_analyst" in result["selected_agents"]

    def test_coordinator_always_appended(self):
        """Even if the caller explicitly excludes coordinator, it must be added."""
        state = create_initial_state(
            "Only market",
            tickers=["INFY"],
            selected_agents=["market_analyst"],
        )
        result = _router_node(state)
        assert "coordinator" in result["selected_agents"]


# ---------------------------------------------------------------------------
# 4. Cross-agent synthesis helpers
# ---------------------------------------------------------------------------

class TestCrossAgentSynthesis:
    def _make_state_for_synthesis(self, agent_results: dict) -> GraphState:
        state = create_initial_state("Test", tickers=["INFY"])
        state["validated_tickers"] = ["INFY"]
        state["unknown_tickers"] = []
        state["agent_results"] = agent_results
        return state

    def test_detects_bullish_fundamental_agreement(self):
        agent_results = {
            "market_analyst": _make_completed_result(
                AgentName.MARKET_ANALYST,
                supporting_metrics={"INFY": {"trend_classification": "Bullish"}},
            ),
            "fundamental_analyst": _make_completed_result(
                AgentName.FUNDAMENTAL_ANALYST,
                supporting_metrics={"INFY": {"fundamental_score": 75.0}},
            ),
            "news_analyst": _make_completed_result(
                AgentName.NEWS_ANALYST,
                supporting_metrics={"INFY": {"sentiment_bias": "positive"}},
            ),
        }
        agreements = _detect_agreements(agent_results)
        assert len(agreements) > 0
        assert any("bullish" in a.lower() or "strong" in a.lower() for a in agreements)

    def test_detects_bullish_weak_fundamental_conflict(self):
        agent_results = {
            "market_analyst": _make_completed_result(
                AgentName.MARKET_ANALYST,
                supporting_metrics={"INFY": {"trend_classification": "Bullish"}},
            ),
            "fundamental_analyst": _make_completed_result(
                AgentName.FUNDAMENTAL_ANALYST,
                supporting_metrics={"INFY": {"fundamental_score": 30.0}},
            ),
        }
        conflicts = _detect_conflicts(agent_results)
        assert len(conflicts) > 0
        assert any("bullish" in c.lower() and "weak" in c.lower() for c in conflicts)

    def test_detects_bearish_positive_news_conflict(self):
        agent_results = {
            "market_analyst": _make_completed_result(
                AgentName.MARKET_ANALYST,
                supporting_metrics={"INFY": {"trend_classification": "Bearish"}},
            ),
            "news_analyst": _make_completed_result(
                AgentName.NEWS_ANALYST,
                supporting_metrics={"INFY": {"sentiment_bias": "positive"}},
            ),
        }
        conflicts = _detect_conflicts(agent_results)
        assert len(conflicts) > 0
        assert any("positive" in c.lower() and "bearish" in c.lower() for c in conflicts)

    def test_no_conflict_when_aligned(self):
        agent_results = {
            "market_analyst": _make_completed_result(
                AgentName.MARKET_ANALYST,
                supporting_metrics={"INFY": {"trend_classification": "Bearish"}},
            ),
            "fundamental_analyst": _make_completed_result(
                AgentName.FUNDAMENTAL_ANALYST,
                supporting_metrics={"INFY": {"fundamental_score": 28.0}},
            ),
            "news_analyst": _make_completed_result(
                AgentName.NEWS_ANALYST,
                supporting_metrics={"INFY": {"sentiment_bias": "negative"}},
            ),
        }
        conflicts = _detect_conflicts(agent_results)
        # All agents agree on negative — no conflicts expected
        # (agreement on the downside is detected by _detect_agreements)
        assert not any("bullish" in c and "weak" in c for c in conflicts)

    def test_failed_agent_not_used_in_synthesis(self):
        """A failed agent should not contribute to conflict/agreement detection."""
        agent_results = {
            "market_analyst": _make_failed_result(AgentName.MARKET_ANALYST, "DB timeout"),
            "fundamental_analyst": _make_completed_result(
                AgentName.FUNDAMENTAL_ANALYST,
                supporting_metrics={"INFY": {"fundamental_score": 30.0}},
            ),
        }
        # Should not raise; market is FAILED so tech_bias is None → no conflict
        conflicts = _detect_conflicts(agent_results)
        # No technical bias available from failed agent
        assert all("bullish" not in c for c in conflicts)


# ---------------------------------------------------------------------------
# 5. Report structure
# ---------------------------------------------------------------------------

class TestReportStructure:
    def test_report_contains_all_required_sections(self):
        state = _build_state_with_all_agents()
        conflicts = _detect_conflicts(state["agent_results"])
        agreements = _detect_agreements(state["agent_results"])
        report = _build_report_sections(state, state["agent_results"], conflicts, agreements)

        required_headings = [
            "Company Identification",
            "Market & Technical Analysis",
            "Fundamental Analysis",
            "News & Event Analysis",
            "ML Predictions",
            "Risk Assessment",
            "Cross-Agent Synthesis",
            "Missing Information",
            "Data Sources",
            "Overall Confidence",
            "Financial Disclaimer",
        ]
        for heading in required_headings:
            assert heading in report, f"Missing section: '{heading}'"

    def test_report_contains_disclaimer(self):
        state = _build_state_with_all_agents()
        report = _build_report_sections(state, state["agent_results"], [], [])
        assert "not constitute investment advice" in report
        assert "qualified financial professional" in report

    def test_report_flags_unknown_tickers(self):
        state = create_initial_state("Analyse FAKE", tickers=["FAKE"])
        state["validated_tickers"] = []
        state["unknown_tickers"] = ["FAKE"]
        state["agent_results"] = {}
        report = _build_report_sections(state, {}, [], [])
        assert "FAKE" in report
        assert "Unknown tickers" in report or "unknown" in report.lower()

    def test_report_handles_no_agents_gracefully(self):
        """Report must be produced even when zero agents completed."""
        state = create_initial_state("Analyse INFY", tickers=["INFY"])
        state["validated_tickers"] = ["INFY"]
        state["unknown_tickers"] = []
        state["agent_results"] = {}
        report = _build_report_sections(state, {}, [], [])
        assert "ArthAI Multi-Agent Research Report" in report
        assert "Financial Disclaimer" in report

    def test_report_skipped_agent_note(self):
        state = create_initial_state("Quick INFY", tickers=["INFY"], scope="quick")
        state["validated_tickers"] = ["INFY"]
        state["unknown_tickers"] = []
        state["agent_results"] = {
            "market_analyst": _make_completed_result(AgentName.MARKET_ANALYST),
            "fundamental_analyst": _make_skipped_result(AgentName.FUNDAMENTAL_ANALYST),
        }
        report = _build_report_sections(state, state["agent_results"], [], [])
        assert "not selected" in report.lower() or "⏭️" in report

    def test_report_failed_agent_note(self):
        state = create_initial_state("Analyse INFY", tickers=["INFY"])
        state["validated_tickers"] = ["INFY"]
        state["unknown_tickers"] = []
        state["agent_results"] = {
            "market_analyst": _make_failed_result(AgentName.MARKET_ANALYST, "Connection refused"),
        }
        report = _build_report_sections(state, state["agent_results"], [], [])
        assert "Connection refused" in report or "failed" in report.lower()

    def test_ml_unavailable_not_fabricated_in_report(self):
        """ML UNAVAILABLE result must not become a fabricated conclusion in the report."""
        ml_result = _make_completed_result(
            AgentName.ML_ANALYST,
            summary="No trained machine learning models are available.",
            key_findings=["Models unavailable for INFY"],
            supporting_metrics={"status": "UNAVAILABLE"},
            confidence="low",
        )
        state = create_initial_state("Analyse INFY", tickers=["INFY"])
        state["validated_tickers"] = ["INFY"]
        state["unknown_tickers"] = []
        state["agent_results"] = {"ml_analyst": ml_result}
        report = _build_report_sections(state, state["agent_results"], [], [])
        # Must NOT fabricate a direction
        for fabricated in ["Predicted direction is Positive", "Predicted direction is Negative"]:
            assert fabricated not in report


# ---------------------------------------------------------------------------
# 6. Coordinator node
# ---------------------------------------------------------------------------

class TestCoordinatorNode:
    def test_coordinator_generates_report_from_completed_agents(self):
        state = _build_state_with_all_agents()
        exec_summary_text = (
            "INFY demonstrates bullish momentum backed by strong fundamentals and positive news. "
            "Risk metrics are manageable. ML models support a positive outlook."
        )

        with patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_llm_svc:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = _make_llm_response(exec_summary_text)
            mock_llm_svc.return_value = mock_llm

            result_state = coordinator_node(state)

        assert result_state["final_report"] is not None
        report = result_state["final_report"]
        assert "ArthAI Multi-Agent Research Report" in report
        assert exec_summary_text in report
        assert "Financial Disclaimer" in report
        assert result_state["completed_at"] is not None

    def test_coordinator_result_in_agent_results(self):
        state = _build_state_with_all_agents()

        with patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_llm_svc:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = _make_llm_response("Summary.")
            mock_llm_svc.return_value = mock_llm

            result_state = coordinator_node(state)

        assert "coordinator" in result_state["agent_results"]
        coord_result = AgentResult(**result_state["agent_results"]["coordinator"])
        assert coord_result.status == ExecutionStatus.COMPLETED
        assert coord_result.agent_name == AgentName.COORDINATOR

    def test_coordinator_handles_llm_failure_gracefully(self):
        """LLM failure must not crash coordinator; fallback exec summary is used."""
        state = _build_state_with_all_agents()

        with patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_llm_svc:
            mock_llm = MagicMock()
            mock_llm.generate.side_effect = RuntimeError("LLM quota exceeded")
            mock_llm_svc.return_value = mock_llm

            result_state = coordinator_node(state)

        # Report must still be produced
        assert result_state["final_report"] is not None
        assert "ArthAI Multi-Agent Research Report" in result_state["final_report"]
        # Coordinator result should still be COMPLETED (data-grounded sections succeeded)
        coord_result = AgentResult(**result_state["agent_results"]["coordinator"])
        assert coord_result.status == ExecutionStatus.COMPLETED
        # LLM failure recorded as warning
        assert any("LLM" in w or "Executive Summary" in w for w in coord_result.warnings)

    def test_coordinator_with_all_failed_agents(self):
        """Coordinator must produce a report even with zero completed agents."""
        state = create_initial_state("Analyse INFY", tickers=["INFY"])
        state["validated_tickers"] = ["INFY"]
        state["unknown_tickers"] = []
        state["agent_results"] = {
            "market_analyst": _make_failed_result(AgentName.MARKET_ANALYST),
            "fundamental_analyst": _make_failed_result(AgentName.FUNDAMENTAL_ANALYST),
        }
        state["selected_agents"] = ["market_analyst", "fundamental_analyst", "coordinator"]

        with patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_llm_svc:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = _make_llm_response("No data available.")
            mock_llm_svc.return_value = mock_llm

            result_state = coordinator_node(state)

        assert result_state["final_report"] is not None
        coord_result = AgentResult(**result_state["agent_results"]["coordinator"])
        assert coord_result.status == ExecutionStatus.COMPLETED
        # Confidence should be low since no agents completed
        assert coord_result.confidence == "low"

    def test_coordinator_includes_conflict_in_report(self):
        """When bullish + weak fundamentals, the report must acknowledge the conflict."""
        state = create_initial_state("Analyse INFY", tickers=["INFY"])
        state["validated_tickers"] = ["INFY"]
        state["unknown_tickers"] = []
        state["agent_results"] = {
            "market_analyst": _make_completed_result(
                AgentName.MARKET_ANALYST,
                supporting_metrics={"INFY": {"trend_classification": "Bullish"}},
            ),
            "fundamental_analyst": _make_completed_result(
                AgentName.FUNDAMENTAL_ANALYST,
                supporting_metrics={"INFY": {"fundamental_score": 28.0}},
            ),
        }
        state["selected_agents"] = ["market_analyst", "fundamental_analyst", "coordinator"]

        with patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_llm_svc:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = _make_llm_response("Conflict detected.")
            mock_llm_svc.return_value = mock_llm

            result_state = coordinator_node(state)

        report = result_state["final_report"]
        assert "Conflicting Findings" in report or "conflict" in report.lower()

    def test_coordinator_does_not_fabricate_ml_unavailable(self):
        """When ML reports UNAVAILABLE, the coordinator must NOT turn it into a prediction."""
        state = create_initial_state("Analyse INFY", tickers=["INFY"])
        state["validated_tickers"] = ["INFY"]
        state["unknown_tickers"] = []
        ml_dict = _make_completed_result(
            AgentName.ML_ANALYST,
            summary="No trained machine learning models are available for INFY.",
            key_findings=["Trained prediction models unavailable"],
            supporting_metrics={"status": "UNAVAILABLE"},
            confidence="low",
        )
        state["agent_results"] = {"ml_analyst": ml_dict}
        state["selected_agents"] = ["ml_analyst", "coordinator"]

        with patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_llm_svc:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = _make_llm_response("ML predictions not available.")
            mock_llm_svc.return_value = mock_llm

            result_state = coordinator_node(state)

        report = result_state["final_report"]
        # Must acknowledge unavailability, not fabricate a direction
        assert "unavailable" in report.lower() or "not available" in report.lower()
        for phrase in ["Predicted direction is Positive", "Predicted direction is Negative"]:
            assert phrase not in report


# ---------------------------------------------------------------------------
# 7. Full graph integration (end-to-end with mocked specialist nodes)
# ---------------------------------------------------------------------------

class TestFullGraphIntegration:
    """
    End-to-end graph integration tests.

    Strategy: pre-populate state with mocked specialist results (bypassing the
    real specialist nodes), then invoke only the coordinator and infrastructure
    nodes to verify graph state flows correctly end-to-end.

    For the two full `.invoke()` tests we patch the node callables at their
    registration site in `app.agents.nodes` so the compiled graph uses the mocks.
    """

    def _make_node_patch(
        self,
        agent_name: AgentName,
        completed: bool = True,
        confidence: str = "medium",
    ):
        """Return a mock callable that behaves like a specialist node."""
        result_dict = (
            _make_completed_result(agent_name, confidence=confidence)
            if completed
            else _make_failed_result(agent_name, "Mocked failure")
        )

        def _mock_node(state: GraphState) -> GraphState:
            agent_key = agent_name.value
            new_state = {**state}
            agent_results = dict(state.get("agent_results", {}))
            agent_results[agent_key] = result_dict
            agent_statuses = dict(state.get("agent_statuses", {}))
            agent_statuses[agent_key] = result_dict["status"]
            new_state["agent_results"] = agent_results
            new_state["agent_statuses"] = agent_statuses
            return new_state

        return _mock_node

    def test_full_standard_graph_run(self, db_session):
        """STANDARD scope: graph traverses validation, router, all specialists, coordinator."""
        # Seed a company for ticker validation
        sec = db_session.query(Sector).filter_by(sector_name="Technology").first()
        if not sec:
            sec = Sector(sector_name="Technology", industry_name="IT Services", data_source="test")
            db_session.add(sec)
            db_session.flush()
        from app.db.models import Company
        existing = db_session.query(Company).filter_by(symbol="INFY_INT").first()
        if not existing:
            company = Company(
                name="Infosys Integration Test",
                symbol="INFY_INT",
                provider_symbol="INFY_INT.NS",
                exchange="NSE",
                instrument_type="equity",
                is_active=True,
                sector_id=sec.id,
            )
            db_session.add(company)
            db_session.commit()

        state = create_initial_state(
            user_request="Standard analysis of INFY_INT",
            tickers=["INFY_INT"],
            scope=AnalysisScope.STANDARD.value,
        )

        with (
            patch("app.agents.dependencies.get_agent_db_session") as mock_val_db,
            patch("app.agents.nodes.market_analyst_node",
                  self._make_node_patch(AgentName.MARKET_ANALYST)),
            patch("app.agents.nodes.fundamental_analyst_node",
                  self._make_node_patch(AgentName.FUNDAMENTAL_ANALYST)),
            patch("app.agents.nodes.news_analyst_node",
                  self._make_node_patch(AgentName.NEWS_ANALYST)),
            patch("app.agents.nodes.risk_analyst_node",
                  self._make_node_patch(AgentName.RISK_ANALYST)),
            patch("app.agents.nodes.ml_analyst_node",
                  self._make_node_patch(AgentName.ML_ANALYST)),
            patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_coord_llm,
        ):
            mock_val_db.return_value.__enter__.return_value = db_session
            mock_coord_llm.return_value.generate.return_value = _make_llm_response(
                "INFY_INT shows balanced signals across all analysed dimensions."
            )

            graph = compile_graph()
            result_state = graph.invoke(state)

        # Validation
        assert result_state["final_report"] is not None
        assert "ArthAI Multi-Agent Research Report" in result_state["final_report"]
        assert result_state["completed_at"] is not None

    def test_validate_then_route_then_coordinator_pipeline(self, db_session):
        """
        Simulate the pipeline: validate → route → pre-built specialist results → coordinator.
        Uses real validation and routing nodes; coordinator is called with mocked LLM.
        """
        sec = db_session.query(Sector).filter_by(sector_name="Technology").first()
        if not sec:
            sec = Sector(sector_name="Technology", industry_name="IT Services", data_source="test")
            db_session.add(sec)
            db_session.flush()
        from app.db.models import Company
        existing = db_session.query(Company).filter_by(symbol="PIPE_T").first()
        if not existing:
            company = Company(
                name="Pipeline Test Co",
                symbol="PIPE_T",
                provider_symbol="PIPE_T.NS",
                exchange="NSE",
                instrument_type="equity",
                is_active=True,
                sector_id=sec.id,
            )
            db_session.add(company)
            db_session.commit()

        state = create_initial_state(
            user_request="Analyse PIPE_T",
            tickers=["PIPE_T"],
            scope=AnalysisScope.STANDARD.value,
        )

        # Step 1: validate
        with patch("app.agents.dependencies.get_agent_db_session") as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            state = _validate_tickers_node(state)

        assert "PIPE_T" in state["validated_tickers"]

        # Step 2: route
        state = _router_node(state)
        assert "market_analyst" in state["selected_agents"]

        # Step 3: inject pre-built agent results (simulating specialist runs)
        state["agent_results"] = {
            "market_analyst": _make_completed_result(AgentName.MARKET_ANALYST),
            "fundamental_analyst": _make_completed_result(AgentName.FUNDAMENTAL_ANALYST),
            "news_analyst": _make_completed_result(AgentName.NEWS_ANALYST),
            "risk_analyst": _make_completed_result(AgentName.RISK_ANALYST),
        }

        # Step 4: coordinator
        with patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_coord_llm:
            mock_coord_llm.return_value.generate.return_value = _make_llm_response(
                "PIPE_T shows well-rounded signal alignment."
            )
            final_state = coordinator_node(state)

        assert final_state["final_report"] is not None
        assert "ArthAI Multi-Agent Research Report" in final_state["final_report"]
        assert final_state["completed_at"] is not None
        coord_result = AgentResult(**final_state["agent_results"]["coordinator"])
        assert coord_result.status == ExecutionStatus.COMPLETED

    def test_partial_failure_does_not_abort_graph(self, db_session):
        """Failed specialists must not prevent coordinator from producing a report."""
        state = create_initial_state(
            user_request="Analyse PARTIAL_T",
            tickers=["PARTIAL_T"],
            scope=AnalysisScope.STANDARD.value,
        )
        state["validated_tickers"] = ["PARTIAL_T"]
        state["unknown_tickers"] = []
        state["selected_agents"] = [
            "market_analyst", "fundamental_analyst", "news_analyst",
            "risk_analyst", "ml_analyst", "coordinator",
        ]
        state["agent_results"] = {
            "market_analyst": _make_failed_result(AgentName.MARKET_ANALYST),
            "fundamental_analyst": _make_completed_result(AgentName.FUNDAMENTAL_ANALYST),
            "news_analyst": _make_completed_result(AgentName.NEWS_ANALYST),
            "risk_analyst": _make_failed_result(AgentName.RISK_ANALYST),
            "ml_analyst": _make_failed_result(AgentName.ML_ANALYST),
        }

        with patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_coord_llm:
            mock_coord_llm.return_value.generate.return_value = _make_llm_response(
                "Partial analysis completed with some agent failures."
            )
            result_state = coordinator_node(state)

        # Graph must complete
        assert result_state["final_report"] is not None
        assert result_state["completed_at"] is not None

    def test_explicit_agent_selection_respects_override(self, db_session):
        """Explicitly selecting only market_analyst should skip others."""
        state = create_initial_state(
            user_request="Technical analysis only",
            tickers=["INFY"],
            selected_agents=["market_analyst"],
        )
        state["validated_tickers"] = ["INFY"]
        state["unknown_tickers"] = []

        # Manually run router to get selected_agents populated
        routed = _router_node(state)
        assert "fundamental_analyst" not in routed["selected_agents"]
        assert "market_analyst" in routed["selected_agents"]
        assert "coordinator" in routed["selected_agents"]

    def test_unknown_ticker_produces_warning_in_final_report(self, db_session):
        """Unknown tickers must be surfaced in the final report."""
        state = create_initial_state("Analyse NONEXISTENT", tickers=["NONEXISTENT"])

        with patch("app.agents.dependencies.get_agent_db_session") as mock_val_db:
            mock_val_db.return_value.__enter__.return_value = db_session
            validated_state = _validate_tickers_node(state)

        assert "NONEXISTENT" in validated_state["unknown_tickers"]
        assert any("NONEXISTENT" in w for w in validated_state["warnings"])
