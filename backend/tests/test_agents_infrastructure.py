"""
Unit tests for Phase 5 LangGraph infrastructure.

Acceptance criteria: all tests pass without real LLM API calls.

Tests cover:
- State validation
- AgentResult validation
- Agent registration
- Graph construction (import + compile)
- Scope routing
- merge_agent_result correctness
- Missing LLM configuration handling
- LLM provider failure handling
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.agents.state import (
    AgentName,
    AgentResult,
    AnalysisScope,
    ExecutionStatus,
    GraphState,
)
from app.agents.registry import AgentRegistry, AgentInfo, registry
from app.agents.graph import create_initial_state, build_graph, _router_node
from app.agents.nodes.base import merge_agent_result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_registry() -> AgentRegistry:
    """Return a new, empty registry for isolation."""
    return AgentRegistry()


@pytest.fixture
def sample_state() -> GraphState:
    return create_initial_state(
        user_request="Analyse INFY",
        tickers=["INFY"],
        scope=AnalysisScope.STANDARD.value,
    )


@pytest.fixture
def completed_result() -> AgentResult:
    r = AgentResult(agent_name=AgentName.MARKET_ANALYST)
    r.mark_running()
    r.summary = "Market looks stable."
    r.key_findings = ["RSI is 55", "Price above 50-day MA"]
    r.supporting_metrics = {"rsi": 55.0, "close": 1800.0}
    r.evidence_sources = ["daily_market_data", "technical_indicators"]
    r.confidence = "high"
    r.mark_completed()
    return r


# ---------------------------------------------------------------------------
# State validation
# ---------------------------------------------------------------------------

class TestGraphState:
    def test_create_initial_state_keys(self, sample_state):
        assert "user_request" in sample_state
        assert "tickers" in sample_state
        assert "agent_results" in sample_state
        assert "agent_statuses" in sample_state
        assert "run_id" in sample_state
        assert "started_at" in sample_state

    def test_create_initial_state_values(self, sample_state):
        assert sample_state["user_request"] == "Analyse INFY"
        assert sample_state["tickers"] == ["INFY"]
        assert sample_state["scope"] == AnalysisScope.STANDARD.value
        assert sample_state["agent_results"] == {}
        assert sample_state["errors"] == []
        assert sample_state["warnings"] == []
        assert sample_state["final_report"] is None

    def test_run_id_is_uuid(self, sample_state):
        import uuid
        uuid.UUID(sample_state["run_id"])  # raises if invalid

    def test_multiple_tickers(self):
        state = create_initial_state(
            user_request="Compare INFY and TCS",
            tickers=["INFY", "TCS"],
        )
        assert len(state["tickers"]) == 2

    def test_deep_scope(self):
        state = create_initial_state(
            user_request="Deep dive",
            tickers=["RELIANCE"],
            scope=AnalysisScope.DEEP.value,
        )
        assert state["scope"] == "deep"


# ---------------------------------------------------------------------------
# AgentResult validation
# ---------------------------------------------------------------------------

class TestAgentResult:
    def test_default_status_is_pending(self):
        r = AgentResult(agent_name=AgentName.NEWS_ANALYST)
        assert r.status == ExecutionStatus.PENDING

    def test_mark_running(self):
        r = AgentResult(agent_name=AgentName.NEWS_ANALYST)
        r.mark_running()
        assert r.status == ExecutionStatus.RUNNING
        assert r.started_at is not None

    def test_mark_completed(self, completed_result):
        assert completed_result.status == ExecutionStatus.COMPLETED
        assert completed_result.completed_at is not None

    def test_mark_failed(self):
        r = AgentResult(agent_name=AgentName.RISK_ANALYST)
        r.mark_failed("DB connection refused")
        assert r.status == ExecutionStatus.FAILED
        assert r.error_message == "DB connection refused"
        assert r.completed_at is not None

    def test_mark_skipped(self):
        r = AgentResult(agent_name=AgentName.ML_ANALYST)
        r.mark_skipped("Not in scope")
        assert r.status == ExecutionStatus.SKIPPED
        assert any("Not in scope" in w for w in r.warnings)

    def test_to_dict_is_json_serialisable(self, completed_result):
        import json
        d = completed_result.to_dict()
        json.dumps(d)  # must not raise

    def test_to_dict_contains_required_keys(self, completed_result):
        d = completed_result.to_dict()
        for key in [
            "agent_name", "status", "summary", "key_findings",
            "supporting_metrics", "evidence_sources", "data_timestamps",
            "confidence", "missing_information", "warnings",
        ]:
            assert key in d, f"Missing key: {key}"

    def test_confidence_values(self):
        for conf in ("low", "medium", "high"):
            r = AgentResult(agent_name=AgentName.COORDINATOR, confidence=conf)
            assert r.confidence == conf

    def test_all_agent_names_valid(self):
        for name in AgentName:
            r = AgentResult(agent_name=name)
            assert r.agent_name == name


# ---------------------------------------------------------------------------
# Agent registration
# ---------------------------------------------------------------------------

class TestAgentRegistry:
    def test_global_registry_has_all_agents(self):
        for name in AgentName:
            assert name.value in registry, f"Missing from global registry: {name.value}"

    def test_global_registry_count(self):
        assert len(registry) == len(AgentName)

    def test_register_and_get(self, fresh_registry):
        info = AgentInfo(
            name=AgentName.MARKET_ANALYST,
            display_name="Test",
            description="Test agent",
            scopes=[AnalysisScope.QUICK],
        )
        fresh_registry.register(info)
        retrieved = fresh_registry.get(AgentName.MARKET_ANALYST)
        assert retrieved.display_name == "Test"

    def test_duplicate_registration_raises(self, fresh_registry):
        info = AgentInfo(
            name=AgentName.MARKET_ANALYST,
            display_name="X",
            description="X",
        )
        fresh_registry.register(info)
        with pytest.raises(ValueError, match="already registered"):
            fresh_registry.register(info)

    def test_get_unknown_raises(self, fresh_registry):
        with pytest.raises(KeyError):
            fresh_registry.get("nonexistent_agent")

    def test_list_for_scope_quick(self):
        agents = registry.list_for_scope(AnalysisScope.QUICK)
        names = [a.name for a in agents]
        assert AgentName.MARKET_ANALYST in names
        assert AgentName.COORDINATOR in names
        # ML_ANALYST is DEEP only
        assert AgentName.ML_ANALYST not in names

    def test_list_for_scope_deep_includes_ml(self):
        agents = registry.list_for_scope(AnalysisScope.DEEP)
        names = [a.name for a in agents]
        assert AgentName.ML_ANALYST in names

    def test_validate_selection_filters_unknowns(self):
        valid = registry.validate_selection(["market_analyst", "ghost_agent"])
        assert "market_analyst" in valid
        assert "ghost_agent" not in valid

    def test_contains_operator(self):
        assert AgentName.COORDINATOR in registry
        assert "coordinator" in registry

    def test_attach_node(self):
        fn = lambda state: state
        # Use the global registry but patch a fresh copy to avoid side effects
        r = AgentRegistry()
        r.register(AgentInfo(
            name=AgentName.COORDINATOR,
            display_name="C",
            description="C",
        ))
        r.attach_node(AgentName.COORDINATOR, fn)
        assert r.get(AgentName.COORDINATOR).node_fn is fn


# ---------------------------------------------------------------------------
# Router node
# ---------------------------------------------------------------------------

class TestRouterNode:
    def test_router_standard_scope(self, sample_state):
        result = _router_node(sample_state)
        selected = result["selected_agents"]
        assert "market_analyst" in selected
        assert "fundamental_analyst" in selected
        assert "coordinator" in selected
        assert "ml_analyst" not in selected  # DEEP only

    def test_router_deep_scope(self):
        state = create_initial_state("Deep", ["INFY"], scope="deep")
        result = _router_node(state)
        assert "ml_analyst" in result["selected_agents"]

    def test_router_quick_scope(self):
        state = create_initial_state("Quick", ["INFY"], scope="quick")
        result = _router_node(state)
        selected = result["selected_agents"]
        assert "market_analyst" in selected
        assert "coordinator" in selected
        assert "fundamental_analyst" not in selected

    def test_router_invalid_scope_defaults_to_standard(self):
        state = create_initial_state("Q", ["INFY"], scope="invalid_scope")
        result = _router_node(state)
        # Should not crash; coordinator must still be selected
        assert "coordinator" in result["selected_agents"]

    def test_router_initialises_statuses(self, sample_state):
        result = _router_node(sample_state)
        for name in result["selected_agents"]:
            assert name in result["agent_statuses"]
            assert result["agent_statuses"][name] == ExecutionStatus.PENDING.value

    def test_router_preserves_existing_run_id(self):
        state = create_initial_state("Q", ["INFY"])
        original_id = state["run_id"]
        result = _router_node(state)
        assert result["run_id"] == original_id

    def test_router_explicit_selection_honoured(self):
        state = create_initial_state(
            "Q", ["INFY"],
            selected_agents=["market_analyst", "coordinator"],
        )
        result = _router_node(state)
        assert "market_analyst" in result["selected_agents"]
        assert "fundamental_analyst" not in result["selected_agents"]


# ---------------------------------------------------------------------------
# merge_agent_result
# ---------------------------------------------------------------------------

class TestMergeAgentResult:
    def test_result_stored_in_state(self, sample_state, completed_result):
        new_state = merge_agent_result(sample_state, completed_result)
        assert "market_analyst" in new_state["agent_results"]

    def test_status_updated(self, sample_state, completed_result):
        new_state = merge_agent_result(sample_state, completed_result)
        assert new_state["agent_statuses"]["market_analyst"] == ExecutionStatus.COMPLETED.value

    def test_evidence_sources_merged(self, sample_state, completed_result):
        new_state = merge_agent_result(sample_state, completed_result)
        assert "daily_market_data" in new_state["evidence_sources"]
        assert "technical_indicators" in new_state["evidence_sources"]

    def test_evidence_sources_deduplicated(self, sample_state, completed_result):
        # Run merge twice with the same sources
        s1 = merge_agent_result(sample_state, completed_result)
        s2 = merge_agent_result(s1, completed_result)
        assert s2["evidence_sources"].count("daily_market_data") == 1

    def test_error_message_propagated(self, sample_state):
        r = AgentResult(agent_name=AgentName.RISK_ANALYST)
        r.mark_failed("timeout")
        new_state = merge_agent_result(sample_state, r)
        assert any("timeout" in e for e in new_state["errors"])

    def test_warnings_propagated(self, sample_state):
        r = AgentResult(agent_name=AgentName.ML_ANALYST)
        r.mark_skipped("no model")
        new_state = merge_agent_result(sample_state, r)
        assert any("no model" in w for w in new_state["warnings"])

    def test_original_state_not_mutated(self, sample_state, completed_result):
        original_results = dict(sample_state.get("agent_results", {}))
        merge_agent_result(sample_state, completed_result)
        assert sample_state.get("agent_results") == original_results


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

class TestGraphConstruction:
    def test_build_graph_returns_state_graph(self):
        from langgraph.graph import StateGraph
        sg = build_graph()
        assert isinstance(sg, StateGraph)

    def test_compile_graph_succeeds(self):
        compiled = build_graph().compile()
        assert compiled is not None

    def test_compiled_graph_has_invoke(self):
        compiled = build_graph().compile()
        assert callable(getattr(compiled, "invoke", None))

    def test_agents_package_importable(self):
        from app.agents import (
            AgentName, AgentResult, AnalysisScope, ExecutionStatus,
            GraphState, registry, compile_graph, create_initial_state,
        )
        assert compile_graph is not None
        assert registry is not None


# ---------------------------------------------------------------------------
# LLM provider failure handling
# ---------------------------------------------------------------------------

class TestLLMProviderFailure:
    def test_base_node_marks_failed_on_llm_error(self, sample_state):
        """BaseAgentNode._call_llm raising must result in a FAILED AgentResult."""
        from app.agents.nodes.base import BaseAgentNode
        from app.agents.state import AgentName

        class DummyNode(BaseAgentNode):
            agent_name = AgentName.MARKET_ANALYST
            system_prompt = "test"

            def _gather_data(self, state):
                return {}

            def _build_prompt(self, state, data):
                return "test prompt"

            def _call_llm(self, prompt):
                raise RuntimeError("Gemini quota exceeded")

        # state must include this agent as selected
        state = {
            **sample_state,
            "selected_agents": ["market_analyst"],
        }
        node = DummyNode()
        result_state = node(state)
        status = result_state["agent_statuses"].get("market_analyst")
        assert status == ExecutionStatus.FAILED.value

    def test_coordinator_fallback_report_on_llm_error(self, sample_state):
        """Coordinator must write a fallback report string when LLM fails."""
        with patch(
            "app.agents.nodes.coordinator.get_agent_llm_service"
        ) as mock_llm_svc:
            mock_llm = MagicMock()
            mock_llm.generate.side_effect = RuntimeError("All LLM providers unavailable")
            mock_llm_svc.return_value = mock_llm

            from app.agents.nodes.coordinator import coordinator_node
            state = {
                **sample_state,
                "selected_agents": ["coordinator"],
                "agent_results": {},
            }
            result_state = coordinator_node(state)

        assert result_state["final_report"] is not None
        assert "Error" in result_state["final_report"]

    def test_missing_llm_config_raises_at_generate(self):
        """LLMService.generate should raise RuntimeError when no provider is configured."""
        with patch.dict("os.environ", {"GEMINI": "", "GROQ": ""}):
            from app.services.llm_service import LLMService
            svc = LLMService()
            svc.gemini_available = False
            svc.groq_available = False
            with pytest.raises(RuntimeError, match="No LLM providers available"):
                svc.generate("test prompt")
