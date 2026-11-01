"""Pydantic schemas for company fundamentals APIs."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MetricObservationSchema(BaseModel):
    period_end: date
    period_type: str
    value: Decimal | None = None
    currency: str | None = None
    source: Literal["reported", "calculated"] = "reported"
    metric_name: str | None = None
    derived_label: str | None = None


class GrowthPointSchema(BaseModel):
    period_end: date
    comparison_period_end: date
    comparison_type: Literal["yoy", "qoq", "same_quarter_yoy"]
    growth_rate: Decimal | None = None
    growth_pct: Decimal | None = None
    current_value: Decimal | None = None
    previous_value: Decimal | None = None
    is_derived: bool = True
    error: str | None = None


class MetricSeriesSchema(BaseModel):
    metric_key: str
    display_name: str
    period_type: str
    observations: list[MetricObservationSchema] = Field(default_factory=list)
    growth: list[GrowthPointSchema] = Field(default_factory=list)
    trend: str
    quality: str
    missing_periods: list[str] = Field(default_factory=list)
    currency: str | None = None
    notes: list[str] = Field(default_factory=list)


class MarginSeriesSchema(BaseModel):
    metric_key: str
    display_name: str
    period_type: str
    observations: list[MetricObservationSchema] = Field(default_factory=list)
    trend: str
    quality: str
    notes: list[str] = Field(default_factory=list)


class CashConversionSchema(BaseModel):
    period_end: date
    operating_cash_flow: Decimal | None = None
    free_cash_flow: Decimal | None = None
    net_income: Decimal | None = None
    ocf_to_ni: Decimal | None = None
    fcf_to_ni: Decimal | None = None
    notes: list[str] = Field(default_factory=list)


class ProfitabilityInsightSchema(BaseModel):
    overall_trend: str
    margin_compression: bool | None = None
    margin_expansion: bool | None = None
    inconsistent_earnings: bool
    notes: list[str] = Field(default_factory=list)


class BalanceSheetInsightSchema(BaseModel):
    leverage_trend: str
    liquidity_trend: str
    strength_trend: str
    notes: list[str] = Field(default_factory=list)


class HistoricalPerformanceResponse(BaseModel):
    symbol: str
    period_type: str
    revenue: MetricSeriesSchema
    gross_profit: MetricSeriesSchema
    operating_income: MetricSeriesSchema
    net_income: MetricSeriesSchema
    eps: MetricSeriesSchema
    gross_margin: MarginSeriesSchema
    operating_margin: MarginSeriesSchema
    net_margin: MarginSeriesSchema
    total_assets: MetricSeriesSchema
    total_liabilities: MetricSeriesSchema
    total_debt: MetricSeriesSchema
    equity: MetricSeriesSchema
    current_assets: MetricSeriesSchema
    current_liabilities: MetricSeriesSchema
    working_capital: MetricSeriesSchema
    operating_cash_flow: MetricSeriesSchema
    investing_cash_flow: MetricSeriesSchema
    financing_cash_flow: MetricSeriesSchema
    free_cash_flow: MetricSeriesSchema
    capital_expenditure: MetricSeriesSchema
    cash_conversion: list[CashConversionSchema]
    profitability_insight: ProfitabilityInsightSchema
    balance_sheet_insight: BalanceSheetInsightSchema
    data_warnings: list[str] = Field(default_factory=list)


class RatioValueSchema(BaseModel):
    name: str
    value: Decimal | None = None
    category: str
    inputs_available: bool = False
    error: str | None = None
    origin: Literal["retrieved", "calculated", "unavailable", "not_applicable"] = "unavailable"


class FinancialRatiosResponse(BaseModel):
    symbol: str
    period_type: str
    valuation: dict[str, RatioValueSchema]
    profitability: dict[str, RatioValueSchema]
    liquidity: dict[str, RatioValueSchema]
    leverage: dict[str, RatioValueSchema]
    efficiency: dict[str, RatioValueSchema]
    growth: dict[str, RatioValueSchema]
    calculated_at: datetime


class StatementLineSchema(BaseModel):
    metric_name: str
    value: Decimal | None = None
    period_end: date | None = None
    period_type: str
    statement_type: str | None = None
    currency: str | None = None
    retrieved_at: datetime


class FinancialStatementsResponse(BaseModel):
    symbol: str
    statement_type: str
    period_type: str
    currency: str | None = None
    lines: list[StatementLineSchema]
    periods: list[date]
    limit: int | None = None
    retrieved_at: datetime | None = None


class AssessmentMetricSchema(BaseModel):
    key: str
    name: str
    value: Decimal | None = None
    unit: str | None = None
    applicable: bool = True
    origin: str = "calculated"


class DimensionAssessmentSchema(BaseModel):
    dimension: str
    classification: str
    metrics_used: list[AssessmentMetricSchema] = Field(default_factory=list)
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    reporting_period: str | None = None
    data_freshness: str | None = None
    explanation: str
    sector_methodology: str


class FundamentalAnalysisResponse(BaseModel):
    symbol: str
    company_name: str
    sector: str | None = None
    industry: str | None = None
    overall_classification: str
    profitability: DimensionAssessmentSchema
    growth: DimensionAssessmentSchema
    financial_stability: DimensionAssessmentSchema
    valuation: DimensionAssessmentSchema
    cash_flow_quality: DimensionAssessmentSchema
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    missing_data_warnings: list[str] = Field(default_factory=list)
    analysis_version: str
    generated_at: datetime


class DimensionScoreSchema(BaseModel):
    dimension: str
    score: Decimal | None = None
    weight: Decimal
    included: bool
    exclusion_reason: str | None = None
    explanation: str | None = None


class FundamentalScoreResponse(BaseModel):
    symbol: str
    score: Decimal | None = None
    classification: str
    data_completeness: Decimal
    metrics_evaluated: int
    dimensions_excluded: list[str] = Field(default_factory=list)
    dimension_scores: list[DimensionScoreSchema] = Field(default_factory=list)
    major_contributors: list[str] = Field(default_factory=list)
    missing_metrics: list[str] = Field(default_factory=list)
    methodology_version: str
    explanation: str
    generated_at: datetime


class CompanyFundamentalOverview(BaseModel):
    symbol: str
    name: str
    exchange: str
    sector: str | None = None
    industry: str | None = None
    business_summary: str | None = None
    market_cap: int | None = None
    enterprise_value: int | None = None
    currency: str | None = None
    employees: int | None = None
    website: str | None = None
    data_source: str | None = None
    retrieved_at: datetime | None = None
    data_freshness: str


class FinancialHighlightSchema(BaseModel):
    key: str
    label: str
    value: Decimal | None = None
    period_end: date | None = None
    period_type: str | None = None
    origin: Literal["retrieved", "calculated", "unavailable"] = "unavailable"
    currency: str | None = None
    unit: str | None = None


class FundamentalsSummaryResponse(BaseModel):
    company: CompanyFundamentalOverview
    highlights: list[FinancialHighlightSchema]
    ratios: FinancialRatiosResponse | None = None
    analysis: FundamentalAnalysisResponse | None = None
    score: FundamentalScoreResponse | None = None
    data_completeness: Decimal
    last_retrieval_at: datetime | None = None


class ComparisonMetricSchema(BaseModel):
    key: str
    label: str
    category: str
    values: dict[str, Decimal | None]
    comparable: bool
    incomparable_reason: str | None = None
    ranking: list[str] | None = None
    ranking_period: str | None = None
    companies_with_data: int = 0
    companies_excluded: list[str] = Field(default_factory=list)


class CompanyComparisonEntry(BaseModel):
    symbol: str
    name: str
    sector: str | None = None
    currency: str | None = None
    reporting_period: str | None = None
    period_end: date | None = None
    overall_classification: str | None = None
    fundamental_score: Decimal | None = None
    metrics: dict[str, Decimal | None] = Field(default_factory=dict)
    classifications: dict[str, str] = Field(default_factory=dict)


class CompanyComparisonResponse(BaseModel):
    symbols: list[str]
    companies: list[CompanyComparisonEntry]
    metrics: list[ComparisonMetricSchema]
    comparability_warnings: list[str] = Field(default_factory=list)
    sector_warning: str | None = None
    generated_at: datetime


class FundamentalsRefreshRequest(BaseModel):
    symbols: list[str] | None = Field(
        default=None,
        description="Symbols to refresh. Omit with refresh_all=true for all companies.",
    )
    refresh_all: bool = False
    include_info: bool = True
    include_statements: bool = True
    include_ratios: bool = True
    max_companies: int = Field(default=25, ge=1, le=100)


class CompanyRefreshStatus(BaseModel):
    symbol: str
    success: bool
    company_info_updated: bool = False
    financials_inserted: int = 0
    financials_updated: int = 0
    ratios_inserted: int = 0
    error: str | None = None


class FundamentalsRefreshResponse(BaseModel):
    run_id: int | None = None
    status: str
    trigger_source: str = "manual"
    companies_requested: int
    companies_processed: int
    successful_count: int
    failed_count: int
    results: list[CompanyRefreshStatus]
    started_at: datetime
    completed_at: datetime | None = None


class CompanyUpdateHealth(BaseModel):
    symbol: str
    last_retrieved_at: datetime | None = None
    data_freshness: str
    has_statements: bool
    has_ratios: bool
    has_company_info: bool
    completeness: Decimal


class FundamentalsHealthResponse(BaseModel):
    provider: str = "yahoo_finance"
    provider_status: str
    last_successful_update: datetime | None = None
    last_attempted_update: datetime | None = None
    last_run_status: str | None = None
    companies: list[CompanyUpdateHealth]
    failed_companies: list[str] = Field(default_factory=list)
    stale_companies: list[str] = Field(default_factory=list)
    checked_at: datetime


class DashboardFundamentalsSummary(BaseModel):
    strong_profiles: list[dict[str, Any]] = Field(default_factory=list)
    improving_profitability: list[dict[str, Any]] = Field(default_factory=list)
    improving_revenue_growth: list[dict[str, Any]] = Field(default_factory=list)
    elevated_debt: list[dict[str, Any]] = Field(default_factory=list)
    insufficient_data: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime
