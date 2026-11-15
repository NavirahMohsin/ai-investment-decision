"""
Financial Assistant Service - Conversational AI for stock research.

Provides intelligent responses to questions about Indian stocks using:
- ArthAI's market data APIs
- Fundamental analysis data
- Technical indicators
- News intelligence
"""

import json
import logging
from typing import Optional, Any
from decimal import Decimal

from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.services.llm_service import get_llm_service, LLMProvider, LLMResponse
from app.db.models import Company, DailyMarketData, NewsArticleCompany, NewsArticle
from app.services.fundamentals import get_company_financials, get_company_fundamental_info
from app.services.indicators import calculate_indicators

logger = logging.getLogger(__name__)


class AssistantMessage(BaseModel):
    """A message in the conversation."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class AssistantResponse(BaseModel):
    """Response from the financial assistant."""
    answer: str = Field(..., description="Direct answer to the question")
    sources: list[str] = Field(
        default_factory=list,
        description="Data sources used (market data, fundamentals, news, etc.)"
    )
    confidence: str = Field(
        default="medium",
        description="Confidence level: low, medium, high"
    )
    disclaimer: str = Field(
        default="This response contains model-generated interpretations. Please verify with official sources.",
        description="Important disclaimer about AI-generated content"
    )
    related_companies: list[str] = Field(
        default_factory=list,
        description="Related companies mentioned"
    )


class FinancialAssistant:
    """Conversational financial assistant powered by LLM."""

    def __init__(self, db: Session):
        self.db = db
        self.llm_service = get_llm_service()
        self.conversation_history: list[AssistantMessage] = []

    def add_to_history(self, role: str, content: str):
        """Add a message to conversation history."""
        self.conversation_history.append(
            AssistantMessage(role=role, content=content)
        )

    def _get_company_context(self, ticker: str) -> dict[str, Any]:
        """Retrieve comprehensive context about a company."""
        try:
            company = self.db.query(Company).filter(
                Company.symbol == ticker.upper()
            ).first()
            
            if not company:
                return {"error": f"Company {ticker} not found"}

            context = {
                "company_name": company.name,
                "ticker": company.symbol,
                "sector": company.sector,
            }

            # Get latest market price
            try:
                latest = self.db.query(DailyMarketData).filter(
                    DailyMarketData.company_id == company.id
                ).order_by(DailyMarketData.date.desc()).first()
                
                if latest:
                    context["latest_price"] = float(latest.close)
                    context["date"] = latest.date.isoformat()
                    context["previous_close"] = float(latest.open)
                    
                    # Calculate change
                    if latest.open and latest.close:
                        change_pct = ((latest.close - latest.open) / latest.open) * 100
                        context["change_percent"] = round(change_pct, 2)
            except Exception as e:
                logger.warning(f"Could not fetch market data for {ticker}: {e}")

            # Get fundamentals
            try:
                fundamentals = get_company_fundamental_info(self.db, company.id)
                if fundamentals:
                    context["fundamentals"] = {
                        "pe_ratio": fundamentals.pe,
                        "pb_ratio": fundamentals.price_to_book,
                        "roe": fundamentals.roe,
                        "debt_to_equity": fundamentals.debt_to_equity,
                    }
            except Exception as e:
                logger.warning(f"Could not fetch fundamentals for {ticker}: {e}")

            # Get recent news
            try:
                news_articles = self.db.query(NewsArticle).join(
                    NewsArticleCompany
                ).filter(
                    NewsArticleCompany.company_id == company.id
                ).order_by(NewsArticle.published_date.desc()).limit(5).all()
                
                if news_articles:
                    context["recent_news"] = [
                        {
                            "title": article.title,
                            "summary": article.summary or article.content[:200],
                            "date": article.published_date.isoformat(),
                        }
                        for article in news_articles
                    ]
            except Exception as e:
                logger.warning(f"Could not fetch news for {ticker}: {e}")

            return context

        except Exception as e:
            logger.error(f"Error getting company context for {ticker}: {e}")
            return {"error": str(e)}

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the financial assistant."""
        return """You are an expert financial analyst assistant for ArthAI, 
an Indian stock market research platform. Your role is to help users understand 
stocks, market trends, and investment decisions.

Guidelines:
1. Provide accurate, data-driven answers based on the information provided
2. Always distinguish between:
   - Factual data (prices, PE ratios, revenues) - clearly state these as facts
   - Model-generated insights and interpretations - prefix with "Analysis suggests" or "Based on our models"
3. Explain technical indicators and financial ratios in simple terms
4. When explaining why a stock got a particular score or signal, reference the specific metrics
5. Use Indian rupee (₹) for currency and refer to Indian market conventions
6. Mention relevant companies and sectors when contextual
7. Always include a disclaimer that users should verify important decisions with official sources
8. Be concise but thorough
9. Ask clarifying questions if the user's intent is unclear
"""

    def _extract_ticker_from_question(self, question: str) -> Optional[str]:
        """Extract ticker symbol from user question."""
        # Simple heuristic: look for uppercase letters that might be a ticker
        import re
        
        # Pattern: 1-4 uppercase letters, optionally followed by .NS or .BO
        pattern = r'\b([A-Z]{1,4})(?:\.(?:NS|BO))?\b'
        matches = re.findall(pattern, question)
        
        if matches:
            # Return the first match (most likely to be the stock being asked about)
            return matches[0]
        
        return None

    def ask_question(
        self,
        question: str,
        include_history: bool = True,
        provider: Optional[LLMProvider] = None,
    ) -> AssistantResponse:
        """
        Ask the assistant a question about stocks and get a structured response.
        
        Args:
            question: User's question about stocks
            include_history: Whether to include conversation history for context
            provider: Specific LLM provider to use (defaults to Gemini)
        
        Returns:
            AssistantResponse with answer and sources
        """
        try:
            # Extract ticker if present
            ticker = self._extract_ticker_from_question(question)
            context = {}
            sources = []
            related_companies = []

            if ticker:
                logger.info(f"Extracted ticker from question: {ticker}")
                context = self._get_company_context(ticker)
                
                if "error" not in context:
                    sources.append(f"Market Data ({ticker})")
                    if "fundamentals" in context:
                        sources.append("Fundamentals")
                    if "indicators" in context:
                        sources.append("Technical Indicators")
                    if "recent_news" in context:
                        sources.append("News Intelligence")
                    related_companies.append(ticker)

            # Build prompt with context
            prompt = self._build_question_prompt(question, context)
            
            # Build conversation context
            messages_text = ""
            if include_history and self.conversation_history:
                for msg in self.conversation_history[-5:]:  # Last 5 messages for context
                    messages_text += f"{msg.role.capitalize()}: {msg.content}\n"
            
            if messages_text:
                prompt = f"Previous conversation:\n{messages_text}\n\nNew question:\n{prompt}"

            # Get response from LLM
            logger.info(f"Sending question to LLM: {question[:100]}...")
            
            llm_response = self.llm_service.generate(
                prompt=prompt,
                system_prompt=self._build_system_prompt(),
                temperature=0.7,
                max_tokens=2048,
                provider=provider,
                fallback_to_groq=True,
            )

            # Parse structured response
            answer = llm_response.content.strip()
            
            # Add to history
            self.add_to_history("user", question)
            self.add_to_history("assistant", answer)

            # Determine confidence based on available context
            confidence = "high" if sources else "medium"

            return AssistantResponse(
                answer=answer,
                sources=sources,
                confidence=confidence,
                related_companies=related_companies,
            )

        except Exception as e:
            logger.error(f"Error in ask_question: {e}")
            error_response = f"I encountered an error processing your question: {str(e)}"
            self.add_to_history("user", question)
            self.add_to_history("assistant", error_response)
            
            return AssistantResponse(
                answer=error_response,
                sources=["Error"],
                confidence="low",
            )

    def _build_question_prompt(self, question: str, context: dict[str, Any]) -> str:
        """Build the complete prompt with question and context."""
        prompt = f"Question: {question}\n\n"
        
        if context and "error" not in context:
            prompt += "Available Data:\n"
            prompt += json.dumps(context, indent=2, default=str)
        elif context and "error" in context:
            prompt += f"Note: {context['error']}\n"
        else:
            prompt += "Note: No specific company data found for this query.\n"
        
        prompt += "\nPlease provide a comprehensive answer based on the available data and your knowledge of the Indian stock market."
        
        return prompt

    def explain_fundamental_score(
        self,
        ticker: str,
        score: float,
        factors: dict[str, Any],
    ) -> str:
        """
        Explain why a company received a particular fundamental score.
        
        Args:
            ticker: Stock ticker
            score: The fundamental score (0-100)
            factors: Dictionary of factors that contributed to the score
        
        Returns:
            Human-readable explanation
        """
        try:
            prompt = f"""
The company {ticker} received a fundamental score of {score}/100.

Contributing factors:
{json.dumps(factors, indent=2, default=str)}

Please explain in simple terms:
1. What this score means for an investor
2. Which factors are most important and why
3. Whether this is a strong or weak score in context
4. Any concerns or positive signals
"""
            
            response = self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are a financial analyst. Explain fundamental scores in simple, actionable terms.",
                temperature=0.5,  # More conservative for factual explanations
                max_tokens=1024,
                fallback_to_groq=True,
            )
            
            return response.content.strip()

        except Exception as e:
            logger.error(f"Error explaining fundamental score: {e}")
            return f"Could not generate explanation: {str(e)}"

    def explain_technical_signal(
        self,
        ticker: str,
        signal: str,
        indicators: dict[str, Any],
    ) -> str:
        """
        Explain a technical signal based on indicator values.
        
        Args:
            ticker: Stock ticker
            signal: The signal name (e.g., "BUY", "SELL", "HOLD")
            indicators: Technical indicators that generated the signal
        
        Returns:
            Human-readable explanation
        """
        try:
            prompt = f"""
The stock {ticker} is showing a "{signal}" signal based on technical analysis.

Current indicators:
{json.dumps(indicators, indent=2, default=str)}

Please explain:
1. What this signal means
2. Which indicators are most important for this signal
3. What price levels should investors watch
4. Potential risks or confirmations needed
"""
            
            response = self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are a technical analyst. Explain trading signals clearly and practically.",
                temperature=0.5,
                max_tokens=1024,
                fallback_to_groq=True,
            )
            
            return response.content.strip()

        except Exception as e:
            logger.error(f"Error explaining technical signal: {e}")
            return f"Could not generate explanation: {str(e)}"

    def compare_stocks(self, tickers: list[str]) -> str:
        """
        Compare multiple stocks and provide analysis.
        
        Args:
            tickers: List of stock tickers to compare
        
        Returns:
            Comparison analysis
        """
        try:
            contexts = {}
            for ticker in tickers:
                contexts[ticker] = self._get_company_context(ticker)

            prompt = f"""
Please compare these Indian stocks: {', '.join(tickers)}

Data available:
{json.dumps(contexts, indent=2, default=str)}

Provide a structured comparison covering:
1. Financial health (P/E, debt, profitability)
2. Growth prospects
3. Valuation relative to peers
4. Risk factors
5. Investment recommendation for different investor types
"""
            
            response = self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are an equity analyst. Provide detailed stock comparisons.",
                temperature=0.7,
                max_tokens=2048,
                fallback_to_groq=True,
            )
            
            return response.content.strip()

        except Exception as e:
            logger.error(f"Error comparing stocks: {e}")
            return f"Could not generate comparison: {str(e)}"


def get_financial_assistant(db: Session) -> FinancialAssistant:
    """Create a financial assistant instance."""
    return FinancialAssistant(db)
