"""Explainable company-level fundamental analysis engine.

Assessments describe financial condition using retrieved/calculated metrics.
They do not predict future stock returns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Company, CompanyFinancial, CompanyFundamentalInfo
from app.services.financial_ratios import calculate_all_ratios
from app.services.fundamentals_freshness import classify_fundamental_freshness
from app.services.historical_performance import (
    TrendDirection,
    analyze_historical_performance,
)
from app.services.sector_rules import SectorRules, metric_applicable, resolve_sector_rules


ANALYSIS_VERSION = "fundamental-analysis-v1"


class Classification(StrEnum):
    STRONG = "STRONG"
    HEALTHY = "HEALTHY"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class AssessmentMetric:
    key: str
    name: str
    value: Decimal | None
    unit: str | None = None
    applicable: bool = True
    origin: str = "calculated"


@dataclass
class DimensionAssessment:
    dimension: str
    classification: Classification
    metrics_used: list[AssessmentMetric] = field(default_factory=list)
    positive_factors: list[str] = field(default_factory=list)
    negative_factors: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    reporting_period: str | None = None
    data_freshness: str | None = None
    explanation: str = ""
    sector_methodology: str = ""


@dataclass
class FundamentalAnalysis:
    symbol: str
    company_name: str
    sector: str | None
    industry: str | None
    overall_classification: Classification
    profitability: DimensionAssessment
    growth: DimensionAssessment
    financial_stability: DimensionAssessment
    valuation: DimensionAssessment
    cash_flow_quality: DimensionAssessment
    positive_factors: list[str] = field(default_factory=list)
    negative_factors: list[str] = field(default_factory=list)
    missing_data_warnings: list[str] = field(default_factory=list)
    analysis_version: str = ANALYSIS_VERSION
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _ratio_value(metrics: dict, key: str) -> Decimal | None:
    item = metrics.get(key)
    if not item:
        return None
    return item.get("value")


def _ratio_available(metrics: dict, key: str) -> bool:
    item = metrics.get(key)
    return bool(item and item.get("inputs_available") and item.get("value") is not None)


def _pct(value: Decimal | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}%"


def _num(value: Decimal | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def _latest_retrieval(db: Session, company_id: int) -> datetime | None:
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
    if not candidates:
        return None
    return max(candidates)


def _assess_profitability(
    ratios: dict,
    history_trend: TrendDirection,
    rules: SectorRules,
    freshness: str,
) -> DimensionAssessment:
    metrics: list[AssessmentMetric] = []
    positives: list[str] = []
    negatives: list[str] = []
    missing: list[str] = []

    keys = [
        ("gross_margin", "Gross Margin", "%"),
        ("operating_margin", "Operating Margin", "%"),
        ("net_margin", "Net Margin", "%"),
        ("roe", "ROE", "%"),
        ("roa", "ROA", "%"),
        ("roce", "ROCE", "%"),
    ]
    values: dict[str, Decimal | None] = {}
    for key, name, unit in keys:
        available = _ratio_available(ratios, key)
        value = _ratio_value(ratios, key) if available else None
        values[key] = value
        metrics.append(
            AssessmentMetric(key=key, name=name, value=value, unit=unit, origin="calculated" if available else "unavailable")
        )
        if not available:
            missing.append(name)

    available_count = sum(1 for v in values.values() if v is not None)
    if available_count < 2:
        return DimensionAssessment(
            dimension="profitability",
            classification=Classification.INSUFFICIENT_DATA,
            metrics_used=metrics,
            missing_information=missing,
            reporting_period="annual/ttm",
            data_freshness=freshness,
            explanation="Fewer than two profitability metrics are available; classification withheld.",
            sector_methodology=rules.label,
        )

    score_points = 0
    checks = 0

    def _band(val: Decimal | None, strong: float, healthy: float, weak: float) -> None:
        nonlocal score_points, checks
        if val is None:
            return
        checks += 1
        f = float(val)
        if f >= strong:
            score_points += 3
            positives.append(f"Metric above strong threshold ({f:.1f}).")
        elif f >= healthy:
            score_points += 2
        elif f >= weak:
            score_points += 1
            negatives.append(f"Metric in weak-to-moderate band ({f:.1f}).")
        else:
            score_points += 0
            negatives.append(f"Metric below weak threshold ({f:.1f}).")

    _band(values["gross_margin"], 40, 25, 10)
    _band(values["operating_margin"], 20, 12, 5)
    _band(values["net_margin"], 15, 8, 3)
    _band(values["roe"], 18, 12, 5)
    _band(values["roa"], 10, 5, 2)
    _band(values["roce"], 15, 10, 4)

    if history_trend in {TrendDirection.IMPROVING, TrendDirection.ACCELERATING}:
        positives.append("Historical profitability/margin trend is improving.")
        score_points += 1
        checks += 1
    elif history_trend in {TrendDirection.DECLINING, TrendDirection.DECELERATING}:
        negatives.append("Historical profitability/margin trend is declining.")
        checks += 1
    elif history_trend == TrendDirection.INCONSISTENT:
        negatives.append("Profitability history is inconsistent across periods.")
        checks += 1

    avg = score_points / max(checks, 1)
    if avg >= 2.5:
        classification = Classification.STRONG
    elif avg >= 1.8:
        classification = Classification.HEALTHY
    elif avg >= 1.0:
        classification = Classification.MODERATE
    else:
        classification = Classification.WEAK

    explanation = (
        f"Profitability classified as {classification.value} using {available_count} available metrics "
        f"(gross/operating/net margins, ROE/ROA/ROCE where present). "
        f"Consistency trend: {history_trend.value}."
    )
    return DimensionAssessment(
        dimension="profitability",
        classification=classification,
        metrics_used=metrics,
        positive_factors=positives[:6],
        negative_factors=negatives[:6],
        missing_information=missing,
        reporting_period="annual/ttm",
        data_freshness=freshness,
        explanation=explanation,
        sector_methodology=rules.label,
    )


def _assess_growth(
    ratios: dict,
    history,
    rules: SectorRules,
    freshness: str,
) -> DimensionAssessment:
    metrics: list[AssessmentMetric] = []
    positives: list[str] = []
    negatives: list[str] = []
    missing: list[str] = []

    rev_growth = _ratio_value(ratios, "revenue_growth")
    eps_growth = _ratio_value(ratios, "eps_growth")
    metrics.append(AssessmentMetric("revenue_growth", "Revenue Growth YoY", rev_growth, "%", origin="calculated" if rev_growth is not None else "unavailable"))
    metrics.append(AssessmentMetric("eps_growth", "EPS Growth YoY", eps_growth, "%", origin="calculated" if eps_growth is not None else "unavailable"))

    # Net income / operating income growth from historical series
    ni_growth = None
    oi_growth = None
    if history.net_income.growth:
        g = history.net_income.growth[-1]
        ni_growth = g.growth_pct
        metrics.append(AssessmentMetric("net_income_growth", "Net Income Growth YoY", ni_growth, "%", origin="calculated"))
    else:
        missing.append("Net Income Growth")
    if history.operating_income.growth:
        g = history.operating_income.growth[-1]
        oi_growth = g.growth_pct
        metrics.append(AssessmentMetric("operating_income_growth", "Operating Income Growth YoY", oi_growth, "%", origin="calculated"))
    else:
        missing.append("Operating Income Growth")

    if rev_growth is None:
        missing.append("Revenue Growth")
    if eps_growth is None:
        missing.append("EPS Growth")

    available = [v for v in (rev_growth, eps_growth, ni_growth, oi_growth) if v is not None]
    if len(available) < 1:
        return DimensionAssessment(
            dimension="growth",
            classification=Classification.INSUFFICIENT_DATA,
            metrics_used=metrics,
            missing_information=missing,
            reporting_period="annual",
            data_freshness=freshness,
            explanation="No growth metrics could be calculated from available history.",
            sector_methodology=rules.label,
        )

    positives_count = 0
    negatives_count = 0
    for label, val in (
        ("Revenue", rev_growth),
        ("EPS", eps_growth),
        ("Net income", ni_growth),
        ("Operating income", oi_growth),
    ):
        if val is None:
            continue
        f = float(val)
        if f >= 15:
            positives.append(f"{label} growth is strong at {_pct(val)}.")
            positives_count += 2
        elif f >= 5:
            positives.append(f"{label} growth is positive at {_pct(val)}.")
            positives_count += 1
        elif f >= 0:
            negatives_count += 0
        else:
            negatives.append(f"{label} growth is negative at {_pct(val)}.")
            negatives_count += 1

    trend = history.revenue.trend
    consistency_note = f"Revenue trend classification: {trend.value}."
    if trend in {TrendDirection.IMPROVING, TrendDirection.ACCELERATING}:
        positives.append(consistency_note)
        positives_count += 1
    elif trend in {TrendDirection.DECLINING, TrendDirection.DECELERATING, TrendDirection.INCONSISTENT}:
        negatives.append(consistency_note)
        negatives_count += 1

    if positives_count >= 4 and negatives_count == 0:
        classification = Classification.STRONG
    elif positives_count >= 2 and negatives_count <= 1:
        classification = Classification.HEALTHY
    elif negatives_count >= 2 and positives_count == 0:
        classification = Classification.WEAK
    else:
        classification = Classification.MODERATE

    return DimensionAssessment(
        dimension="growth",
        classification=classification,
        metrics_used=metrics,
        positive_factors=positives[:6],
        negative_factors=negatives[:6],
        missing_information=missing,
        reporting_period="annual",
        data_freshness=freshness,
        explanation=(
            f"Growth classified as {classification.value} from available YoY changes "
            f"({len(available)} metrics). Assessments describe historical performance only."
        ),
        sector_methodology=rules.label,
    )


def _assess_stability(
    ratios: dict,
    history,
    rules: SectorRules,
    freshness: str,
) -> DimensionAssessment:
    metrics: list[AssessmentMetric] = []
    positives: list[str] = []
    negatives: list[str] = []
    missing: list[str] = []

    def _add(key: str, name: str, value: Decimal | None, unit: str | None = None) -> None:
        applicable = metric_applicable(rules, key)
        metrics.append(
            AssessmentMetric(
                key=key,
                name=name,
                value=value if applicable else None,
                unit=unit,
                applicable=applicable,
                origin="calculated" if (applicable and value is not None) else ("not_applicable" if not applicable else "unavailable"),
            )
        )
        if not applicable:
            missing.append(f"{name} (not applicable for {rules.profile.value})")
        elif value is None:
            missing.append(name)

    de = _ratio_value(ratios, "debt_to_equity")
    cr = _ratio_value(ratios, "current_ratio")
    ic = _ratio_value(ratios, "interest_coverage")
    _add("debt_to_equity", "Debt-to-Equity", de)
    _add("current_ratio", "Current Ratio", cr)
    _add("interest_coverage", "Interest Coverage", ic)

    # Net debt from latest annual
    total_debt = None
    cash = None
    if history.total_debt.observations:
        total_debt = history.total_debt.observations[-1].value
    # cash from ratio engine path
    # leave as optional via history notes
    metrics.append(
        AssessmentMetric(
            key="net_debt",
            name="Net Debt (approx)",
            value=None,
            applicable=metric_applicable(rules, "debt_to_equity"),
            origin="unavailable",
        )
    )

    usable = [m for m in metrics if m.applicable and m.value is not None]
    if len(usable) < 1 and rules.profile == rules.profile:  # always true; keep structure
        if not any(m.applicable and m.origin != "not_applicable" for m in metrics if m.key != "net_debt"):
            pass

    applicable_available = [m for m in metrics if m.applicable and m.value is not None and m.key != "net_debt"]
    if not applicable_available:
        # Banks may have all industrial metrics excluded — use debt trend only
        if history.balance_sheet_insight.leverage_trend != TrendDirection.INSUFFICIENT_DATA:
            if history.balance_sheet_insight.leverage_trend == TrendDirection.IMPROVING:
                classification = Classification.HEALTHY
                positives.append("Balance-sheet leverage trend is improving.")
            elif history.balance_sheet_insight.leverage_trend == TrendDirection.DECLINING:
                classification = Classification.WEAK
                negatives.append("Balance-sheet leverage trend is deteriorating.")
            else:
                classification = Classification.MODERATE
            return DimensionAssessment(
                dimension="financial_stability",
                classification=classification,
                metrics_used=metrics,
                positive_factors=positives,
                negative_factors=negatives,
                missing_information=missing,
                reporting_period="annual",
                data_freshness=freshness,
                explanation=(
                    f"Stability assessed primarily from balance-sheet trends under {rules.label}. "
                    + " ".join(rules.methodology_notes)
                ),
                sector_methodology=rules.label,
            )
        return DimensionAssessment(
            dimension="financial_stability",
            classification=Classification.INSUFFICIENT_DATA,
            metrics_used=metrics,
            missing_information=missing,
            reporting_period="annual",
            data_freshness=freshness,
            explanation="Insufficient applicable stability metrics for classification.",
            sector_methodology=rules.label,
        )

    points = 0
    checks = 0
    if metric_applicable(rules, "debt_to_equity") and de is not None:
        checks += 1
        f = float(de)
        if f <= rules.debt_to_equity_elevated / 2:
            points += 3
            positives.append(f"Debt-to-equity {_num(de)} is within a healthy band for {rules.profile.value}.")
        elif f <= rules.debt_to_equity_elevated:
            points += 2
            positives.append(f"Debt-to-equity {_num(de)} is moderate.")
        elif f <= rules.debt_to_equity_high:
            points += 1
            negatives.append(f"Debt-to-equity {_num(de)} is elevated.")
        else:
            negatives.append(f"Debt-to-equity {_num(de)} is high.")

    if rules.use_current_ratio and cr is not None:
        checks += 1
        f = float(cr)
        if f >= 1.5:
            points += 3
            positives.append(f"Current ratio {_num(cr)} indicates comfortable liquidity.")
        elif f >= rules.current_ratio_concern:
            points += 2
        else:
            negatives.append(f"Current ratio {_num(cr)} indicates liquidity concerns.")

    if ic is not None:
        checks += 1
        f = float(ic)
        if f >= 5:
            points += 3
            positives.append(f"Interest coverage {_num(ic)} is strong.")
        elif f >= rules.interest_coverage_weak:
            points += 2
        else:
            negatives.append(f"Interest coverage {_num(ic)} is weak.")
            points += 0

    # Cash-flow strength cue
    if history.operating_cash_flow.trend in {TrendDirection.IMPROVING, TrendDirection.ACCELERATING}:
        positives.append("Operating cash flow trend is improving.")
        points += 1
        checks += 1
    elif history.operating_cash_flow.trend in {TrendDirection.DECLINING}:
        negatives.append("Operating cash flow trend is declining.")
        checks += 1

    avg = points / max(checks, 1)
    if avg >= 2.5:
        classification = Classification.STRONG
    elif avg >= 1.8:
        classification = Classification.HEALTHY
    elif avg >= 1.0:
        classification = Classification.MODERATE
    else:
        classification = Classification.WEAK

    return DimensionAssessment(
        dimension="financial_stability",
        classification=classification,
        metrics_used=metrics,
        positive_factors=positives[:6],
        negative_factors=negatives[:6],
        missing_information=missing,
        reporting_period="annual",
        data_freshness=freshness,
        explanation=(
            f"Financial stability classified as {classification.value} using sector methodology "
            f"'{rules.label}'. " + " ".join(rules.methodology_notes)
        ),
        sector_methodology=rules.label,
    )


def _assess_valuation(
    ratios: dict,
    rules: SectorRules,
    freshness: str,
) -> DimensionAssessment:
    metrics: list[AssessmentMetric] = []
    positives: list[str] = []
    negatives: list[str] = []
    missing: list[str] = []

    pe = _ratio_value(ratios, "pe_ratio")
    pb = _ratio_value(ratios, "pb_ratio")
    ev = _ratio_value(ratios, "ev_ebitda") if rules.use_ev_ebitda else None
    # P/S and dividend from stored ttm ratios handled via ratios dict if present later
    ps = None
    dy = None

    for key, name, value, applicable in (
        ("pe_ratio", "P/E", pe, True),
        ("pb_ratio", "P/B", pb, True),
        ("ev_ebitda", "EV/EBITDA", ev, rules.use_ev_ebitda),
        ("ps_ratio", "P/S", ps, True),
        ("dividend_yield", "Dividend Yield", dy, True),
    ):
        metrics.append(
            AssessmentMetric(
                key=key,
                name=name,
                value=value if applicable else None,
                applicable=applicable,
                origin=("not_applicable" if not applicable else ("calculated" if value is not None else "unavailable")),
            )
        )
        if not applicable:
            missing.append(f"{name} (not applicable)")
        elif value is None:
            missing.append(name)

    available = [m for m in metrics if m.applicable and m.value is not None]
    if len(available) < 1:
        return DimensionAssessment(
            dimension="valuation",
            classification=Classification.INSUFFICIENT_DATA,
            metrics_used=metrics,
            missing_information=missing,
            reporting_period="ttm/market",
            data_freshness=freshness,
            explanation="Insufficient valuation metrics. A single ratio is never used to label a stock undervalued or overvalued.",
            sector_methodology=rules.label,
        )

    # Context-only classification: describe richness/cheapness bands cautiously
    notes_pos = []
    notes_neg = []
    if pe is not None:
        f = float(pe)
        if 0 < f < 15:
            notes_pos.append(f"Trailing P/E {_num(pe)} is in a lower historical-style band (context only).")
        elif f > 40:
            notes_neg.append(f"Trailing P/E {_num(pe)} is elevated versus common long-term bands (context only).")
        else:
            notes_pos.append(f"Trailing P/E {_num(pe)} is in a mid-range band (context only).")
    if pb is not None:
        f = float(pb)
        if 0 < f < 1.5:
            notes_pos.append(f"P/B {_num(pb)} is relatively low (context only).")
        elif f > 5:
            notes_neg.append(f"P/B {_num(pb)} is relatively high (context only).")
    if ev is not None and rules.use_ev_ebitda:
        f = float(ev)
        if 0 < f < 10:
            notes_pos.append(f"EV/EBITDA {_num(ev)} is in a lower band (context only).")
        elif f > 20:
            notes_neg.append(f"EV/EBITDA {_num(ev)} is elevated (context only).")

    if notes_pos and not notes_neg:
        classification = Classification.HEALTHY
    elif notes_neg and not notes_pos:
        classification = Classification.MODERATE
    elif notes_pos and notes_neg:
        classification = Classification.MODERATE
    else:
        classification = Classification.MODERATE

    # Never STRONG/WEAK solely from valuation
    explanation = (
        f"Valuation context classified as {classification.value} using {len(available)} metric(s). "
        "This is not a buy/sell signal and does not assert intrinsic undervaluation or overvaluation "
        "from a single ratio. Historical peer/context bands are indicative only."
    )
    return DimensionAssessment(
        dimension="valuation",
        classification=classification,
        metrics_used=metrics,
        positive_factors=notes_pos[:6],
        negative_factors=notes_neg[:6],
        missing_information=missing,
        reporting_period="ttm/market",
        data_freshness=freshness,
        explanation=explanation,
        sector_methodology=rules.label,
    )


def _assess_cash_flow(
    history,
    rules: SectorRules,
    freshness: str,
) -> DimensionAssessment:
    metrics: list[AssessmentMetric] = []
    positives: list[str] = []
    negatives: list[str] = []
    missing: list[str] = []

    ocf_obs = history.operating_cash_flow.observations
    fcf_obs = history.free_cash_flow.observations
    latest_ocf = ocf_obs[-1].value if ocf_obs else None
    latest_fcf = fcf_obs[-1].value if fcf_obs else None
    metrics.append(AssessmentMetric("operating_cash_flow", "Operating Cash Flow", latest_ocf, origin="reported" if latest_ocf is not None else "unavailable"))
    metrics.append(AssessmentMetric("free_cash_flow", "Free Cash Flow", latest_fcf, origin="calculated" if latest_fcf is not None else "unavailable"))

    conversion = history.cash_conversion[-1] if history.cash_conversion else None
    ocf_ni = conversion.ocf_to_ni if conversion else None
    metrics.append(AssessmentMetric("ocf_to_ni", "OCF / Net Income", ocf_ni, origin="calculated" if ocf_ni is not None else "unavailable"))

    if latest_ocf is None:
        missing.append("Operating Cash Flow")
    if latest_fcf is None:
        missing.append("Free Cash Flow")

    if latest_ocf is None and latest_fcf is None:
        return DimensionAssessment(
            dimension="cash_flow_quality",
            classification=Classification.INSUFFICIENT_DATA,
            metrics_used=metrics,
            missing_information=missing,
            reporting_period=history.period_type,
            data_freshness=freshness,
            explanation="Cash-flow statements are unavailable for assessment.",
            sector_methodology=rules.label,
        )

    points = 0
    checks = 0
    if latest_ocf is not None:
        checks += 1
        if latest_ocf > 0:
            points += 3
            positives.append("Latest operating cash flow is positive.")
        else:
            negatives.append("Latest operating cash flow is negative.")
    if latest_fcf is not None:
        checks += 1
        if latest_fcf > 0:
            points += 2
            positives.append("Latest free cash flow is positive.")
        else:
            negatives.append("Latest free cash flow is negative or zero.")
            # Check persistence
            fcf_vals = [o.value for o in fcf_obs if o.value is not None]
            if len(fcf_vals) >= 2 and all(v <= 0 for v in fcf_vals[-2:]):
                negatives.append("Free cash flow has been non-positive across recent periods.")

    if ocf_ni is not None:
        checks += 1
        if float(ocf_ni) >= 1:
            points += 2
            positives.append(f"Operating cash conversion vs net income is {_num(ocf_ni)} (≥ 1).")
        elif float(ocf_ni) >= 0.7:
            points += 1
        else:
            negatives.append(f"Weak cash conversion: OCF/NI = {_num(ocf_ni)}.")

    if history.operating_cash_flow.trend == TrendDirection.INCONSISTENT:
        negatives.append("Operating cash flow is inconsistent across periods.")
        checks += 1
    elif history.operating_cash_flow.trend in {TrendDirection.IMPROVING, TrendDirection.STABLE}:
        positives.append(f"OCF trend: {history.operating_cash_flow.trend.value}.")
        points += 1
        checks += 1

    avg = points / max(checks, 1)
    if avg >= 2.4:
        classification = Classification.STRONG
    elif avg >= 1.7:
        classification = Classification.HEALTHY
    elif avg >= 1.0:
        classification = Classification.MODERATE
    else:
        classification = Classification.WEAK

    return DimensionAssessment(
        dimension="cash_flow_quality",
        classification=classification,
        metrics_used=metrics,
        positive_factors=positives[:6],
        negative_factors=negatives[:6],
        missing_information=missing,
        reporting_period=history.period_type,
        data_freshness=freshness,
        explanation=f"Cash-flow quality classified as {classification.value} from reported/derived cash-flow metrics.",
        sector_methodology=rules.label,
    )


_CLASS_RANK = {
    Classification.STRONG: 4,
    Classification.HEALTHY: 3,
    Classification.MODERATE: 2,
    Classification.WEAK: 1,
    Classification.INSUFFICIENT_DATA: 0,
}


def _overall_classification(dims: list[DimensionAssessment]) -> Classification:
    usable = [d.classification for d in dims if d.classification != Classification.INSUFFICIENT_DATA]
    if len(usable) < 2:
        return Classification.INSUFFICIENT_DATA
    avg = sum(_CLASS_RANK[c] for c in usable) / len(usable)
    if avg >= 3.5:
        return Classification.STRONG
    if avg >= 2.5:
        return Classification.HEALTHY
    if avg >= 1.5:
        return Classification.MODERATE
    return Classification.WEAK


def analyze_fundamentals(
    db: Session,
    company: Company,
    current_price: Decimal | None = None,
    market_cap: Decimal | None = None,
    industry: str | None = None,
) -> FundamentalAnalysis:
    """Produce an explainable fundamental analysis for a company."""
    info = db.scalar(
        select(CompanyFundamentalInfo).where(CompanyFundamentalInfo.company_id == company.id)
    )
    industry = industry or None
    rules = resolve_sector_rules(company.sector, industry)
    retrieved = _latest_retrieval(db, company.id)
    freshness = classify_fundamental_freshness(retrieved).value

    if market_cap is None and info and info.market_cap is not None:
        market_cap = Decimal(info.market_cap)

    ratio_bundle = calculate_all_ratios(db, company, current_price=current_price, market_cap=market_cap)
    # Flatten for helpers
    flat: dict[str, dict] = {}
    for category in ("valuation", "profitability", "liquidity", "leverage", "efficiency", "growth"):
        flat.update(ratio_bundle.get(category, {}))

    history = analyze_historical_performance(db, company, period_type="annual", limit=8)

    profitability = _assess_profitability(flat, history.profitability_insight.overall_trend, rules, freshness)
    growth = _assess_growth(flat, history, rules, freshness)
    stability = _assess_stability(flat, history, rules, freshness)
    valuation = _assess_valuation(flat, rules, freshness)
    cash_flow = _assess_cash_flow(history, rules, freshness)

    dims = [profitability, growth, stability, valuation, cash_flow]
    overall = _overall_classification(dims)

    positives: list[str] = []
    negatives: list[str] = []
    missing: list[str] = []
    for d in dims:
        positives.extend(d.positive_factors[:2])
        negatives.extend(d.negative_factors[:2])
        missing.extend(d.missing_information[:2])

    if rules.profile.value == "GENERAL":
        missing.append("Sector-specific calibration unavailable; general methodology applied.")

    return FundamentalAnalysis(
        symbol=company.symbol,
        company_name=company.name,
        sector=company.sector,
        industry=industry,
        overall_classification=overall,
        profitability=profitability,
        growth=growth,
        financial_stability=stability,
        valuation=valuation,
        cash_flow_quality=cash_flow,
        positive_factors=list(dict.fromkeys(positives))[:10],
        negative_factors=list(dict.fromkeys(negatives))[:10],
        missing_data_warnings=list(dict.fromkeys(missing))[:15],
        analysis_version=ANALYSIS_VERSION,
        generated_at=datetime.now(timezone.utc),
    )
