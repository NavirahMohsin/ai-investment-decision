"""Unified Stock Intelligence API route.

Aggregates market data, technical signals, fundamentals, news, ML predictions,
risk metrics, and optional research insights into one consolidated response.
Each section is isolated so a single failure never breaks the whole payload.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import (
    Company,
    DailyMarketData,
    CompanyFinancial,
    CompanyFundamentalInfo,
    NewsArticle,
    NewsArticleCompany,
    NewsSource,
    ResearchReport,
)
from app.schemas.intelligence import UnifiedStockIntelligenceResponse
from app.services.indicators import IndicatorParameters, calculate_indicators
from app.services.signals import classify_trend, generate_signals

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])

DISCLAIMER = (
    "This report is generated for informational purposes only and does not "
    "constitute investment advice. Past performance is not indicative of future "
    "results. All financial data is sourced from the ArthAI database and may not "
    "reflect the most recent corporate disclosures."
)


def _safe_float(val: Any) -> float | None:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _unavailable(reason: str) -> dict[str, Any]:
    return {"status": "unavailable", "reason": reason}


@router.get("/{symbol}", response_model=UnifiedStockIntelligenceResponse)
async def get_unified_stock_intelligence(
    symbol: str,
    db: Session = Depends(get_db),
) -> dict:
    """Return consolidated stock intelligence for a given symbol."""
    sym = symbol.strip().upper()
    if not sym or len(sym) > 50:
        raise HTTPException(status_code=422, detail="Invalid symbol")

    company = db.query(Company).filter(Company.symbol == sym).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{sym}' not found")

    warnings: list[str] = []
    result: dict[str, Any] = {
        "symbol": sym,
        "company_name": company.name,
        "sector": company.sector,
        "industry": company.industry,
        "exchange": company.exchange,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": DISCLAIMER,
        "warnings": warnings,
    }

    # ── Market data ──────────────────────────────────────────────────────────
    try:
        rows = (
            db.query(DailyMarketData)
            .filter(DailyMarketData.company_id == company.id)
            .order_by(DailyMarketData.trading_date.desc())
            .limit(252)
            .all()
        )
        rows = list(reversed(rows))
        if rows:
            latest = rows[-1]
            prev = rows[-2] if len(rows) >= 2 else None
            close_prices = [_safe_float(r.close) for r in rows if r.close is not None]

            day_change = None
            day_change_pct = None
            if prev and prev.close and latest.close:
                day_change = float(latest.close) - float(prev.close)
                day_change_pct = day_change / float(prev.close) * 100

            w52_high = max(close_prices) if close_prices else None
            w52_low = min(close_prices) if close_prices else None

            # Freshness based on trading date age (daily bars)
            as_of = latest.trading_date
            age_days = (datetime.now(timezone.utc).date() - as_of).days
            if age_days <= 1:
                freshness = "fresh"
            elif age_days <= 5:
                freshness = "delayed"
            else:
                freshness = "stale"
                warnings.append(f"Market data last bar is {age_days} days old")

            result["market_intelligence"] = {
                "status": "available",
                "current_price": _safe_float(latest.close),
                "open": _safe_float(latest.open),
                "high": _safe_float(latest.high),
                "low": _safe_float(latest.low),
                "volume": int(latest.volume) if latest.volume else None,
                "day_change": round(day_change, 2) if day_change is not None else None,
                "day_change_pct": round(day_change_pct, 2) if day_change_pct is not None else None,
                "52w_high": round(w52_high, 2) if w52_high else None,
                "52w_low": round(w52_low, 2) if w52_low else None,
                "as_of_date": as_of.isoformat(),
                "data_points": len(rows),
                "freshness": freshness,
                "source": latest.provider or "database",
            }
        else:
            result["market_intelligence"] = _unavailable("No market data in database")
            warnings.append("Market data unavailable")
    except Exception as exc:
        logger.warning("Market data fetch failed for %s: %s", sym, exc)
        result["market_intelligence"] = _unavailable(str(exc))
        warnings.append("Market data service failed")

    # ── Technical signals ────────────────────────────────────────────────────
    try:
        rows_tech = (
            db.query(DailyMarketData)
            .filter(DailyMarketData.company_id == company.id)
            .order_by(DailyMarketData.trading_date.desc())
            .limit(300)
            .all()
        )
        rows_tech = list(reversed(rows_tech))
        if len(rows_tech) >= 30:
            params = IndicatorParameters()
            records, _, _, _ = calculate_indicators(rows_tech, params)
            latest_rec = records[-1] if records else {}

            closes = pd.Series(
                [_safe_float(r.close) for r in rows_tech], dtype=float
            ).dropna()
            highs = pd.Series([_safe_float(r.high) for r in rows_tech], dtype=float).dropna()
            lows = pd.Series([_safe_float(r.low) for r in rows_tech], dtype=float).dropna()

            prev_close = closes.shift(1)
            tr = pd.concat(
                [highs - lows, (highs - prev_close).abs(), (lows - prev_close).abs()],
                axis=1,
            ).max(axis=1)
            atr14 = float(tr.rolling(14).mean().iloc[-1]) if len(tr) >= 14 else None
            log_returns = np.log(closes / closes.shift(1)).dropna()
            ann_vol = float(log_returns.std() * np.sqrt(252)) if len(log_returns) >= 20 else None
            cummax = closes.cummax()
            drawdown = (closes - cummax) / cummax
            max_dd = float(drawdown.min()) if not drawdown.empty else None

            trend_payload = None
            if latest_rec.get("close") is not None:
                trend = classify_trend(
                    current_price=float(latest_rec["close"]),
                    ema=latest_rec.get("ema"),
                    rsi=latest_rec.get("rsi"),
                    adx=latest_rec.get("adx"),
                    macd_histogram=latest_rec.get("macd_histogram"),
                )
                trend_payload = {
                    "classification": trend.classification,
                    "explanation": trend.explanation,
                }

            signals = []
            try:
                raw_signals = generate_signals(rows_tech, params)
                signals = [
                    {
                        "signal_type": s.signal_type,
                        "timestamp": s.timestamp.isoformat(),
                        "price": s.price,
                        "explanation": s.explanation,
                        "strength": s.strength,
                    }
                    for s in raw_signals[-10:]
                ]
            except Exception as sig_exc:
                logger.debug("Signal generation partial failure for %s: %s", sym, sig_exc)

            result["technical_intelligence"] = {
                "status": "available",
                "rsi_14": _safe_float(latest_rec.get("rsi")),
                "ema_20": _safe_float(latest_rec.get("ema")),
                "ema_50": None,
                "macd": _safe_float(latest_rec.get("macd")),
                "macd_signal": _safe_float(latest_rec.get("macd_signal")),
                "bb_upper": _safe_float(latest_rec.get("bollinger_upper")),
                "bb_lower": _safe_float(latest_rec.get("bollinger_lower")),
                "atr_14": round(atr14, 4) if atr14 else None,
                "annualized_volatility_pct": round(ann_vol * 100, 2) if ann_vol else None,
                "max_drawdown_pct": round(max_dd * 100, 2) if max_dd is not None else None,
                "data_window_days": len(rows_tech),
                "signals": signals,
                "trend": trend_payload,
                "source": "indicators+signals",
            }
        else:
            result["technical_intelligence"] = _unavailable(
                "Insufficient price history (<30 bars)"
            )
            warnings.append("Technical analysis unavailable")
    except Exception as exc:
        logger.warning("Technical analysis failed for %s: %s", sym, exc)
        result["technical_intelligence"] = _unavailable(str(exc))
        warnings.append("Technical analysis service failed")

    # ── Fundamental intelligence ─────────────────────────────────────────────
    try:
        fin = (
            db.query(CompanyFinancial)
            .filter(CompanyFinancial.company_id == company.id)
            .order_by(CompanyFinancial.period_end.desc())
            .first()
        )
        fund_info = (
            db.query(CompanyFundamentalInfo)
            .filter(CompanyFundamentalInfo.company_id == company.id)
            .first()
        )
        if fin or fund_info:
            fd: dict[str, Any] = {"status": "available", "source": "database"}
            if fin:
                fd["period_end"] = fin.period_end.isoformat() if fin.period_end else None
                fd["revenue"] = _safe_float(fin.revenue)
                fd["net_income"] = _safe_float(fin.net_income)
                fd["ebitda"] = _safe_float(fin.ebitda)
                fd["total_assets"] = _safe_float(fin.total_assets)
                fd["total_equity"] = _safe_float(fin.total_equity)
                fd["total_debt"] = _safe_float(fin.total_debt)
                fd["operating_cash_flow"] = _safe_float(fin.operating_cash_flow)
                fd["free_cash_flow"] = _safe_float(fin.free_cash_flow)
                fd["roe"] = _safe_float(fin.roe)
                fd["roa"] = _safe_float(fin.roa)
                fd["profit_margin"] = _safe_float(fin.profit_margin)
                fd["debt_to_equity"] = _safe_float(fin.debt_to_equity)
                fd["current_ratio"] = _safe_float(fin.current_ratio)
                fd["pe_ratio"] = _safe_float(fin.pe_ratio)
            if fund_info:
                fd["market_cap"] = _safe_float(fund_info.market_cap)
                fd["book_value_per_share"] = _safe_float(fund_info.book_value_per_share)
                fd["dividend_yield"] = _safe_float(fund_info.dividend_yield)
            result["fundamental_intelligence"] = fd
        else:
            result["fundamental_intelligence"] = _unavailable(
                "No fundamental data in database"
            )
            warnings.append("Fundamentals unavailable")
    except Exception as exc:
        logger.warning("Fundamental data fetch failed for %s: %s", sym, exc)
        result["fundamental_intelligence"] = _unavailable(str(exc))
        warnings.append("Fundamentals service failed")

    # ── News & sentiment ─────────────────────────────────────────────────────
    try:
        rows_news = (
            db.query(NewsArticle, NewsSource)
            .join(NewsArticleCompany, NewsArticleCompany.article_id == NewsArticle.id)
            .join(NewsSource, NewsSource.id == NewsArticle.source_id)
            .filter(NewsArticleCompany.company_id == company.id)
            .order_by(NewsArticle.published_at.desc())
            .limit(10)
            .all()
        )

        if rows_news:
            def _label_from_score(score: Any) -> str:
                if score is None:
                    return "neutral"
                try:
                    val = float(score)
                except (TypeError, ValueError):
                    return "neutral"
                if val > 0.15:
                    return "positive"
                if val < -0.15:
                    return "negative"
                return "neutral"

            labels = [_label_from_score(a.sentiment_score) for a, _ in rows_news]
            pos = sum(1 for s in labels if s == "positive")
            neg = sum(1 for s in labels if s == "negative")
            neu = sum(1 for s in labels if s == "neutral")
            scores = [
                float(a.sentiment_score)
                for a, _ in rows_news
                if a.sentiment_score is not None
            ]
            avg_score = round(sum(scores) / len(scores), 4) if scores else None

            result["news_intelligence"] = {
                "status": "available",
                "article_count": len(rows_news),
                "positive": pos,
                "negative": neg,
                "neutral": neu,
                "average_sentiment_score": avg_score,
                "latest_articles": [
                    {
                        "title": a.headline,
                        "source": src.name if src else None,
                        "published_at": a.published_at.isoformat() if a.published_at else None,
                        "sentiment": _label_from_score(a.sentiment_score),
                        "url": a.canonical_url,
                    }
                    for a, src in rows_news[:5]
                ],
                "source": "news_articles",
            }
        else:
            result["news_intelligence"] = _unavailable(
                "No news articles in database for this symbol"
            )
    except Exception as exc:
        logger.warning("News fetch failed for %s: %s", sym, exc)
        result["news_intelligence"] = _unavailable(str(exc))
        warnings.append("News service failed")

    # ── ML prediction ────────────────────────────────────────────────────────
    try:
        from app.ml.model_server import ModelServer
        from app.services.prediction import PredictionService, PredictionRequest

        model_dir = Path("models")
        ms = ModelServer(model_dir=model_dir)
        models_list = ms.list_models()

        if models_list:
            best = max(models_list, key=lambda m: m.get("accuracy") or 0)
            ps = PredictionService(ms)
            req = PredictionRequest(
                symbol=sym,
                model_id=best["model_id"],
                model_version="latest",
                horizon_days=1,
            )
            pred = ps.predict_for_symbol(db, req)
            result["ml_intelligence"] = {
                "status": "available",
                "model_id": pred.model_id,
                "model_type": best.get("model_type", "unknown"),
                "predicted_class": pred.predicted_class,
                "confidence": round(pred.confidence, 4),
                "probabilities": pred.probabilities,
                "horizon_days": pred.horizon_days,
                "as_of_date": pred.as_of_date.isoformat(),
                "model_accuracy": best.get("accuracy"),
                "source": "model_server",
            }
        else:
            result["ml_intelligence"] = _unavailable(
                "No trained models found in models/ directory"
            )
            warnings.append("ML prediction unavailable")
    except Exception as exc:
        logger.warning("ML prediction failed for %s: %s", sym, exc)
        result["ml_intelligence"] = _unavailable(str(exc))
        warnings.append("ML prediction service failed")

    # ── Risk intelligence ────────────────────────────────────────────────────
    try:
        risk_rows = (
            db.query(DailyMarketData)
            .filter(DailyMarketData.company_id == company.id)
            .order_by(DailyMarketData.trading_date.desc())
            .limit(252)
            .all()
        )
        risk_rows = list(reversed(risk_rows))
        if len(risk_rows) >= 20:
            closes = pd.Series(
                [_safe_float(r.close) for r in risk_rows], dtype=float
            ).dropna()
            highs = pd.Series([_safe_float(r.high) for r in risk_rows], dtype=float).dropna()
            lows = pd.Series([_safe_float(r.low) for r in risk_rows], dtype=float).dropna()

            prev_c = closes.shift(1)
            tr = pd.concat(
                [highs - lows, (highs - prev_c).abs(), (lows - prev_c).abs()],
                axis=1,
            ).max(axis=1)
            atr14 = float(tr.rolling(14).mean().iloc[-1]) if len(tr) >= 14 else None
            log_ret = np.log(closes / closes.shift(1)).dropna()
            ann_vol_pct = (
                float(log_ret.std() * np.sqrt(252) * 100) if len(log_ret) >= 20 else None
            )
            cummax = closes.cummax()
            dd = (closes - cummax) / cummax
            max_dd_pct = float(dd.min() * 100)

            if ann_vol_pct is None:
                vol_label = "Unknown"
            elif ann_vol_pct < 20:
                vol_label = "Low"
            elif ann_vol_pct < 35:
                vol_label = "Moderate"
            elif ann_vol_pct < 50:
                vol_label = "High"
            else:
                vol_label = "Very High"

            risk_warnings: list[str] = []
            if ann_vol_pct is not None and ann_vol_pct >= 50:
                risk_warnings.append("Annualized volatility is very high")
            if max_dd_pct <= -30:
                risk_warnings.append("Large historical drawdown observed in the lookback window")

            result["risk_intelligence"] = {
                "status": "available",
                "atr_14": round(atr14, 2) if atr14 else None,
                "annualized_volatility_pct": round(ann_vol_pct, 2) if ann_vol_pct else None,
                "volatility_profile": vol_label,
                "max_drawdown_pct": round(max_dd_pct, 2),
                "data_window_days": len(risk_rows),
                "warnings": risk_warnings,
                "source": "deterministic_price_metrics",
            }
        else:
            result["risk_intelligence"] = _unavailable(
                "Insufficient price data for risk metrics"
            )
            warnings.append("Risk metrics unavailable")
    except Exception as exc:
        logger.warning("Risk metrics failed for %s: %s", sym, exc)
        result["risk_intelligence"] = _unavailable(str(exc))
        warnings.append("Risk metrics service failed")

    # ── Research / agent insights (persisted reports when available) ─────────
    try:
        reports = (
            db.query(ResearchReport)
            .filter(ResearchReport.ticker == sym)
            .order_by(ResearchReport.created_at.desc())
            .limit(3)
            .all()
        )
        if reports:
            result["agent_insights"] = {
                "status": "available",
                "insights": [
                    {
                        "report_id": r.report_id,
                        "report_type": r.report_type,
                        "generated_at": r.generated_at.isoformat() if r.generated_at else None,
                        "excerpt": (r.content or "")[:500],
                        "sources": r.sources,
                    }
                    for r in reports
                ],
                "source": "research_reports",
            }
        else:
            result["agent_insights"] = _unavailable(
                "No persisted research reports for this symbol"
            )
    except Exception as exc:
        logger.warning("Research insights failed for %s: %s", sym, exc)
        result["agent_insights"] = _unavailable(str(exc))

    # ── AI synthesis ─────────────────────────────────────────────────────────
    try:
        from app.services.llm_service import get_llm_service

        llm = get_llm_service()
        if llm and llm.is_available():
            mkt = result.get("market_intelligence", {})
            tch = result.get("technical_intelligence", {})
            fnd = result.get("fundamental_intelligence", {})
            nws = result.get("news_intelligence", {})
            ml = result.get("ml_intelligence", {})
            rsk = result.get("risk_intelligence", {})

            summary_parts = [
                f"Company: {company.name} ({sym}), Sector: {company.sector}"
            ]
            if mkt.get("status") == "available":
                summary_parts.append(
                    f"Price: ₹{mkt.get('current_price')} ({mkt.get('day_change_pct', 0):+.2f}% day), "
                    f"52W High: ₹{mkt.get('52w_high')}, 52W Low: ₹{mkt.get('52w_low')}"
                )
            if tch.get("status") == "available":
                trend = (tch.get("trend") or {}).get("classification")
                summary_parts.append(
                    f"Trend: {trend}, RSI-14: {tch.get('rsi_14')}, "
                    f"Vol: {tch.get('annualized_volatility_pct')}% pa, MaxDD: {tch.get('max_drawdown_pct')}%"
                )
            if fnd.get("status") == "available":
                summary_parts.append(
                    f"P/E: {fnd.get('pe_ratio')}, ROE: {fnd.get('roe')}, "
                    f"Profit Margin: {fnd.get('profit_margin')}, D/E: {fnd.get('debt_to_equity')}"
                )
            if nws.get("status") == "available":
                summary_parts.append(
                    f"News: {nws.get('article_count')} articles — "
                    f"Pos:{nws.get('positive')} Neg:{nws.get('negative')} Neu:{nws.get('neutral')}"
                )
            if ml.get("status") == "available":
                summary_parts.append(
                    f"ML ({ml.get('model_id')}): {ml.get('predicted_class')} "
                    f"{(ml.get('confidence') or 0) * 100:.1f}% confidence "
                    f"({ml.get('horizon_days')}D, model accuracy {ml.get('model_accuracy')})"
                )
            if rsk.get("status") == "available":
                summary_parts.append(
                    f"Risk: Volatility {rsk.get('annualized_volatility_pct')}% pa "
                    f"({rsk.get('volatility_profile')}), MaxDrawdown {rsk.get('max_drawdown_pct')}%"
                )

            data_summary = ". ".join(summary_parts)
            prompt = (
                f"You are a senior Indian equity analyst. Using ONLY the following verified data, "
                f"write a 3-4 sentence investment synthesis for {sym}. "
                f"Do NOT fabricate numbers beyond what is provided. Use ₹ for prices. "
                f"Mention any missing sections as data limitations.\n\nData:\n{data_summary}"
            )
            synthesis = llm.generate_text(prompt, max_tokens=400)
            result["ai_synthesis"] = {
                "status": "available",
                "synthesis": synthesis,
                "disclaimer": "AI-generated interpretation of verified data. Not investment advice.",
            }
        else:
            result["ai_synthesis"] = _unavailable("LLM service not configured")
    except Exception as exc:
        logger.warning("AI synthesis failed for %s: %s", sym, exc)
        result["ai_synthesis"] = _unavailable(str(exc))

    result["warnings"] = warnings
    return result
