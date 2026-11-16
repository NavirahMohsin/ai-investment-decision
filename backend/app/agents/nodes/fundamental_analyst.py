"""
Fundamental Analyst Agent Node.

Responsibilities:
- Retrieve company financial statements and fundamental information.
- Analyse key financial dimensions: profitability, growth, liquidity & leverage, valuation, cash flow quality.
- Review historical financial performance and multidimensional assessments.
- Retrieve overall transparent fundamental score (0-100) and dimension scoring.
- Identify core financial strengths and balance sheet weaknesses.
- Highlight missing financial reports and flag stale reporting periods (> 90 days).
- Reuse: fundamental_analysis.py, fundamental_scoring.py, financial_ratios.py, historical_performance.py.
- Constraint: Never invent ratios or financial data.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json
import logging
from typing import Any

from sqlalchemy import select

from app.db.models import Company, CompanyFinancial, CompanyFundamentalInfo
from app.agents.state import AgentName, GraphState
from app.agents.prompts import FUNDAMENTAL_ANALYST_SYSTEM
from app.agents.nodes.base import BaseAgentNode
from app.agents.dependencies import get_agent_db_session
from app.services.fundamental_analysis import analyze_fundamentals, FundamentalAnalysis
from app.services.fundamental_scoring import calculate_fundamental_score, FundamentalScoreResult
from app.services.financial_ratios import calculate_all_ratios

logger = logging.getLogger(__name__)


def _decimal_serializer(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)


class FundamentalAnalystNode(BaseAgentNode):
    agent_name = AgentName.FUNDAMENTAL_ANALYST
    system_prompt = FUNDAMENTAL_ANALYST_SYSTEM

    def _gather_data(self, state: GraphState) -> dict[str, Any]:
        tickers = state.get("tickers", [])
        data: dict[str, Any] = {
            "tickers": tickers,
            "fundamental_scores": {},
            "dimensions": {},
            "ratios": {},
            "strengths": {},
            "weaknesses": {},
            "freshness": {},
            "missing_information": [],
            "warnings": [],
            "evidence_sources": [
                "CompanyFinancial",
                "CompanyFundamentalInfo",
                "analyze_fundamentals",
                "calculate_fundamental_score",
                "calculate_all_ratios",
            ],
            "data_timestamps": {},
        }

        with get_agent_db_session() as db:
            for ticker in tickers:
                symbol = ticker.upper()
                company = db.scalar(
                    select(Company).where(
                        Company.symbol == symbol,
                        Company.is_active.is_(True),
                    )
                )
                if not company:
                    data["missing_information"].append(f"Company {symbol} not found or inactive in database.")
                    continue

                # Run fundamental analysis
                try:
                    analysis: FundamentalAnalysis = analyze_fundamentals(db, company)
                    
                    data["dimensions"][symbol] = {
                        "overall_classification": analysis.overall_classification.value,
                        "profitability": {
                            "classification": analysis.profitability.classification.value,
                            "reporting_period": analysis.profitability.reporting_period,
                            "data_freshness": analysis.profitability.data_freshness,
                            "explanation": analysis.profitability.explanation,
                            "metrics": [
                                {"key": m.key, "name": m.name, "value": float(m.value) if m.value is not None else None, "unit": m.unit}
                                for m in analysis.profitability.metrics_used
                            ],
                        },
                        "growth": {
                            "classification": analysis.growth.classification.value,
                            "reporting_period": analysis.growth.reporting_period,
                            "data_freshness": analysis.growth.data_freshness,
                            "explanation": analysis.growth.explanation,
                            "metrics": [
                                {"key": m.key, "name": m.name, "value": float(m.value) if m.value is not None else None, "unit": m.unit}
                                for m in analysis.growth.metrics_used
                            ],
                        },
                        "financial_stability": {
                            "classification": analysis.financial_stability.classification.value,
                            "reporting_period": analysis.financial_stability.reporting_period,
                            "data_freshness": analysis.financial_stability.data_freshness,
                            "explanation": analysis.financial_stability.explanation,
                            "metrics": [
                                {"key": m.key, "name": m.name, "value": float(m.value) if m.value is not None else None, "unit": m.unit}
                                for m in analysis.financial_stability.metrics_used
                            ],
                        },
                        "valuation": {
                            "classification": analysis.valuation.classification.value,
                            "reporting_period": analysis.valuation.reporting_period,
                            "data_freshness": analysis.valuation.data_freshness,
                            "explanation": analysis.valuation.explanation,
                            "metrics": [
                                {"key": m.key, "name": m.name, "value": float(m.value) if m.value is not None else None, "unit": m.unit}
                                for m in analysis.valuation.metrics_used
                            ],
                        },
                        "cash_flow_quality": {
                            "classification": analysis.cash_flow_quality.classification.value,
                            "reporting_period": analysis.cash_flow_quality.reporting_period,
                            "data_freshness": analysis.cash_flow_quality.data_freshness,
                            "explanation": analysis.cash_flow_quality.explanation,
                            "metrics": [
                                {"key": m.key, "name": m.name, "value": float(m.value) if m.value is not None else None, "unit": m.unit}
                                for m in analysis.cash_flow_quality.metrics_used
                            ],
                        },
                    }

                    data["strengths"][symbol] = analysis.positive_factors
                    data["weaknesses"][symbol] = analysis.negative_factors
                    if analysis.missing_data_warnings:
                        data["warnings"].extend([f"{symbol}: {w}" for w in analysis.missing_data_warnings])

                except Exception as e:
                    logger.warning("analyze_fundamentals failed for %s: %s", symbol, e)
                    data["warnings"].append(f"Fundamental analysis computation error for {symbol}: {e}")

                # Run fundamental scoring
                try:
                    score_res: FundamentalScoreResult = calculate_fundamental_score(db, company)
                    data["fundamental_scores"][symbol] = {
                        "score": float(score_res.score) if score_res.score is not None else None,
                        "classification": score_res.classification.value,
                        "data_completeness": float(score_res.data_completeness),
                        "metrics_evaluated": score_res.metrics_evaluated,
                        "dimensions_excluded": score_res.dimensions_excluded,
                        "dimension_scores": [
                            {
                                "dimension": ds.dimension,
                                "score": float(ds.score) if ds.score is not None else None,
                                "weight": float(ds.weight),
                                "included": ds.included,
                                "exclusion_reason": ds.exclusion_reason,
                            }
                            for ds in score_res.dimension_scores
                        ],
                        "major_contributors": score_res.major_contributors,
                        "missing_metrics": score_res.missing_metrics,
                    }
                    if score_res.missing_metrics:
                        data["missing_information"].extend([f"{symbol}: Missing metric {m}" for m in score_res.missing_metrics])
                except Exception as e:
                    logger.warning("calculate_fundamental_score failed for %s: %s", symbol, e)
                    data["warnings"].append(f"Fundamental score computation error for {symbol}: {e}")

                # Check freshness of underlying fundamental info
                info = db.scalar(
                    select(CompanyFundamentalInfo).where(
                        CompanyFundamentalInfo.company_id == company.id
                    )
                )
                if info and info.retrieved_at:
                    retrieved_date = info.retrieved_at.date() if isinstance(info.retrieved_at, datetime) else info.retrieved_at
                    days_old = (date.today() - retrieved_date).days
                    freshness = "FRESH" if days_old <= 30 else ("AGING" if days_old <= 90 else "STALE")
                    data["freshness"][symbol] = {
                        "retrieved_at": info.retrieved_at.isoformat(),
                        "days_old": days_old,
                        "freshness": freshness,
                    }
                    data["data_timestamps"][f"{symbol}_fundamentals"] = info.retrieved_at.isoformat()
                    if freshness == "STALE":
                        data["warnings"].append(
                            f"Fundamental data for {symbol} is {days_old} days old. Reporting period may be out of date."
                        )
                else:
                    data["missing_information"].append(f"No CompanyFundamentalInfo timestamp for {symbol}.")

        return data

    def _build_prompt(self, state: GraphState, data: dict[str, Any]) -> str:
        prompt_payload = {
            "user_request": state.get("user_request", ""),
            "tickers": data.get("tickers", []),
            "fundamental_scores": data.get("fundamental_scores", {}),
            "dimensions": data.get("dimensions", {}),
            "strengths": data.get("strengths", {}),
            "weaknesses": data.get("weaknesses", {}),
            "freshness": data.get("freshness", {}),
            "missing_information": data.get("missing_information", []),
            "warnings": data.get("warnings", []),
        }

        return (
            "Analyse the following real company fundamental metrics and score results, and produce "
            "a structured AgentResult JSON strictly matching the schema.\n\n"
            f"{json.dumps(prompt_payload, indent=2, default=_decimal_serializer)}\n\n"
            "Evaluate profitability, growth, liquidity, leverage, valuation, and cash flow. "
            "Identify key balance sheet strengths and weaknesses, highlight stale reporting periods, "
            "and clearly cite the verified fundamental score."
        )

    def _populate_result(
        self,
        result: Any,
        llm_response: str,
        data: dict[str, Any],
    ) -> None:
        super()._populate_result(result, llm_response, data)
        for s in data.get("evidence_sources", []):
            if s not in result.evidence_sources:
                result.evidence_sources.append(s)
        for k, v in data.get("data_timestamps", {}).items():
            result.data_timestamps[k] = v
        for miss in data.get("missing_information", []):
            if miss not in result.missing_information:
                result.missing_information.append(miss)
        for warn in data.get("warnings", []):
            if warn not in result.warnings:
                result.warnings.append(warn)

        if not isinstance(result.supporting_metrics, dict):
            result.supporting_metrics = {}
        result.supporting_metrics.setdefault("fundamental_scores", data.get("fundamental_scores", {}))
        result.supporting_metrics.setdefault("dimensions", data.get("dimensions", {}))


fundamental_analyst_node = FundamentalAnalystNode()
