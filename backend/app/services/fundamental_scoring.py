"""Transparent 0–100 fundamental score with fixed dimension weights.

Weights are not silently redistributed when dimensions are missing.
If minimum data requirements are not met, score is withheld (INSUFFICIENT_DATA).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import Company
from app.services.fundamental_analysis import (
    Classification,
    DimensionAssessment,
    FundamentalAnalysis,
    analyze_fundamentals,
)


SCORING_VERSION = "fundamental-score-v1"

# Documented final weights (must sum to 1.0)
DIMENSION_WEIGHTS: dict[str, Decimal] = {
    "profitability": Decimal("0.25"),
    "growth": Decimal("0.20"),
    "financial_stability": Decimal("0.25"),
    "valuation": Decimal("0.15"),
    "cash_flow_quality": Decimal("0.15"),
}

# Minimum dimensions with non-INSUFFICIENT classifications before a score is issued
MIN_DIMENSIONS_REQUIRED = 3

# Valuation is contextual — cap its contribution so a "cheap" multiple cannot dominate
CLASSIFICATION_TO_SCORE: dict[Classification, Decimal | None] = {
    Classification.STRONG: Decimal("90"),
    Classification.HEALTHY: Decimal("75"),
    Classification.MODERATE: Decimal("55"),
    Classification.WEAK: Decimal("30"),
    Classification.INSUFFICIENT_DATA: None,
}


@dataclass
class DimensionScore:
    dimension: str
    score: Decimal | None
    weight: Decimal
    included: bool
    exclusion_reason: str | None = None
    explanation: str | None = None


@dataclass
class FundamentalScoreResult:
    symbol: str
    score: Decimal | None
    classification: Classification
    data_completeness: Decimal
    metrics_evaluated: int
    dimensions_excluded: list[str] = field(default_factory=list)
    dimension_scores: list[DimensionScore] = field(default_factory=list)
    major_contributors: list[str] = field(default_factory=list)
    missing_metrics: list[str] = field(default_factory=list)
    methodology_version: str = SCORING_VERSION
    explanation: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _dimension_map(analysis: FundamentalAnalysis) -> dict[str, DimensionAssessment]:
    return {
        "profitability": analysis.profitability,
        "growth": analysis.growth,
        "financial_stability": analysis.financial_stability,
        "valuation": analysis.valuation,
        "cash_flow_quality": analysis.cash_flow_quality,
    }


def score_from_analysis(analysis: FundamentalAnalysis) -> FundamentalScoreResult:
    """Compute score from an existing analysis object (no extra DB work)."""
    dims = _dimension_map(analysis)
    dimension_scores: list[DimensionScore] = []
    excluded: list[str] = []
    missing_metrics: list[str] = []
    metrics_evaluated = 0
    weighted_sum = Decimal("0")
    included_weight = Decimal("0")
    contributors: list[tuple[str, Decimal]] = []

    for key, weight in DIMENSION_WEIGHTS.items():
        assessment = dims[key]
        metrics_evaluated += sum(1 for m in assessment.metrics_used if m.value is not None and m.applicable)
        missing_metrics.extend(assessment.missing_information)
        raw = CLASSIFICATION_TO_SCORE[assessment.classification]
        if raw is None:
            excluded.append(key)
            dimension_scores.append(
                DimensionScore(
                    dimension=key,
                    score=None,
                    weight=weight,
                    included=False,
                    exclusion_reason="INSUFFICIENT_DATA — weight not redistributed",
                    explanation=assessment.explanation,
                )
            )
            continue
        dimension_scores.append(
            DimensionScore(
                dimension=key,
                score=raw,
                weight=weight,
                included=True,
                explanation=f"{assessment.classification.value} → dimension score {raw}",
            )
        )
        weighted_sum += raw * weight
        included_weight += weight
        contributors.append((key, raw * weight))

    # Completeness = included weight / total weight (fixed denominator — no silent redistribution)
    total_weight = sum(DIMENSION_WEIGHTS.values())
    data_completeness = (included_weight / total_weight * Decimal("100")).quantize(Decimal("0.01"))

    included_count = sum(1 for d in dimension_scores if d.included)
    if included_count < MIN_DIMENSIONS_REQUIRED:
        return FundamentalScoreResult(
            symbol=analysis.symbol,
            score=None,
            classification=Classification.INSUFFICIENT_DATA,
            data_completeness=data_completeness,
            metrics_evaluated=metrics_evaluated,
            dimensions_excluded=excluded,
            dimension_scores=dimension_scores,
            major_contributors=[],
            missing_metrics=list(dict.fromkeys(missing_metrics))[:20],
            methodology_version=SCORING_VERSION,
            explanation=(
                f"Score withheld: only {included_count} of {MIN_DIMENSIONS_REQUIRED} required dimensions "
                f"have sufficient data. Dimension weights were not redistributed. "
                f"Completeness={data_completeness}% of weighted coverage. "
                f"Methodology {SCORING_VERSION}; weights: "
                + ", ".join(f"{k}={v}" for k, v in DIMENSION_WEIGHTS.items())
            ),
            generated_at=datetime.now(timezone.utc),
        )

    # Score uses only included dimensions' weighted points over FULL weight base
    # so incomplete companies cannot appear stronger via redistribution.
    score = (weighted_sum / total_weight).quantize(Decimal("0.01"))

    if score >= Decimal("80"):
        overall = Classification.STRONG
    elif score >= Decimal("65"):
        overall = Classification.HEALTHY
    elif score >= Decimal("45"):
        overall = Classification.MODERATE
    else:
        overall = Classification.WEAK

    contributors.sort(key=lambda x: x[1], reverse=True)
    major = [f"{name} contributed {contrib:.2f} weighted points" for name, contrib in contributors[:3]]

    explanation = (
        f"Fundamental score {score}/100 ({overall.value}) using methodology {SCORING_VERSION}. "
        f"Weights — profitability 25%, growth 20%, financial stability 25%, valuation 15%, "
        f"cash-flow quality 15%. Included dimensions: {included_count}/5 "
        f"(completeness {data_completeness}%). "
        f"Excluded dimensions retain zero contribution without weight redistribution. "
        "A high score is not a guarantee of investment performance."
    )

    return FundamentalScoreResult(
        symbol=analysis.symbol,
        score=score,
        classification=overall,
        data_completeness=data_completeness,
        metrics_evaluated=metrics_evaluated,
        dimensions_excluded=excluded,
        dimension_scores=dimension_scores,
        major_contributors=major,
        missing_metrics=list(dict.fromkeys(missing_metrics))[:20],
        methodology_version=SCORING_VERSION,
        explanation=explanation,
        generated_at=datetime.now(timezone.utc),
    )


def calculate_fundamental_score(
    db: Session,
    company: Company,
    current_price: Decimal | None = None,
    market_cap: Decimal | None = None,
    analysis: FundamentalAnalysis | None = None,
) -> FundamentalScoreResult:
    """Calculate fundamental score, optionally reusing an existing analysis."""
    if analysis is None:
        analysis = analyze_fundamentals(
            db, company, current_price=current_price, market_cap=market_cap
        )
    return score_from_analysis(analysis)
