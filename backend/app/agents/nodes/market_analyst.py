"""
Market Analyst Agent Node.

Responsibilities:
- Retrieve historical stock market data (DailyMarketData).
- Analyse recent price movements (price, change, percentage change, volume).
- Compute and evaluate technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands, ATR, VWAP, ADX).
- Generate rule-based technical signals using existing signals service.
- Classify technical trend (Strong Bullish, Bullish, Neutral, Bearish, Strong Bearish).
- Examine sector and market context where data permits.
- Highlight data freshness and flag insufficient historical data.
- Strict constraint: Never invent prices or claim delayed data is real-time.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json
import logging
from typing import Any

from sqlalchemy import desc, select

from app.db.models import Company, DailyMarketData, Sector
from app.agents.state import AgentName, GraphState
from app.agents.prompts import MARKET_ANALYST_SYSTEM
from app.agents.nodes.base import BaseAgentNode
from app.agents.dependencies import get_agent_db_session
from app.services.indicators import IndicatorParameters, calculate_indicators
from app.services.signals import classify_trend, generate_signals

logger = logging.getLogger(__name__)


def _decimal_to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


class MarketAnalystNode(BaseAgentNode):
    agent_name = AgentName.MARKET_ANALYST
    system_prompt = MARKET_ANALYST_SYSTEM

    def _gather_data(self, state: GraphState) -> dict[str, Any]:
        tickers = state.get("tickers", [])
        data: dict[str, Any] = {
            "tickers": tickers,
            "market_summary": {},
            "technical_indicators": {},
            "technical_signals": {},
            "trend_analysis": {},
            "sector_context": {},
            "freshness": {},
            "missing_information": [],
            "warnings": [],
            "evidence_sources": [
                "DailyMarketData",
                "calculate_indicators",
                "generate_signals",
                "classify_trend",
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

                # Retrieve historical rows
                rows = list(
                    db.scalars(
                        select(DailyMarketData)
                        .where(DailyMarketData.company_id == company.id)
                        .order_by(DailyMarketData.trading_date)
                    )
                )

                if len(rows) < 2:
                    data["missing_information"].append(
                        f"Insufficient historical market data for {symbol} (found {len(rows)} record(s), need at least 2)."
                    )
                    data["warnings"].append(
                        f"Technical indicator calculation for {symbol} withheld due to lack of historical data."
                    )
                    continue

                latest = rows[-1]
                prev = rows[-2] if len(rows) >= 2 else None

                latest_close = _decimal_to_float(latest.close)
                prev_close = _decimal_to_float(prev.close) if prev else None
                abs_change = latest_close - prev_close if (latest_close is not None and prev_close is not None) else None
                pct_change = (abs_change / prev_close * 100.0) if (abs_change is not None and prev_close) else None

                # Calculate data freshness
                last_date: date = latest.trading_date
                days_old = (date.today() - last_date).days
                freshness_status = "FRESH" if days_old <= 3 else ("DELAYED" if days_old <= 7 else "STALE")

                data["data_timestamps"][f"{symbol}_market_data"] = last_date.isoformat()
                data["freshness"][symbol] = {
                    "as_of_date": last_date.isoformat(),
                    "days_old": days_old,
                    "status": freshness_status,
                    "provider": latest.provider or "yahoo_finance",
                }

                if freshness_status == "STALE":
                    data["warnings"].append(
                        f"Market data for {symbol} is {days_old} days old (as of {last_date.isoformat()}). Historical analysis only."
                    )

                # Price action summary
                data["market_summary"][symbol] = {
                    "company_name": company.name,
                    "exchange": company.exchange,
                    "latest_close": latest_close,
                    "previous_close": prev_close,
                    "open": _decimal_to_float(latest.open),
                    "day_high": _decimal_to_float(latest.high),
                    "day_low": _decimal_to_float(latest.low),
                    "volume": latest.volume,
                    "absolute_change": round(abs_change, 2) if abs_change is not None else None,
                    "percentage_change": round(pct_change, 2) if pct_change is not None else None,
                    "total_historical_bars": len(rows),
                }

                # Calculate technical indicators
                params = IndicatorParameters()
                try:
                    records, available_count, first_d, last_d = calculate_indicators(rows, params)
                    if records:
                        rec = records[-1]
                        data["technical_indicators"][symbol] = {
                            "sma_20": rec.get("sma"),
                            "ema_20": rec.get("ema"),
                            "rsi_14": rec.get("rsi"),
                            "macd": rec.get("macd"),
                            "macd_signal": rec.get("macd_signal"),
                            "macd_histogram": rec.get("macd_histogram"),
                            "bollinger_upper": rec.get("bollinger_upper"),
                            "bollinger_middle": rec.get("bollinger_middle"),
                            "bollinger_lower": rec.get("bollinger_lower"),
                            "atr_14": rec.get("atr"),
                            "vwap": rec.get("vwap"),
                            "adx": rec.get("adx"),
                        }

                        # Trend classification
                        if latest_close is not None:
                            trend_analysis = classify_trend(
                                current_price=latest_close,
                                ema=rec.get("ema"),
                                rsi=rec.get("rsi"),
                                adx=rec.get("adx"),
                                macd_histogram=rec.get("macd_histogram"),
                            )
                            data["trend_analysis"][symbol] = {
                                "classification": trend_analysis.classification,
                                "explanation": trend_analysis.explanation,
                            }
                except Exception as e:
                    logger.warning("Indicator calculation failed for %s: %s", symbol, e)
                    data["warnings"].append(f"Technical indicators calculation error for {symbol}: {e}")

                # Rule-based technical signals
                try:
                    signals = generate_signals(rows, params)
                    data["technical_signals"][symbol] = [
                        {
                            "signal_type": s.signal_type,
                            "timestamp": s.timestamp.isoformat(),
                            "price": s.price,
                            "explanation": s.explanation,
                            "strength": s.strength,
                            "indicator_values": s.indicator_values,
                        }
                        for s in signals[-10:]  # last 10 generated signals
                    ]
                except Exception as e:
                    logger.warning("Signals generation failed for %s: %s", symbol, e)
                    data["technical_signals"][symbol] = []

                # Sector context
                if company.sector_id:
                    sector = db.get(Sector, company.sector_id)
                    if sector:
                        data["sector_context"][symbol] = {
                            "sector_name": sector.sector_name,
                            "industry_name": sector.industry_name,
                        }

        return data

    def _build_prompt(self, state: GraphState, data: dict[str, Any]) -> str:
        prompt_payload = {
            "user_request": state.get("user_request", ""),
            "tickers": data.get("tickers", []),
            "market_summary": data.get("market_summary", {}),
            "freshness": data.get("freshness", {}),
            "trend_analysis": data.get("trend_analysis", {}),
            "technical_indicators": data.get("technical_indicators", {}),
            "recent_technical_signals": data.get("technical_signals", {}),
            "sector_context": data.get("sector_context", {}),
            "missing_information": data.get("missing_information", []),
            "warnings": data.get("warnings", []),
        }

        return (
            "Analyse the following real technical market data and produce a structured "
            "financial analysis JSON strictly matching the requested AgentResult schema.\n\n"
            f"{json.dumps(prompt_payload, indent=2, default=str)}\n\n"
            "Highlight price trends, key moving averages, RSI/MACD signals, ADX strength, "
            "data freshness, and note any missing data."
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
        result.supporting_metrics.setdefault("market_summary", data.get("market_summary", {}))
        result.supporting_metrics.setdefault("technical_indicators", data.get("technical_indicators", {}))
        result.supporting_metrics.setdefault("trend_analysis", data.get("trend_analysis", {}))


market_analyst_node = MarketAnalystNode()
