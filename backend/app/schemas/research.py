"""
Schemas for Research Assistant and Explanations APIs.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# Research Endpoints

class CompanyOverviewRequest(BaseModel):
    """Request for company overview."""
    ticker: str = Field(..., description="Stock ticker symbol", min_length=1, max_length=10)
    language: str = Field(
        default="simple",
        description="Language complexity: simple or technical"
    )


class CompanyOverviewResponse(BaseModel):
    """Response with company overview."""
    overview: str = Field(..., description="Company overview text")
    ticker: str = Field(..., description="Stock ticker")


class FinancialAnalysisRequest(BaseModel):
    """Request for financial analysis."""
    ticker: str = Field(..., description="Stock ticker", min_length=1, max_length=10)
    period: str = Field(
        default="5Y",
        description="Analysis period: 1Y, 3Y, 5Y"
    )


class FinancialAnalysisResponse(BaseModel):
    """Response with financial analysis."""
    analysis: str = Field(..., description="Financial analysis")
    ticker: str = Field(..., description="Stock ticker")
    period: str = Field(..., description="Analysis period")


class SWOTRequest(BaseModel):
    """Request for SWOT analysis."""
    ticker: str = Field(..., description="Stock ticker", min_length=1, max_length=10)


class SWOTResponse(BaseModel):
    """Response with SWOT analysis."""
    swot: str = Field(..., description="SWOT analysis")
    ticker: str = Field(..., description="Stock ticker")


class ComparisonRequest(BaseModel):
    """Request to compare companies."""
    tickers: List[str] = Field(
        ...,
        description="Stock tickers to compare",
        min_length=2,
        max_length=5
    )


class ComparisonResponse(BaseModel):
    """Response with company comparison."""
    comparison: str = Field(..., description="Comparison analysis")
    tickers: List[str] = Field(..., description="Tickers compared")


class ResearchReportRequest(BaseModel):
    """Request for research report."""
    ticker: str = Field(..., description="Stock ticker", min_length=1, max_length=10)
    report_type: str = Field(
        default="comprehensive",
        description="Report type: summary or comprehensive"
    )


class ResearchReportResponse(BaseModel):
    """Response with research report."""
    report: str = Field(..., description="Full research report")
    ticker: str = Field(..., description="Stock ticker")
    report_id: Optional[int] = Field(None, description="Saved report ID if stored")


class SavedReportResponse(BaseModel):
    """Response for saved report."""
    id: int = Field(..., description="Report ID")
    ticker: str = Field(..., description="Stock ticker")
    report_type: str = Field(..., description="Report type")
    generated_at: str = Field(..., description="Generation timestamp")


class SavedReportListResponse(BaseModel):
    """Response with list of saved reports."""
    reports: List[SavedReportResponse] = Field(..., description="List of reports")
    count: int = Field(..., description="Total count")


class ReportRetrieveResponse(BaseModel):
    """Response when retrieving a saved report."""
    id: int = Field(..., description="Report ID")
    ticker: str = Field(..., description="Stock ticker")
    report_type: str = Field(..., description="Report type")
    content: str = Field(..., description="Report content")
    generated_at: str = Field(..., description="Generation timestamp")


# Explanation Endpoints

class MLPredictionExplanationRequest(BaseModel):
    """Request to explain ML prediction."""
    ticker: str = Field(..., description="Stock ticker", min_length=1, max_length=10)
    direction: str = Field(..., description="Prediction direction: UP or DOWN")
    confidence: float = Field(..., description="Confidence score (0-1)", ge=0, le=1)
    current_price: float = Field(..., description="Current stock price")
    prediction_price: float = Field(..., description="Predicted stock price")


class ExplanationResponse(BaseModel):
    """Response with explanation."""
    explanation: str = Field(..., description="Explanation text")
    ticker: str = Field(..., description="Stock ticker")
    type: str = Field(..., description="Explanation type")


class TechnicalSignalExplanationRequest(BaseModel):
    """Request to explain technical signal."""
    ticker: str = Field(..., description="Stock ticker", min_length=1, max_length=10)
    signal: str = Field(..., description="Signal: BUY, SELL, HOLD")
    indicators: Dict[str, Any] = Field(..., description="Indicator values")


class FundamentalScoreExplanationRequest(BaseModel):
    """Request to explain fundamental score."""
    ticker: str = Field(..., description="Stock ticker", min_length=1, max_length=10)
    score: float = Field(..., description="Score (0-100)", ge=0, le=100)
    factors: Dict[str, Any] = Field(..., description="Contributing factors")


class NewsSentimentExplanationRequest(BaseModel):
    """Request to explain news sentiment."""
    ticker: str = Field(..., description="Stock ticker", min_length=1, max_length=10)
    sentiment_score: float = Field(
        ...,
        description="Sentiment score (0-1)",
        ge=0,
        le=1
    )
    sentiment_category: str = Field(
        ...,
        description="Sentiment category: positive, negative, neutral"
    )
    themes: Optional[Dict[str, Any]] = Field(
        None,
        description="Key themes in sentiment"
    )


# Health Check

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Status: healthy or degraded")
    services_ready: List[str] = Field(..., description="Ready services")
    message: str = Field(..., description="Status message")
