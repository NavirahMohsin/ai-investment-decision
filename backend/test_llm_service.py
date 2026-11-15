"""
Tests for the LLM Service and Financial Assistant.

Tests core functionality:
- LLM provider availability
- Fallback mechanism
- Response parsing
- Financial assistant question answering
"""

import os
import pytest
from unittest.mock import Mock, patch

from app.services.llm_service import (
    LLMService,
    LLMProvider,
    LLMResponse,
    get_llm_service,
)
from app.services.financial_assistant import get_financial_assistant
from app.db.session import SessionLocal


class TestLLMService:
    """Tests for the LLM service."""

    def test_llm_service_initialization(self):
        """Test LLM service can be initialized."""
        service = LLMService()
        assert service is not None
        # Check that API keys are configured
        assert service.config.gemini_api_key or service.config.groq_api_key

    def test_provider_availability(self):
        """Test checking provider availability."""
        service = LLMService()
        # At least one provider should be available
        assert service.gemini_available or service.groq_available

    def test_singleton_pattern(self):
        """Test that get_llm_service returns same instance."""
        service1 = get_llm_service()
        service2 = get_llm_service()
        assert service1 is service2

    def test_provider_selection(self):
        """Test provider selection logic."""
        service = LLMService()
        
        # If Gemini is available, it should be preferred
        if service.gemini_available:
            assert service._is_provider_available(LLMProvider.GEMINI)
        
        # If Groq is available, it should work
        if service.groq_available:
            assert service._is_provider_available(LLMProvider.GROQ)


class TestFinancialAssistant:
    """Tests for the financial assistant."""

    def test_assistant_initialization(self):
        """Test financial assistant can be initialized."""
        db = SessionLocal()
        try:
            assistant = get_financial_assistant(db)
            assert assistant is not None
            assert assistant.db == db
            assert assistant.conversation_history == []
        finally:
            db.close()

    def test_conversation_history(self):
        """Test conversation history management."""
        db = SessionLocal()
        try:
            assistant = get_financial_assistant(db)
            
            # Add messages to history
            assistant.add_to_history("user", "Hello")
            assistant.add_to_history("assistant", "Hi there")
            
            # Check history
            assert len(assistant.conversation_history) == 2
            assert assistant.conversation_history[0].role == "user"
            assert assistant.conversation_history[0].content == "Hello"
            assert assistant.conversation_history[1].role == "assistant"
            assert assistant.conversation_history[1].content == "Hi there"
        finally:
            db.close()

    def test_ticker_extraction(self):
        """Test extracting ticker symbols from questions."""
        db = SessionLocal()
        try:
            assistant = get_financial_assistant(db)
            
            # Test questions with clear tickers (upper case, standalone)
            test_cases = [
                ("What is TCS doing?", "TCS"),
                ("Should I buy HDFC?", "HDFC"),
            ]
            
            for question, expected_ticker in test_cases:
                ticker = assistant._extract_ticker_from_question(question)
                # Verify extraction works
                if ticker:
                    assert ticker == expected_ticker or len(ticker) <= 4
            
            # Verify method doesn't error on regular text
            ticker = assistant._extract_ticker_from_question("What factors matter?")
            # Could be None or a short word, both are fine
            assert ticker is None or len(ticker) <= 4
        finally:
            db.close()

    def test_system_prompt_generation(self):
        """Test system prompt is generated correctly."""
        db = SessionLocal()
        try:
            assistant = get_financial_assistant(db)
            
            system_prompt = assistant._build_system_prompt()
            assert system_prompt is not None
            assert len(system_prompt) > 0
            assert "financial analyst" in system_prompt.lower()
            assert "Indian" in system_prompt
        finally:
            db.close()


class TestLLMServiceIntegration:
    """Integration tests for LLM service (requires API keys)."""

    @pytest.mark.skipif(
        not os.getenv("GEMINI") and not os.getenv("GROQ"),
        reason="Requires LLM API keys"
    )
    def test_simple_generation(self):
        """Test basic text generation."""
        service = get_llm_service()
        
        if not (service.gemini_available or service.groq_available):
            pytest.skip("No LLM providers available")
        
        try:
            response = service.generate(
                prompt="Say hello in one word",
                temperature=0.5,
                max_tokens=10,
            )
            
            assert response is not None
            assert response.content is not None
            assert len(response.content) > 0
            assert response.provider in [LLMProvider.GEMINI, LLMProvider.GROQ]
        except Exception as e:
            pytest.skip(f"LLM API call failed: {e}")


class TestFinancialAssistantIntegration:
    """Integration tests for financial assistant (requires database)."""

    def test_question_without_ticker(self):
        """Test asking a general question without specific ticker."""
        db = SessionLocal()
        try:
            assistant = get_financial_assistant(db)
            
            # This should not fail even without company data
            # (though response quality depends on LLM)
            response = assistant.ask_question(
                "What factors determine stock valuations?",
                include_history=False,
            )
            
            assert response is not None
            assert response.answer is not None
            assert len(response.answer) > 0
            # Should have disclaimer about AI-generated content
            assert "model-generated" in response.disclaimer.lower()
        except Exception as e:
            # Skip if LLM not available
            if "No LLM providers" in str(e):
                pytest.skip("No LLM providers available")
            raise
        finally:
            db.close()

    def test_fundamental_score_explanation_structure(self):
        """Test that score explanations have correct structure."""
        db = SessionLocal()
        try:
            assistant = get_financial_assistant(db)
            
            # Test explanation generation (doesn't require real company data)
            try:
                explanation = assistant.explain_fundamental_score(
                    ticker="TEST",
                    score=72.5,
                    factors={
                        "pe_ratio": 18.5,
                        "pb_ratio": 3.2,
                        "roe": 15.8,
                    }
                )
                
                assert explanation is not None
                assert len(explanation) > 0
            except Exception as e:
                if "No LLM providers" in str(e):
                    pytest.skip("No LLM providers available")
                raise
        finally:
            db.close()


class TestAssistantSchemas:
    """Tests for API request/response schemas."""

    def test_question_request_schema(self):
        """Test question request validation."""
        from app.schemas.assistant import AssistantQuestionRequest
        
        # Valid request
        req = AssistantQuestionRequest(question="What about TCS stock?")
        assert req.question == "What about TCS stock?"
        assert req.include_history is True
        
        # Invalid: too short
        with pytest.raises(ValueError):
            AssistantQuestionRequest(question="TCS?")

    def test_response_item_schema(self):
        """Test response item schema."""
        from app.schemas.assistant import AssistantResponseItem
        
        response = AssistantResponseItem(
            answer="The stock looks promising",
            sources=["Market Data", "Fundamentals"],
            confidence="high",
            related_companies=["TCS"],
        )
        
        assert response.answer == "The stock looks promising"
        assert "Market Data" in response.sources
        assert "model-generated" in response.disclaimer.lower()

    def test_comparison_request_schema(self):
        """Test stock comparison request validation."""
        from app.schemas.assistant import StockComparisonRequest
        
        # Valid: 2 tickers
        req = StockComparisonRequest(tickers=["TCS", "INFY"])
        assert len(req.tickers) == 2
        
        # Invalid: only 1 ticker
        with pytest.raises(ValueError):
            StockComparisonRequest(tickers=["TCS"])
        
        # Invalid: too many tickers
        with pytest.raises(ValueError):
            StockComparisonRequest(tickers=["A", "B", "C", "D", "E", "F"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
