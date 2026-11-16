"""
Risk Analyst Agent Node.

Responsibilities:
- Calculate historical annualized volatility deterministically from daily log returns.
- Calculate historical maximum drawdown and current drawdown from peak.
- Calculate ATR-based volatility and ATR as a percentage of current price.
- Measure recent downside movements (worst 1-day decline, negative day ratio, downside semi-deviation).
- Identify sector and concentration risks using verified company and sector data.
- Identify data gaps in historical price and fundamental records.
- Detect and explain risks associated with conflicting findings across specialist agents
  (e.g., Bullish technical trend vs Weak fundamental score, or Rising price vs Negative news sentiment).
- Constraint: Risk metrics must be calculated deterministically using verified data.
  The LLM may explain the metrics but must never invent or modify them.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json
import logging
import math
from typing import Any

import numpy as np
from sqlalchemy import select

from app.db.models import Company, DailyMarketData, Sector
from app.agents.state import AgentName, GraphState
from app.agents.prompts import RISK_ANALYST_SYSTEM
from app.agents.nodes.base import BaseAgentNode
from app.agents.dependencies import get_agent_db_session
from app.services.indicators import IndicatorParameters, calculate_indicators
from app.services.sector_intelligence import sector_intelligence

logger = logging.getLogger(__name__)


def _decimal_to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def calculate_deterministic_risk_metrics(rows: list[DailyMarketData]) -> dict[str, Any]:
    """
    Deterministically compute key investment risk metrics from historical daily bars.
    """
    if len(rows) < 2:
        return {
            "historical_volatility_annualized": None,
            "max_drawdown_pct": None,
            "current_drawdown_pct": None,
            "worst_daily_drop_pct": None,
            "negative_day_pct": None,
            "downside_semi_deviation_annualized": None,
            "data_points": len(rows),
        }

    prices = [_decimal_to_float(r.close) for r in rows if r.close is not None]
    prices = [p for p in prices if p is not None and p > 0]

    if len(prices) < 2:
        return {"data_points": len(prices)}

    p_arr = np.array(prices, dtype=float)
    daily_returns = np.diff(p_arr) / p_arr[:-1]
    log_returns = np.log(p_arr[1:] / p_arr[:-1])

    # 1. Historical annualized volatility
    vol_annual = float(np.std(log_returns, ddof=1) * math.sqrt(252) * 100.0) if len(log_returns) > 1 else 0.0

    # 2. Maximum drawdown
    cum_max = np.maximum.accumulate(p_arr)
    drawdowns = (p_arr - cum_max) / cum_max * 100.0
    max_drawdown = float(np.min(drawdowns))
    current_drawdown = float(drawdowns[-1])

    # 3. Downside movements & semi-deviation
    negative_returns = daily_returns[daily_returns < 0]
    worst_drop = float(np.min(daily_returns) * 100.0) if len(daily_returns) > 0 else 0.0
    neg_day_pct = float(len(negative_returns) / len(daily_returns) * 100.0) if len(daily_returns) > 0 else 0.0
    
    if len(negative_returns) > 0:
        semi_dev = float(math.sqrt(np.mean(negative_returns ** 2)) * math.sqrt(252) * 100.0)
    else:
        semi_dev = 0.0

    return {
        "historical_volatility_annualized": round(vol_annual, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "current_drawdown_pct": round(current_drawdown, 2),
        "worst_daily_drop_pct": round(worst_drop, 2),
        "negative_day_pct": round(neg_day_pct, 1),
        "downside_semi_deviation_annualized": round(semi_dev, 2),
        "data_points": len(prices),
    }


class RiskAnalystNode(BaseAgentNode):
    agent_name = AgentName.RISK_ANALYST
    system_prompt = RISK_ANALYST_SYSTEM

    def _gather_data(self, state: GraphState) -> dict[str, Any]:
        tickers = state.get("tickers", [])
        data: dict[str, Any] = {
            "tickers": tickers,
            "risk_metrics": {},
            "atr_volatility": {},
            "sector_risks": {},
            "cross_agent_conflicts": {},
            "missing_information": [],
            "warnings": [],
            "evidence_sources": [
                "DailyMarketData",
                "calculate_deterministic_risk_metrics",
                "calculate_indicators",
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

                # Fetch market data up to 252 bars
                rows = list(
                    db.scalars(
                        select(DailyMarketData)
                        .where(DailyMarketData.company_id == company.id)
                        .order_by(DailyMarketData.trading_date)
                    )
                )

                if len(rows) < 2:
                    data["missing_information"].append(
                        f"Insufficient price history for {symbol} to calculate historical risk metrics."
                    )
                    continue

                latest = rows[-1]
                data["data_timestamps"][f"{symbol}_risk_market_data"] = latest.trading_date.isoformat()

                # Deterministic risk metrics
                risk_calcs = calculate_deterministic_risk_metrics(rows)
                data["risk_metrics"][symbol] = risk_calcs

                if risk_calcs.get("data_points", 0) < 50:
                    data["warnings"].append(
                        f"Short price history for {symbol} ({risk_calcs.get('data_points')} bars). Risk estimates may understate tail events."
                    )

                # ATR-based volatility
                try:
                    params = IndicatorParameters()
                    records, _, _, _ = calculate_indicators(rows, params)
                    if records and records[-1].get("atr") is not None:
                        latest_rec = records[-1]
                        atr_val = latest_rec.get("atr")
                        close_val = latest_rec.get("close")
                        atr_pct = (atr_val / close_val * 100.0) if (atr_val and close_val) else None
                        data["atr_volatility"][symbol] = {
                            "atr_14": round(atr_val, 2) if atr_val else None,
                            "atr_pct_of_price": round(atr_pct, 2) if atr_pct else None,
                        }
                except Exception as e:
                    logger.warning("ATR risk calculation failed for %s: %s", symbol, e)

                # Sector risks & peer concentration
                if company.sector_id:
                    sector = db.get(Sector, company.sector_id)
                    if sector:
                        data["evidence_sources"].append("Sector")
                        data["sector_risks"][symbol] = {
                            "sector_name": sector.sector_name,
                            "industry_name": sector.industry_name,
                        }
                        try:
                            s_intel = sector_intelligence(db, sector.sector_name, limit=10)
                            data["sector_risks"][symbol]["average_fundamental_score"] = _decimal_to_float(
                                s_intel.get("average_fundamental_score")
                            )
                            data["sector_risks"][symbol]["tracked_peer_count"] = s_intel.get("tracked_company_count")
                        except Exception:
                            pass

        # -------------------------------------------------------------
        # Cross-Agent Conflict Analysis
        # -------------------------------------------------------------
        agent_results = state.get("agent_results", {})
        conflicts = []

        m_res = agent_results.get("market_analyst", {})
        f_res = agent_results.get("fundamental_analyst", {})
        n_res = agent_results.get("news_analyst", {})

        m_trend = m_res.get("supporting_metrics", {}).get("trend_analysis", {})
        f_scores = f_res.get("supporting_metrics", {}).get("fundamental_scores", {})
        n_sent = n_res.get("supporting_metrics", {}).get("sentiment_aggregation", {})

        for ticker in tickers:
            sym = ticker.upper()
            t_trend = m_trend.get(sym, {}).get("classification")
            f_class = f_scores.get(sym, {}).get("classification")
            s_trend = n_sent.get(sym, {}).get("sentiment_trend")

            # Technical vs Fundamental conflict
            if t_trend in ("STRONG_BULLISH", "BULLISH") and f_class in ("WEAK", "MODERATE"):
                conflicts.append(
                    f"{sym}: Technical trend is {t_trend} despite {f_class} fundamental classification. "
                    "Indicates speculative momentum unsupported by underlying financial strength."
                )
            elif t_trend in ("STRONG_BEARISH", "BEARISH") and f_class in ("STRONG", "HEALTHY"):
                conflicts.append(
                    f"{sym}: Technical trend is {t_trend} while fundamentals are classified as {f_class}. "
                    "Suggests broad market pessimism or an unrecognised value divergence."
                )

            # Technical vs News conflict
            if t_trend in ("STRONG_BULLISH", "BULLISH") and s_trend == "negative":
                conflicts.append(
                    f"{sym}: Bullish price action conflicts with negative news sentiment. "
                    "Heightened vulnerability to adverse headline reactions."
                )

        data["cross_agent_conflicts"] = conflicts
        if conflicts:
            data["warnings"].extend(conflicts)

        return data

    def _build_prompt(self, state: GraphState, data: dict[str, Any]) -> str:
        prompt_payload = {
            "user_request": state.get("user_request", ""),
            "tickers": data.get("tickers", []),
            "deterministic_risk_metrics": data.get("risk_metrics", {}),
            "atr_volatility": data.get("atr_volatility", {}),
            "sector_risks": data.get("sector_risks", {}),
            "cross_agent_conflicts": data.get("cross_agent_conflicts", []),
            "missing_information": data.get("missing_information", []),
            "warnings": data.get("warnings", []),
        }

        return (
            "Analyse the following deterministically calculated risk metrics and produce a "
            "structured AgentResult JSON strictly matching the schema.\n\n"
            f"{json.dumps(prompt_payload, indent=2, default=str)}\n\n"
            "Explain historical volatility, max drawdown, ATR volatility as % of price, downside risks, "
            "and any cross-agent contradictions between technicals, fundamentals, and news sentiment. "
            "Never invent or alter numeric values."
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
        result.supporting_metrics.setdefault("risk_metrics", data.get("risk_metrics", {}))
        result.supporting_metrics.setdefault("atr_volatility", data.get("atr_volatility", {}))
        result.supporting_metrics.setdefault("cross_agent_conflicts", data.get("cross_agent_conflicts", []))


risk_analyst_node = RiskAnalystNode()
