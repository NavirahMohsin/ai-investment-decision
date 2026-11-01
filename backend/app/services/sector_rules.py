"""Sector-aware evaluation rules for fundamental analysis.

Yahoo Finance sector/industry labels are used when available. When a company
cannot be mapped to a calibrated sector profile, the GENERAL methodology is
applied and clearly labelled — it is not presented as sector-calibrated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SectorProfile(StrEnum):
    BANKING = "BANKING"
    FINANCIAL_SERVICES = "FINANCIAL_SERVICES"
    IT = "IT"
    MANUFACTURING = "MANUFACTURING"
    ENERGY = "ENERGY"
    FMCG = "FMCG"
    PHARMACEUTICALS = "PHARMACEUTICALS"
    GENERAL = "GENERAL"


@dataclass(frozen=True)
class SectorRules:
    profile: SectorProfile
    label: str
    # Metrics that are typically not meaningful for this sector
    excluded_metrics: frozenset[str] = field(default_factory=frozenset)
    # Notes shown in assessments
    methodology_notes: tuple[str, ...] = ()
    # Soft threshold overrides (classification helpers use these)
    debt_to_equity_elevated: float = 1.5
    debt_to_equity_high: float = 2.5
    current_ratio_concern: float = 1.0
    interest_coverage_weak: float = 2.0
    use_current_ratio: bool = True
    use_inventory_turnover: bool = True
    use_ev_ebitda: bool = True


BANKING_RULES = SectorRules(
    profile=SectorProfile.BANKING,
    label="Banking (sector-aware)",
    excluded_metrics=frozenset({
        "current_ratio",
        "quick_ratio",
        "inventory_turnover",
        "debt_to_equity",  # regulatory capital preferred; D/E misleading for banks
        "working_capital",
    }),
    methodology_notes=(
        "Debt-to-equity and current ratio are not applied using industrial thresholds for banks.",
        "Stability emphasises leverage context and cash-flow quality rather than working-capital ratios.",
    ),
    debt_to_equity_elevated=8.0,
    debt_to_equity_high=15.0,
    use_current_ratio=False,
    use_inventory_turnover=False,
    use_ev_ebitda=False,
)

FINANCIAL_RULES = SectorRules(
    profile=SectorProfile.FINANCIAL_SERVICES,
    label="Financial services (sector-aware)",
    excluded_metrics=frozenset({
        "current_ratio",
        "quick_ratio",
        "inventory_turnover",
    }),
    methodology_notes=(
        "Liquidity ratios designed for industrial firms are de-emphasised for financial services.",
    ),
    debt_to_equity_elevated=3.0,
    debt_to_equity_high=5.0,
    use_current_ratio=False,
    use_inventory_turnover=False,
    use_ev_ebitda=True,
)

IT_RULES = SectorRules(
    profile=SectorProfile.IT,
    label="Information technology (sector-aware)",
    excluded_metrics=frozenset({"inventory_turnover"}),
    methodology_notes=(
        "Inventory turnover is generally not applicable for asset-light IT/services companies.",
    ),
    debt_to_equity_elevated=0.8,
    debt_to_equity_high=1.5,
    use_inventory_turnover=False,
)

MANUFACTURING_RULES = SectorRules(
    profile=SectorProfile.MANUFACTURING,
    label="Manufacturing (sector-aware)",
    methodology_notes=("Standard industrial ratio interpretation applied.",),
)

ENERGY_RULES = SectorRules(
    profile=SectorProfile.ENERGY,
    label="Energy (sector-aware)",
    methodology_notes=(
        "Energy firms often carry project-related leverage; absolute debt levels are interpreted cautiously.",
    ),
    debt_to_equity_elevated=1.8,
    debt_to_equity_high=3.0,
)

FMCG_RULES = SectorRules(
    profile=SectorProfile.FMCG,
    label="FMCG (sector-aware)",
    methodology_notes=("Working-capital and margin consistency are emphasised for FMCG.",),
    debt_to_equity_elevated=1.0,
    debt_to_equity_high=2.0,
)

PHARMA_RULES = SectorRules(
    profile=SectorProfile.PHARMACEUTICALS,
    label="Pharmaceuticals (sector-aware)",
    methodology_notes=("R&D intensity can compress near-term margins; growth consistency is weighted carefully.",),
)

GENERAL_RULES = SectorRules(
    profile=SectorProfile.GENERAL,
    label="General (not sector-calibrated)",
    methodology_notes=(
        "No reliable sector-specific calibration was available for this company; general thresholds are used.",
    ),
)


_SECTOR_KEYWORDS: list[tuple[tuple[str, ...], SectorRules]] = [
    (("bank", "banks", "banking"), BANKING_RULES),
    (("financial services", "capital markets", "insurance", "nbfc", "asset management"), FINANCIAL_RULES),
    (("information technology", "software", "it services", "technology"), IT_RULES),
    (("consumer defensive", "fmcg", "packaged foods", "beverages", "household"), FMCG_RULES),
    (("drug manufacturers", "pharmaceutical", "biotechnology", "healthcare"), PHARMA_RULES),
    (("oil", "gas", "energy", "utilities"), ENERGY_RULES),
    (("manufacturing", "industrials", "industrial", "auto", "cement", "steel", "metals"), MANUFACTURING_RULES),
]


def resolve_sector_rules(sector: str | None, industry: str | None = None) -> SectorRules:
    """Map Yahoo Finance sector/industry text to a sector rule profile."""
    blob = f"{sector or ''} {industry or ''}".strip().lower()
    if not blob:
        return GENERAL_RULES
    for keywords, rules in _SECTOR_KEYWORDS:
        if any(k in blob for k in keywords):
            return rules
    return GENERAL_RULES


def metric_applicable(rules: SectorRules, metric_key: str) -> bool:
    return metric_key not in rules.excluded_metrics
