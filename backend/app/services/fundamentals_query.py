"""Read-side helpers for fundamentals API responses (no provider calls)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Company,
    CompanyFinancial,
    CompanyFundamentalInfo,
    CompanyProfile,
    FundamentalDataUpdateRun,
)
from app.services.financial_ratios import calculate_all_ratios, get_metric_value
from app.services.fundamental_analysis import (
    DimensionAssessment,
    FundamentalAnalysis,
    analyze_fundamentals,
)
from app.services.fundamental_scoring import FundamentalScoreResult, calculate_fundamental_score
from app.services.fundamentals_freshness import classify_fundamental_freshness
from app.services.historical_performance import (
    HistoricalPerformanceReport,
    MetricSeries,
    MarginSeries,
    analyze_historical_performance,
)


def get_active_company(db: Session, symbol: str) -> Company | None:
    company = db.scalar(
        select(Company).where(
            Company.symbol == symbol.upper(),
            Company.is_active.is_(True),
        )
    )
    if company is None:
        company = db.scalar(
            select(Company).where(
                Company.symbol.ilike(symbol),
                Company.is_active.is_(True),
            )
        )
    return company


def latest_retrieval_at(db: Session, company_id: int) -> datetime | None:
    info_ts = db.scalar(
        select(CompanyFundamentalInfo.retrieved_at).where(
            CompanyFundamentalInfo.company_id == company_id
        )
    )
    fin_ts = db.scalar(
        select(func.max(CompanyFinancial.retrieved_at)).where(
            CompanyFinancial.company_id == company_id
        )
    )
    candidates = [t for t in (info_ts, fin_ts) if t is not None]
    return max(candidates) if candidates else None


def data_completeness(db: Session, company: Company) -> Decimal:
    """Rough completeness score 0–100 based on presence of core datasets."""
    info = db.scalar(
        select(CompanyFundamentalInfo).where(CompanyFundamentalInfo.company_id == company.id)
    )
    profile = db.scalar(
        select(CompanyProfile).where(CompanyProfile.company_id == company.id)
    )
    has_info = 1 if info else 0
    has_income = 1 if db.scalar(
        select(CompanyFinancial.id).where(
            CompanyFinancial.company_id == company.id,
            CompanyFinancial.statement_type == "income",
        ).limit(1)
    ) else 0
    has_balance = 1 if db.scalar(
        select(CompanyFinancial.id).where(
            CompanyFinancial.company_id == company.id,
            CompanyFinancial.statement_type == "balance",
        ).limit(1)
    ) else 0
    has_cf = 1 if db.scalar(
        select(CompanyFinancial.id).where(
            CompanyFinancial.company_id == company.id,
            CompanyFinancial.statement_type == "cashflow",
        ).limit(1)
    ) else 0
    has_ratios = 1 if db.scalar(
        select(CompanyFinancial.id).where(
            CompanyFinancial.company_id == company.id,
            CompanyFinancial.statement_type == "ratio",
        ).limit(1)
    ) else 0
    return (Decimal(has_info + has_income + has_balance + has_cf + has_ratios) / Decimal(5) * 100).quantize(
        Decimal("0.01")
    )


def _series_to_dict(series: MetricSeries) -> dict[str, Any]:
    return {
        "metric_key": series.metric_key,
        "display_name": series.display_name,
        "period_type": series.period_type,
        "observations": [
            {
                "period_end": o.period_end,
                "period_type": o.period_type,
                "value": o.value,
                "currency": o.currency,
                "source": o.source,
                "metric_name": o.metric_name,
                "derived_label": o.derived_label,
            }
            for o in series.observations
        ],
        "growth": [
            {
                "period_end": g.period_end,
                "comparison_period_end": g.comparison_period_end,
                "comparison_type": g.comparison_type,
                "growth_rate": g.growth_rate,
                "growth_pct": g.growth_pct,
                "current_value": g.current_value,
                "previous_value": g.previous_value,
                "is_derived": g.is_derived,
                "error": g.error,
            }
            for g in series.growth
        ],
        "trend": series.trend.value,
        "quality": series.quality.value,
        "missing_periods": series.missing_periods,
        "currency": series.currency,
        "notes": series.notes,
    }


def _margin_to_dict(series: MarginSeries) -> dict[str, Any]:
    return {
        "metric_key": series.metric_key,
        "display_name": series.display_name,
        "period_type": series.period_type,
        "observations": [
            {
                "period_end": o.period_end,
                "period_type": o.period_type,
                "value": o.value,
                "currency": o.currency,
                "source": o.source,
                "metric_name": o.metric_name,
                "derived_label": o.derived_label,
            }
            for o in series.observations
        ],
        "trend": series.trend.value,
        "quality": series.quality.value,
        "notes": series.notes,
    }


def historical_report_to_dict(report: HistoricalPerformanceReport) -> dict[str, Any]:
    return {
        "symbol": report.symbol,
        "period_type": report.period_type,
        "revenue": _series_to_dict(report.revenue),
        "gross_profit": _series_to_dict(report.gross_profit),
        "operating_income": _series_to_dict(report.operating_income),
        "net_income": _series_to_dict(report.net_income),
        "eps": _series_to_dict(report.eps),
        "gross_margin": _margin_to_dict(report.gross_margin),
        "operating_margin": _margin_to_dict(report.operating_margin),
        "net_margin": _margin_to_dict(report.net_margin),
        "total_assets": _series_to_dict(report.total_assets),
        "total_liabilities": _series_to_dict(report.total_liabilities),
        "total_debt": _series_to_dict(report.total_debt),
        "equity": _series_to_dict(report.equity),
        "current_assets": _series_to_dict(report.current_assets),
        "current_liabilities": _series_to_dict(report.current_liabilities),
        "working_capital": _series_to_dict(report.working_capital),
        "operating_cash_flow": _series_to_dict(report.operating_cash_flow),
        "investing_cash_flow": _series_to_dict(report.investing_cash_flow),
        "financing_cash_flow": _series_to_dict(report.financing_cash_flow),
        "free_cash_flow": _series_to_dict(report.free_cash_flow),
        "capital_expenditure": _series_to_dict(report.capital_expenditure),
        "cash_conversion": [
            {
                "period_end": c.period_end,
                "operating_cash_flow": c.operating_cash_flow,
                "free_cash_flow": c.free_cash_flow,
                "net_income": c.net_income,
                "ocf_to_ni": c.ocf_to_ni,
                "fcf_to_ni": c.fcf_to_ni,
                "notes": c.notes,
            }
            for c in report.cash_conversion
        ],
        "profitability_insight": {
            "overall_trend": report.profitability_insight.overall_trend.value,
            "margin_compression": report.profitability_insight.margin_compression,
            "margin_expansion": report.profitability_insight.margin_expansion,
            "inconsistent_earnings": report.profitability_insight.inconsistent_earnings,
            "notes": report.profitability_insight.notes,
        },
        "balance_sheet_insight": {
            "leverage_trend": report.balance_sheet_insight.leverage_trend.value,
            "liquidity_trend": report.balance_sheet_insight.liquidity_trend.value,
            "strength_trend": report.balance_sheet_insight.strength_trend.value,
            "notes": report.balance_sheet_insight.notes,
        },
        "data_warnings": report.data_warnings,
    }


def _assessment_to_dict(a: DimensionAssessment) -> dict[str, Any]:
    return {
        "dimension": a.dimension,
        "classification": a.classification.value,
        "metrics_used": [
            {
                "key": m.key,
                "name": m.name,
                "value": m.value,
                "unit": m.unit,
                "applicable": m.applicable,
                "origin": m.origin,
            }
            for m in a.metrics_used
        ],
        "positive_factors": a.positive_factors,
        "negative_factors": a.negative_factors,
        "missing_information": a.missing_information,
        "reporting_period": a.reporting_period,
        "data_freshness": a.data_freshness,
        "explanation": a.explanation,
        "sector_methodology": a.sector_methodology,
    }


def analysis_to_dict(analysis: FundamentalAnalysis) -> dict[str, Any]:
    return {
        "symbol": analysis.symbol,
        "company_name": analysis.company_name,
        "sector": analysis.sector,
        "industry": analysis.industry,
        "overall_classification": analysis.overall_classification.value,
        "profitability": _assessment_to_dict(analysis.profitability),
        "growth": _assessment_to_dict(analysis.growth),
        "financial_stability": _assessment_to_dict(analysis.financial_stability),
        "valuation": _assessment_to_dict(analysis.valuation),
        "cash_flow_quality": _assessment_to_dict(analysis.cash_flow_quality),
        "positive_factors": analysis.positive_factors,
        "negative_factors": analysis.negative_factors,
        "missing_data_warnings": analysis.missing_data_warnings,
        "analysis_version": analysis.analysis_version,
        "generated_at": analysis.generated_at,
    }


def score_to_dict(score: FundamentalScoreResult) -> dict[str, Any]:
    return {
        "symbol": score.symbol,
        "score": score.score,
        "classification": score.classification.value,
        "data_completeness": score.data_completeness,
        "metrics_evaluated": score.metrics_evaluated,
        "dimensions_excluded": score.dimensions_excluded,
        "dimension_scores": [
            {
                "dimension": d.dimension,
                "score": d.score,
                "weight": d.weight,
                "included": d.included,
                "exclusion_reason": d.exclusion_reason,
                "explanation": d.explanation,
            }
            for d in score.dimension_scores
        ],
        "major_contributors": score.major_contributors,
        "missing_metrics": score.missing_metrics,
        "methodology_version": score.methodology_version,
        "explanation": score.explanation,
        "generated_at": score.generated_at,
    }


def ratio_origin(item: dict) -> str:
    if item.get("error") and "not applicable" in (item.get("error") or "").lower():
        return "not_applicable"
    if item.get("inputs_available") and item.get("value") is not None:
        return "calculated"
    return "unavailable"


def ratios_to_dict(symbol: str, metrics: dict, period_type: str = "annual") -> dict[str, Any]:
    def pack(category: dict) -> dict:
        return {
            key: {
                "name": item.get("name", key),
                "value": item.get("value"),
                "category": item.get("category", ""),
                "inputs_available": bool(item.get("inputs_available")),
                "error": item.get("error"),
                "origin": ratio_origin(item),
            }
            for key, item in category.items()
        }

    return {
        "symbol": symbol,
        "period_type": period_type,
        "valuation": pack(metrics.get("valuation", {})),
        "profitability": pack(metrics.get("profitability", {})),
        "liquidity": pack(metrics.get("liquidity", {})),
        "leverage": pack(metrics.get("leverage", {})),
        "efficiency": pack(metrics.get("efficiency", {})),
        "growth": pack(metrics.get("growth", {})),
        "calculated_at": datetime.now(timezone.utc),
    }


def build_highlights(db: Session, company: Company) -> list[dict[str, Any]]:
    info = db.scalar(
        select(CompanyFundamentalInfo).where(CompanyFundamentalInfo.company_id == company.id)
    )
    market_cap = Decimal(info.market_cap) if info and info.market_cap else None
    ratios = calculate_all_ratios(db, company, market_cap=market_cap)
    flat: dict[str, dict] = {}
    for cat in ratios:
        flat.update(ratios[cat])

    def latest(name: str, statement: str) -> tuple[Decimal | None, Any, str | None]:
        row = db.scalar(
            select(CompanyFinancial)
            .where(
                CompanyFinancial.company_id == company.id,
                CompanyFinancial.metric_name == name,
                CompanyFinancial.period_type == "annual",
                CompanyFinancial.statement_type == statement,
            )
            .order_by(CompanyFinancial.period_end.desc().nullslast())
            .limit(1)
        )
        if not row:
            return None, None, None
        return row.metric_value, row.period_end, row.currency

    revenue, rev_pe, rev_ccy = latest("Total Revenue", "income")
    ni, ni_pe, ni_ccy = latest("Net Income", "income")
    eps, eps_pe, eps_ccy = latest("Basic EPS", "income")
    fcf, fcf_pe, fcf_ccy = latest("Free Cash Flow", "cashflow")

    def ratio_highlight(key: str, label: str) -> dict[str, Any]:
        item = flat.get(key) or {}
        return {
            "key": key,
            "label": label,
            "value": item.get("value"),
            "period_end": None,
            "period_type": "ttm/calculated",
            "origin": ratio_origin(item) if item else "unavailable",
            "currency": None,
            "unit": None,
        }

    highlights = [
        {
            "key": "revenue",
            "label": "Revenue",
            "value": revenue,
            "period_end": rev_pe,
            "period_type": "annual",
            "origin": "retrieved" if revenue is not None else "unavailable",
            "currency": rev_ccy,
            "unit": None,
        },
        {
            "key": "net_income",
            "label": "Net Income",
            "value": ni,
            "period_end": ni_pe,
            "period_type": "annual",
            "origin": "retrieved" if ni is not None else "unavailable",
            "currency": ni_ccy,
            "unit": None,
        },
        {
            "key": "eps",
            "label": "EPS",
            "value": eps,
            "period_end": eps_pe,
            "period_type": "annual",
            "origin": "retrieved" if eps is not None else "unavailable",
            "currency": eps_ccy,
            "unit": None,
        },
        ratio_highlight("pe_ratio", "P/E"),
        ratio_highlight("pb_ratio", "P/B"),
        {
            "key": "dividend_yield",
            "label": "Dividend Yield",
            "value": get_metric_value(db, company.id, "dividend_yield", "ttm", "ratio"),
            "period_end": None,
            "period_type": "ttm",
            "origin": "retrieved"
            if get_metric_value(db, company.id, "dividend_yield", "ttm", "ratio") is not None
            else "unavailable",
            "currency": None,
            "unit": "%",
        },
        ratio_highlight("roe", "ROE"),
        ratio_highlight("debt_to_equity", "Debt-to-Equity"),
        {
            "key": "free_cash_flow",
            "label": "Free Cash Flow",
            "value": fcf,
            "period_end": fcf_pe,
            "period_type": "annual",
            "origin": "retrieved" if fcf is not None else "unavailable",
            "currency": fcf_ccy,
            "unit": None,
        },
    ]
    return highlights


def build_company_overview(db: Session, company: Company) -> dict[str, Any]:
    info = db.scalar(
        select(CompanyFundamentalInfo).where(CompanyFundamentalInfo.company_id == company.id)
    )
    profile = db.scalar(
        select(CompanyProfile).where(CompanyProfile.company_id == company.id)
    )
    retrieved = info.retrieved_at if info else latest_retrieval_at(db, company.id)
    return {
        "symbol": company.symbol,
        "name": company.name,
        "exchange": company.exchange,
        "sector": company.sector,
        "industry": profile.industry if profile else None,
        "business_summary": info.business_summary if info else None,
        "market_cap": info.market_cap if info else None,
        "enterprise_value": info.enterprise_value if info else None,
        "currency": info.currency if info else None,
        "employees": info.employees if info else None,
        "website": info.website if info else None,
        "data_source": info.data_source if info else None,
        "retrieved_at": retrieved,
        "data_freshness": classify_fundamental_freshness(retrieved).value,
    }


def build_fundamentals_summary(db: Session, company: Company) -> dict[str, Any]:
    overview = build_company_overview(db, company)
    info = db.scalar(
        select(CompanyFundamentalInfo).where(CompanyFundamentalInfo.company_id == company.id)
    )
    market_cap = Decimal(info.market_cap) if info and info.market_cap else None
    ratios = calculate_all_ratios(db, company, market_cap=market_cap)
    analysis = analyze_fundamentals(db, company, market_cap=market_cap)
    score = calculate_fundamental_score(db, company, market_cap=market_cap, analysis=analysis)
    return {
        "company": overview,
        "highlights": build_highlights(db, company),
        "ratios": ratios_to_dict(company.symbol, ratios),
        "analysis": analysis_to_dict(analysis),
        "score": score_to_dict(score),
        "data_completeness": data_completeness(db, company),
        "last_retrieval_at": latest_retrieval_at(db, company.id),
    }


def build_health_report(db: Session) -> dict[str, Any]:
    companies = list(
        db.scalars(
            select(Company).where(
                Company.is_active.is_(True),
                Company.instrument_type.ilike("company"),
            )
        )
    )
    last_run = db.scalar(
        select(FundamentalDataUpdateRun).order_by(FundamentalDataUpdateRun.started_at.desc()).limit(1)
    )
    last_success = db.scalar(
        select(FundamentalDataUpdateRun)
        .where(FundamentalDataUpdateRun.status.in_(["completed", "partial"]))
        .order_by(FundamentalDataUpdateRun.completed_at.desc())
        .limit(1)
    )

    company_health = []
    stale: list[str] = []
    failed: list[str] = []
    if last_run and last_run.failed_symbols:
        failed = [s for s in last_run.failed_symbols.split(",") if s]

    for company in companies:
        retrieved = latest_retrieval_at(db, company.id)
        freshness = classify_fundamental_freshness(retrieved)
        if freshness.value == "STALE":
            stale.append(company.symbol)
        has_statements = bool(
            db.scalar(
                select(CompanyFinancial.id)
                .where(
                    CompanyFinancial.company_id == company.id,
                    CompanyFinancial.statement_type.in_(["income", "balance", "cashflow"]),
                )
                .limit(1)
            )
        )
        has_ratios = bool(
            db.scalar(
                select(CompanyFinancial.id)
                .where(
                    CompanyFinancial.company_id == company.id,
                    CompanyFinancial.statement_type == "ratio",
                )
                .limit(1)
            )
        )
        has_info = bool(
            db.scalar(
                select(CompanyFundamentalInfo.id).where(
                    CompanyFundamentalInfo.company_id == company.id
                )
            )
        )
        company_health.append(
            {
                "symbol": company.symbol,
                "last_retrieved_at": retrieved,
                "data_freshness": freshness.value,
                "has_statements": has_statements,
                "has_ratios": has_ratios,
                "has_company_info": has_info,
                "completeness": data_completeness(db, company),
            }
        )

    return {
        "provider": "yahoo_finance",
        "provider_status": "operational_unofficial",
        "last_successful_update": last_success.completed_at if last_success else None,
        "last_attempted_update": last_run.started_at if last_run else None,
        "last_run_status": last_run.status if last_run else None,
        "companies": company_health,
        "failed_companies": failed,
        "stale_companies": stale,
        "checked_at": datetime.now(timezone.utc),
    }


def build_dashboard_fundamentals(db: Session, limit: int = 5) -> dict[str, Any]:
    companies = list(
        db.scalars(
            select(Company).where(
                Company.is_active.is_(True),
                Company.instrument_type.ilike("company"),
            ).limit(40)
        )
    )
    strong: list[dict] = []
    improving_profit: list[dict] = []
    improving_growth: list[dict] = []
    elevated_debt: list[dict] = []
    insufficient: list[dict] = []

    for company in companies:
        try:
            analysis = analyze_fundamentals(db, company)
            score = calculate_fundamental_score(db, company, analysis=analysis)
            entry = {
                "symbol": company.symbol,
                "name": company.name,
                "classification": analysis.overall_classification.value,
                "score": score.score,
            }
            if analysis.overall_classification.value in {"STRONG", "HEALTHY"} and score.score is not None:
                strong.append(entry)
            if analysis.profitability.classification.value in {"STRONG", "HEALTHY"}:
                if any("improving" in f.lower() for f in analysis.profitability.positive_factors):
                    improving_profit.append(entry)
            if analysis.growth.classification.value in {"STRONG", "HEALTHY"}:
                improving_growth.append(entry)
            if any("elevated" in f.lower() or "high" in f.lower() for f in analysis.financial_stability.negative_factors):
                elevated_debt.append(entry)
            if analysis.overall_classification.value == "INSUFFICIENT_DATA":
                insufficient.append({"symbol": company.symbol, "name": company.name})
        except Exception:
            insufficient.append({"symbol": company.symbol, "name": company.name})

    strong.sort(key=lambda x: x.get("score") or Decimal("0"), reverse=True)
    return {
        "strong_profiles": strong[:limit],
        "improving_profitability": improving_profit[:limit],
        "improving_revenue_growth": improving_growth[:limit],
        "elevated_debt": elevated_debt[:limit],
        "insufficient_data": insufficient[:limit],
        "generated_at": datetime.now(timezone.utc),
    }
