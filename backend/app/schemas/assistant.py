"""
Schemas for the Financial Assistant API.
"""

from typing import Optional
from pydantic import BaseModel, Field


class AssistantQuestionRequest(BaseModel):
    """Request to ask the financial assistant a question."""
    question: str = Field(..., description="Question about stocks or market", min_length=5)
    include_history: bool = Field(
        default=True,
        description="Whether to include conversation history for context"
    )


class AssistantResponseItem(BaseModel):
    """Response from the financial assistant."""
    answer: str = Field(..., description="Direct answer to the question")
    sources: list[str] = Field(
        default_factory=list,
        description="Data sources used (market data, fundamentals, news, etc.)"
    )
    confidence: str = Field(
        default="medium",
        description="Confidence level: low, medium, high"
    )
    disclaimer: str = Field(
        default="This response contains model-generated interpretations. Please verify with official sources.",
        description="Important disclaimer about AI-generated content"
    )
    related_companies: list[str] = Field(
        default_factory=list,
        description="Related companies mentioned"
    )


class ExplanationRequest(BaseModel):
    """Request to explain a score or signal."""
    ticker: str = Field(..., description="Stock ticker symbol", min_length=1, max_length=10)
    type: str = Field(..., description="Type: 'fundamental_score' or 'technical_signal'")
    score_or_signal: Optional[float | str] = Field(
        None,
        description="The score (0-100) or signal name (BUY/SELL/HOLD)"
    )
    factors: dict = Field(
        default_factory=dict,
        description="Factors/indicators contributing to the score or signal"
    )


class ExplanationResponse(BaseModel):
    """Response with explanation."""
    explanation: str = Field(..., description="The explanation")
    ticker: str = Field(..., description="Stock ticker")
    type: str = Field(..., description="Type of explanation")


class StockComparisonRequest(BaseModel):
    """Request to compare stocks."""
    tickers: list[str] = Field(
        ...,
        description="Stock tickers to compare",
        min_length=2,
        max_length=5
    )


class StockComparisonResponse(BaseModel):
    """Response with comparison analysis."""
    comparison: str = Field(..., description="Detailed comparison analysis")
    tickers: list[str] = Field(..., description="Stocks compared")


class HealthResponse(BaseModel):
    """Health check response for LLM service."""
    status: str = Field(..., description="Status: 'healthy' or 'degraded'")
    gemini_available: bool = Field(..., description="Is Gemini API available")
    groq_available: bool = Field(..., description="Is Groq API available")
    message: str = Field(..., description="Status message")
