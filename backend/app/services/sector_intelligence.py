from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Company, CompanyFinancial, CompanyFundamentalInfo, DailyMarketData, Sector
from app.services.fundamental_scoring import calculate_fundamental_score


def _company_score(db: Session, company: Company) -> tuple[Decimal | None, str | None]:
    result = calculate_fundamental_score(db, company)
    return result.score, result.classification.value


def list_sector_items(db: Session) -> list[dict]:
    rows = list(
        db.execute(
            select(Sector, Company)
            .join(Company, Company.sector_id == Sector.id)
            .where(Company.is_active.is_(True), Company.instrument_type.ilike("company"))
        ).all()
    )
    grouped: dict[str, dict] = {}
    for sector, company in rows:
        item = grouped.setdefault(
            sector.sector_name,
            {"sector": sector.sector_name, "industries": set(), "company_count": 0, "latest_data_at": None},
        )
        if sector.industry_name:
            item["industries"].add(sector.industry_name)
        item["company_count"] += 1
        info_ts = db.scalar(
            select(CompanyFundamentalInfo.retrieved_at)
            .where(CompanyFundamentalInfo.company_id == company.id)
        )
        if info_ts and (item["latest_data_at"] is None or info_ts > item["latest_data_at"]):
            item["latest_data_at"] = info_ts
    return [
        {**item, "industries": sorted(item["industries"])}
        for item in sorted(grouped.values(), key=lambda value: value["sector"].lower())
    ]


def sector_intelligence(db: Session, sector_name: str, limit: int = 50) -> dict:
    sectors = list(
        db.scalars(
            select(Sector).where(Sector.sector_name.ilike(sector_name))
        )
    )
    if not sectors:
        raise ValueError(f"Sector not found: {sector_name}")
    sector_ids = [sector.id for sector in sectors]
    companies = list(
        db.scalars(
            select(Company)
            .where(
                Company.sector_id.in_(sector_ids),
                Company.is_active.is_(True),
                Company.instrument_type.ilike("company"),
            )
            .order_by(Company.symbol)
            .limit(limit)
        )
    )
    entries = []
    daily_changes: list[Decimal] = []
    scores: list[Decimal] = []
    for company in companies:
        info = db.scalar(select(CompanyFundamentalInfo).where(CompanyFundamentalInfo.company_id == company.id))
        prices = list(
            db.scalars(
                select(DailyMarketData)
                .where(DailyMarketData.company_id == company.id)
                .order_by(DailyMarketData.trading_date.desc())
                .limit(2)
            )
        )
        latest_close = prices[0].close if prices else None
        change = None
        if len(prices) == 2 and prices[1].close not in (None, 0):
            change = (prices[0].close - prices[1].close) / prices[1].close * Decimal("100")
            daily_changes.append(change)
        score, classification = _company_score(db, company)
        if score is not None:
            scores.append(score)
        entries.append(
            {
                "symbol": company.symbol,
                "name": company.name,
                "industry": next((s.industry_name for s in sectors if s.id == company.sector_id), None),
                "market_cap": info.market_cap if info else None,
                "latest_close": latest_close,
                "daily_change_pct": change,
                "fundamental_score": score,
                "classification": classification,
            }
        )
    entries.sort(key=lambda item: (item["fundamental_score"] is None, -(item["fundamental_score"] or Decimal("0"))))
    warnings = [
        "This is an average for the tracked ArthAI company universe, not a market-wide benchmark.",
        "Yahoo Finance data may be delayed, stale, revised, or missing for some companies.",
    ]
    return {
        "sector": sectors[0].sector_name,
        "tracked_company_count": len(companies),
        "industry_count": len({s.industry_name for s in sectors if s.industry_name}),
        "average_daily_change_pct": sum(daily_changes, Decimal("0")) / len(daily_changes) if daily_changes else None,
        "average_fundamental_score": sum(scores, Decimal("0")) / len(scores) if scores else None,
        "companies": entries,
        "data_scope": "tracked_universe",
        "warnings": warnings,
        "generated_at": datetime.now(timezone.utc),
    }
