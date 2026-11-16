"""
Research Assistant Service - Company Analysis & Reports

Provides comprehensive financial research capabilities:
- Company overviews
- Financial performance analysis
- SWOT analysis
- Peer comparisons
- Research report generation
- Report storage and retrieval
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.services.llm_service import get_llm_service, LLMProvider
from app.db.models import (
    Company,
    DailyMarketData,
    CompanyFinancial,
    CompanyFundamentalInfo,
    CompanyProfile,
    NewsArticle,
    NewsArticleCompany,
    ResearchReport,
    MLModel,
    Prediction,
)
from app.services.financial_assistant import FinancialAssistant

logger = logging.getLogger(__name__)


class ResearchAssistant:
    """Generate comprehensive research on companies."""

    def __init__(self, db: Session):
        self.db = db
        self.llm_service = get_llm_service()
        self.financial_assistant = FinancialAssistant(db)

    def generate_company_overview(
        self,
        ticker: str,
        language: str = "simple",
    ) -> str:
        """Generate executive summary of a company."""
        try:
            # Fetch company data
            company = self.db.query(Company).filter(
                Company.symbol == ticker.upper()
            ).first()

            if not company:
                return f"Company with ticker {ticker} not found"

            # Get latest market price
            latest_price = self.db.query(DailyMarketData).filter(
                DailyMarketData.company_id == company.id
            ).order_by(DailyMarketData.trading_date.desc()).first()

            # Get financial data
            financials = self.db.query(CompanyFinancial).filter(
                CompanyFinancial.company_id == company.id
            ).order_by(CompanyFinancial.period_end.desc()).first()

            # Build context
            context = {
                "name": company.name,
                "ticker": ticker,
                "sector": company.sector,
                "current_price": float(latest_price.close) if latest_price else "N/A",
            }

            prompt = f"""
Create a professional company overview for {company.name} ({ticker}).

Company Information:
{json.dumps(context, indent=2, default=str)}

Structure your response as markdown with these sections:
1. **At a Glance** - Quick key facts (sector, trading info)
2. **Business Model** - What the company does (2-3 sentences)
3. **Key Services/Products** - Main revenue drivers
4. **Recent Performance** - Latest trading data
5. **Market Position** - Competitive stance

Guidelines:
- Use simple, clear language ({language})
- Use Indian rupee (₹) for currency
- Keep it 400-600 words
- Format as professional markdown
- Be factual based on provided data
- Include uncertainty disclaimer
"""

            response = self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are a financial analyst. Create clear, professional company overviews.",
                temperature=0.5,
                max_tokens=1500,
            )

            # Add uncertainty footer
            footer = "\n\n---\n*This overview is AI-generated and should be verified with official company sources and recent financial statements.*"
            return response.content + footer if response else "Unable to generate overview"

        except Exception as e:
            logger.error(f"Error generating company overview: {e}")
            return f"Error generating overview: {str(e)}"

    def analyze_financial_performance(
        self,
        ticker: str,
        period: str = "5Y",
    ) -> str:
        """Analyze and explain financial performance using actual verified market data."""
        try:
            company = self.db.query(Company).filter(
                Company.symbol == ticker.upper()
            ).first()

            if not company:
                return f"Company {ticker} not found"

            # Map requested period to target trading records
            period_target_map = {"1Y": 252, "3Y": 756, "5Y": 1260}
            target_limit = period_target_map.get(period.upper(), 1260)

            # Get historical market data
            market_data = self.db.query(DailyMarketData).filter(
                DailyMarketData.company_id == company.id
            ).order_by(DailyMarketData.trading_date.desc()).limit(target_limit).all()

            if not market_data:
                return f"No market data available for {ticker}"

            # Calculate verified metrics
            latest = market_data[0]
            oldest = market_data[-1] if len(market_data) > 1 else latest
            data_points = len(market_data)

            price_change = float(latest.close) - float(oldest.close)
            price_change_pct = (price_change / float(oldest.close) * 100) if oldest.close else 0

            # Compute actual date span genuinely supported by available data
            start_date_str = str(oldest.trading_date)
            end_date_str = str(latest.trading_date)
            approx_years = round(data_points / 252.0, 1) if data_points >= 126 else round(data_points / 252.0, 2)

            data_span_note = (
                f"{data_points} trading days ({start_date_str} to {end_date_str}, approx {approx_years} year(s))"
            )

            # Build analysis data with true boundaries
            analysis_data = {
                "ticker": ticker,
                "company_name": company.name,
                "requested_period": period,
                "genuine_data_span": data_span_note,
                "current_price": float(latest.close),
                "start_price": float(oldest.close),
                "price_change": price_change,
                "price_change_pct": round(price_change_pct, 2),
                "volume_avg": float(latest.volume) if latest.volume else "N/A",
                "data_points": data_points,
            }

            prompt = f"""
