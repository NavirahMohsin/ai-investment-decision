"""Fundamentals API routes — business logic stays in services."""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CompanyFinancial
from app.db.session import get_db
from app.schemas.fundamentals import (
    CompanyComparisonResponse,
    DashboardFundamentalsSummary,
    FinancialRatiosResponse,
    FinancialStatementsResponse,
    FundamentalAnalysisResponse,
    FundamentalScoreResponse,
    FundamentalsHealthResponse,
    FundamentalsRefreshRequest,
    FundamentalsRefreshResponse,
    FundamentalsSummaryResponse,
    HistoricalPerformanceResponse,
    StatementLineSchema,
)
from app.services.company_comparison import (
    ComparisonValidationError,
    compare_companies,
)
from app.services.financial_ratios import calculate_all_ratios
from app.services.fundamental_analysis import analyze_fundamentals
from app.services.fundamental_scoring import calculate_fundamental_score
from app.services.fundamentals_query import (
    analysis_to_dict,
    build_dashboard_fundamentals,
    build_fundamentals_summary,
    build_health_report,
    get_active_company,
    historical_report_to_dict,
    ratios_to_dict,
    score_to_dict,
)
from app.services.fundamentals_refresh import RefreshInProgressError, refresh_companies
from app.services.historical_performance import analyze_historical_performance
from decimal import Decimal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fundamentals", tags=["fundamentals"])


def _require_company(db: Session, symbol: str):
    company = get_active_company(db, symbol)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company not found: {symbol}")
    if company.instrument_type.lower() not in {"company", "equity", "stock"}:
        raise HTTPException(
            status_code=400,
            detail=f"Instrument {symbol} is not a company (type={company.instrument_type})",
        )
    return company


@router.get("/health", response_model=FundamentalsHealthResponse)
def fundamentals_health(db: Session = Depends(get_db)):
    return build_health_report(db)


@router.get("/dashboard", response_model=DashboardFundamentalsSummary)
def fundamentals_dashboard(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    return build_dashboard_fundamentals(db, limit=limit)


@router.get("/compare", response_model=CompanyComparisonResponse)
def fundamentals_compare(
    symbols: list[str] = Query(..., description="Company symbols to compare"),
    db: Session = Depends(get_db),
):
    try:
        result = compare_companies(db, symbols)
    except ComparisonValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "symbols": result.symbols,
        "companies": [
            {
                "symbol": c.symbol,
                "name": c.name,
                "sector": c.sector,
                "currency": c.currency,
                "reporting_period": c.reporting_period,
                "period_end": c.period_end,
                "overall_classification": c.overall_classification,
                "fundamental_score": c.fundamental_score,
                "metrics": c.metrics,
                "classifications": c.classifications,
            }
            for c in result.companies
        ],
        "metrics": [
            {
                "key": m.key,
                "label": m.label,
                "category": m.category,
                "values": m.values,
                "comparable": m.comparable,
                "incomparable_reason": m.incomparable_reason,
                "ranking": m.ranking,
                "ranking_period": m.ranking_period,
                "companies_with_data": m.companies_with_data,
                "companies_excluded": m.companies_excluded,
            }
            for m in result.metrics
        ],
        "comparability_warnings": result.comparability_warnings,
        "sector_warning": result.sector_warning,
        "generated_at": result.generated_at,
    }


