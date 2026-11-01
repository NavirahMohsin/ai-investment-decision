"""Fundamental data ingestion and management service."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Company,
    CompanyFinancial,
    CompanyFundamentalInfo,
    CompanyProfile,
    FundamentalDataUpdateRun,
    Sector,
)
from app.services.providers.yahoo import YahooFinanceProvider, CompanyInfo, FinancialStatement


class IngestionResult(TypedDict):
    """Result of a fundamental data ingestion operation."""
    company_symbol: str
    success: bool
    company_info_updated: bool
    financials_inserted: int
    financials_updated: int
    ratios_inserted: int
    error: str | None


def ingest_company_info(
    db: Session,
    company: Company,
    provider: YahooFinanceProvider,
) -> bool:
    """
    Ingest or update company fundamental information.
    
    Args:
        db: Database session
        company: Company model instance
        provider: Yahoo Finance provider
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Fetch company info from Yahoo Finance
        info = provider.get_company_info(company.provider_symbol)
        sector_name = info.get("sector")
        industry_name = info.get("industry")
        if sector_name:
            sector = db.scalar(
                select(Sector).where(
                    Sector.sector_name == sector_name,
                    Sector.industry_name == industry_name,
                )
            )
            if sector is None:
                sector = Sector(
                    sector_name=sector_name,
                    industry_name=industry_name,
                    data_source="yahoo_finance",
                    retrieved_at=info.get("retrieved_at") or datetime.now(timezone.utc),
                )
                db.add(sector)
                db.flush()
            company.sector = sector_name
            company.sector_id = sector.id
        
        # Check if info exists
        existing = db.scalar(
            select(CompanyFundamentalInfo).where(
                CompanyFundamentalInfo.company_id == company.id
            )
        )
        
        if existing:
            # Update existing record
            existing.business_summary = info.get("business_summary")
            existing.website = info.get("website")
            existing.country = info.get("country")
            existing.currency = info.get("currency")
            existing.market_cap = info.get("market_cap")
            existing.enterprise_value = info.get("enterprise_value")
            existing.employees = info.get("employees")
            existing.data_source = "yahoo_finance"
            existing.retrieved_at = info.get("retrieved_at") or datetime.now(timezone.utc)
            existing.updated_at = datetime.now(timezone.utc)
        else:
            # Create new record
            fundamental_info = CompanyFundamentalInfo(
                company_id=company.id,
                business_summary=info.get("business_summary"),
                website=info.get("website"),
                country=info.get("country"),
                currency=info.get("currency"),
                market_cap=info.get("market_cap"),
                enterprise_value=info.get("enterprise_value"),
                employees=info.get("employees"),
                data_source="yahoo_finance",
                retrieved_at=info.get("retrieved_at") or datetime.now(timezone.utc),
            )
            db.add(fundamental_info)

        profile = db.scalar(
            select(CompanyProfile).where(CompanyProfile.company_id == company.id)
        )
        profile_values = {
            "industry": industry_name,
            "headquarters_city": info.get("headquarters_city"),
            "headquarters_state": info.get("headquarters_state"),
            "headquarters_country": info.get("headquarters_country") or info.get("country"),
            "full_time_employees": info.get("employees"),
            "fiscal_year_end": str(info["fiscal_year_end"]) if info.get("fiscal_year_end") is not None else None,
            "data_source": "yahoo_finance",
            "retrieved_at": info.get("retrieved_at") or datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        if profile:
            for key, value in profile_values.items():
                setattr(profile, key, value)
        else:
            db.add(CompanyProfile(company_id=company.id, **profile_values))
        
        db.commit()
        return True
    
    except Exception as error:
        db.rollback()
        print(f"Error ingesting company info for {company.symbol}: {error}")
        return False


def ingest_financial_statements(
    db: Session,
    company: Company,
    provider: YahooFinanceProvider,
    statement_types: list[str] | None = None,
    period_types: list[str] | None = None,
) -> tuple[int, int]:
    """
    Ingest financial statements for a company.
    
    Args:
        db: Database session
        company: Company model instance
        provider: Yahoo Finance provider
        statement_types: List of statement types to ingest (default: all)
        period_types: List of period types to ingest (default: annual and quarterly)
    
    Returns:
        Tuple of (inserted_count, updated_count)
    """
    if statement_types is None:
        statement_types = ["income", "balance", "cashflow"]
    
    if period_types is None:
        period_types = ["annual", "quarterly"]
    
    inserted = 0
    updated = 0
    
    for statement_type in statement_types:
        for period_type in period_types:
            try:
                statements = provider.get_financials(
                    company.provider_symbol,
                    statement_type,
                    period_type,
                )
                
                for statement in statements:
                    result = _upsert_financial_metric(
                        db,
                        company.id,
                        statement,
                        statement_type,
                    )
                    
                    if result == "inserted":
                        inserted += 1
                    elif result == "updated":
                        updated += 1
            
            except Exception as error:
                print(f"Error ingesting {period_type} {statement_type} for {company.symbol}: {error}")
                continue
    
    db.commit()
    return inserted, updated


def ingest_financial_ratios(
    db: Session,
    company: Company,
    provider: YahooFinanceProvider,
) -> int:
    """
    Ingest pre-calculated financial ratios for a company.
    
    Args:
        db: Database session
        company: Company model instance
        provider: Yahoo Finance provider
    
    Returns:
        Number of ratios inserted/updated
    """
    try:
        ratios = provider.get_financial_ratios(company.provider_symbol)
        
        count = 0
        retrieved_at = datetime.now(timezone.utc)
        
        for metric_name, metric_value in ratios.items():
            if metric_value is None:
                continue
            
            # Ratios are TTM (trailing twelve months) or point-in-time
            result = _upsert_financial_metric(
                db,
                company.id,
                FinancialStatement(
                    metric=metric_name,
                    value=metric_value,
                    period_end=None,  # Ratios don't have specific period end
                    period_type="ttm",
                    currency=None,
                ),
                "ratio",
                retrieved_at,
            )
            
            if result in ("inserted", "updated"):
                count += 1
        
        db.commit()
        return count
    
    except Exception as error:
        db.rollback()
        print(f"Error ingesting ratios for {company.symbol}: {error}")
        return 0


def _upsert_financial_metric(
    db: Session,
    company_id: int,
    statement: FinancialStatement,
    statement_type: str,
    retrieved_at: datetime | None = None,
) -> str:
    """
    Insert or update a financial metric.
    
    Args:
        db: Database session
        company_id: Company ID
        statement: Financial statement data
        statement_type: Type of statement (income, balance, cashflow, ratio)
        retrieved_at: Retrieval timestamp
    
    Returns:
        'inserted', 'updated', or 'skipped'
    """
    metric_name = statement["metric"]
    metric_value = statement.get("value")
    period_end = statement.get("period_end")
    period_type = statement["period_type"]
    currency = statement.get("currency")
    
    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc)
    
    # Check if record exists
    existing = db.scalar(
        select(CompanyFinancial).where(
            CompanyFinancial.company_id == company_id,
            CompanyFinancial.metric_name == metric_name,
            CompanyFinancial.period_end == period_end,
            CompanyFinancial.period_type == period_type,
        )
    )
    
    if existing:
        # Update if value changed
        if existing.metric_value != metric_value:
            existing.metric_value = metric_value
            existing.currency = currency
            existing.retrieved_at = retrieved_at
            existing.updated_at = datetime.now(timezone.utc)
            return "updated"
        return "skipped"
    else:
        # Insert new record
        financial = CompanyFinancial(
            company_id=company_id,
            metric_name=metric_name,
            metric_value=metric_value,
            period_end=period_end,
            period_type=period_type,
            statement_type=statement_type,
            currency=currency,
            data_source="yahoo_finance",
            retrieved_at=retrieved_at,
        )
        db.add(financial)
        return "inserted"