Analyze the financial performance of {company.name} ({ticker}).

Market Data Summary:
{json.dumps(analysis_data, indent=2, default=str)}

Create analysis with these sections:
1. **Verified Timeframe** - State clearly that data covers {data_span_note}. Do not falsely claim full 5-year coverage if the available data only spans {data_points} trading days.
2. **Price Movement** - How has the price moved from ₹{oldest.close:.2f} ({start_date_str}) to ₹{latest.close:.2f} ({end_date_str})? ({price_change_pct:+.2f}%)
3. **Volatility & Range** - Price stability and observed trading range
4. **Trading Volume** - Volume patterns and market liquidity observations
5. **Technical Observations** - Trend and key inflection points

Guidelines:
- Use markdown formatting
- Be strictly factual based on the verified {data_points} trading sessions
- Never fabricate historical price levels or claim periods not supported by data
- Keep professional objective tone
"""

            response = self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are a financial analyst. Analyze market data clearly, objectively, and strictly within verified timeframes.",
                temperature=0.5,
                max_tokens=1500,
            )

            footer = f"\n\n---\n*Analysis strictly bounded to verified data: {data_span_note}. Past performance does not guarantee future results.*"
            return response.content + footer if response else f"Analysis for {ticker}: {price_change_pct:+.2f}% over {data_span_note}."

        except Exception as e:
            logger.error(f"Error analyzing financial performance: {e}")
            return f"Error: {str(e)}"

    def generate_swot_analysis(
        self,
        ticker: str,
    ) -> str:
        """Generate SWOT analysis for a company."""
        try:
            company = self.db.query(Company).filter(
                Company.symbol == ticker.upper()
            ).first()

            if not company:
                return f"Company {ticker} not found"

            # Get market data for context
            latest_price = self.db.query(DailyMarketData).filter(
                DailyMarketData.company_id == company.id
            ).order_by(DailyMarketData.trading_date.desc()).first()

            context = {
                "name": company.name,
                "ticker": ticker,
                "sector": company.sector,
                "current_price": float(latest_price.close) if latest_price else "N/A",
            }

            prompt = f"""
Create a comprehensive SWOT analysis for {company.name} ({ticker}).

Company Context:
{json.dumps(context, indent=2, default=str)}

Structure:
1. **Strengths** (✓) - 5 key strengths
2. **Weaknesses** (⚠) - 5 key weaknesses
3. **Opportunities** (🚀) - 5 opportunities
4. **Threats** (⚠️) - 5 threats

For each point include:
- Bold title
- Brief 2-3 sentence explanation
- Relevance to investors

Guidelines:
- Use markdown formatting
- Be specific and realistic
- Draw from {company.sector} sector knowledge
- Include investment implications
- Keep professional tone
"""

            response = self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are a business analyst. Create insightful, balanced SWOT analysis.",
                temperature=0.6,
                max_tokens=2000,
            )

            footer = "\n\n---\n*This SWOT analysis is AI-generated and represents one perspective. Conduct your own research for investment decisions.*"
            return response.content + footer if response else "Unable to generate SWOT"

        except Exception as e:
            logger.error(f"Error generating SWOT: {e}")
            return f"Error: {str(e)}"

    def compare_companies(
        self,
        tickers: List[str],
    ) -> str:
        """Compare multiple companies."""
        try:
            if not tickers or len(tickers) < 2:
                return "At least 2 tickers required for comparison"

            companies_data = {}

            for ticker in tickers:
                company = self.db.query(Company).filter(
                    Company.symbol == ticker.upper()
                ).first()

                if company:
                    latest = self.db.query(DailyMarketData).filter(
                        DailyMarketData.company_id == company.id
                    ).order_by(DailyMarketData.trading_date.desc()).first()

                    companies_data[ticker] = {
                        "name": company.name,
                        "sector": company.sector,
                        "price": float(latest.close) if latest else None,
                        "volume": float(latest.volume) if latest and latest.volume else None,
                    }

            if not companies_data:
                return "No data found for provided tickers"

            prompt = f"""
Create a detailed peer comparison for: {', '.join(tickers)}