@router.post("/refresh", response_model=FundamentalsRefreshResponse)
def fundamentals_refresh(
    body: FundamentalsRefreshRequest,
    db: Session = Depends(get_db),
):
    try:
        run, results = refresh_companies(
            db,
            symbols=body.symbols,
            refresh_all=body.refresh_all,
            include_info=body.include_info,
            include_statements=body.include_statements,
            include_ratios=body.include_ratios,
            max_companies=body.max_companies,
            trigger_source="manual",
        )
    except RefreshInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Fundamentals refresh failed")
        raise HTTPException(status_code=500, detail=f"Refresh failed: {exc}") from exc

    return {
        "run_id": run.id,
        "status": run.status,
        "trigger_source": run.trigger_source,
        "companies_requested": len(results),
        "companies_processed": run.companies_processed,
        "successful_count": run.successful_count,
        "failed_count": run.failed_count,
        "results": [
            {
                "symbol": r["company_symbol"],
                "success": r["success"],
                "company_info_updated": r["company_info_updated"],
                "financials_inserted": r["financials_inserted"],
                "financials_updated": r["financials_updated"],
                "ratios_inserted": r["ratios_inserted"],
                "error": r["error"],
            }
            for r in results
        ],
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


@router.get("/{symbol}", response_model=FundamentalsSummaryResponse)
def get_fundamentals(symbol: str, db: Session = Depends(get_db)):
    company = _require_company(db, symbol)
    return build_fundamentals_summary(db, company)


@router.get("/{symbol}/statements", response_model=FinancialStatementsResponse)
def get_statements(
    symbol: str,
    statement_type: Literal["income", "balance", "cashflow"] = Query("income"),
    period_type: Literal["annual", "quarterly"] = Query("annual"),
    limit: int = Query(40, ge=1, le=200),
    db: Session = Depends(get_db),
):
    company = _require_company(db, symbol)
    # Map balance_sheet alias
    st = "balance" if statement_type in {"balance", "balance_sheet"} else statement_type
    rows = list(
        db.scalars(
            select(CompanyFinancial)
            .where(
                CompanyFinancial.company_id == company.id,
                CompanyFinancial.statement_type == st,
                CompanyFinancial.period_type == period_type,
            )
            .order_by(
                CompanyFinancial.period_end.desc().nullslast(),
                CompanyFinancial.metric_name,
            )
            .limit(limit)
        )
    )
    periods = sorted({r.period_end for r in rows if r.period_end is not None}, reverse=True)
    currency = next((r.currency for r in rows if r.currency), None)
    retrieved = max((r.retrieved_at for r in rows), default=None)
    return {
        "symbol": company.symbol,
        "statement_type": st,
        "period_type": period_type,
        "currency": currency,
        "lines": [
            StatementLineSchema(
                metric_name=r.metric_name,
                value=r.metric_value,
                period_end=r.period_end,
                period_type=r.period_type,
                statement_type=r.statement_type,
                currency=r.currency,
                retrieved_at=r.retrieved_at,
            )
            for r in rows
        ],
        "periods": periods,
        "limit": limit,
        "retrieved_at": retrieved,
    }


@router.get("/{symbol}/ratios", response_model=FinancialRatiosResponse)
def get_ratios(
    symbol: str,
    period_type: Literal["annual", "quarterly", "ttm"] = Query("annual"),
    db: Session = Depends(get_db),
):
    company = _require_company(db, symbol)
    from app.db.models import CompanyFundamentalInfo

    info = db.scalar(
        select(CompanyFundamentalInfo).where(CompanyFundamentalInfo.company_id == company.id)
    )
    market_cap = Decimal(info.market_cap) if info and info.market_cap else None
    metrics = calculate_all_ratios(db, company, market_cap=market_cap, period_type=period_type)
    return ratios_to_dict(company.symbol, metrics, period_type=period_type)


@router.get("/{symbol}/history", response_model=HistoricalPerformanceResponse)
def get_history(
    symbol: str,
    period_type: Literal["annual", "quarterly"] = Query("annual"),
    limit: int = Query(12, ge=1, le=40),
    db: Session = Depends(get_db),
):
    company = _require_company(db, symbol)
    report = analyze_historical_performance(db, company, period_type=period_type, limit=limit)
    return historical_report_to_dict(report)


@router.get("/{symbol}/analysis", response_model=FundamentalAnalysisResponse)
def get_analysis(symbol: str, db: Session = Depends(get_db)):
    company = _require_company(db, symbol)
    analysis = analyze_fundamentals(db, company)
    return analysis_to_dict(analysis)


@router.get("/{symbol}/score", response_model=FundamentalScoreResponse)
def get_score(symbol: str, db: Session = Depends(get_db)):
    company = _require_company(db, symbol)
    score = calculate_fundamental_score(db, company)
    return score_to_dict(score)
