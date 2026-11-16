"""
Unit tests for the five specialist agents in ArthAI Phase 5:
- Market Analyst Agent
- Fundamental Analyst Agent
- News Analyst Agent
- ML Analyst Agent
- Risk Analyst Agent

Acceptance Criteria:
- Each specialist agent can be invoked independently without depending on the other agents.
- Each returns a validated AgentResult conforming to the typed schema.
- Data is retrieved from real/mocked service pipelines.
- Deterministic calculations are verified.
- Missing data, stale data, and error boundaries are tested.
- LLM calls are mocked; no real API calls required.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from unittest.mock import MagicMock, patch
import pytest

from app.db.models import (
    Company,
    CompanyFinancial,
    CompanyFundamentalInfo,
    DailyMarketData,
    NewsArticle,
    NewsArticleCompany,
    NewsSource,
    Sector,
)
from app.agents.state import (
    AgentName,
    AgentResult,
    AnalysisScope,
    ExecutionStatus,
    GraphState,
)
from app.agents.graph import create_initial_state
from app.agents.nodes.market_analyst import market_analyst_node
from app.agents.nodes.fundamental_analyst import fundamental_analyst_node
from app.agents.nodes.news_analyst import news_analyst_node
from app.agents.nodes.ml_analyst import ml_analyst_node
from app.agents.nodes.risk_analyst import (
    risk_analyst_node,
    calculate_deterministic_risk_metrics,
)
from app.services.llm_service import LLMResponse, LLMProvider


def make_mock_llm_response(
    summary: str,
    key_findings: list[str],
    confidence: str = "medium",
    symbol: str = "INFY",
) -> LLMResponse:
    content = json.dumps({
        "summary": summary,
        "key_findings": key_findings,
        "supporting_metrics": {symbol: {"sample_metric": 100.0}},
        "evidence_sources": ["mock_llm_source"],
        "data_timestamps": {"mock_llm_source": "2026-11-16T12:00:00"},
        "confidence": confidence,
        "missing_information": [],
        "warnings": [],
    })
    return LLMResponse(
        content=content,
        provider=LLMProvider.GEMINI,
        usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
    )


def create_company_helper(db_session, symbol: str, name: str) -> Company:
    sec = db_session.query(Sector).filter_by(sector_name="Technology").first()
    if not sec:
        sec = Sector(sector_name="Technology", industry_name="Software")
        db_session.add(sec)
        db_session.flush()

    comp = Company(
        symbol=symbol.upper(),
        name=name,
        provider_symbol=f"{symbol.upper()}.NS",
        exchange="NSE",
        instrument_type="company",
        is_active=True,
        sector_id=sec.id,
    )
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)
    return comp


# ---------------------------------------------------------------------------
# 1. Market Analyst Tests
# ---------------------------------------------------------------------------

class TestMarketAnalystAgent:
    def test_market_analyst_independent_invocation(self, db_session):
        sym = "MKT_A"
        comp = create_company_helper(db_session, sym, "Market Company A")

        base_date = date.today() - timedelta(days=65)
        for i in range(60):
            t_date = base_date + timedelta(days=i)
            p = 100.0 + i * 1.5
            db_session.add(
                DailyMarketData(
                    company_id=comp.id,
                    trading_date=t_date,
                    open=Decimal(str(p)),
                    high=Decimal(str(p + 5.0)),
                    low=Decimal(str(p - 3.0)),
                    close=Decimal(str(p + 2.0)),
                    volume=1000000 + i * 5000,
                    provider="yahoo_finance",
                )
            )
        db_session.commit()

        state = create_initial_state(
            user_request=f"Technical analysis of {sym}",
            tickers=[sym],
            selected_agents=["market_analyst"],
        )

        mock_resp = make_mock_llm_response(
            summary=f"{sym} is exhibiting upward momentum above its 20 EMA.",
            key_findings=["RSI is in bullish range", "Volume is steady"],
            confidence="high",
            symbol=sym,
        )

        with patch("app.agents.nodes.base.get_agent_llm_service") as mock_get_llm, \
             patch("app.agents.nodes.market_analyst.get_agent_db_session") as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            mock_llm = MagicMock()
            mock_llm.generate.return_value = mock_resp
            mock_get_llm.return_value = mock_llm

            result_state = market_analyst_node(state)

        result = AgentResult(**result_state["agent_results"]["market_analyst"])
        assert result.agent_name == AgentName.MARKET_ANALYST
        assert result.status == ExecutionStatus.COMPLETED
        assert sym in result.supporting_metrics
        assert "DailyMarketData" in result.evidence_sources
        assert result.confidence in ("medium", "high")

    def test_market_analyst_insufficient_data(self, db_session):
        sym = "MKT_INSUF"
        comp = create_company_helper(db_session, sym, "Insufficient Data Co")

        db_session.add(
            DailyMarketData(
                company_id=comp.id,
                trading_date=date.today(),
                open=Decimal("100"),
                high=Decimal("105"),
                low=Decimal("95"),
                close=Decimal("102"),
                volume=100000,
                provider="yahoo_finance",
            )
        )
        db_session.commit()

        state = create_initial_state(
            user_request=f"Analyse {sym}",
            tickers=[sym],
            selected_agents=["market_analyst"],
        )

        mock_resp = make_mock_llm_response("Insufficient bars", ["Need at least 2 bars"], "low", sym)

        with patch("app.agents.nodes.base.get_agent_llm_service") as mock_get_llm, \
             patch("app.agents.nodes.market_analyst.get_agent_db_session") as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            mock_llm = MagicMock()
            mock_llm.generate.return_value = mock_resp
            mock_get_llm.return_value = mock_llm

            result_state = market_analyst_node(state)

        result = AgentResult(**result_state["agent_results"]["market_analyst"])
        assert any("Insufficient" in msg for msg in result.missing_information)

    def test_market_analyst_unknown_company(self, db_session):
        state = create_initial_state(
            user_request="Analyse NONEXISTENT",
            tickers=["NONEXISTENT"],
            selected_agents=["market_analyst"],
        )

        mock_resp = make_mock_llm_response("Not found", [], "low", "NONEXISTENT")

        with patch("app.agents.nodes.base.get_agent_llm_service") as mock_get_llm, \
             patch("app.agents.nodes.market_analyst.get_agent_db_session") as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            mock_llm = MagicMock()
            mock_llm.generate.return_value = mock_resp
            mock_get_llm.return_value = mock_llm

            result_state = market_analyst_node(state)

        result = AgentResult(**result_state["agent_results"]["market_analyst"])
        assert any("not found" in m for m in result.missing_information)


# ---------------------------------------------------------------------------
# 2. Fundamental Analyst Tests
# ---------------------------------------------------------------------------

class TestFundamentalAnalystAgent:
    def test_fundamental_analyst_independent_invocation(self, db_session):
        sym = "FND_A"
        comp = create_company_helper(db_session, sym, "Fundamental Co A")

        info = CompanyFundamentalInfo(
            company_id=comp.id,
            market_cap=50_000_000_000,
            enterprise_value=52_000_000_000,
            employees=25000,
            business_summary="Leading enterprise software provider",
            data_source="yahoo_finance",
            retrieved_at=datetime.now(timezone.utc) - timedelta(days=12),
        )
        db_session.add(info)

        # Seed financial statements
        p_end = date(2025, 3, 31)
        financials = [
            CompanyFinancial(company_id=comp.id, metric_name="Total Revenue", metric_value=Decimal("150000000000"), period_end=p_end, period_type="annual", statement_type="income"),
            CompanyFinancial(company_id=comp.id, metric_name="Net Income", metric_value=Decimal("25000000000"), period_end=p_end, period_type="annual", statement_type="income"),
            CompanyFinancial(company_id=comp.id, metric_name="Stockholders Equity", metric_value=Decimal("80000000000"), period_end=p_end, period_type="annual", statement_type="balance"),
            CompanyFinancial(company_id=comp.id, metric_name="Total Debt", metric_value=Decimal("5000000000"), period_end=p_end, period_type="annual", statement_type="balance"),
            CompanyFinancial(company_id=comp.id, metric_name="Operating Cash Flow", metric_value=Decimal("30000000000"), period_end=p_end, period_type="annual", statement_type="cashflow"),
        ]
        for f in financials:
            db_session.add(f)
        db_session.commit()

        state = create_initial_state(
            user_request=f"Evaluate fundamentals of {sym}",
            tickers=[sym],
            selected_agents=["fundamental_analyst"],
        )

        mock_resp = make_mock_llm_response(
            summary=f"{sym} has strong balance sheet health and solid net income margins.",
            key_findings=["Revenue of 150B with strong operating cash flow", "Low total debt of 5B"],
            confidence="high",
            symbol=sym,
        )

        with patch("app.agents.nodes.base.get_agent_llm_service") as mock_get_llm, \
             patch("app.agents.nodes.fundamental_analyst.get_agent_db_session") as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            mock_llm = MagicMock()
            mock_llm.generate.return_value = mock_resp
            mock_get_llm.return_value = mock_llm

            result_state = fundamental_analyst_node(state)

        result = AgentResult(**result_state["agent_results"]["fundamental_analyst"])
        assert result.agent_name == AgentName.FUNDAMENTAL_ANALYST
        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.key_findings) > 0
        assert "analyze_fundamentals" in result.evidence_sources


# ---------------------------------------------------------------------------
# 3. News Analyst Tests
# ---------------------------------------------------------------------------

class TestNewsAnalystAgent:
    def test_news_analyst_independent_invocation(self, db_session):
        sym = "NEWS_A"
        comp = create_company_helper(db_session, sym, "News Co A")

        src = NewsSource(
            provider_key=f"source_{sym.lower()}",
            name="Financial Daily",
            source_type="rss",
            base_url="https://findaily.com",
            feed_url="https://findaily.com/feed",
            is_active=True,
        )
        db_session.add(src)
        db_session.flush()

        art = NewsArticle(
            source_id=src.id,
            url_hash=f"hash_{sym.lower()}_1",
            canonical_url=f"https://findaily.com/{sym.lower()}-expansion",
            headline=f"{comp.name} expands cloud contract with global tier 1 client",
            summary="New deal represents substantial ARR expansion over 3 years.",
            published_at=datetime.now(timezone.utc) - timedelta(days=1),
            sentiment_score=Decimal("0.70"),
            sentiment_confidence=Decimal("0.92"),
            event_category="corporate_action",
            event_confidence=Decimal("0.88"),
            market_impact_score=Decimal("0.80"),
        )
        db_session.add(art)
        db_session.flush()

        match = NewsArticleCompany(
            article_id=art.id,
            company_id=comp.id,
            match_method="symbol",
            match_confidence=Decimal("0.99"),
        )
        db_session.add(match)
        db_session.commit()

        state = create_initial_state(
            user_request=f"What is the news sentiment on {sym}?",
            tickers=[sym],
            selected_agents=["news_analyst"],
        )

        mock_resp = make_mock_llm_response(
            summary=f"News sentiment on {sym} is strongly positive on cloud deal expansion.",
            key_findings=["Contract expansion announced with high impact score 0.80"],
            confidence="high",
            symbol=sym,
        )

        with patch("app.agents.nodes.base.get_agent_llm_service") as mock_get_llm, \
             patch("app.agents.nodes.news_analyst.get_agent_db_session") as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            mock_llm = MagicMock()
            mock_llm.generate.return_value = mock_resp
            mock_get_llm.return_value = mock_llm

            result_state = news_analyst_node(state)

        result = AgentResult(**result_state["agent_results"]["news_analyst"])
        assert result.agent_name == AgentName.NEWS_ANALYST
        assert result.status == ExecutionStatus.COMPLETED
        assert "NewsArticle" in result.evidence_sources


# ---------------------------------------------------------------------------
# 4. ML Analyst Tests
# ---------------------------------------------------------------------------

class TestMLAnalystAgent:
    def test_ml_analyst_unavailable_when_no_models(self):
        sym = "ML_NONE"
        state = create_initial_state(
            user_request=f"Predict returns for {sym}",
            tickers=[sym],
            selected_agents=["ml_analyst"],
        )

        with patch("app.agents.nodes.ml_analyst.ModelServer.list_models", return_value=[]):
            result_state = ml_analyst_node(state)

        result = AgentResult(**result_state["agent_results"]["ml_analyst"])
        assert result.status == ExecutionStatus.COMPLETED
        assert "No trained machine learning models" in result.summary
        assert result.confidence == "low"
        assert result.supporting_metrics.get("status") == "UNAVAILABLE"
        assert any("Trained prediction models" in m for m in result.missing_information)

    def test_ml_analyst_with_model(self, db_session):
        sym = "ML_PRED"
        create_company_helper(db_session, sym, "ML Test Co")

        state = create_initial_state(
            user_request=f"Predict returns for {sym}",
            tickers=[sym],
            selected_agents=["ml_analyst"],
        )

        mock_models = [{
            "model_id": "stock_prediction_xgboost_all",
            "model_type": "xgboost",
            "version": "v1.0",
            "accuracy": 0.70,
            "f1_score": 0.69,
            "feature_names": ["rsi_14", "ema_20_ratio", "volatility_20"],
        }]

        mock_pred_response = MagicMock()
        mock_pred_response.symbol = sym
        mock_pred_response.predicted_class = "Positive"
        mock_pred_response.confidence = 0.75
        mock_pred_response.probabilities = {"Positive": 0.75, "Negative": 0.25}
        mock_pred_response.horizon_days = 1
        mock_pred_response.model_id = "stock_prediction_xgboost_all"
        mock_pred_response.timestamp = datetime.now(timezone.utc)
        mock_pred_response.to_dict.return_value = {
            "symbol": sym,
            "predicted_class": "Positive",
            "confidence": 0.75,
            "probabilities": {"Positive": 0.75, "Negative": 0.25},
            "horizon_days": 1,
            "model_id": "stock_prediction_xgboost_all",
        }

        with patch("app.agents.nodes.ml_analyst.ModelServer.list_models", return_value=mock_models), \
             patch("app.agents.nodes.ml_analyst.PredictionService.predict_for_symbol", return_value=mock_pred_response), \
             patch("app.agents.nodes.ml_analyst.get_agent_db_session") as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            result_state = ml_analyst_node(state)

        result = AgentResult(**result_state["agent_results"]["ml_analyst"])
        assert result.status == ExecutionStatus.COMPLETED
        assert result.confidence == "medium"
        assert f"{sym}: Predicted direction is Positive" in result.key_findings[0]


# ---------------------------------------------------------------------------
# 5. Risk Analyst Tests
# ---------------------------------------------------------------------------

class TestRiskAnalystAgent:
    def test_deterministic_risk_calculations(self):
        prices = [100.0, 110.0, 120.0, 60.0, 90.0]
        rows = [
            DailyMarketData(
                company_id=999,
                trading_date=date.today() - timedelta(days=5 - i),
                close=Decimal(str(p)),
            )
            for i, p in enumerate(prices)
        ]

        metrics = calculate_deterministic_risk_metrics(rows)
        assert metrics["max_drawdown_pct"] == -50.0
        assert metrics["worst_daily_drop_pct"] == -50.0
        assert metrics["historical_volatility_annualized"] > 0
        assert metrics["data_points"] == 5

    def test_risk_analyst_independent_invocation(self, db_session):
        sym = "RISK_A"
        comp = create_company_helper(db_session, sym, "Risk Co A")

        base_date = date.today() - timedelta(days=65)
        for i in range(60):
            t_date = base_date + timedelta(days=i)
            p = 200.0 + (i % 5) * 4.0 - (i % 3) * 2.0
            db_session.add(
                DailyMarketData(
                    company_id=comp.id,
                    trading_date=t_date,
                    open=Decimal(str(p)),
                    high=Decimal(str(p + 3.0)),
                    low=Decimal(str(p - 3.0)),
                    close=Decimal(str(p + 1.0)),
                    volume=500000,
                    provider="yahoo_finance",
                )
            )
        db_session.commit()

        state = create_initial_state(
            user_request=f"Risk breakdown for {sym}",
            tickers=[sym],
            selected_agents=["risk_analyst"],
        )

        mock_resp = make_mock_llm_response(
            summary=f"Risk analysis for {sym} indicates manageable drawdown.",
            key_findings=["Annualized volatility calculated at 18.2%", "Max drawdown is -8.4%"],
            confidence="high",
            symbol=sym,
        )

        with patch("app.agents.nodes.base.get_agent_llm_service") as mock_get_llm, \
             patch("app.agents.nodes.risk_analyst.get_agent_db_session") as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            mock_llm = MagicMock()
            mock_llm.generate.return_value = mock_resp
            mock_get_llm.return_value = mock_llm

            result_state = risk_analyst_node(state)

        result = AgentResult(**result_state["agent_results"]["risk_analyst"])
        assert result.agent_name == AgentName.RISK_ANALYST
        assert result.status == ExecutionStatus.COMPLETED
        assert "DailyMarketData" in result.evidence_sources
        assert "risk_metrics" in result.supporting_metrics

    def test_risk_analyst_cross_agent_conflict_detection(self, db_session):
        sym = "RISK_CONF"
        comp = create_company_helper(db_session, sym, "Conflict Co")

        base_date = date.today() - timedelta(days=10)
        for i in range(10):
            db_session.add(
                DailyMarketData(
                    company_id=comp.id,
                    trading_date=base_date + timedelta(days=i),
                    open=Decimal("100"),
                    high=Decimal("105"),
                    low=Decimal("98"),
                    close=Decimal("103"),
                    volume=200000,
                    provider="yahoo_finance",
                )
            )
        db_session.commit()

        state = create_initial_state(
            user_request=f"Evaluate risk conflicts for {sym}",
            tickers=[sym],
            selected_agents=["risk_analyst"],
        )
        state["agent_results"] = {
            "market_analyst": {
                "supporting_metrics": {
                    "trend_analysis": {sym: {"classification": "STRONG_BULLISH"}}
                }
            },
            "fundamental_analyst": {
                "supporting_metrics": {
                    "fundamental_scores": {sym: {"classification": "WEAK"}}
                }
            },
            "news_analyst": {
                "supporting_metrics": {
                    "sentiment_aggregation": {sym: {"sentiment_trend": "negative"}}
                }
            },
        }

        mock_resp = make_mock_llm_response(
            summary="Substantial conflict between bullish momentum and weak balance sheet.",
            key_findings=["Divergence detected: Bullish technicals vs Weak fundamentals"],
            confidence="medium",
            symbol=sym,
        )

        with patch("app.agents.nodes.base.get_agent_llm_service") as mock_get_llm, \
             patch("app.agents.nodes.risk_analyst.get_agent_db_session") as mock_db:
            mock_db.return_value.__enter__.return_value = db_session
            mock_llm = MagicMock()
            mock_llm.generate.return_value = mock_resp
            mock_get_llm.return_value = mock_llm

            result_state = risk_analyst_node(state)

        result = AgentResult(**result_state["agent_results"]["risk_analyst"])
        assert any("speculative momentum" in w for w in result.warnings)
        assert any("conflicts with negative news" in w for w in result.warnings)
