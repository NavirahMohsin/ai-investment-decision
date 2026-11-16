"""
News Analyst Agent Node.

Responsibilities:
- Retrieve recent company-related news articles from the database.
- Analyse aggregated sentiment score, trend, and distribution.
- Identify and classify important event categories (earnings, regulatory, litigation, etc.).
- Examine market impact scores and sentiment confidence.
- Highlight material developments, distinguishing company-specific from sector-wide events.
- Identify contradictory news coverage, unreliable sources, or thin/missing coverage (< 3 articles).
- Preserve article references (headline, source, published date) without treating headlines as proven facts.
- Reuse: news_intelligence.py, news_analysis.py, news_signals.py.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json
import logging
from typing import Any

from sqlalchemy import select

from app.db.models import Company, NewsArticle, NewsArticleCompany, NewsSource
from app.agents.state import AgentName, GraphState
from app.agents.prompts import NEWS_ANALYST_SYSTEM
from app.agents.nodes.base import BaseAgentNode
from app.agents.dependencies import get_agent_db_session
from app.services.news_intelligence import NewsIntelligenceService
from app.services.news_signals import NewsSignalService

logger = logging.getLogger(__name__)


def _decimal_to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


class NewsAnalystNode(BaseAgentNode):
    agent_name = AgentName.NEWS_ANALYST
    system_prompt = NEWS_ANALYST_SYSTEM

    def _gather_data(self, state: GraphState) -> dict[str, Any]:
        tickers = state.get("tickers", [])
        data: dict[str, Any] = {
            "tickers": tickers,
            "articles": {},
            "sentiment_aggregation": {},
            "event_categories": {},
            "coverage_quality": {},
            "missing_information": [],
            "warnings": [],
            "evidence_sources": [
                "NewsArticle",
                "NewsArticleCompany",
                "NewsIntelligenceService",
                "NewsSignalService",
            ],
            "data_timestamps": {},
        }

        with get_agent_db_session() as db:
            intel_svc = NewsIntelligenceService(db)
            signal_svc = NewsSignalService(db)

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

                # Query company articles with their attribution
                article_pairs = intel_svc.get_articles_for_company(company.id, limit=20)
                articles_list = []
                event_counts: dict[str, int] = {}
                latest_pub_date: datetime | None = None

                for art, match in article_pairs:
                    source_name = "Unknown"
                    if art.source_id:
                        src = db.get(NewsSource, art.source_id)
                        if src:
                            source_name = src.name

                    pub_iso = art.published_at.isoformat() if art.published_at else "N/A"
                    if art.published_at and (latest_pub_date is None or art.published_at > latest_pub_date):
                        latest_pub_date = art.published_at

                    cat = art.event_category or "general"
                    event_counts[cat] = event_counts.get(cat, 0) + 1

                    articles_list.append({
                        "article_id": art.id,
                        "headline": art.headline,
                        "source": source_name,
                        "published_at": pub_iso,
                        "sentiment_score": _decimal_to_float(art.sentiment_score),
                        "sentiment_confidence": _decimal_to_float(art.sentiment_confidence),
                        "event_category": art.event_category,
                        "event_confidence": _decimal_to_float(art.event_confidence),
                        "market_impact_score": _decimal_to_float(art.market_impact_score),
                        "match_confidence": _decimal_to_float(match.match_confidence) if match else None,
                    })

                data["articles"][symbol] = articles_list
                data["event_categories"][symbol] = event_counts

                if latest_pub_date:
                    data["data_timestamps"][f"{symbol}_latest_news"] = latest_pub_date.isoformat()

                # Sentiment aggregation over last 30 days
                try:
                    agg = signal_svc.aggregate_sentiment(company.id, days=30)
                    data["sentiment_aggregation"][symbol] = agg.to_dict()
                except Exception as e:
                    logger.warning("Sentiment aggregation failed for %s: %s", symbol, e)
                    data["sentiment_aggregation"][symbol] = {
                        "avg_sentiment": 0.0,
                        "sentiment_trend": "no_data",
                        "article_count": len(articles_list),
                    }

                # Evaluate coverage quality & contradiction detection
                count = len(articles_list)
                if count == 0:
                    data["coverage_quality"][symbol] = "NO_COVERAGE"
                    data["missing_information"].append(f"No recent news articles found for {symbol}.")
                    data["warnings"].append(f"No news intelligence available for {symbol}. News sentiment cannot be verified.")
                elif count < 3:
                    data["coverage_quality"][symbol] = "THIN_COVERAGE"
                    data["warnings"].append(
                        f"Thin news coverage for {symbol} ({count} article(s)). Sentiment signals may have low reliability."
                    )
                else:
                    data["coverage_quality"][symbol] = "ADEQUATE"

                # Detect contradictory coverage
                pos_count = sum(1 for a in articles_list if (a["sentiment_score"] or 0) > 0.2)
                neg_count = sum(1 for a in articles_list if (a["sentiment_score"] or 0) < -0.2)
                if pos_count > 0 and neg_count > 0:
                    data["warnings"].append(
                        f"Contradictory sentiment detected for {symbol}: {pos_count} positive vs {neg_count} negative article(s)."
                    )

        return data

    def _build_prompt(self, state: GraphState, data: dict[str, Any]) -> str:
        prompt_payload = {
            "user_request": state.get("user_request", ""),
            "tickers": data.get("tickers", []),
            "articles": data.get("articles", {}),
            "sentiment_aggregation": data.get("sentiment_aggregation", {}),
            "event_categories": data.get("event_categories", {}),
            "coverage_quality": data.get("coverage_quality", {}),
            "missing_information": data.get("missing_information", []),
            "warnings": data.get("warnings", []),
        }

        return (
            "Analyse the following real news articles and sentiment metrics, and produce a "
            "structured AgentResult JSON strictly matching the schema.\n\n"
            f"{json.dumps(prompt_payload, indent=2, default=str)}\n\n"
            "Evaluate sentiment balance, event categories (earnings, legal, corporate actions), "
            "highlight material developments, flag contradictory coverage or data gaps, "
            "and preserve article headline references and publication dates."
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
        result.supporting_metrics.setdefault("sentiment_aggregation", data.get("sentiment_aggregation", {}))
        result.supporting_metrics.setdefault("event_categories", data.get("event_categories", {}))
        result.supporting_metrics.setdefault(
            "article_count",
            {t: len(data.get("articles", {}).get(t, [])) for t in data.get("tickers", [])}
        )


news_analyst_node = NewsAnalystNode()
