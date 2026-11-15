"""News intelligence service integrating analysis with article ingestion.

Handles:
- Analyzing articles when ingested
- Storing analysis results
- Retrieving analyzed articles by sentiment/category/impact
- Batch analysis operations
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import NewsArticle, Company, NewsArticleCompany
from app.services.news_analysis import NewsAnalyzer, EventCategory

logger = logging.getLogger(__name__)


class NewsIntelligenceService:
    """Service for analyzing and storing news intelligence."""
    
    def __init__(self, db_session: Session, use_finbert: bool = False):
        """Initialize intelligence service.
        
        Args:
            db_session: SQLAlchemy database session
            use_finbert: Use FinBERT for better sentiment (slower)
        """
        self.db = db_session
        self.analyzer = NewsAnalyzer(use_finbert=use_finbert)
    
    def analyze_article(
        self,
        article_id: int,
        headline: str,
        summary: str | None = None,
        content: str | None = None,
    ) -> bool:
        """Analyze a single article and store results.
        
        Args:
            article_id: ID of article to analyze
            headline: Article headline
            summary: Article summary
            content: Full article content (optional)
            
        Returns:
            True if analysis stored successfully, False otherwise
        """
        try:
            # Perform analysis
            analysis = self.analyzer.analyze(headline, summary, content)
            
            # Get article and update with analysis results
            article = self.db.scalars(
                select(NewsArticle).where(NewsArticle.id == article_id)
            ).first()
            
            if not article:
                logger.warning(f"Article {article_id} not found")
                return False
            
            # Store results
            article.sentiment_score = Decimal(str(analysis.sentiment.score))
            article.sentiment_confidence = Decimal(str(analysis.sentiment.confidence))
            article.sentiment_model = analysis.sentiment.model_used
            article.event_category = analysis.event_category.category.value
            article.event_confidence = Decimal(str(analysis.event_category.confidence))
            article.market_impact_score = Decimal(str(analysis.market_impact_score))
            article.analysis_version = analysis.analysis_version
            article.analyzed_at = datetime.now(timezone.utc)
            
            self.db.commit()
            
            logger.info(
                f"Analyzed article {article_id}: "
                f"sentiment={analysis.sentiment.label} ({analysis.sentiment.score:.2f}), "
                f"event={analysis.event_category.category.value}, "
                f"impact={analysis.market_impact_score:.2f}"
            )
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to analyze article {article_id}: {e}")
            self.db.rollback()
            return False
    
    def analyze_batch(
        self,
        limit: int = 100,
        skip_analyzed: bool = True,
    ) -> dict[str, int]:
        """Analyze articles in batch.
        
        Args:
            limit: Maximum articles to analyze
            skip_analyzed: Skip articles that have already been analyzed
            
        Returns:
            Dictionary with success/failure counts
        """
        # Get unanalyzed articles
        query = select(NewsArticle)
        
        if skip_analyzed:
            query = query.where(NewsArticle.sentiment_score.is_(None))
        
        articles = self.db.scalars(
            query.order_by(NewsArticle.discovered_at.desc()).limit(limit)
        ).all()
        
        results = {
            "total": len(articles),
            "analyzed": 0,
            "failed": 0,
        }
        
        for article in articles:
            success = self.analyze_article(
                article.id,
                article.headline,
                article.summary,
                None  # Don't have full content in this context
            )
            
            if success:
                results["analyzed"] += 1
            else:
                results["failed"] += 1
        
        logger.info(
            f"Batch analysis complete: {results['analyzed']} analyzed, "
            f"{results['failed']} failed out of {results['total']}"
        )
        
        return results
    
    def get_articles_by_sentiment(
        self,
        sentiment: str,  # "positive", "negative", "neutral"
        min_confidence: float = 0.5,
        limit: int = 50,
    ) -> list[NewsArticle]:
        """Get articles filtered by sentiment.
        
        Args:
            sentiment: "positive", "negative", or "neutral"
            min_confidence: Minimum sentiment confidence
            limit: Maximum articles to return
            
        Returns:
            List of NewsArticle objects
        """
        # Map sentiment to score ranges
        if sentiment == "positive":
            score_filter = NewsArticle.sentiment_score > Decimal("0.1")
        elif sentiment == "negative":
            score_filter = NewsArticle.sentiment_score < Decimal("-0.1")
        else:  # neutral
            score_filter = (
                (NewsArticle.sentiment_score >= Decimal("-0.1")) &
                (NewsArticle.sentiment_score <= Decimal("0.1"))
            )
        
        articles = self.db.scalars(
            select(NewsArticle)
            .where(score_filter)
            .where(NewsArticle.sentiment_confidence >= Decimal(str(min_confidence)))
            .order_by(NewsArticle.published_at.desc())
            .limit(limit)
        ).all()
        
        return articles
    
    def get_articles_by_event_category(
        self,
        category: EventCategory | str,
        min_confidence: float = 0.5,
        limit: int = 50,
    ) -> list[NewsArticle]:
        """Get articles filtered by event category.
        
        Args:
            category: EventCategory enum or string
            min_confidence: Minimum classification confidence
            limit: Maximum articles to return
            
        Returns:
            List of NewsArticle objects
        """
        if isinstance(category, EventCategory):
            category_str = category.value
        else:
            category_str = category
        
        articles = self.db.scalars(
            select(NewsArticle)
            .where(NewsArticle.event_category == category_str)
            .where(NewsArticle.event_confidence >= Decimal(str(min_confidence)))
            .order_by(NewsArticle.published_at.desc())
            .limit(limit)
        ).all()
        
        return articles
    
    def get_high_impact_articles(
        self,
        min_impact: float = 0.7,
        limit: int = 50,
    ) -> list[NewsArticle]:
        """Get high-impact articles (market-moving potential).
        
        Args:
            min_impact: Minimum market impact score
            limit: Maximum articles to return
            
        Returns:
            List of NewsArticle objects
        """
        articles = self.db.scalars(
            select(NewsArticle)
            .where(NewsArticle.market_impact_score >= Decimal(str(min_impact)))
            .order_by(NewsArticle.market_impact_score.desc())
            .limit(limit)
        ).all()
        
        return articles
    
    def get_articles_for_company(
        self,
        company_id: int,
        sentiment: str | None = None,
        category: EventCategory | str | None = None,
        min_impact: float | None = None,
        limit: int = 50,
    ) -> list[tuple[NewsArticle, NewsArticleCompany]]:
        """Get analyzed articles for a specific company.
        
        Args:
            company_id: Company ID to filter by
            sentiment: Optional sentiment filter
            category: Optional event category filter
            min_impact: Optional minimum impact score
            limit: Maximum articles to return
            
        Returns:
            List of (NewsArticle, NewsArticleCompany) tuples
        """
        query = (
            select(NewsArticle, NewsArticleCompany)
            .join(NewsArticleCompany, NewsArticle.id == NewsArticleCompany.article_id)
            .where(NewsArticleCompany.company_id == company_id)
        )
        
        # Apply sentiment filter if specified
        if sentiment:
            if sentiment == "positive":
                query = query.where(NewsArticle.sentiment_score > Decimal("0.1"))
            elif sentiment == "negative":
                query = query.where(NewsArticle.sentiment_score < Decimal("-0.1"))
            else:
                query = query.where(
                    (NewsArticle.sentiment_score >= Decimal("-0.1")) &
                    (NewsArticle.sentiment_score <= Decimal("0.1"))
                )
        
        # Apply category filter if specified
        if category:
            if isinstance(category, EventCategory):
                category_str = category.value
            else:
                category_str = category
            query = query.where(NewsArticle.event_category == category_str)
        
        # Apply impact filter if specified
        if min_impact is not None:
            query = query.where(
                NewsArticle.market_impact_score >= Decimal(str(min_impact))
            )
        
        # Order by recency and impact
        query = (
            query
            .order_by(NewsArticle.published_at.desc())
            .limit(limit)
        )
        
        results = self.db.execute(query).all()
        return results
    
    def get_analytics_summary(self) -> dict:
        """Get summary analytics of analyzed articles.
        
        Returns:
            Dictionary with analytics data
        """
        from sqlalchemy import func
        
        total_analyzed = self.db.scalar(
            select(func.count(NewsArticle.id))
            .where(NewsArticle.sentiment_score.isnot(None))
        ) or 0
        
        positive_count = self.db.scalar(
            select(func.count(NewsArticle.id))
            .where(NewsArticle.sentiment_score > Decimal("0.1"))
        ) or 0
        
        negative_count = self.db.scalar(
            select(func.count(NewsArticle.id))
            .where(NewsArticle.sentiment_score < Decimal("-0.1"))
        ) or 0
        
        neutral_count = self.db.scalar(
            select(func.count(NewsArticle.id))
            .where(
                (NewsArticle.sentiment_score >= Decimal("-0.1")) &
                (NewsArticle.sentiment_score <= Decimal("0.1"))
            )
        ) or 0
        
        # Count by event category
        category_counts = {}
        for category in EventCategory:
            count = self.db.scalar(
                select(func.count(NewsArticle.id))
                .where(NewsArticle.event_category == category.value)
            ) or 0
            category_counts[category.value] = count
        
        # High-impact articles
        high_impact = self.db.scalar(
            select(func.count(NewsArticle.id))
            .where(NewsArticle.market_impact_score >= Decimal("0.7"))
        ) or 0
        
        return {
            "total_analyzed": total_analyzed,
            "sentiment_distribution": {
                "positive": positive_count,
                "negative": negative_count,
                "neutral": neutral_count,
            },
            "event_categories": category_counts,
            "high_impact_articles": high_impact,
        }
