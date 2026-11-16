"""
Tests for Multi-Agent FastAPI endpoints (/api/v1/agents/*).

Covers:
- GET  /api/v1/agents/health (orchestration, LLM provider availability)
- GET  /api/v1/agents        (agent catalogue, metadata, scopes)
- POST /api/v1/agents/research (ticker validation, scope, selected_agents, full execution)
- POST /api/v1/agents/analyze  (NL query parsing, ticker extraction, scope inference)
- Request validation tests (invalid scope, missing ticker, unknown agent)
- Error handling (404 on unknown ticker, 400 on unknown agent)
- Partial agent failure (returns partial_failure status without crashing)
- LLM unavailable resilience (returns degraded health and fallback report)
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest

from app.db.models import Company, Sector, DailyMarketData
from app.agents.state import AgentName, ExecutionStatus
from app.services.llm_service import LLMProvider, LLMResponse


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------

def create_company_helper(db_session, symbol: str, name: str) -> Company:
    sec = db_session.query(Sector).filter_by(sector_name="Technology").first()
    if not sec:
        sec = Sector(sector_name="Technology", industry_name="IT Services", data_source="test")
        db_session.add(sec)
        db_session.flush()

    comp = db_session.query(Company).filter_by(symbol=symbol).first()
    if not comp:
        comp = Company(
            name=name,
            symbol=symbol,
            provider_symbol=f"{symbol}.NS",
            exchange="NSE",
            instrument_type="equity",
            is_active=True,
            sector_id=sec.id,
        )
        db_session.add(comp)
        db_session.commit()
    return comp


def make_mock_llm_response(text: str = "Synthesised report text.") -> LLMResponse:
    return LLMResponse(
        content=text,
        provider=LLMProvider.GEMINI,
        usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
    )


# ---------------------------------------------------------------------------
# 1. Health Endpoint Tests
# ---------------------------------------------------------------------------

class TestAgentsHealthEndpoint:
    def test_health_healthy_when_llm_available(self, client):
        mock_llm = MagicMock()
        mock_llm.gemini_available = True
        mock_llm.groq_available = False

        with patch("app.api.routes.agents.get_llm_service", return_value=mock_llm):
            resp = client.get("/api/v1/agents/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["orchestration_available"] is True
        assert "market_analyst" in data["registered_agents"]
        assert "coordinator" in data["registered_agents"]
        assert data["total_agents"] >= 6
        assert data["gemini_available"] is True
        assert "gemini" in data["active_providers"]

    def test_health_degraded_when_no_llm_available(self, client):
        mock_llm = MagicMock()
        mock_llm.gemini_available = False
        mock_llm.groq_available = False

        with patch("app.api.routes.agents.get_llm_service", return_value=mock_llm):
            resp = client.get("/api/v1/agents/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["orchestration_available"] is True
        assert data["active_providers"] == []
        assert "deterministic logic active" in data["message"].lower()

    def test_health_never_exposes_credentials(self, client):
        resp = client.get("/api/v1/agents/health")
        assert resp.status_code == 200
        text = resp.text.lower()
        for sensitive in ["api_key", "secret", "token", "password", "key"]:
            assert f'"{sensitive}"' not in text


# ---------------------------------------------------------------------------
# 2. Agent Catalogue Endpoint Tests
# ---------------------------------------------------------------------------

class TestAgentsListEndpoint:
    def test_list_all_registered_agents(self, client):
        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        data = resp.json()

        assert "agents" in data
        assert data["total"] >= 6

        names = [a["name"] for a in data["agents"]]
        expected = [
            "market_analyst",
            "fundamental_analyst",
            "news_analyst",
            "ml_analyst",
            "risk_analyst",
            "coordinator",
        ]
        for exp in expected:
            assert exp in names

    def test_agent_metadata_structure(self, client):
        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        agent = resp.json()["agents"][0]
        assert "name" in agent
        assert "display_name" in agent
        assert "description" in agent
        assert "scopes" in agent
        assert "requires_db" in agent
        assert "requires_llm" in agent
        assert "is_available" in agent


# ---------------------------------------------------------------------------
# 3. Research Endpoint Validation Tests
# ---------------------------------------------------------------------------

class TestResearchEndpointValidation:
    def test_research_unknown_ticker_returns_404(self, client):
        payload = {"ticker": "NONEXISTENT_TICKER_XYZ"}
        resp = client.post("/api/v1/agents/research", json=payload)
        assert resp.status_code == 404
        assert "not found in the company universe" in resp.json()["detail"]

    def test_research_empty_ticker_returns_422(self, client):
        payload = {"ticker": ""}
        resp = client.post("/api/v1/agents/research", json=payload)
        assert resp.status_code == 422

    def test_research_invalid_scope_returns_422(self, client):
        payload = {"ticker": "INFY", "scope": "super_deep_unsupported"}
        resp = client.post("/api/v1/agents/research", json=payload)
        assert resp.status_code == 422

    def test_research_unknown_agent_returns_400(self, client, db_session):
        create_company_helper(db_session, "RELIANCE_T1", "Reliance Industries T1")
        payload = {
            "ticker": "RELIANCE_T1",
            "selected_agents": ["market_analyst", "crypto_wizard_fake"],
        }
        resp = client.post("/api/v1/agents/research", json=payload)
        assert resp.status_code == 400
        assert "crypto_wizard_fake" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 4. Research Endpoint Execution Tests
# ---------------------------------------------------------------------------

class TestResearchEndpointExecution:
    def test_research_successful_standard_workflow(self, client, db_session):
        sym = "TCS_TEST"
        comp = create_company_helper(db_session, sym, "Tata Consultancy Services")

        payload = {
            "ticker": sym,
            "question": f"Is {sym} a good investment currently?",
            "scope": "standard",
        }

        mock_report = "## Executive Summary\n\nTCS demonstrates robust momentum.\n\n# ArthAI Multi-Agent Research Report"

        with patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_coord_llm, \
             patch("app.agents.dependencies.get_agent_db_session") as mock_db_ctx:
            mock_coord_llm.return_value.generate.return_value = make_mock_llm_response(mock_report)
            mock_db_ctx.return_value.__enter__.return_value = db_session

            resp = client.post("/api/v1/agents/research", json=payload)

        assert resp.status_code == 200
        data = resp.json()

        assert data["run_id"] != ""
        assert data["status"] in ("completed", "partial_failure")
        assert data["tickers"] == [sym]
        assert data["scope"] == "standard"
        assert "coordinator" in data["selected_agents"]
        assert data["final_report"] is not None
        assert "agent_results" in data
        assert "coordinator" in data["agent_results"]
        assert data["execution_time_seconds"] is not None
        assert data["execution_time_seconds"] >= 0

    def test_research_selective_agent_execution(self, client, db_session):
        sym = "WIPRO_TEST"
        create_company_helper(db_session, sym, "Wipro Technologies")

        payload = {
            "ticker": sym,
            "selected_agents": ["market_analyst"],
            "scope": "quick",
        }

        with patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_coord_llm, \
             patch("app.agents.dependencies.get_agent_db_session") as mock_db_ctx:
            mock_coord_llm.return_value.generate.return_value = make_mock_llm_response("Technical snapshot.")
            mock_db_ctx.return_value.__enter__.return_value = db_session

            resp = client.post("/api/v1/agents/research", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "market_analyst" in data["selected_agents"]
        assert "fundamental_analyst" not in data["selected_agents"]
        assert "coordinator" in data["selected_agents"]


# ---------------------------------------------------------------------------
# 5. Analyze Endpoint Tests
# ---------------------------------------------------------------------------

class TestAnalyzeEndpoint:
    def test_analyze_with_explicit_ticker(self, client, db_session):
        sym = "INFY_AN1"
        create_company_helper(db_session, sym, "Infosys Test 1")

        payload = {
            "request": f"Analyse financial health and risk for {sym}",
            "tickers": [sym],
            "scope": "standard",
        }

        with patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_coord_llm, \
             patch("app.agents.dependencies.get_agent_db_session") as mock_db_ctx:
            mock_coord_llm.return_value.generate.return_value = make_mock_llm_response("Financial analysis.")
            mock_db_ctx.return_value.__enter__.return_value = db_session

            resp = client.post("/api/v1/agents/analyze", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("completed", "partial_failure")
        assert sym in data["tickers"]

    def test_analyze_ticker_extraction_from_prompt(self, client, db_session):
        sym = "HDFC_EXTRACT"
        create_company_helper(db_session, sym, "HDFC Bank Extract")

        payload = {
            "request": f"What is the outlook for {sym} over the next quarter?",
        }

        with patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_coord_llm, \
             patch("app.agents.dependencies.get_agent_db_session") as mock_db_ctx:
            mock_coord_llm.return_value.generate.return_value = make_mock_llm_response("Outlook report.")
            mock_db_ctx.return_value.__enter__.return_value = db_session

            resp = client.post("/api/v1/agents/analyze", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert sym in data["tickers"]

    def test_analyze_unrecognised_query_returns_400(self, client, db_session):
        payload = {
            "request": "Tell me a random joke about horses with no company mentioned at all",
        }
        resp = client.post("/api/v1/agents/analyze", json=payload)
        assert resp.status_code == 400
        assert "Could not detect any valid company ticker" in resp.json()["detail"]

    def test_analyze_invalid_explicit_ticker_returns_404(self, client):
        payload = {
            "request": "Analyse performance",
            "tickers": ["FAKE_UNKNOWN_TICKER"],
        }
        resp = client.post("/api/v1/agents/analyze", json=payload)
        assert resp.status_code == 404

    def test_analyze_unknown_agent_returns_400(self, client, db_session):
        sym = "ICICI_T2"
        create_company_helper(db_session, sym, "ICICI Bank T2")
        payload = {
            "request": f"Review {sym}",
            "tickers": [sym],
            "selected_agents": ["quantum_trader_ai"],
        }
        resp = client.post("/api/v1/agents/analyze", json=payload)
        assert resp.status_code == 400
        assert "quantum_trader_ai" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 6. Partial Failure and Error Handling
# ---------------------------------------------------------------------------

class TestPartialFailureAndResilience:
    def test_partial_agent_failure_reports_partial_status(self, client, db_session):
        sym = "PARTIAL_API_T"
        create_company_helper(db_session, sym, "Partial Test Company")

        payload = {
            "ticker": sym,
            "scope": "standard",
        }

        # Simulate market analyst throwing an exception
        def failing_market_node(state):
            from app.agents.state import AgentResult, AgentName
            from app.agents.nodes.base import merge_agent_result
            r = AgentResult(agent_name=AgentName.MARKET_ANALYST)
            r.mark_running()
            r.mark_failed("Data provider connection timeout")
            return merge_agent_result(state, r)

        with patch("app.agents.nodes.market_analyst_node", failing_market_node), \
             patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_coord_llm, \
             patch("app.agents.dependencies.get_agent_db_session") as mock_db_ctx:
            mock_coord_llm.return_value.generate.return_value = make_mock_llm_response("Partial report.")
            mock_db_ctx.return_value.__enter__.return_value = db_session

            resp = client.post("/api/v1/agents/research", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "partial_failure"
        assert "market_analyst" in data["agent_results"]
        assert data["agent_results"]["market_analyst"]["status"] == "failed"
        assert "Data provider connection timeout" in data["agent_results"]["market_analyst"]["error_message"]
        assert data["final_report"] is not None

    def test_llm_failure_during_synthesis_still_returns_200(self, client, db_session):
        sym = "LLM_FAIL_T"
        create_company_helper(db_session, sym, "LLM Failure Company")

        payload = {"ticker": sym, "scope": "quick"}

        with patch("app.agents.nodes.coordinator.get_agent_llm_service") as mock_coord_llm, \
             patch("app.agents.dependencies.get_agent_db_session") as mock_db_ctx:
            mock_llm = MagicMock()
            mock_llm.generate.side_effect = RuntimeError("Provider rate limit reached")
            mock_coord_llm.return_value = mock_llm
            mock_db_ctx.return_value.__enter__.return_value = db_session

            resp = client.post("/api/v1/agents/research", json=payload)

        # Must not crash with 500; returns fallback report gracefully
        assert resp.status_code == 200
        data = resp.json()
        assert data["final_report"] is not None
        assert "ArthAI Multi-Agent Research Report" in data["final_report"]