Company Data:
{json.dumps(companies_data, indent=2, default=str)}

Structure your response as markdown:
1. **Quick Comparison Table** - Side-by-side metrics
2. **Key Differences** - Main distinguishing factors
3. **Sector Context** - How they compare in their sector
4. **Investment Perspective** - Which might suit different investors
5. **Recommendation** - Balanced assessment

Guidelines:
- Use markdown tables for comparison
- Be objective and factual
- Explain differences clearly
- Consider investor types (growth, value, dividend)
- Include risk assessments
- Professional tone
"""

            response = self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are an equity analyst. Create detailed peer comparisons.",
                temperature=0.6,
                max_tokens=2000,
            )

            footer = "\n\n---\n*This comparison is AI-generated. Always verify data with official sources before making investment decisions.*"
            return response.content + footer if response else "Unable to generate comparison"

        except Exception as e:
            logger.error(f"Error comparing companies: {e}")
            return f"Error: {str(e)}"

    def generate_research_report(
        self,
        ticker: str,
        report_type: str = "comprehensive",
    ) -> str:
        """Generate comprehensive research report string (backward-compatible)."""
        dossier = self.generate_research_dossier(ticker, report_type)
        return dossier.get("report", f"Error generating research report for {ticker}")

    def generate_research_dossier(
        self,
        ticker: str,
        report_type: str = "comprehensive",
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive, evidence-backed research dossier using actual ArthAI data.

        Includes:
        1. Executive summary
        2. Company overview & business model
        3. Latest market information
        4. Technical analysis
        5. Fundamental analysis
        6. Financial performance (verified timeframe)
        7. News and sentiment analysis
        8. ML prediction insights (if available)
        9. Deterministic risk analysis (ATR, volatility, drawdown)
        10. Opportunities and threats (SWOT)
        11. Limitations, data freshness, and sources
        """
        sym = ticker.upper()
        now_utc = datetime.now(timezone.utc)
        now_str = now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')

        company = self.db.query(Company).filter(Company.symbol == sym).first()
        if not company:
            return {
                "report": f"# Error\n\nCompany with ticker `{sym}` was not found in universe.",
                "structured_sections": {},
                "sources": [],
                "company_name": sym,
                "generated_at": now_utc.isoformat(),
            }

        sources: List[Dict[str, Any]] = []

        # 1. Market Data & Quotes
        market_rows = self.db.query(DailyMarketData).filter(
            DailyMarketData.company_id == company.id
        ).order_by(DailyMarketData.trading_date.desc()).limit(500).all()

        latest_price_val = "N/A"
        price_change_str = "N/A"
        risk_metrics = {"volatility_annualized": None, "max_drawdown": None, "atr_14": None}

        if market_rows:
            sources.append({
                "type": "market_data",
                "name": "Historical Daily Market Data (NSE)",
                "as_of": str(market_rows[0].trading_date),
                "records_available": len(market_rows),
            })
            latest = market_rows[0]
            latest_price_val = f"₹{float(latest.close):,.2f}"
            if len(market_rows) > 1:
                prev = market_rows[1]
                chg = float(latest.close) - float(prev.close)
                chg_pct = (chg / float(prev.close)) * 100 if prev.close else 0
                price_change_str = f"₹{chg:+.2f} ({chg_pct:+.2f}%)"

            # Calculate deterministic risk metrics from price series
            closes = [float(r.close) for r in reversed(market_rows) if r.close is not None]
            if len(closes) >= 10:
                returns = np.diff(closes) / closes[:-1]
                if len(returns) > 0 and np.std(returns) > 0:
                    ann_vol = float(np.std(returns) * np.sqrt(252))
                    risk_metrics["volatility_annualized"] = round(ann_vol, 4)

                peak = np.maximum.accumulate(closes)
                drawdown = (closes - peak) / peak
                max_dd = float(np.min(drawdown))
                risk_metrics["max_drawdown"] = round(max_dd, 4)

            # 14-day ATR calculation
            if len(market_rows) >= 15:
                trs = []
                for idx in range(1, 15):
                    curr_bar = market_rows[idx - 1]
                    prev_bar = market_rows[idx]
                    h = float(curr_bar.high) if curr_bar.high is not None else float(curr_bar.close)
                    l = float(curr_bar.low) if curr_bar.low is not None else float(curr_bar.close)
                    pc = float(prev_bar.close) if prev_bar.close is not None else float(curr_bar.close)
                    tr = max(h - l, abs(h - pc), abs(l - pc))
                    trs.append(tr)
                if trs:
                    risk_metrics["atr_14"] = round(float(np.mean(trs)), 2)

        # 2. Fundamentals
        financial_rows = self.db.query(CompanyFinancial).filter(
            CompanyFinancial.company_id == company.id
        ).all()

        fin_dict: Dict[str, Any] = {}
        if financial_rows:
            sources.append({
                "type": "fundamentals",
                "name": "Financial Statements & Ratios",
                "as_of": str(financial_rows[0].period_end) if financial_rows[0].period_end else "N/A",
                "metrics_count": len(financial_rows),
            })
            for f in financial_rows:
                if f.metric_name and f.metric_value is not None:
                    fin_dict[f.metric_name] = float(f.metric_value)

        # 3. News Articles
        news_links = self.db.query(NewsArticleCompany).filter(
            NewsArticleCompany.company_id == company.id
        ).limit(10).all()

        article_summaries = []
        if news_links:
            art_ids = [l.article_id for l in news_links]
            arts = self.db.query(NewsArticle).filter(NewsArticle.id.in_(art_ids)).all()
            for a in arts:
                article_summaries.append({
                    "headline": a.headline,
                    "sentiment_score": float(a.sentiment_score) if a.sentiment_score is not None else None,
                    "event_category": a.event_category,
                    "published_at": str(a.published_at) if a.published_at else None,
                    "url": a.canonical_url,
                })
            sources.append({
                "type": "news",
                "name": "Financial Press & News Sources",
                "count": len(arts),
            })

        # 4. ML Models
        ml_model_record = self.db.query(MLModel).filter(
            MLModel.status == "ready"
        ).order_by(desc(MLModel.accuracy)).first()

        ml_summary_text = (
            f"Available Model: {ml_model_record.model_id} (Version: {ml_model_record.version}, "
            f"Accuracy: {float(ml_model_record.accuracy):.1%}, Type: {ml_model_record.model_type})"
            if ml_model_record and ml_model_record.accuracy
            else "No production model currently registered."
        )

        # Generate individual sections
        overview_text = self.generate_company_overview(sym, language="simple")
        performance_text = self.analyze_financial_performance(sym, period="5Y")
        swot_text = self.generate_swot_analysis(sym)

        # Build Technical Analysis section
        tech_text = f"""### Key Technical Levels & Indicators
- **Latest Close:** {latest_price_val}
- **Recent Day Delta:** {price_change_str}
- **14-Day Average True Range (ATR):** ₹{risk_metrics['atr_14'] if risk_metrics['atr_14'] is not None else 'N/A'}
- **Data Series Sampled:** {len(market_rows)} trading sessions
"""

        # Build Fundamental Summary section
        if fin_dict:
            fund_lines = [f"- **{k.replace('_', ' ').title()}:** {v:,.2f}" for k, v in list(fin_dict.items())[:8]]
            fund_text = "### Core Fundamental Metrics\n" + "\n".join(fund_lines)
        else:
            fund_text = "### Core Fundamental Metrics\n*Detailed company balance sheet metrics are currently pending next quarterly ingestion cycle.*"

        # Build News Summary section
        if article_summaries:
            news_items = []
            for art in article_summaries[:4]:
                sent_label = (
                    f" (Sentiment: {art['sentiment_score']:+.2f})"
                    if art['sentiment_score'] is not None
                    else ""
                )
                cat_label = f"[{art['event_category'].title()}] " if art['event_category'] else ""
                date_label = f" *({art['published_at'][:10]})*" if art['published_at'] else ""
                news_items.append(f"- {cat_label}**{art['headline']}**{sent_label}{date_label}")
            news_text = "### Recent Developments & Market Coverage\n" + "\n".join(news_items)
        else:
            news_text = "### Recent Developments & Market Coverage\n*No material regulatory or earnings headlines registered in the immediate monitoring window.*"

        # Build Risk Section
        vol_str = f"{risk_metrics['volatility_annualized']*100:.2f}%" if risk_metrics['volatility_annualized'] is not None else "N/A"
        dd_str = f"{risk_metrics['max_drawdown']*100:.2f}%" if risk_metrics['max_drawdown'] is not None else "N/A"
        risk_text = f"""### Deterministic Risk Metrics
- **Annualized Historical Volatility:** {vol_str}
- **Maximum Drawdown (Observed History):** {dd_str}
- **14-Day ATR:** ₹{risk_metrics['atr_14'] if risk_metrics['atr_14'] is not None else 'N/A'}
- **Risk Assessment:** Calculated deterministically from verified price records; strictly avoids subjective labeling.
"""

        # Build Comprehensive Markdown Dossier
        report_markdown = f"""# {company.name} ({sym}) — Equity Research Dossier

**Generated:** {now_str}  
**Sector:** {company.sector or 'Diversified'} | **Exchange:** {company.exchange}  
**Latest Market Price:** {latest_price_val} ({price_change_str})

---

## 1. Executive Summary & Overview

{overview_text}

---

## 2. Market Information & Technical Structure

{tech_text}

---

## 3. Fundamental Analysis & Ratios

{fund_text}

---

## 4. Financial Performance & Historical Movement

{performance_text}

---

## 5. News Intelligence & Material Events

{news_text}

---

## 6. Machine Learning Forecasts & Modeling

{ml_summary_text}

---

## 7. Risk Analysis

{risk_text}

---

## 8. Strategic SWOT Analysis

{swot_text}

---

## 9. Research Methodology, Sources & Disclaimer

**Evidence Sources Utilized:**
{chr(10).join(f"- {s['name']} (As of: {s.get('as_of', 'Latest')})" for s in sources)}

**Data Freshness & Transparency:**
- Market quotes and indicators reflect verified exchange records.
- Financial metrics reflect reported corporate disclosures.
- Machine learning insights and AI explanations clearly separate historical factual data from probabilistic forecasts.

*Disclaimer: This research report is produced by ArthAI for informational and analytical purposes only. It does not constitute investment advice, financial promotion, or a solicitation to buy or sell securities.*
"""

        structured_sections = {
            "executive_summary": overview_text,
            "technical_analysis": tech_text,
            "fundamental_analysis": fund_text,
            "financial_performance": performance_text,
            "news_and_events": news_text,
            "ml_insights": ml_summary_text,
            "risk_analysis": risk_text,
            "swot": swot_text,
        }

        return {
            "report": report_markdown,
            "structured_sections": structured_sections,
            "sources": sources,
            "company_name": company.name,
            "generated_at": now_utc.isoformat(),
        }

    # -----------------------------------------------------------------------
    # Database Persistence Operations
    # -----------------------------------------------------------------------

    def save_report(
        self,
        ticker: str,
        content: str,
        report_type: str = "comprehensive",
        company_name: Optional[str] = None,
        structured_sections: Optional[Dict[str, Any]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> ResearchReport:
        """Persist a research report to the database."""
        report_id = f"rep_{uuid.uuid4().hex[:12]}"
        sym = ticker.upper()

        if not company_name:
            comp = self.db.query(Company).filter(Company.symbol == sym).first()
            company_name = comp.name if comp else sym

        report_obj = ResearchReport(
            report_id=report_id,
            ticker=sym,
            company_name=company_name,
            report_type=report_type,
            content=content,
            structured_sections=structured_sections,
            sources=sources,
            parameters=parameters,
            generated_at=datetime.now(timezone.utc),
        )
        self.db.add(report_obj)
        self.db.commit()
        self.db.refresh(report_obj)
        logger.info(f"Saved research report {report_id} for {sym}")
        return report_obj

    def list_reports(
        self,
        ticker: Optional[str] = None,
        report_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[ResearchReport], int]:
        """List persisted research reports with pagination and filtering."""
        query = self.db.query(ResearchReport)
        if ticker:
            query = query.filter(ResearchReport.ticker == ticker.upper())
        if report_type:
            query = query.filter(ResearchReport.report_type == report_type.lower())

        total = query.count()
        reports = (
            query.order_by(desc(ResearchReport.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )
        return reports, total

    def get_report_by_id(self, report_id: str) -> Optional[ResearchReport]:
        """Retrieve a specific report by unique report_id or integer ID."""
        # Check by report_id string first
        rep = self.db.query(ResearchReport).filter(
            ResearchReport.report_id == report_id
        ).first()
        if not rep and report_id.isdigit():
            rep = self.db.query(ResearchReport).filter(
                ResearchReport.id == int(report_id)
            ).first()
        return rep

    def delete_report(self, report_id: str) -> bool:
        """Delete a report by report_id or integer ID."""
        rep = self.get_report_by_id(report_id)
        if not rep:
            return False
        self.db.delete(rep)
        self.db.commit()
        logger.info(f"Deleted research report {report_id}")
        return True


def get_research_assistant(db: Session) -> ResearchAssistant:
    """Create research assistant instance."""
    return ResearchAssistant(db)
