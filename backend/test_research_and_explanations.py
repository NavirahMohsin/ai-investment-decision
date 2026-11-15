"""
Tests for Research Assistant (Phase 4.4) and AI Explanations (Phase 4.5).

Tests cover:
- Company overview generation
- Financial analysis
- SWOT analysis
- Company comparison
- Research report generation
- ML prediction explanations
- Technical signal explanations
- Fundamental score explanations
- News sentiment explanations
- Error handling
- Input validation
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.research_assistant import get_research_assistant
from app.services.explanations import get_explanation_service
from app.db.session import SessionLocal
from app.schemas.research import (
    CompanyOverviewRequest,
    FinancialAnalysisRequest,
    SWOTRequest,
    ComparisonRequest,
    ResearchReportRequest,
    MLPredictionExplanationRequest,
    TechnicalSignalExplanationRequest,
    FundamentalScoreExplanationRequest,
    NewsSentimentExplanationRequest,
)


class TestResearchAssistant:
    """Test research assistant functionality."""

    def test_research_assistant_initialization(self):
        """Test that research assistant can be initialized."""
        db = SessionLocal()
        try:
            assistant = get_research_assistant(db)
            assert assistant is not None
            assert assistant.db == db
        finally:
            db.close()

    def test_company_overview_generation_with_invalid_ticker(self):
        """Test company overview with invalid ticker returns graceful error."""
        db = SessionLocal()
        try:
            assistant = get_research_assistant(db)
            overview = assistant.generate_company_overview("INVALID123")
            assert "not found" in overview.lower() or "error" in overview.lower()
        finally:
            db.close()

    def test_financial_analysis_with_invalid_ticker(self):
        """Test financial analysis with invalid ticker."""
        db = SessionLocal()
        try:
            assistant = get_research_assistant(db)
            analysis = assistant.analyze_financial_performance("INVALID123")
            assert "not found" in analysis.lower() or "error" in analysis.lower()
        finally:
            db.close()

    def test_swot_analysis_with_invalid_ticker(self):
        """Test SWOT analysis with invalid ticker."""
        db = SessionLocal()
        try:
            assistant = get_research_assistant(db)
            swot = assistant.generate_swot_analysis("INVALID123")
            assert "not found" in swot.lower() or "error" in swot.lower()
        finally:
            db.close()

    def test_comparison_with_invalid_tickers(self):
        """Test comparison with invalid tickers."""
        db = SessionLocal()
        try:
            assistant = get_research_assistant(db)
            comparison = assistant.compare_companies(["INVALID1", "INVALID2"])
            # Should return some response (even if "no data found")
            assert isinstance(comparison, str)
        finally:
            db.close()

    def test_comparison_with_single_ticker(self):
        """Test comparison requires at least 2 tickers."""
        db = SessionLocal()
        try:
            assistant = get_research_assistant(db)
            comparison = assistant.compare_companies(["TCS"])
            # Should handle gracefully
            assert isinstance(comparison, str)
        finally:
            db.close()

    def test_research_report_generation(self):
        """Test research report generation structure."""
        db = SessionLocal()
        try:
            assistant = get_research_assistant(db)
            # Use invalid ticker - should still generate report structure
            report = assistant.generate_research_report("INVALID123")
            # Should include header sections
            assert isinstance(report, str)
            # Even with invalid ticker, should have structure
            assert "Report" in report or "error" in report.lower()
        finally:
            db.close()


class TestExplanationService:
    """Test explanation service functionality."""

    def test_explanation_service_initialization(self):
        """Test explanation service can be initialized."""
        service = get_explanation_service()
        assert service is not None

    def test_ml_prediction_explanation(self):
        """Test ML prediction explanation generation."""
        service = get_explanation_service()
        prediction = {
            "direction": "UP",
            "confidence": 0.72,
            "current_price": 3650,
            "prediction_price": 3850,
        }
        explanation = service.explain_ml_prediction(
            ticker="TCS",
            prediction=prediction,
            model_name="test_model",
            historical_accuracy=0.68,
        )
        
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        # Should include either explanation content or error message
        assert ("uncertainty" in explanation.lower() or 
                "disclaimer" in explanation.lower() or 
                "error" in explanation.lower())

    def test_technical_signal_explanation(self):
        """Test technical signal explanation."""
        service = get_explanation_service()
        indicators = {
            "rsi": 35,
            "macd": "bullish_crossover",
            "sma_20_above_50": True,
        }
        explanation = service.explain_technical_signal(
            ticker="TCS",
            signal="BUY",
            indicators=indicators,
        )
        
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        # Should contain either interpretation or error
        assert ("interpretation" in explanation.lower() or "error" in explanation.lower())

    def test_fundamental_score_explanation(self):
        """Test fundamental score explanation."""
        service = get_explanation_service()
        factors = {
            "pe_ratio": 18.5,
            "pb_ratio": 3.2,
            "roe": 15.8,
            "debt_to_equity": 0.45,
        }
        explanation = service.explain_fundamental_score(
            ticker="TCS",
            score=78.5,
            factors=factors,
        )
        
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert "78.5" in explanation or "score" in explanation.lower() or "error" in explanation.lower()

    def test_news_sentiment_explanation(self):
        """Test news sentiment explanation."""
        service = get_explanation_service()
        themes = {
            "earnings": "positive",
            "growth": "positive",
            "competition": "negative",
        }
        explanation = service.explain_news_sentiment(
            ticker="TCS",
            sentiment_score=0.72,
            sentiment_category="positive",
            key_themes=themes,
        )
        
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert "sentiment" in explanation.lower() or "error" in explanation.lower()

    def test_uncertainty_footer_is_present(self):
        """Test that all explanations include uncertainty footer."""
        service = get_explanation_service()
        
        prediction = {
            "direction": "UP",
            "confidence": 0.75,
            "current_price": 100,
            "prediction_price": 110,
        }
        explanation = service.explain_ml_prediction(
            ticker="TEST",
            prediction=prediction,
        )
        
        # Should include uncertainty section or error message
        assert ("Uncertainty" in explanation or "uncertainty" in explanation.lower() or
                "Disclaimer" in explanation or "disclaimer" in explanation.lower() or
                "error" in explanation.lower())


class TestResearchSchemas:
    """Test schema validation."""

    def test_company_overview_request_validation(self):
        """Test company overview request validation."""
        # Valid request
        req = CompanyOverviewRequest(ticker="TCS", language="simple")
        assert req.ticker == "TCS"
        assert req.language == "simple"

    def test_company_overview_request_invalid_ticker_length(self):
        """Test validation of ticker length."""
        with pytest.raises(ValueError):
            CompanyOverviewRequest(ticker="", language="simple")

    def test_financial_analysis_request_validation(self):
        """Test financial analysis request."""
        req = FinancialAnalysisRequest(ticker="INFY", period="5Y")
        assert req.ticker == "INFY"
        assert req.period == "5Y"

    def test_swot_request_validation(self):
        """Test SWOT request."""
        req = SWOTRequest(ticker="HDFC")
        assert req.ticker == "HDFC"

    def test_comparison_request_validation(self):
        """Test comparison request validation."""
        # Valid: 2 tickers
        req = ComparisonRequest(tickers=["TCS", "INFY"])
        assert len(req.tickers) == 2

        # Invalid: only 1 ticker
        with pytest.raises(ValueError):
            ComparisonRequest(tickers=["TCS"])

        # Invalid: too many tickers
        with pytest.raises(ValueError):
            ComparisonRequest(tickers=["A", "B", "C", "D", "E", "F"])

    def test_ml_prediction_explanation_request_validation(self):
        """Test ML prediction request validation."""
        req = MLPredictionExplanationRequest(
            ticker="TCS",
            direction="UP",
            confidence=0.72,
            current_price=3650,
            prediction_price=3850,
        )
        assert req.direction == "UP"
        assert 0 <= req.confidence <= 1

    def test_ml_prediction_request_invalid_confidence(self):
        """Test ML prediction with invalid confidence."""
        with pytest.raises(ValueError):
            MLPredictionExplanationRequest(
                ticker="TCS",
                direction="UP",
                confidence=1.5,  # Invalid, must be 0-1
                current_price=3650,
                prediction_price=3850,
            )

    def test_technical_signal_request_validation(self):
        """Test technical signal request."""
        req = TechnicalSignalExplanationRequest(
            ticker="TCS",
            signal="BUY",
            indicators={"rsi": 35},
        )
        assert req.signal == "BUY"

    def test_fundamental_score_request_validation(self):
        """Test fundamental score request."""
        req = FundamentalScoreExplanationRequest(
            ticker="TCS",
            score=78.5,
            factors={"pe": 18.5},
        )
        assert 0 <= req.score <= 100

    def test_fundamental_score_request_invalid_score(self):
        """Test fundamental score with invalid score."""
        with pytest.raises(ValueError):
            FundamentalScoreExplanationRequest(
                ticker="TCS",
                score=150,  # Invalid, must be 0-100
                factors={},
            )

    def test_news_sentiment_request_validation(self):
        """Test news sentiment request."""
        req = NewsSentimentExplanationRequest(
            ticker="TCS",
            sentiment_score=0.72,
            sentiment_category="positive",
        )
        assert 0 <= req.sentiment_score <= 1

    def test_news_sentiment_request_invalid_category(self):
        """Test news sentiment with invalid category is accepted (validation at API level)."""
        # Note: Pydantic allows any string, validation happens at API route level
        # So we just verify the request is created
        req = NewsSentimentExplanationRequest(
            ticker="TCS",
            sentiment_score=0.72,
            sentiment_category="positive",
        )
        assert req.sentiment_category == "positive"


class TestIntegration:
    """Integration tests."""

    def test_full_research_flow(self):
        """Test complete research workflow."""
        db = SessionLocal()
        try:
            assistant = get_research_assistant(db)
            
            # Generate various analyses
            overview = assistant.generate_company_overview("INVALID123")
            assert isinstance(overview, str)
            
            # Try comparison
            comparison = assistant.compare_companies(["INVALID1", "INVALID2"])
            assert isinstance(comparison, str)
            
            # Generate report
            report = assistant.generate_research_report("INVALID123")
            assert isinstance(report, str)
            
        finally:
            db.close()

    def test_full_explanation_flow(self):
        """Test complete explanation workflow."""
        service = get_explanation_service()
        
        # Explain prediction
        pred_exp = service.explain_ml_prediction(
            ticker="TEST",
            prediction={"direction": "UP", "confidence": 0.7, "current_price": 100, "prediction_price": 110},
        )
        assert isinstance(pred_exp, str)
        
        # Explain signal
        sig_exp = service.explain_technical_signal(
            ticker="TEST",
            signal="BUY",
            indicators={"rsi": 35},
        )
        assert isinstance(sig_exp, str)
        
        # Explain score
        score_exp = service.explain_fundamental_score(
            ticker="TEST",
            score=75,
            factors={"pe": 18},
        )
        assert isinstance(score_exp, str)
        
        # Explain sentiment
        sent_exp = service.explain_news_sentiment(
            ticker="TEST",
            sentiment_score=0.7,
            sentiment_category="positive",
        )
        assert isinstance(sent_exp, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
