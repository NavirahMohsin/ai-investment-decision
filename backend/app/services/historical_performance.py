"""Historical financial performance analysis from persisted statements."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Company, CompanyFinancial
from app.services.financial_ratios import safe_divide, safe_multiply


class TrendDirection(StrEnum):
    IMPROVING = "IMPROVING"
    DECLINING = "DECLINING"
    STABLE = "STABLE"
    ACCELERATING = "ACCELERATING"
    DECELERATING = "DECELERATING"
    INCONSISTENT = "INCONSISTENT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class SeriesQuality(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    EMPTY = "EMPTY"


PeriodType = Literal["annual", "quarterly"]


# Canonical Yahoo Finance metric names used by the ingestion layer.
METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "revenue": ("Total Revenue", "Operating Revenue"),
    "gross_profit": ("Gross Profit",),
    "operating_income": ("Operating Income", "EBIT"),
    "net_income": ("Net Income", "Net Income Common Stockholders"),
    "eps": ("Basic EPS", "Diluted EPS"),
    "total_assets": ("Total Assets",),
    "total_liabilities": ("Total Liabilities Net Minority Interest", "Total Liabilities"),
    "total_debt": ("Total Debt",),
    "equity": ("Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"),
    "current_assets": ("Current Assets",),
    "current_liabilities": ("Current Liabilities",),
    "operating_cash_flow": ("Operating Cash Flow", "Cash Flow From Continuing Operating Activities"),
    "investing_cash_flow": ("Investing Cash Flow", "Cash Flow From Continuing Investing Activities"),
    "financing_cash_flow": ("Financing Cash Flow", "Cash Flow From Continuing Financing Activities"),
    "capital_expenditure": ("Capital Expenditure", "Purchase Of PPE"),
    "free_cash_flow": ("Free Cash Flow",),
}


@dataclass
class PeriodObservation:
    """A single reported or derived observation for a period."""

    period_end: date
    period_type: PeriodType
    value: Decimal | None
    currency: str | None
    source: Literal["reported", "calculated"]
    metric_name: str | None = None
    derived_label: str | None = None


@dataclass
class GrowthPoint:
    """Period-over-period growth for a metric."""

    period_end: date
    comparison_period_end: date
    comparison_type: Literal["yoy", "qoq", "same_quarter_yoy"]
    growth_rate: Decimal | None  # decimal fraction, e.g. 0.12 = 12%
    growth_pct: Decimal | None
    current_value: Decimal | None
    previous_value: Decimal | None
    is_derived: bool = True
    error: str | None = None


@dataclass
class MetricSeries:
    """Time series for one financial metric."""

    metric_key: str
    display_name: str
    period_type: PeriodType
    observations: list[PeriodObservation] = field(default_factory=list)
    growth: list[GrowthPoint] = field(default_factory=list)
    trend: TrendDirection = TrendDirection.INSUFFICIENT_DATA
    quality: SeriesQuality = SeriesQuality.EMPTY
    missing_periods: list[str] = field(default_factory=list)
    currency: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class MarginSeries:
    """Margin series derived from two reported series."""

    metric_key: str
    display_name: str
    period_type: PeriodType
    observations: list[PeriodObservation] = field(default_factory=list)
    trend: TrendDirection = TrendDirection.INSUFFICIENT_DATA
    quality: SeriesQuality = SeriesQuality.EMPTY
    notes: list[str] = field(default_factory=list)


@dataclass
class CashConversionPoint:
    period_end: date
    operating_cash_flow: Decimal | None
    free_cash_flow: Decimal | None
    net_income: Decimal | None
    ocf_to_ni: Decimal | None
    fcf_to_ni: Decimal | None
    notes: list[str] = field(default_factory=list)


@dataclass
class BalanceSheetInsight:
    leverage_trend: TrendDirection
    liquidity_trend: TrendDirection
    strength_trend: TrendDirection
    notes: list[str] = field(default_factory=list)


@dataclass
class ProfitabilityInsight:
    overall_trend: TrendDirection
    margin_compression: bool | None
    margin_expansion: bool | None
    inconsistent_earnings: bool
    notes: list[str] = field(default_factory=list)


@dataclass
class HistoricalPerformanceReport:
    """Full historical performance analysis for a company."""

    symbol: str
    period_type: PeriodType
    revenue: MetricSeries
    gross_profit: MetricSeries
    operating_income: MetricSeries
    net_income: MetricSeries
    eps: MetricSeries
    gross_margin: MarginSeries
    operating_margin: MarginSeries
    net_margin: MarginSeries
    total_assets: MetricSeries
    total_liabilities: MetricSeries
    total_debt: MetricSeries
    equity: MetricSeries
    current_assets: MetricSeries
    current_liabilities: MetricSeries
    working_capital: MetricSeries
    operating_cash_flow: MetricSeries
    investing_cash_flow: MetricSeries
    financing_cash_flow: MetricSeries
    free_cash_flow: MetricSeries
    capital_expenditure: MetricSeries
    cash_conversion: list[CashConversionPoint]
    profitability_insight: ProfitabilityInsight
    balance_sheet_insight: BalanceSheetInsight
    data_warnings: list[str] = field(default_factory=list)


def _decimal_or_none(value: Decimal | None) -> Decimal | None:
    return value


def calculate_growth(
    current: Decimal | None,
    previous: Decimal | None,
) -> tuple[Decimal | None, str | None]:
    """
    Calculate growth rate as a fraction.

    Returns (growth_rate, error). Never fabricates values when previous is zero
    or either input is missing.
    """
    if current is None or previous is None:
        return None, "Missing period value"
    if previous == 0:
        return None, "Previous period value is zero"
    return safe_divide(current - previous, previous), None


def _sorted_unique_periods(observations: list[PeriodObservation]) -> list[date]:
    return sorted({o.period_end for o in observations})


def _detect_missing_annual_periods(period_ends: list[date]) -> list[str]:
    if len(period_ends) < 2:
        return []
    missing: list[str] = []
    years = sorted({p.year for p in period_ends})
    for year in range(years[0], years[-1] + 1):
        if year not in years:
            missing.append(str(year))
    return missing


def _detect_missing_quarterly_periods(period_ends: list[date]) -> list[str]:
    if len(period_ends) < 2:
        return []
    missing: list[str] = []
    # Approximate quarters by calendar year-quarter labels using period end months.
    labels = set()
    for p in period_ends:
        q = (p.month - 1) // 3 + 1
        labels.add((p.year, q))
    years = sorted({y for y, _ in labels})
    for year in range(years[0], years[-1] + 1):
        for q in range(1, 5):
            if (year, q) not in labels and not (
                year == years[0] and q < min(qq for yy, qq in labels if yy == years[0])
            ) and not (
                year == years[-1] and q > max(qq for yy, qq in labels if yy == years[-1])
            ):
                missing.append(f"{year}-Q{q}")
    return missing


def _classify_trend(values: list[Decimal | None], *, min_points: int = 3) -> TrendDirection:
    usable = [v for v in values if v is not None]
    if len(usable) < 2:
        return TrendDirection.INSUFFICIENT_DATA
    if len(usable) < min_points:
        # Two-point trend only
        if usable[-1] > usable[0]:
            return TrendDirection.IMPROVING
        if usable[-1] < usable[0]:
            return TrendDirection.DECLINING
        return TrendDirection.STABLE

    deltas = [usable[i] - usable[i - 1] for i in range(1, len(usable))]
    up = sum(1 for d in deltas if d > 0)
    down = sum(1 for d in deltas if d < 0)
    flat = sum(1 for d in deltas if d == 0)

    if up == len(deltas):
        # Check acceleration on last two deltas when possible
        if len(deltas) >= 2 and deltas[-1] > deltas[-2] > 0:
            return TrendDirection.ACCELERATING
        if len(deltas) >= 2 and 0 < deltas[-1] < deltas[-2]:
            return TrendDirection.DECELERATING
        return TrendDirection.IMPROVING
    if down == len(deltas):
        if len(deltas) >= 2 and deltas[-1] < deltas[-2] < 0:
            return TrendDirection.ACCELERATING  # accelerating decline
        if len(deltas) >= 2 and deltas[-2] < deltas[-1] < 0:
            return TrendDirection.DECELERATING
        return TrendDirection.DECLINING
    if flat == len(deltas):
        return TrendDirection.STABLE
    if up >= down and flat + up >= down:
        # Majority non-negative but mixed
        if up > 0 and down > 0:
            return TrendDirection.INCONSISTENT
        return TrendDirection.STABLE
    if down > up:
        return TrendDirection.INCONSISTENT if up > 0 else TrendDirection.DECLINING
    return TrendDirection.INCONSISTENT


def _load_metric_history(
    db: Session,
    company_id: int,
    metric_names: tuple[str, ...],
    period_type: PeriodType,
    limit: int | None = None,
) -> list[CompanyFinancial]:
    query = (
        select(CompanyFinancial)
        .where(
            CompanyFinancial.company_id == company_id,
            CompanyFinancial.metric_name.in_(metric_names),
            CompanyFinancial.period_type == period_type,
            CompanyFinancial.period_end.is_not(None),
        )
        .order_by(CompanyFinancial.period_end.asc())
    )
    records = list(db.scalars(query))
    # Prefer first alias that has data per period
    by_period: dict[date, CompanyFinancial] = {}
    alias_priority = {name: idx for idx, name in enumerate(metric_names)}
    for record in records:
        pe = record.period_end
        if pe is None:
            continue
        existing = by_period.get(pe)
        if existing is None:
            by_period[pe] = record
        else:
            if alias_priority.get(record.metric_name, 99) < alias_priority.get(existing.metric_name, 99):
                if record.metric_value is not None or existing.metric_value is None:
                    by_period[pe] = record
            elif (
                existing.metric_value is None
                and record.metric_value is not None
                and alias_priority.get(record.metric_name, 99) == alias_priority.get(existing.metric_name, 99)
            ):
                by_period[pe] = record
    ordered = [by_period[k] for k in sorted(by_period.keys())]
    if limit is not None and limit > 0:
        ordered = ordered[-limit:]
    return ordered


def build_metric_series(
    db: Session,
    company: Company,
    metric_key: str,
    display_name: str,
    period_type: PeriodType,
    limit: int | None = None,
    *,
    include_yoy: bool = True,
    include_qoq: bool = False,
) -> MetricSeries:
    aliases = METRIC_ALIASES.get(metric_key, (metric_key,))
    records = _load_metric_history(db, company.id, aliases, period_type, limit)

    observations = [
        PeriodObservation(
            period_end=r.period_end,  # type: ignore[arg-type]
            period_type=period_type,
            value=_decimal_or_none(r.metric_value),
            currency=r.currency,
            source="reported",
            metric_name=r.metric_name,
        )
        for r in records
        if r.period_end is not None
    ]

    series = MetricSeries(
        metric_key=metric_key,
        display_name=display_name,
        period_type=period_type,
        observations=observations,
        currency=next((o.currency for o in observations if o.currency), None),
    )

    if not observations:
        series.quality = SeriesQuality.EMPTY
        series.trend = TrendDirection.INSUFFICIENT_DATA
        series.notes.append("No reported observations for this metric.")
        return series

    period_ends = _sorted_unique_periods(observations)
    if period_type == "annual":
        series.missing_periods = _detect_missing_annual_periods(period_ends)
    else:
        series.missing_periods = _detect_missing_quarterly_periods(period_ends)

    none_count = sum(1 for o in observations if o.value is None)
    if series.missing_periods or none_count:
        series.quality = SeriesQuality.INCOMPLETE
        if series.missing_periods:
            series.notes.append(
                f"Incomplete time series; missing periods: {', '.join(series.missing_periods)}"
            )
        if none_count:
            series.notes.append(f"{none_count} period(s) have null reported values.")
    else:
        series.quality = SeriesQuality.COMPLETE

    # Growth calculations — chronological order already ascending
    if include_yoy and period_type == "annual":
        for i in range(1, len(observations)):
            curr = observations[i]
            prev = observations[i - 1]
            rate, error = calculate_growth(curr.value, prev.value)
            series.growth.append(
                GrowthPoint(
                    period_end=curr.period_end,
                    comparison_period_end=prev.period_end,
                    comparison_type="yoy",
                    growth_rate=rate,
                    growth_pct=safe_multiply(rate, Decimal("100")) if rate is not None else None,
                    current_value=curr.value,
                    previous_value=prev.value,
                    is_derived=True,
                    error=error,
                )
            )

    if period_type == "quarterly":
        if include_qoq:
            for i in range(1, len(observations)):
                curr = observations[i]
                prev = observations[i - 1]
                rate, error = calculate_growth(curr.value, prev.value)
                series.growth.append(
                    GrowthPoint(
                        period_end=curr.period_end,
                        comparison_period_end=prev.period_end,
                        comparison_type="qoq",
                        growth_rate=rate,
                        growth_pct=safe_multiply(rate, Decimal("100")) if rate is not None else None,
                        current_value=curr.value,
                        previous_value=prev.value,
                        is_derived=True,
                        error=error,
                    )
                )
        # Same-quarter year-over-year
        by_key = {(o.period_end.year, (o.period_end.month - 1) // 3 + 1): o for o in observations}
        for o in observations:
            q = (o.period_end.month - 1) // 3 + 1
            prior = by_key.get((o.period_end.year - 1, q))
            if prior is None:
                continue
            rate, error = calculate_growth(o.value, prior.value)
            series.growth.append(
                GrowthPoint(
                    period_end=o.period_end,
                    comparison_period_end=prior.period_end,
                    comparison_type="same_quarter_yoy",
                    growth_rate=rate,
                    growth_pct=safe_multiply(rate, Decimal("100")) if rate is not None else None,
                    current_value=o.value,
                    previous_value=prior.value,
                    is_derived=True,
                    error=error,
                )
            )

    series.trend = _classify_trend([o.value for o in observations])

    # Revenue acceleration/deceleration note when enough YoY growth points exist
    yoy_rates = [
        g.growth_rate
        for g in series.growth
        if g.comparison_type in {"yoy", "same_quarter_yoy"} and g.growth_rate is not None
    ]
    if metric_key == "revenue" and len(yoy_rates) >= 2:
        if yoy_rates[-1] > yoy_rates[-2]:
            series.notes.append("Recent growth rate is higher than the prior period (acceleration).")
            if series.trend == TrendDirection.IMPROVING:
                series.trend = TrendDirection.ACCELERATING
        elif yoy_rates[-1] < yoy_rates[-2]:
            series.notes.append("Recent growth rate is lower than the prior period (deceleration).")
            if series.trend in {TrendDirection.IMPROVING, TrendDirection.STABLE}:
                series.trend = TrendDirection.DECELERATING

    return series


def build_margin_series(
    numerator: MetricSeries,
    denominator: MetricSeries,
    metric_key: str,
    display_name: str,
) -> MarginSeries:
    """Build margin series as calculated (not reported) percentages."""
    denom_by_period = {o.period_end: o for o in denominator.observations}
    observations: list[PeriodObservation] = []
    notes: list[str] = ["Margin values are calculated from reported financials."]

    for num in numerator.observations:
        den = denom_by_period.get(num.period_end)
        if den is None:
            observations.append(
                PeriodObservation(
                    period_end=num.period_end,
                    period_type=numerator.period_type,
                    value=None,
                    currency=None,
                    source="calculated",
                    derived_label=metric_key,
                )
            )
            continue
        ratio = safe_divide(num.value, den.value)
        pct = safe_multiply(ratio, Decimal("100")) if ratio is not None else None
        if den.value == 0:
            notes.append(f"Denominator zero for period {num.period_end}; margin unavailable.")
        observations.append(
            PeriodObservation(
                period_end=num.period_end,
                period_type=numerator.period_type,
                value=pct,
                currency=None,
                source="calculated",
                derived_label=metric_key,
            )
        )

    quality = SeriesQuality.EMPTY
    if observations:
        if any(o.value is None for o in observations) or len(observations) < len(numerator.observations):
            quality = SeriesQuality.INCOMPLETE
        else:
            quality = SeriesQuality.COMPLETE

    return MarginSeries(
        metric_key=metric_key,
        display_name=display_name,
        period_type=numerator.period_type,
        observations=observations,
        trend=_classify_trend([o.value for o in observations]),
        quality=quality,
        notes=notes,
    )


def build_working_capital_series(
    current_assets: MetricSeries,
    current_liabilities: MetricSeries,
) -> MetricSeries:
    cl_by = {o.period_end: o for o in current_liabilities.observations}
    observations: list[PeriodObservation] = []
    for ca in current_assets.observations:
        cl = cl_by.get(ca.period_end)
        if cl is None or ca.value is None or cl.value is None:
            value = None
        else:
            value = ca.value - cl.value
        observations.append(
            PeriodObservation(
                period_end=ca.period_end,
                period_type=current_assets.period_type,
                value=value,
                currency=ca.currency or (cl.currency if cl else None),
                source="calculated",
                derived_label="working_capital",
            )
        )
    quality = SeriesQuality.EMPTY if not observations else (
        SeriesQuality.INCOMPLETE if any(o.value is None for o in observations) else SeriesQuality.COMPLETE
    )
    return MetricSeries(
        metric_key="working_capital",
        display_name="Working Capital",
        period_type=current_assets.period_type,
        observations=observations,
        trend=_classify_trend([o.value for o in observations]),
        quality=quality,
        currency=current_assets.currency,
        notes=["Working capital is calculated as Current Assets − Current Liabilities."],
    )


def _derive_free_cash_flow_if_missing(
    ocf: MetricSeries,
    capex: MetricSeries,
    fcf: MetricSeries,
) -> MetricSeries:
    """Fill FCF from OCF − CapEx only where FCF is missing and both inputs exist."""
    if fcf.observations and all(o.value is not None for o in fcf.observations):
        return fcf

    capex_by = {o.period_end: o for o in capex.observations}
    fcf_by = {o.period_end: o for o in fcf.observations}
    observations: list[PeriodObservation] = []
    notes = list(fcf.notes)
    notes.append(
        "Where Free Cash Flow is not reported, it is derived as Operating Cash Flow − Capital Expenditure "
        "(CapEx stored as negative by Yahoo is added)."
    )

    periods = sorted(
        {o.period_end for o in ocf.observations}
        | set(fcf_by.keys())
        | set(capex_by.keys())
    )
    for pe in periods:
        existing = fcf_by.get(pe)
        if existing and existing.value is not None:
            observations.append(existing)
            continue
        o = next((x for x in ocf.observations if x.period_end == pe), None)
        c = capex_by.get(pe)
        value = None
        if o is not None and o.value is not None and c is not None and c.value is not None:
            # Yahoo CapEx is typically negative; FCF = OCF + CapEx when CapEx < 0,
            # or OCF − CapEx when CapEx is absolute positive.
            if c.value <= 0:
                value = o.value + c.value
            else:
                value = o.value - c.value
        observations.append(
            PeriodObservation(
                period_end=pe,
                period_type=ocf.period_type,
                value=value,
                currency=o.currency if o else (c.currency if c else None),
                source="calculated" if value is not None else "reported",
                derived_label="free_cash_flow",
                metric_name="Free Cash Flow" if existing else None,
            )
        )

    quality = SeriesQuality.EMPTY if not observations else (
        SeriesQuality.INCOMPLETE if any(o.value is None for o in observations) else SeriesQuality.COMPLETE
    )
    return MetricSeries(
        metric_key="free_cash_flow",
        display_name="Free Cash Flow",
        period_type=ocf.period_type,
        observations=observations,
        growth=fcf.growth,
        trend=_classify_trend([o.value for o in observations]),
        quality=quality,
        currency=fcf.currency or ocf.currency,
        notes=notes,
        missing_periods=fcf.missing_periods,
    )


def analyze_cash_conversion(
    ocf: MetricSeries,
    fcf: MetricSeries,
    net_income: MetricSeries,
) -> list[CashConversionPoint]:
    ocf_by = {o.period_end: o for o in ocf.observations}
    fcf_by = {o.period_end: o for o in fcf.observations}
    ni_by = {o.period_end: o for o in net_income.observations}
    periods = sorted(set(ocf_by) | set(fcf_by) | set(ni_by))
    points: list[CashConversionPoint] = []
    for pe in periods:
        o = ocf_by.get(pe)
        f = fcf_by.get(pe)
        n = ni_by.get(pe)
        o_val = o.value if o else None
        f_val = f.value if f else None
        n_val = n.value if n else None
        notes: list[str] = []
        ocf_to_ni, err1 = calculate_growth(o_val, n_val) if False else (
            (safe_divide(o_val, n_val), None) if o_val is not None and n_val not in (None, Decimal("0")) else (None, "unavailable")
        )
        if err1 == "unavailable":
            notes.append("OCF/NI unavailable due to missing or zero net income.")
            ocf_to_ni = None
        fcf_to_ni = (
            safe_divide(f_val, n_val)
            if f_val is not None and n_val not in (None, Decimal("0"))
            else None
        )
        if f_val is not None and n_val == 0:
            notes.append("FCF/NI unavailable because net income is zero.")
        points.append(
            CashConversionPoint(
                period_end=pe,
                operating_cash_flow=o_val,
                free_cash_flow=f_val,
                net_income=n_val,
                ocf_to_ni=ocf_to_ni,
                fcf_to_ni=fcf_to_ni,
                notes=notes,
            )
        )
    return points


def _profitability_insight(
    gross_margin: MarginSeries,
    operating_margin: MarginSeries,
    net_margin: MarginSeries,
    net_income: MetricSeries,
) -> ProfitabilityInsight:
    trends = [gross_margin.trend, operating_margin.trend, net_margin.trend]
    improving = sum(1 for t in trends if t in {TrendDirection.IMPROVING, TrendDirection.ACCELERATING})
    declining = sum(1 for t in trends if t in {TrendDirection.DECLINING, TrendDirection.DECELERATING})
    inconsistent = net_income.trend == TrendDirection.INCONSISTENT or any(
        t == TrendDirection.INCONSISTENT for t in trends
    )

    if improving + declining == 0:
        overall = TrendDirection.INSUFFICIENT_DATA
    elif improving > declining:
        overall = TrendDirection.IMPROVING
    elif declining > improving:
        overall = TrendDirection.DECLINING
    else:
        overall = TrendDirection.INCONSISTENT

    margin_compression = None
    margin_expansion = None
    for series in (gross_margin, operating_margin, net_margin):
        vals = [o.value for o in series.observations if o.value is not None]
        if len(vals) >= 2:
            if vals[-1] < vals[0]:
                margin_compression = True if margin_compression is None else margin_compression or True
            if vals[-1] > vals[0]:
                margin_expansion = True if margin_expansion is None else margin_expansion or True

    notes: list[str] = []
    if margin_compression:
        notes.append("Evidence of margin compression across available periods.")
    if margin_expansion:
        notes.append("Evidence of margin expansion across available periods.")
    if inconsistent:
        notes.append("Earnings or margins show inconsistent period-to-period changes.")

    return ProfitabilityInsight(
        overall_trend=overall,
        margin_compression=margin_compression,
        margin_expansion=margin_expansion,
        inconsistent_earnings=inconsistent,
        notes=notes,
    )


def _balance_sheet_insight(
    total_debt: MetricSeries,
    equity: MetricSeries,
    current_assets: MetricSeries,
    current_liabilities: MetricSeries,
    total_assets: MetricSeries,
) -> BalanceSheetInsight:
    notes: list[str] = []
    leverage = TrendDirection.INSUFFICIENT_DATA
    # Debt growth vs equity growth
    debt_vals = [o.value for o in total_debt.observations if o.value is not None]
    equity_vals = [o.value for o in equity.observations if o.value is not None]
    if len(debt_vals) >= 2 and len(equity_vals) >= 2:
        debt_up = debt_vals[-1] > debt_vals[0]
        equity_up = equity_vals[-1] > equity_vals[0]
        if debt_up and (not equity_up or debt_vals[-1] / debt_vals[0] > equity_vals[-1] / equity_vals[0]):
            leverage = TrendDirection.DECLINING  # increasing leverage = worsening
            notes.append("Debt growth outpaces equity growth — increasing leverage.")
        elif not debt_up and equity_up:
            leverage = TrendDirection.IMPROVING
            notes.append("Equity growth with stable/declining debt — improving leverage profile.")
        else:
            leverage = TrendDirection.STABLE

    liquidity = TrendDirection.INSUFFICIENT_DATA
    ca = [o.value for o in current_assets.observations if o.value is not None]
    cl = [o.value for o in current_liabilities.observations if o.value is not None]
    if len(ca) >= 2 and len(cl) >= 2:
        # Compare current ratios at ends
        start_ratio = safe_divide(ca[0], cl[0])
        end_ratio = safe_divide(ca[-1], cl[-1])
        if start_ratio is not None and end_ratio is not None:
            if end_ratio < start_ratio:
                liquidity = TrendDirection.DECLINING
                notes.append("Current ratio trend indicates deteriorating liquidity.")
            elif end_ratio > start_ratio:
                liquidity = TrendDirection.IMPROVING
                notes.append("Current ratio trend indicates improving liquidity.")
            else:
                liquidity = TrendDirection.STABLE

    strength = TrendDirection.INSUFFICIENT_DATA
    assets = [o.value for o in total_assets.observations if o.value is not None]
    if len(assets) >= 2 and len(equity_vals) >= 2:
        if assets[-1] > assets[0] and equity_vals[-1] > equity_vals[0] and leverage != TrendDirection.DECLINING:
            strength = TrendDirection.IMPROVING
            notes.append("Growing assets and equity with controlled leverage suggest improving balance-sheet strength.")
        elif leverage == TrendDirection.DECLINING or liquidity == TrendDirection.DECLINING:
            strength = TrendDirection.DECLINING
        else:
            strength = TrendDirection.STABLE

    return BalanceSheetInsight(
        leverage_trend=leverage,
        liquidity_trend=liquidity,
        strength_trend=strength,
        notes=notes,
    )


def analyze_historical_performance(
    db: Session,
    company: Company,
    period_type: PeriodType = "annual",
    limit: int | None = 12,
) -> HistoricalPerformanceReport:
    """
    Build a historical performance report from persisted financial statements.

    Does not call Yahoo Finance. Uses stored CompanyFinancial rows only.
    Annual and quarterly series are never mixed.
    """
    if period_type not in {"annual", "quarterly"}:
        raise ValueError("period_type must be 'annual' or 'quarterly'")

    include_qoq = period_type == "quarterly"
    warnings: list[str] = []

    revenue = build_metric_series(
        db, company, "revenue", "Revenue", period_type, limit, include_yoy=True, include_qoq=include_qoq
    )
    gross_profit = build_metric_series(
        db, company, "gross_profit", "Gross Profit", period_type, limit, include_yoy=True, include_qoq=include_qoq
    )
    operating_income = build_metric_series(
        db, company, "operating_income", "Operating Income", period_type, limit, include_yoy=True, include_qoq=include_qoq
    )
    net_income = build_metric_series(
        db, company, "net_income", "Net Income", period_type, limit, include_yoy=True, include_qoq=include_qoq
    )
    eps = build_metric_series(
        db, company, "eps", "EPS", period_type, limit, include_yoy=True, include_qoq=include_qoq
    )

    gross_margin = build_margin_series(gross_profit, revenue, "gross_margin", "Gross Margin %")
    operating_margin = build_margin_series(operating_income, revenue, "operating_margin", "Operating Margin %")
    net_margin = build_margin_series(net_income, revenue, "net_margin", "Net Profit Margin %")

    total_assets = build_metric_series(
        db, company, "total_assets", "Total Assets", period_type, limit, include_yoy=True, include_qoq=include_qoq
    )
    total_liabilities = build_metric_series(
        db, company, "total_liabilities", "Total Liabilities", period_type, limit, include_yoy=True, include_qoq=include_qoq
    )
    total_debt = build_metric_series(
        db, company, "total_debt", "Total Debt", period_type, limit, include_yoy=True, include_qoq=include_qoq
    )
    equity = build_metric_series(
        db, company, "equity", "Shareholders' Equity", period_type, limit, include_yoy=True, include_qoq=include_qoq
    )
    current_assets = build_metric_series(
        db, company, "current_assets", "Current Assets", period_type, limit, include_yoy=True, include_qoq=include_qoq
    )
    current_liabilities = build_metric_series(
        db, company, "current_liabilities", "Current Liabilities", period_type, limit, include_yoy=True, include_qoq=include_qoq
    )
    working_capital = build_working_capital_series(current_assets, current_liabilities)

    ocf = build_metric_series(
        db, company, "operating_cash_flow", "Operating Cash Flow", period_type, limit, include_yoy=True, include_qoq=include_qoq
    )
    investing = build_metric_series(
        db, company, "investing_cash_flow", "Investing Cash Flow", period_type, limit, include_yoy=False, include_qoq=False
    )
    financing = build_metric_series(
        db, company, "financing_cash_flow", "Financing Cash Flow", period_type, limit, include_yoy=False, include_qoq=False
    )
    capex = build_metric_series(
        db, company, "capital_expenditure", "Capital Expenditure", period_type, limit, include_yoy=True, include_qoq=include_qoq
    )
    fcf_raw = build_metric_series(
        db, company, "free_cash_flow", "Free Cash Flow", period_type, limit, include_yoy=True, include_qoq=include_qoq
    )
    fcf = _derive_free_cash_flow_if_missing(ocf, capex, fcf_raw)

    if revenue.quality == SeriesQuality.EMPTY:
        warnings.append("No revenue history available for the selected period type.")
    if period_type == "quarterly" and revenue.quality == SeriesQuality.INCOMPLETE:
        warnings.append("Quarterly series is incomplete; same-quarter YoY comparisons may be limited.")

    currencies = {
        s.currency
        for s in (revenue, net_income, total_assets, ocf)
        if s.currency
    }
    if len(currencies) > 1:
        warnings.append(
            f"Multiple currencies observed in historical series: {', '.join(sorted(currencies))}."
        )

    return HistoricalPerformanceReport(
        symbol=company.symbol,
        period_type=period_type,
        revenue=revenue,
        gross_profit=gross_profit,
        operating_income=operating_income,
        net_income=net_income,
        eps=eps,
        gross_margin=gross_margin,
        operating_margin=operating_margin,
        net_margin=net_margin,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        total_debt=total_debt,
        equity=equity,
        current_assets=current_assets,
        current_liabilities=current_liabilities,
        working_capital=working_capital,
        operating_cash_flow=ocf,
        investing_cash_flow=investing,
        financing_cash_flow=financing,
        free_cash_flow=fcf,
        capital_expenditure=capex,
        cash_conversion=analyze_cash_conversion(ocf, fcf, net_income),
        profitability_insight=_profitability_insight(gross_margin, operating_margin, net_margin, net_income),
        balance_sheet_insight=_balance_sheet_insight(
            total_debt, equity, current_assets, current_liabilities, total_assets
        ),
        data_warnings=warnings,
    )