def ingest_company_fundamentals(
    db: Session,
    company: Company,
    provider: YahooFinanceProvider | None = None,
    include_info: bool = True,
    include_statements: bool = True,
    include_ratios: bool = True,
) -> IngestionResult:
    """
    Ingest all fundamental data for a company.
    
    Args:
        db: Database session
        company: Company model instance
        provider: Yahoo Finance provider (created if None)
        include_info: Whether to ingest company info
        include_statements: Whether to ingest financial statements
        include_ratios: Whether to ingest financial ratios
    
    Returns:
        IngestionResult with details of the operation
    """
    if provider is None:
        provider = YahooFinanceProvider()
    
    result: IngestionResult = {
        "company_symbol": company.symbol,
        "success": True,
        "company_info_updated": False,
        "financials_inserted": 0,
        "financials_updated": 0,
        "ratios_inserted": 0,
        "error": None,
    }
    
    try:
        # Ingest company info
        if include_info:
            result["company_info_updated"] = ingest_company_info(db, company, provider)
            if not result["company_info_updated"]:
                result["success"] = False
                result["error"] = "Company information could not be retrieved."
        
        # Ingest financial statements
        if include_statements:
            inserted, updated = ingest_financial_statements(db, company, provider)
            result["financials_inserted"] = inserted
            result["financials_updated"] = updated
        
        # Ingest financial ratios
        if include_ratios:
            result["ratios_inserted"] = ingest_financial_ratios(db, company, provider)
    
    except Exception as error:
        result["success"] = False
        result["error"] = str(error)
    
    return result


