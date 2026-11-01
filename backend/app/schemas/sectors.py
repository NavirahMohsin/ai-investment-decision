from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CompanyProfileResponse(BaseModel):
    symbol: str
    name: str
    provider_symbol: str
    exchange: str
    sector: str | None
    industry: str | None
    business_summary: str | None
    website: str | None
    country: str | None
    currency: str | None
    headquarters_city: str | None
    headquarters_state: str | None
    headquarters_country: str | None
    employees: int | None
    fiscal_year_end: str | None
    products_services: list[str] | None
    revenue_segments: dict[str, float] | None
    market_cap: int | None
    enterprise_value: int | None
    data_source: str | None
    retrieved_at: datetime | None
    data_freshness: str


class SectorListItem(BaseModel):
    sector: str
    industries: list[str] = Field(default_factory=list)
    company_count: int
    latest_data_at: datetime | None = None


class SectorCompanyItem(BaseModel):
    symbol: str
    name: str
    industry: str | None
    market_cap: int | None
    latest_close: Decimal | None
    daily_change_pct: Decimal | None
    fundamental_score: Decimal | None
    classification: str | None


class SectorIntelligenceResponse(BaseModel):
    sector: str
    tracked_company_count: int
    industry_count: int
    average_daily_change_pct: Decimal | None
    average_fundamental_score: Decimal | None
    companies: list[SectorCompanyItem]
    data_scope: str
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime
