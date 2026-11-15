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
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from app.services.llm_service import get_llm_service, LLMProvider
from app.db.models import Company, DailyMarketData, CompanyFinancial
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
            ).order_by(DailyMarketData.date.desc()).first()

            # Get financial data
            financials = self.db.query(CompanyFinancial).filter(
                CompanyFinancial.company_id == company.id
            ).order_by(CompanyFinancial.quarter.desc()).first()

            # Build context
            context = {
                "name": company.name,
                "ticker": ticker,
                "sector": company.sector,
                "description": company.description if hasattr(company, 'description') else "",
                "market_cap": company.market_cap if hasattr(company, 'market_cap') else "N/A",
                "current_price": float(latest_price.close) if latest_price else "N/A",
                "employees": company.employees if hasattr(company, 'employees') else "N/A",
            }

            prompt = f"""
Create a professional company overview for {company.name} ({ticker}).

Company Information:
{json.dumps(context, indent=2, default=str)}

Structure your response as markdown with these sections:
1. **At a Glance** - Quick key facts (market cap, sector, employees, founded)
2. **Business Model** - What the company does (2-3 sentences)
3. **Key Services/Products** - Main revenue drivers
4. **Recent Performance** - Latest financial metrics
5. **Market Position** - Competitive stance

Guidelines:
- Use simple, clear language ({language})
- Use Indian rupee (₹) for currency
- Keep it 400-600 words
- Format as professional markdown
- Be factual based on provided data
"""

            response = self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are a financial analyst. Create clear, professional company overviews.",
                temperature=0.5,
                max_tokens=1500,
            )

            return response.content

        except Exception as e:
            logger.error(f"Error generating company overview: {e}")
            return f"Error generating overview: {str(e)}"

    def analyze_financial_performance(
        self,
        ticker: str,
        period: str = "5Y",
    ) -> str:
        """Analyze and explain financial performance."""
        try:
            company = self.db.query(Company).filter(
                Company.symbol == ticker.upper()
            ).first()

            if not company:
                return f"Company {ticker} not found"

            # Get historical market data
            market_data = self.db.query(DailyMarketData).filter(
                DailyMarketData.company_id == company.id
            ).order_by(DailyMarketData.date.desc()).limit(250).all()

            if not market_data:
                return f"No market data available for {ticker}"

            # Calculate metrics
            latest = market_data[0]
            oldest = market_data[-1] if len(market_data) > 1 else latest

            price_change = float(latest.close) - float(oldest.close)
            price_change_pct = (price_change / float(oldest.close) * 100) if oldest.close else 0

            # Build analysis data
            analysis_data = {
                "ticker": ticker,
                "company_name": company.name,
                "current_price": float(latest.close),
                "price_change": price_change,
                "price_change_pct": price_change_pct,
                "volume_avg": float(latest.volume) if latest.volume else "N/A",
                "data_points": len(market_data),
            }

            prompt = f"""
Analyze the financial performance of {company.name} ({ticker}).

Market Data Summary:
{json.dumps(analysis_data, indent=2, default=str)}

Create analysis with these sections:
1. **Price Movement** - How has the price moved over the period?
2. **Volatility Assessment** - Price stability analysis
3. **Trading Volume** - Volume patterns and implications
4. **Technical Observations** - What the data tells us

Guidelines:
- Use markdown formatting
- Include actual numbers from data
- Explain what metrics mean for investors
- Be objective and data-driven
- Suggest what to watch for
- Keep professional tone
"""

            response = self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are a financial analyst. Analyze market data clearly and objectively.",
                temperature=0.5,
                max_tokens=1500,
            )

            return response.content

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
            ).order_by(DailyMarketData.date.desc()).first()

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
- Use emoji markers
"""

            response = self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are a business analyst. Create insightful, balanced SWOT analysis.",
                temperature=0.6,
                max_tokens=2000,
            )

            return response.content

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
                    ).order_by(DailyMarketData.date.desc()).first()

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

            return response.content

        except Exception as e:
            logger.error(f"Error comparing companies: {e}")
            return f"Error: {str(e)}"

    def generate_research_report(
        self,
        ticker: str,
        report_type: str = "comprehensive",
    ) -> str:
        """Generate comprehensive research report."""
        try:
            company = self.db.query(Company).filter(
                Company.symbol == ticker.upper()
            ).first()

            if not company:
                return f"Company {ticker} not found"

            # Generate all sections
            logger.info(f"Generating report sections for {ticker}")

            overview = self.generate_company_overview(ticker, language="simple")
            performance = self.analyze_financial_performance(ticker)
            swot = self.generate_swot_analysis(ticker)

            # Combine into report
            report = f"""# {company.name} ({ticker}) - Research Report

**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

---

## Executive Overview

{overview}

---

## Financial Performance Analysis

{performance}

---

## SWOT Analysis

{swot}

---

## Report Disclaimer

This report is generated using AI analysis of publicly available data. 
It is for informational purposes only and should not be considered investment advice.
Always conduct your own research and consult with financial advisors before making investment decisions.

**Data Freshness:** Analysis based on latest available market data
**Confidence:** Medium (AI-generated interpretations mixed with factual data)
**Last Updated:** {datetime.utcnow().isoformat()}
"""

            return report

        except Exception as e:
            logger.error(f"Error generating research report: {e}")
            return f"Error: {str(e)}"


def get_research_assistant(db: Session) -> ResearchAssistant:
    """Create research assistant instance."""
    return ResearchAssistant(db)