def ingest_all_companies_fundamentals(
    db: Session,
    include_info: bool = True,
    include_statements: bool = True,
    include_ratios: bool = True,
) -> FundamentalDataUpdateRun:
    """
    Ingest fundamental data for all active companies.
    
    Args:
        db: Database session
        include_info: Whether to ingest company info
        include_statements: Whether to ingest financial statements
        include_ratios: Whether to ingest financial ratios
    
    Returns:
        FundamentalDataUpdateRun record
    """
    # Determine run type
    run_type_parts = []
    if include_info:
        run_type_parts.append("info")
    if include_statements:
        run_type_parts.append("statements")
    if include_ratios:
        run_type_parts.append("ratios")
    run_type = "+".join(run_type_parts) if run_type_parts else "all"
    
    # Create update run record
    run = FundamentalDataUpdateRun(
        run_type=run_type,
        status="running",
        companies_processed=0,
        successful_count=0,
        failed_count=0,
        failed_symbols=None,
        trigger_source="manual",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    
    # Get all active companies (excluding indices)
    companies = list(
        db.scalars(
            select(Company).where(
                Company.is_active.is_(True),
                Company.instrument_type.ilike("company"),
            )
        )
    )
    
    provider = YahooFinanceProvider()
    successful = 0
    failed = 0
    failed_symbols: list[str] = []
    
    for company in companies:
        run.companies_processed += 1
        
        try:
            result = ingest_company_fundamentals(
                db,
                company,
                provider,
                include_info,
                include_statements,
                include_ratios,
            )
            
            if result["success"]:
                successful += 1
            else:
                failed += 1
                failed_symbols.append(company.symbol)
        
        except Exception as error:
            failed += 1
            failed_symbols.append(company.symbol)
            print(f"Failed to ingest fundamentals for {company.symbol}: {error}")
    
    # Update run record
    run.successful_count = successful
    run.failed_count = failed
    run.failed_symbols = ",".join(failed_symbols) if failed_symbols else None
    run.status = "completed" if failed == 0 else "partial" if successful > 0 else "failed"
    run.completed_at = datetime.now(timezone.utc)
    
    db.commit()
    return run


def get_company_financials(
    db: Session,
    company: Company,
    statement_type: str | None = None,
    period_type: str | None = None,
    metric_names: list[str] | None = None,
    limit: int | None = None,
) -> list[CompanyFinancial]:
    """
    Retrieve financial data for a company.
    
    Args:
        db: Database session
        company: Company model instance
        statement_type: Filter by statement type
        period_type: Filter by period type
        metric_names: Filter by specific metric names
        limit: Maximum number of records to return
    
    Returns:
        List of CompanyFinancial records
    """
    query = select(CompanyFinancial).where(
        CompanyFinancial.company_id == company.id
    )
    
    if statement_type:
        query = query.where(CompanyFinancial.statement_type == statement_type)
    
    if period_type:
        query = query.where(CompanyFinancial.period_type == period_type)
    
    if metric_names:
        query = query.where(CompanyFinancial.metric_name.in_(metric_names))
    
    query = query.order_by(
        CompanyFinancial.period_end.desc().nullslast(),
        CompanyFinancial.metric_name,
    )
    
    if limit:
        query = query.limit(limit)
    
    return list(db.scalars(query))


def get_company_fundamental_info(
    db: Session,
    company: Company,
) -> CompanyFundamentalInfo | None:
    """
    Get company fundamental information.
    
    Args:
        db: Database session
        company: Company model instance
    
    Returns:
        CompanyFundamentalInfo record or None
    """
    return db.scalar(
        select(CompanyFundamentalInfo).where(
            CompanyFundamentalInfo.company_id == company.id
        )
    )
