"""News signal aggregation and correlation with market data.

Provides:
- Sentiment aggregation over time periods
- News timelines with events
- Correlation between news sentiment and price movements
- Sector-level news analysis
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import Optional
import logging

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import NewsArticle, NewsArticleCompany, Company, DailyMarketData, Sector
from app.services.news_analysis import EventCategory

logger = logging.getLogger(__name__)


class NewsSentimentPeriod:
    """Aggregated sentiment over a time period."""
    
    def __init__(
        self,
        period_start: date,
        period_end: date,
        avg_sentiment: float,
        positive_count: int,
        negative_count: int,
        neutral_count: int,
        high_impact_count: int,
        article_count: int,
    ):
        self.period_start = period_start
        self.period_end = period_end
        self.avg_sentiment = avg_sentiment
        self.positive_count = positive_count
        self.negative_count = negative_count
        self.neutral_count = neutral_count
        self.high_impact_count = high_impact_count
        self.article_count = article_count
        
        # Calculate sentiment trend
        if article_count > 0:
            self.sentiment_trend = "positive" if avg_sentiment > 0.1 else ("negative" if avg_sentiment < -0.1 else "neutral")
        else:
            self.sentiment_trend = "no_data"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "avg_sentiment": float(self.avg_sentiment),
            "sentiment_trend": self.sentiment_trend,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "neutral_count": self.neutral_count,
            "high_impact_count": self.high_impact_count,
            "article_count": self.article_count,
        }


class NewsEvent:
    """Single news event with context."""
    
    def __init__(
        self,
        article_id: int,
        headline: str,
        published_at: Optional[datetime],
        sentiment_score: Optional[float],
        event_category: Optional[str],
        market_impact_score: Optional[float],
        companies: list[str],
    ):
        self.article_id = article_id
        self.headline = headline
        self.published_at = published_at
        self.sentiment_score = sentiment_score or 0.0
        self.event_category = event_category or "other"
        self.market_impact_score = market_impact_score or 0.0
        self.companies = companies
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "article_id": self.article_id,
            "headline": self.headline,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "sentiment_score": float(self.sentiment_score),
            "event_category": self.event_category,
            "market_impact_score": float(self.market_impact_score),
            "companies": self.companies,
        }


class NewsSignalService:
    """Service for aggregating and analyzing news signals."""
    
    def __init__(self, db: Session):
        """Initialize service.
        
        Args:
            db: SQLAlchemy session
        """
        self.db = db
    
    def aggregate_sentiment_period(
        self,
        company_id: int,
        days: int = 30,
        end_date: Optional[date] = None,
    ) -> NewsSentimentPeriod:
        """Aggregate sentiment for a company over a time period.
        
        Args:
            company_id: Company ID
            days: Number of days to look back
            end_date: End date (default: today)
            
        Returns:
            NewsSentimentPeriod with aggregated metrics
        """
        if end_date is None:
            end_date = date.today()
        
        start_date = end_date - timedelta(days=days)
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
        
        # Get articles for company in period
        articles = self.db.scalars(
            select(NewsArticle)
            .join(NewsArticleCompany, NewsArticle.id == NewsArticleCompany.article_id)
            .where(NewsArticleCompany.company_id == company_id)
            .where(NewsArticle.published_at >= start_dt)
            .where(NewsArticle.published_at <= end_dt)
            .where(NewsArticle.sentiment_score.isnot(None))
        ).all()
        
        # Calculate aggregates
        if not articles:
            return NewsSentimentPeriod(
                period_start=start_date,
                period_end=end_date,
                avg_sentiment=0.0,
                positive_count=0,
                negative_count=0,
                neutral_count=0,
                high_impact_count=0,
                article_count=0,
            )
        
        sentiments = [float(a.sentiment_score) for a in articles if a.sentiment_score]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
        
        positive_count = sum(1 for a in articles if a.sentiment_score and float(a.sentiment_score) > 0.1)
        negative_count = sum(1 for a in articles if a.sentiment_score and float(a.sentiment_score) < -0.1)
        neutral_count = sum(1 for a in articles if a.sentiment_score and 
                          -0.1 <= float(a.sentiment_score) <= 0.1)
        high_impact_count = sum(1 for a in articles if a.market_impact_score and 
                               float(a.market_impact_score) > 0.7)
        
        return NewsSentimentPeriod(
            period_start=start_date,
            period_end=end_date,
            avg_sentiment=avg_sentiment,
            positive_count=positive_count,
            negative_count=negative_count,
            neutral_count=neutral_count,
            high_impact_count=high_impact_count,
            article_count=len(articles),
        )
    
    def get_sentiment_timeline(
        self,
        company_id: int,
        start_date: date,
        end_date: date,
        interval_days: int = 7,
    ) -> list[NewsSentimentPeriod]:
        """Get sentiment timeline for company over period with intervals.
        
        Args:
            company_id: Company ID
            start_date: Timeline start
            end_date: Timeline end
            interval_days: Aggregation interval (7 for weekly, 1 for daily)
            
        Returns:
            List of NewsSentimentPeriod for each interval
        """
        timeline = []
        current_start = start_date
        
        while current_start < end_date:
            current_end = min(current_start + timedelta(days=interval_days), end_date)
            period = self.aggregate_sentiment_period(
                company_id=company_id,
                days=interval_days,
                end_date=current_end,
            )
            timeline.append(period)
            current_start = current_end
        
        return timeline
    
    def get_news_timeline(
        self,
        company_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        min_impact: float = 0.0,
        categories: Optional[list[str]] = None,
        limit: int = 100,
    ) -> list[NewsEvent]:
        """Get timeline of news events for company.
        
        Args:
            company_id: Company ID
            start_date: Start date (default: 90 days ago)
            end_date: End date (default: today)
            min_impact: Minimum market impact score
            categories: Filter by event categories
            limit: Maximum events to return
            
        Returns:
            List of NewsEvent objects
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=90)
        
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
        
        # Build query
        query = (
            select(NewsArticle, NewsArticleCompany)
            .join(NewsArticleCompany, NewsArticle.id == NewsArticleCompany.article_id)
            .where(NewsArticleCompany.company_id == company_id)
            .where(NewsArticle.published_at >= start_dt)
            .where(NewsArticle.published_at <= end_dt)
            .where(NewsArticle.market_impact_score >= Decimal(str(min_impact)))
        )
        
        # Filter by categories if specified
        if categories:
            query = query.where(NewsArticle.event_category.in_(categories))
        
        # Order by published date descending
        query = query.order_by(NewsArticle.published_at.desc()).limit(limit)
        
        results = self.db.execute(query).all()
        
        # Build events
        events = []
        for article, company_match in results:
            # Get all companies for this article
            article_companies = self.db.scalars(
                select(Company)
                .join(NewsArticleCompany, Company.id == NewsArticleCompany.company_id)
                .where(NewsArticleCompany.article_id == article.id)
            ).all()
            
            company_names = [c.symbol for c in article_companies]
            
            event = NewsEvent(
                article_id=article.id,
                headline=article.headline,
                published_at=article.published_at,
                sentiment_score=float(article.sentiment_score) if article.sentiment_score else None,
                event_category=article.event_category,
                market_impact_score=float(article.market_impact_score) if article.market_impact_score else None,
                companies=company_names,
            )
            events.append(event)
        
        return events
    
    def get_sector_sentiment(
        self,
        sector_id: int,
        days: int = 30,
    ) -> dict:
        """Get aggregated sentiment for a sector.
        
        Args:
            sector_id: Sector ID
            days: Number of days to look back
            
        Returns:
            Dictionary with sector sentiment metrics
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
        
        # Get all companies in sector
        companies = self.db.scalars(
            select(Company).where(Company.sector_id == sector_id)
        ).all()
        
        if not companies:
            return {
                "sector_id": sector_id,
                "avg_sentiment": 0.0,
                "sentiment_trend": "no_data",
                "article_count": 0,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
            }
        
        company_ids = [c.id for c in companies]
        
        # Get articles for all companies in sector
        articles = self.db.scalars(
            select(NewsArticle)
            .join(NewsArticleCompany, NewsArticle.id == NewsArticleCompany.article_id)
            .where(NewsArticleCompany.company_id.in_(company_ids))
            .where(NewsArticle.published_at >= start_dt)
            .where(NewsArticle.published_at <= end_dt)
            .where(NewsArticle.sentiment_score.isnot(None))
        ).all()
        
        if not articles:
            return {
                "sector_id": sector_id,
                "avg_sentiment": 0.0,
                "sentiment_trend": "no_data",
                "article_count": 0,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
            }
        
        sentiments = [float(a.sentiment_score) for a in articles if a.sentiment_score]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
        
        positive_count = sum(1 for a in articles if a.sentiment_score and float(a.sentiment_score) > 0.1)
        negative_count = sum(1 for a in articles if a.sentiment_score and float(a.sentiment_score) < -0.1)
        neutral_count = sum(1 for a in articles if a.sentiment_score and 
                          -0.1 <= float(a.sentiment_score) <= 0.1)
        
        sentiment_trend = "positive" if avg_sentiment > 0.1 else ("negative" if avg_sentiment < -0.1 else "neutral")
        
        return {
            "sector_id": sector_id,
            "avg_sentiment": float(avg_sentiment),
            "sentiment_trend": sentiment_trend,
            "article_count": len(articles),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
        }
    
    def correlate_news_to_price(
        self,
        company_id: int,
        days: int = 30,
    ) -> dict:
        """Correlate news sentiment with price movements.
        
        Args:
            company_id: Company ID
            days: Days to analyze
            
        Returns:
            Correlation analysis
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Get price data
        price_data = self.db.scalars(
            select(DailyMarketData)
            .where(DailyMarketData.company_id == company_id)
            .where(DailyMarketData.trading_date >= start_date)
            .where(DailyMarketData.trading_date <= end_date)
            .order_by(DailyMarketData.trading_date)
        ).all()
        
        if not price_data:
            return {
                "company_id": company_id,
                "analysis": "insufficient_price_data",
                "correlation": None,
            }
        
        # Calculate price returns
        prices = [float(p.close) for p in price_data]
        returns = [(prices[i+1] - prices[i]) / prices[i] for i in range(len(prices)-1)]
        avg_return = sum(returns) / len(returns) if returns else 0.0
        
        # Get news sentiment
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
        
        articles = self.db.scalars(
            select(NewsArticle)
            .join(NewsArticleCompany, NewsArticle.id == NewsArticleCompany.article_id)
            .where(NewsArticleCompany.company_id == company_id)
            .where(NewsArticle.published_at >= start_dt)
            .where(NewsArticle.published_at <= end_dt)
            .where(NewsArticle.sentiment_score.isnot(None))
        ).all()
        
        if not articles:
            return {
                "company_id": company_id,
                "analysis": "insufficient_news_data",
                "correlation": None,
            }
        
        sentiments = [float(a.sentiment_score) for a in articles if a.sentiment_score]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
        
        # Simple correlation indicator
        if len(returns) > 1:
            variance_return = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            variance_sentiment = sum((s - avg_sentiment) ** 2 for s in sentiments) / len(sentiments) if len(sentiments) > 1 else 0
            
            if variance_sentiment > 0 and variance_return > 0:
                covariance = sum(
                    (returns[min(i, len(returns)-1)] - avg_return) * (sentiments[min(i, len(sentiments)-1)] - avg_sentiment)
                    for i in range(max(len(returns), len(sentiments)))
                ) / max(len(returns), len(sentiments))
                
                correlation = covariance / (variance_sentiment ** 0.5 * variance_return ** 0.5) if (variance_sentiment ** 0.5 * variance_return ** 0.5) > 0 else 0
            else:
                correlation = 0.0
        else:
            correlation = 0.0
        
        return {
            "company_id": company_id,
            "analysis": "complete",
            "avg_sentiment": float(avg_sentiment),
            "avg_return": float(avg_return),
            "correlation": float(correlation),
            "interpretation": (
                "positive_correlation" if correlation > 0.3 else
                "negative_correlation" if correlation < -0.3 else
                "weak_correlation"
            ),
            "article_count": len(articles),
            "price_points": len(price_data),
        }
