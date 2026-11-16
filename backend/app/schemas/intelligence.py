"""Schemas for unified stock intelligence responses."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class SectionStatus(BaseModel):
    status: Literal["available", "unavailable"]
    reason: Optional[str] = None


class MarketIntelligenceSection(SectionStatus):
    current_price: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[int] = None
    day_change: Optional[float] = None
    day_change_pct: Optional[float] = None
    week_52_high: Optional[float] = Field(default=None, alias="52w_high")
    week_52_low: Optional[float] = Field(default=None, alias="52w_low")
    as_of_date: Optional[str] = None
    data_points: Optional[int] = None
    freshness: Optional[str] = None
    source: Optional[str] = None

    model_config = {"populate_by_name": True}


class TechnicalIntelligenceSection(SectionStatus):
    rsi_14: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    atr_14: Optional[float] = None
    annualized_volatility_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    data_window_days: Optional[int] = None
    signals: Optional[Any] = None
    trend: Optional[dict[str, Any]] = None
    source: Optional[str] = None


class FundamentalIntelligenceSection(SectionStatus):
    period_end: Optional[str] = None
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    ebitda: Optional[float] = None
    total_assets: Optional[float] = None
    total_equity: Optional[float] = None
    total_debt: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    free_cash_flow: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    profit_margin: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    pe_ratio: Optional[float] = None
    market_cap: Optional[float] = None
    book_value_per_share: Optional[float] = None
    dividend_yield: Optional[float] = None
    source: Optional[str] = None


class NewsArticleBrief(BaseModel):
    title: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = None
    sentiment: Optional[str] = None
    url: Optional[str] = None


class NewsIntelligenceSection(SectionStatus):
    article_count: Optional[int] = None
    positive: Optional[int] = None
    negative: Optional[int] = None
    neutral: Optional[int] = None
    average_sentiment_score: Optional[float] = None
    latest_articles: Optional[list[NewsArticleBrief]] = None
    source: Optional[str] = None


class MLIntelligenceSection(SectionStatus):
    model_id: Optional[str] = None
    model_type: Optional[str] = None
    predicted_class: Optional[str] = None
    confidence: Optional[float] = None
    probabilities: Optional[dict[str, float]] = None
    horizon_days: Optional[int] = None
    as_of_date: Optional[str] = None
    model_accuracy: Optional[float] = None
    source: Optional[str] = None


class RiskIntelligenceSection(SectionStatus):
    atr_14: Optional[float] = None
    annualized_volatility_pct: Optional[float] = None
    volatility_profile: Optional[str] = None
    max_drawdown_pct: Optional[float] = None
    data_window_days: Optional[int] = None
    warnings: Optional[list[str]] = None
    source: Optional[str] = None


class AgentInsightSection(SectionStatus):
    insights: Optional[list[dict[str, Any]]] = None
    source: Optional[str] = None


class AISynthesisSection(SectionStatus):
    synthesis: Optional[str] = None
    disclaimer: Optional[str] = None


class UnifiedStockIntelligenceResponse(BaseModel):
    symbol: str
    company_name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    exchange: Optional[str] = None
    generated_at: str
    disclaimer: str
    warnings: list[str] = Field(default_factory=list)
    market_intelligence: dict[str, Any]
    technical_intelligence: dict[str, Any]
    fundamental_intelligence: dict[str, Any]
    news_intelligence: dict[str, Any]
    ml_intelligence: dict[str, Any]
    risk_intelligence: dict[str, Any]
    agent_insights: Optional[dict[str, Any]] = None
    ai_synthesis: dict[str, Any]
