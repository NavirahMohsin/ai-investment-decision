"""Multi-company fundamental comparison with comparability validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Company, CompanyFinancial, CompanyFundamentalInfo
from app.services.financial_ratios import calculate_all_ratios, get_metric_value
from app.services.fundamental_analysis import analyze_fundamentals
from app.services.fundamental_scoring import calculate_fundamental_score
from app.services.historical_performance import analyze_historical_performance


MAX_COMPARISON_COMPANIES = 8

# key, label, category, direction: higher | lower | none
COMPARISON_METRICS: list[tuple[str, str, str, str]] = [
    ("revenue", "Revenue", "performance", "higher"),
    ("revenue_growth", "Revenue Growth %", "growth", "higher"),
    ("net_income", "Net Income", "performance", "higher"),
    ("net_income_growth", "Net Income Growth %", "growth", "higher"),
    ("eps", "EPS", "performance", "higher"),
    ("gross_margin", "Gross Margin %", "profitability", "higher"),
    ("operating_margin", "Operating Margin %", "profitability", "higher"),
    ("net_margin", "Net Margin %", "profitability", "higher"),
    ("roe", "ROE %", "profitability", "higher"),
    ("roa", "ROA %", "profitability", "higher"),
    ("roce", "ROCE %", "profitability", "higher"),
    ("debt_to_equity", "Debt-to-Equity", "stability", "lower"),
    ("current_ratio", "Current Ratio", "stability", "higher"),
    ("interest_coverage", "Interest Coverage", "stability", "higher"),
    ("pe_ratio", "P/E", "valuation", "none"),
    ("pb_ratio", "P/B", "valuation", "none"),
    ("ev_ebitda", "EV/EBITDA", "valuation", "none"),
    ("dividend_yield", "Dividend Yield", "valuation", "higher"),
    ("ps_ratio", "P/S", "valuation", "none"),
    ("operating_cash_flow", "Operating Cash Flow", "cash_flow", "higher"),
    ("free_cash_flow", "Free Cash Flow", "cash_flow", "higher"),
    ("cash_conversion", "OCF / Net Income", "cash_flow", "higher"),
    ("fundamental_score", "Fundamental Score", "assessment", "higher"),
]


@dataclass
class ComparisonMetricResult:
    key: str
    label: str
    category: str
    values: dict[str, Decimal | None]
    comparable: bool
    incomparable_reason: str | None = None
    ranking: list[str] | None = None
    ranking_period: str | None = None
    companies_with_data: int = 0
    companies_excluded: list[str] = field(default_factory=list)


@dataclass
class CompanyComparisonEntry:
    symbol: str
    name: str
    sector: str | None
    currency: str | None
    reporting_period: str | None
    period_end: date | None
    overall_classification: str | None
    fundamental_score: Decimal | None
    metrics: dict[str, Decimal | None]
    classifications: dict[str, str]


@dataclass
class CompanyComparisonResult:
    symbols: list[str]
    companies: list[CompanyComparisonEntry]
    metrics: list[ComparisonMetricResult]
    comparability_warnings: list[str] = field(default_factory=list)
    sector_warning: str | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ComparisonValidationError(ValueError):
    """Raised when comparison request is invalid."""


def _normalize_symbols(symbols: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in symbols:
        sym = (raw or "").strip().upper()
        if not sym:
            continue
        if sym in seen:
            continue
        seen.add(sym)
        cleaned.append(sym)
    return cleaned


def resolve_comparison_companies(db: Session, symbols: list[str]) -> list[Company]:
    normalized = _normalize_symbols(symbols)
    if not normalized:
        raise ComparisonValidationError("At least one company symbol is required.")
    if len(normalized) > MAX_COMPARISON_COMPANIES:
        raise ComparisonValidationError(
            f"Maximum {MAX_COMPARISON_COMPANIES} companies allowed per comparison."
        )

    companies: list[Company] = []
    missing: list[str] = []
    non_company: list[str] = []
    for sym in normalized:
        company = db.scalar(select(Company).where(Company.symbol == sym))
        if company is None:
            company = db.scalar(select(Company).where(Company.symbol.ilike(sym)))
        if company is None:
            missing.append(sym)
            continue
        if company.instrument_type.lower() not in {"company", "equity", "stock"}:
            non_company.append(sym)
            continue
        companies.append(company)

    if missing:
        raise ComparisonValidationError(f"Unknown symbols: {', '.join(missing)}")
    if non_company:
        raise ComparisonValidationError(
            f"Indices/non-company instruments excluded: {', '.join(non_company)}"
        )
    if len(companies) < 2:
        raise ComparisonValidationError(
            "At least two valid companies are required for comparison."
        )
    return companies


def _latest_period_end(db: Session, company_id: int) -> date | None:
    return db.scalar(
        select(CompanyFinancial.period_end)
        .where(
            CompanyFinancial.company_id == company_id,
            CompanyFinancial.period_type == "annual",
            CompanyFinancial.period_end.is_not(None),
        )
        .order_by(CompanyFinancial.period_end.desc())
        .limit(1)
    )


def _collect_company_metrics(
    db: Session,
    company: Company,
) -> tuple[CompanyComparisonEntry, dict[str, Decimal | None]]:
    info = db.scalar(
        select(CompanyFundamentalInfo).where(CompanyFundamentalInfo.company_id == company.id)
    )
    market_cap = Decimal(info.market_cap) if info and info.market_cap else None
    ratios = calculate_all_ratios(db, company, market_cap=market_cap)
    flat: dict[str, dict] = {}
    for cat in ratios:
        flat.update(ratios[cat])

    history = analyze_historical_performance(db, company, period_type="annual", limit=5)
    analysis = analyze_fundamentals(db, company, market_cap=market_cap)
    score = calculate_fundamental_score(db, company, market_cap=market_cap, analysis=analysis)

    def rv(key: str) -> Decimal | None:
        item = flat.get(key)
        if not item:
            return None
        return item.get("value")

    revenue = history.revenue.observations[-1].value if history.revenue.observations else None
    net_income = history.net_income.observations[-1].value if history.net_income.observations else None
    eps = history.eps.observations[-1].value if history.eps.observations else None
    ocf = (
        history.operating_cash_flow.observations[-1].value
        if history.operating_cash_flow.observations
        else None
    )
    fcf = history.free_cash_flow.observations[-1].value if history.free_cash_flow.observations else None
    ni_growth = history.net_income.growth[-1].growth_pct if history.net_income.growth else None
    cash_conv = history.cash_conversion[-1].ocf_to_ni if history.cash_conversion else None
    period_end = (
        history.revenue.observations[-1].period_end
        if history.revenue.observations
        else _latest_period_end(db, company.id)
    )

    dy = get_metric_value(db, company.id, "dividend_yield", "ttm", "ratio")
    ps = get_metric_value(db, company.id, "price_to_sales", "ttm", "ratio")
    if dy is not None and dy < 1:
        dy = dy * Decimal("100")

    metrics: dict[str, Decimal | None] = {
        "revenue": revenue,
        "revenue_growth": rv("revenue_growth"),
        "net_income": net_income,
        "net_income_growth": ni_growth,
        "eps": eps,
        "gross_margin": rv("gross_margin"),
        "operating_margin": rv("operating_margin"),
        "net_margin": rv("net_margin"),
        "roe": rv("roe"),
        "roa": rv("roa"),
        "roce": rv("roce"),
        "debt_to_equity": rv("debt_to_equity"),
        "current_ratio": rv("current_ratio"),
        "interest_coverage": rv("interest_coverage"),
        "pe_ratio": rv("pe_ratio"),
        "pb_ratio": rv("pb_ratio"),
        "ev_ebitda": rv("ev_ebitda"),
        "dividend_yield": dy,
        "ps_ratio": ps,
        "operating_cash_flow": ocf,
        "free_cash_flow": fcf,
        "cash_conversion": cash_conv,
        "fundamental_score": score.score,
    }

    entry = CompanyComparisonEntry(
        symbol=company.symbol,
        name=company.name,
        sector=company.sector,
        currency=info.currency if info else None,
        reporting_period="annual",
        period_end=period_end,
        overall_classification=analysis.overall_classification.value,
        fundamental_score=score.score,
        metrics=metrics,
        classifications={
            "profitability": analysis.profitability.classification.value,
            "growth": analysis.growth.classification.value,
            "financial_stability": analysis.financial_stability.classification.value,
            "valuation": analysis.valuation.classification.value,
            "cash_flow_quality": analysis.cash_flow_quality.classification.value,
        },
    )
    return entry, metrics


def _rank_metric(
    values: dict[str, Decimal | None],
    direction: str,
) -> tuple[list[str] | None, list[str], int]:
    present = {s: v for s, v in values.items() if v is not None}
    excluded = [s for s, v in values.items() if v is None]
    if len(present) < 2 or direction == "none":
        return None, excluded, len(present)
    reverse = direction == "higher"
    ranking = sorted(present.keys(), key=lambda s: present[s], reverse=reverse)  # type: ignore[arg-type, return-value]
    return ranking, excluded, len(present)


def compare_companies(db: Session, symbols: list[str]) -> CompanyComparisonResult:
    """Compare companies using stored fundamentals only (no provider calls)."""
    companies = resolve_comparison_companies(db, symbols)
    entries: list[CompanyComparisonEntry] = []
    all_metrics: dict[str, dict[str, Decimal | None]] = {key: {} for key, *_ in COMPARISON_METRICS}

    warnings: list[str] = []
    currencies: set[str] = set()
    sectors: set[str] = set()
    period_ends: set[date] = set()

    for company in companies:
        entry, metrics = _collect_company_metrics(db, company)
        entries.append(entry)
        if entry.currency:
            currencies.add(entry.currency)
        if entry.sector:
            sectors.add(entry.sector)
        if entry.period_end:
            period_ends.add(entry.period_end)
        for key in all_metrics:
            all_metrics[key][company.symbol] = metrics.get(key)

    if len(currencies) > 1:
        warnings.append(
            f"Companies report in different currencies ({', '.join(sorted(currencies))}). "
            "Absolute amounts are not currency-converted and must not be ranked across currencies."
        )
    if len(period_ends) > 1:
        warnings.append(
            "Reporting period end dates differ across companies; period alignment should be reviewed "
            f"({', '.join(sorted(p.isoformat() for p in period_ends))})."
        )

    sector_warning = None
    if len(sectors) > 1:
        sector_warning = (
            f"Selected companies span multiple sectors ({', '.join(sorted(sectors))}). "
            "Cross-sector ratio comparisons can be misleading."
        )

    metric_results: list[ComparisonMetricResult] = []
    for key, label, category, direction in COMPARISON_METRICS:
        values = all_metrics[key]
        comparable = True
        reason: str | None = None

        if key in {"revenue", "net_income", "operating_cash_flow", "free_cash_flow"} and len(currencies) > 1:
            comparable = False
            reason = "Different reporting currencies; absolute values not ranked."

        ranking = None
        excluded: list[str] = [s for s, v in values.items() if v is None]
        with_data = sum(1 for v in values.values() if v is not None)

        if direction == "none":
            ranking = None
            if reason is None:
                reason = "Valuation metrics shown without automatic ranking."
            comparable = reason is None or not reason.startswith("Different")
        elif comparable:
            ranking, excluded, with_data = _rank_metric(values, direction)
            if ranking is None and with_data < 2:
                reason = reason or "Fewer than two companies have valid data for ranking."
                comparable = False

        metric_results.append(
            ComparisonMetricResult(
                key=key,
                label=label,
                category=category,
                values=values,
                comparable=comparable,
                incomparable_reason=reason,
                ranking=ranking,
                ranking_period="annual" if ranking else None,
                companies_with_data=with_data,
                companies_excluded=excluded,
            )
        )

    return CompanyComparisonResult(
        symbols=[c.symbol for c in companies],
        companies=entries,
        metrics=metric_results,
        comparability_warnings=warnings,
        sector_warning=sector_warning,
        generated_at=datetime.now(timezone.utc),
    )
