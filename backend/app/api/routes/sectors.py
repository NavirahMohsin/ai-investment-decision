from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Company, CompanyFundamentalInfo, CompanyProfile
from app.db.session import get_db
from app.schemas.sectors import CompanyProfileResponse, SectorIntelligenceResponse, SectorListItem
from app.services.fundamentals_freshness import classify_fundamental_freshness
from app.services.sector_intelligence import list_sector_items, sector_intelligence

router = APIRouter(prefix="/api/v1", tags=["company profiles and sectors"])


@router.get("/sectors", response_model=list[SectorListItem])
def sectors(db: Session = Depends(get_db)):
    return list_sector_items(db)


@router.get("/sectors/{sector_name}", response_model=SectorIntelligenceResponse)
def sector_detail(
    sector_name: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    try:
        return sector_intelligence(db, sector_name, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/companies/{symbol}/profile", response_model=CompanyProfileResponse)
def company_profile(symbol: str, db: Session = Depends(get_db)):
    company = db.scalar(
        select(Company).where(
            Company.symbol == symbol.upper(),
            Company.is_active.is_(True),
        )
    )
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company not found: {symbol}")
    info = db.scalar(select(CompanyFundamentalInfo).where(CompanyFundamentalInfo.company_id == company.id))
    profile = db.scalar(select(CompanyProfile).where(CompanyProfile.company_id == company.id))
    retrieved = max(
        [value for value in (info.retrieved_at if info else None, profile.retrieved_at if profile else None) if value is not None],
        default=None,
    )
    return {
        "symbol": company.symbol,
        "name": company.name,
        "provider_symbol": company.provider_symbol,
        "exchange": company.exchange,
        "sector": company.sector,
        "industry": profile.industry if profile else None,
        "business_summary": info.business_summary if info else None,
        "website": info.website if info else None,
        "country": info.country if info else None,
        "currency": info.currency if info else None,
        "headquarters_city": profile.headquarters_city if profile else None,
        "headquarters_state": profile.headquarters_state if profile else None,
        "headquarters_country": profile.headquarters_country if profile else None,
        "employees": profile.full_time_employees if profile else (info.employees if info else None),
        "fiscal_year_end": profile.fiscal_year_end if profile else None,
        "products_services": profile.products_services if profile else None,
        "revenue_segments": profile.revenue_segments if profile else None,
        "market_cap": info.market_cap if info else None,
        "enterprise_value": info.enterprise_value if info else None,
        "data_source": info.data_source if info else (profile.data_source if profile else None),
        "retrieved_at": retrieved,
        "data_freshness": classify_fundamental_freshness(retrieved).value,
    }
