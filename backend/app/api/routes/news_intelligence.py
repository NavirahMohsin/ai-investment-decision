"""News intelligence API endpoints for sentiment, events, and impact analysis."""

from __future__ import annotations

import logging
from typing import Optional
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.db.models import NewsArticle, Company, Sector
from app.services.news_intelligence import NewsIntelligenceService
from app.services.news_signals import NewsSignalService
from app.services.news_analysis import EventCategory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/news", tags=["news_intelligence"])


# Response schemas
class SentimentInfo(BaseModel):
    """Sentiment analysis info."""
    score: float = Field(..., ge=-1, le=1, description="Score from -1 (negative) to 1 (positive)")
    confidence: float = Field(..., ge=0, le=1, description="Confidence 0-1")
    label: str = Field(..., description="negative, neutral, or positive")


class EventInfo(BaseModel):
    """Event classification info."""
    category: str = Field(..., description="Event category")
    confidence: float = Field(..., ge=0, le=1, description="Classification confidence")


class ArticleIntelligence(BaseModel):
    """Complete article intelligence."""
    id: int
    headline: str
    sentiment: SentimentInfo
    event: EventInfo
    market_impact_score: float = Field(..., ge=0, le=1, description="Market impact 0-1")
    published_at: Optional[str]


class SentimentPeriodInfo(BaseModel):
    """Sentiment aggregated over period."""
    period_start: str
    period_end: str
    avg_sentiment: float = Field(..., ge=-1, le=1)
    sentiment_trend: str
    positive_count: int
    negative_count: int
    neutral_count: int
    high_impact_count: int
    article_count: int


class NewsEventInfo(BaseModel):
    """News event with context."""
    article_id: int
    headline: str
    published_at: Optional[str]
    sentiment_score: float = Field(..., ge=-1, le=1)
    event_category: str
    market_impact_score: float = Field(..., ge=0, le=1)
    companies: list[str]


class AnalysisStats(BaseModel):
    """Analytics statistics."""
    total_analyzed: int
    sentiment_distribution: dict
    event_categories: dict
    high_impact_articles: int


class SectorSentimentInfo(BaseModel):
    """Sector-level sentiment."""
    sector_id: int
    avg_sentiment: float = Field(..., ge=-1, le=1)
    sentiment_trend: str
    article_count: int
    positive_count: int
    negative_count: int
    neutral_count: int


class NewsCorrelationInfo(BaseModel):
    """Correlation between news and price."""
    company_id: int
    analysis: str
    avg_sentiment: Optional[float]
    avg_return: Optional[float]
    correlation: Optional[float]
    interpretation: Optional[str]
    article_count: Optional[int]
    price_points: Optional[int]


def get_intelligence_service(db: Session = Depends(get_db)) -> NewsIntelligenceService:
    """Get news intelligence service."""
    return NewsIntelligenceService(db, use_finbert=False)


def get_signal_service(db: Session = Depends(get_db)) -> NewsSignalService:
    """Get news signal service."""
    return NewsSignalService(db)


@router.post("/analyze/{article_id}")
async def analyze_article(
    article_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Analyze a single article.
    
    Args:
        article_id: ID of article to analyze
        
    Returns:
        Analysis result
    """
    article = db.query(NewsArticle).filter(NewsArticle.id == article_id).first()
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    service = NewsIntelligenceService(db, use_finbert=False)
    success = service.analyze_article(
        article_id,
        article.headline,
        article.summary,
        None
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Analysis failed")
    
    # Refresh article to get updated analysis
    db.refresh(article)
    
    return {
        "id": article.id,
        "headline": article.headline,
        "sentiment": {
            "score": float(article.sentiment_score) if article.sentiment_score is not None else 0.0,
            "confidence": float(article.sentiment_confidence) if article.sentiment_confidence is not None else 0.0,
            "label": _score_to_label(float(article.sentiment_score) if article.sentiment_score is not None else 0.0),
        },
        "event": {
            "category": article.event_category or "other",
            "confidence": float(article.event_confidence) if article.event_confidence is not None else 0.0,
        },
        "market_impact_score": float(article.market_impact_score) if article.market_impact_score is not None else 0.0,
    }


@router.post("/analyze/batch")
async def analyze_batch(
    limit: int = Query(100, ge=1, le=1000),
    skip_analyzed: bool = Query(True),
    db: Session = Depends(get_db),
) -> dict:
    """Analyze articles in batch.
    
    Args:
        limit: Maximum articles to analyze
        skip_analyzed: Skip already-analyzed articles
        
    Returns:
        Batch analysis results
    """
    service = NewsIntelligenceService(db, use_finbert=False)
    
    # Get unanalyzed articles
    query = select(NewsArticle)
    if skip_analyzed:
        query = query.where(NewsArticle.sentiment_score.is_(None))
    query = query.limit(limit)
    
    articles = db.scalars(query).all()
    
    if not articles:
        return {
            "total": 0,
            "analyzed": 0,
            "failed": 0,
            "message": "No articles to analyze"
        }
    
    analyzed = 0
    failed = 0
    
    for article in articles:
        success = service.analyze_article(
            article.id,
            article.headline,
            article.summary,
            None
        )
        if success:
            analyzed += 1
        else:
            failed += 1
    
    return {
        "total": len(articles),
        "analyzed": analyzed,
        "failed": failed,
        "message": f"Analyzed {analyzed} articles"
    }


@router.get("/company/{company_id}/sentiment", response_model=SentimentPeriodInfo)
async def get_company_sentiment(
    company_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    signal_service: NewsSignalService = Depends(get_signal_service),
) -> dict:
    """Get aggregated sentiment for a company.
    
    Args:
        company_id: Company ID
        days: Number of days to aggregate
        
    Returns:
        Sentiment period info
    """
    # Verify company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    period = signal_service.aggregate_sentiment_period(company_id, days=days)
    return period.to_dict()


@router.get("/company/{company_id}/sentiment-timeline", response_model=list[SentimentPeriodInfo])
async def get_company_sentiment_timeline(
    company_id: int,
    start_date: date = Query(..., description="Start date YYYY-MM-DD"),
    end_date: date = Query(..., description="End date YYYY-MM-DD"),
    interval_days: int = Query(7, ge=1, le=90, description="Aggregation interval"),
    db: Session = Depends(get_db),
    signal_service: NewsSignalService = Depends(get_signal_service),
) -> list[dict]:
    """Get sentiment timeline for company.
    
    Args:
        company_id: Company ID
        start_date: Start date
        end_date: End date
        interval_days: Aggregation interval (7=weekly, 1=daily)
        
    Returns:
        List of sentiment periods
    """
    # Verify company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    if start_date >= end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    
    timeline = signal_service.get_sentiment_timeline(
        company_id,
        start_date=start_date,
        end_date=end_date,
        interval_days=interval_days
    )
    
    return [p.to_dict() for p in timeline]


@router.get("/company/{company_id}/timeline", response_model=list[NewsEventInfo])
async def get_company_news_timeline(
    company_id: int,
    start_date: Optional[date] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[date] = Query(None, description="End date YYYY-MM-DD"),
    min_impact: float = Query(0.0, ge=0, le=1),
    category: Optional[str] = Query(None, pattern="^(earnings|acquisition|litigation|regulatory|management|partnership|product|other)$"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    signal_service: NewsSignalService = Depends(get_signal_service),
) -> list[dict]:
    """Get news timeline for company.
    
    Args:
        company_id: Company ID
        start_date: Optional start date
        end_date: Optional end date
        min_impact: Minimum market impact score
        category: Optional event category filter
        limit: Maximum events
        
    Returns:
        List of news events
    """
    # Verify company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    categories = [category] if category else None
    
    events = signal_service.get_news_timeline(
        company_id,
        start_date=start_date,
        end_date=end_date,
        min_impact=min_impact,
        categories=categories,
        limit=limit
    )
    
    return [e.to_dict() for e in events]


@router.get("/articles/sentiment/{sentiment}", response_model=list[ArticleIntelligence])
async def get_articles_by_sentiment(
    sentiment: str = Path(..., pattern="^(positive|negative|neutral)$"),
    min_confidence: float = Query(0.5, ge=0, le=1),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    service: NewsIntelligenceService = Depends(get_intelligence_service),
) -> list[dict]:
    """Get articles filtered by sentiment.
    
    Args:
        sentiment: positive, negative, or neutral
        min_confidence: Minimum confidence threshold
        limit: Maximum results
        
    Returns:
        List of articles with intelligence
    """
    articles = service.get_articles_by_sentiment(
        sentiment=sentiment,
        min_confidence=min_confidence,
        limit=limit
    )
    
    return [
        {
            "id": a.id,
            "headline": a.headline,
            "sentiment": {
                "score": float(a.sentiment_score) if a.sentiment_score is not None else 0.0,
                "confidence": float(a.sentiment_confidence) if a.sentiment_confidence is not None else 0.0,
                "label": sentiment,
            },
            "event": {
                "category": a.event_category or "other",
                "confidence": float(a.event_confidence) if a.event_confidence is not None else 0.0,
            },
            "market_impact_score": float(a.market_impact_score) if a.market_impact_score is not None else 0.0,
            "published_at": a.published_at.isoformat() if a.published_at else None,
        }
        for a in articles
    ]


@router.get("/articles/event/{category}", response_model=list[ArticleIntelligence])
async def get_articles_by_event(
    category: str = Path(..., pattern="^(earnings|acquisition|litigation|regulatory|management|partnership|product|other)$"),
    min_confidence: float = Query(0.5, ge=0, le=1),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    service: NewsIntelligenceService = Depends(get_intelligence_service),
) -> list[dict]:
    """Get articles filtered by event category.
    
    Args:
        category: Event category
        min_confidence: Minimum confidence threshold
        limit: Maximum results
        
    Returns:
        List of articles with intelligence
    """
    articles = service.get_articles_by_event_category(
        category=category,
        min_confidence=min_confidence,
        limit=limit
    )
    
    return [
        {
            "id": a.id,
            "headline": a.headline,
            "sentiment": {
                "score": float(a.sentiment_score) if a.sentiment_score is not None else 0.0,
                "confidence": float(a.sentiment_confidence) if a.sentiment_confidence is not None else 0.0,
                "label": _score_to_label(float(a.sentiment_score) if a.sentiment_score is not None else 0.0),
            },
            "event": {
                "category": a.event_category or "other",
                "confidence": float(a.event_confidence) if a.event_confidence is not None else 0.0,
            },
            "market_impact_score": float(a.market_impact_score) if a.market_impact_score is not None else 0.0,
            "published_at": a.published_at.isoformat() if a.published_at else None,
        }
        for a in articles
    ]


@router.get("/articles/impact", response_model=list[ArticleIntelligence])
async def get_high_impact_articles(
    min_impact: float = Query(0.7, ge=0, le=1),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    service: NewsIntelligenceService = Depends(get_intelligence_service),
) -> list[dict]:
    """Get high-impact articles (market-moving potential).
    
    Args:
        min_impact: Minimum market impact score
        limit: Maximum results
        
    Returns:
        List of articles with intelligence
    """
    articles = service.get_high_impact_articles(
        min_impact=min_impact,
        limit=limit
    )
    
    return [
        {
            "id": a.id,
            "headline": a.headline,
            "sentiment": {
                "score": float(a.sentiment_score) if a.sentiment_score is not None else 0.0,
                "confidence": float(a.sentiment_confidence) if a.sentiment_confidence is not None else 0.0,
                "label": _score_to_label(float(a.sentiment_score) if a.sentiment_score is not None else 0.0),
            },
            "event": {
                "category": a.event_category or "other",
                "confidence": float(a.event_confidence) if a.event_confidence is not None else 0.0,
            },
            "market_impact_score": float(a.market_impact_score) if a.market_impact_score is not None else 0.0,
            "published_at": a.published_at.isoformat() if a.published_at else None,
        }
        for a in articles
    ]


@router.get("/company/{company_id}/articles", response_model=list[ArticleIntelligence])
async def get_company_articles(
    company_id: int,
    sentiment: Optional[str] = Query(None, pattern="^(positive|negative|neutral)$"),
    category: Optional[str] = Query(None),
    min_impact: Optional[float] = Query(None, ge=0, le=1),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    service: NewsIntelligenceService = Depends(get_intelligence_service),
) -> list[dict]:
    """Get analyzed articles for a company.
    
    Args:
        company_id: Company ID
        sentiment: Optional sentiment filter
        category: Optional event category filter
        min_impact: Optional minimum market impact
        limit: Maximum results
        
    Returns:
        List of company-related articles with intelligence
    """
    # Verify company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    results = service.get_articles_for_company(
        company_id=company_id,
        sentiment=sentiment,
        category=category,
        min_impact=min_impact,
        limit=limit
    )
    
    return [
        {
            "id": a[0].id,
            "headline": a[0].headline,
            "sentiment": {
                "score": float(a[0].sentiment_score) if a[0].sentiment_score is not None else 0.0,
                "confidence": float(a[0].sentiment_confidence) if a[0].sentiment_confidence is not None else 0.0,
                "label": _score_to_label(float(a[0].sentiment_score) if a[0].sentiment_score is not None else 0.0),
            },
            "event": {
                "category": a[0].event_category or "other",
                "confidence": float(a[0].event_confidence) if a[0].event_confidence is not None else 0.0,
            },
            "market_impact_score": float(a[0].market_impact_score) if a[0].market_impact_score is not None else 0.0,
            "published_at": a[0].published_at.isoformat() if a[0].published_at else None,
        }
        for a in results
    ]


@router.get("/sector/{sector_id}/sentiment", response_model=SectorSentimentInfo)
async def get_sector_sentiment(
    sector_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    signal_service: NewsSignalService = Depends(get_signal_service),
) -> dict:
    """Get aggregated sentiment for a sector.
    
    Args:
        sector_id: Sector ID
        days: Number of days to aggregate
        
    Returns:
        Sector sentiment info
    """
    # Verify sector exists
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Sector not found")
    
    result = signal_service.get_sector_sentiment(sector_id, days=days)
    return result


@router.get("/company/{company_id}/news-price-correlation", response_model=NewsCorrelationInfo)
async def get_news_price_correlation(
    company_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    signal_service: NewsSignalService = Depends(get_signal_service),
) -> dict:
    """Get correlation between news sentiment and price movements.
    
    Args:
        company_id: Company ID
        days: Days to analyze
        
    Returns:
        Correlation analysis
    """
    # Verify company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    result = signal_service.correlate_news_to_price(company_id, days=days)
    return result


@router.get("/analytics", response_model=AnalysisStats)
async def get_analytics(
    db: Session = Depends(get_db),
    service: NewsIntelligenceService = Depends(get_intelligence_service),
) -> dict:
    """Get news analysis statistics.
    
    Returns:
        Analytics summary
    """
    stats = service.get_analytics_summary()
    
    return {
        "total_analyzed": stats["total_analyzed"],
        "sentiment_distribution": stats["sentiment_distribution"],
        "event_categories": stats["event_categories"],
        "high_impact_articles": stats["high_impact_articles"],
    }


def _score_to_label(score: float) -> str:
    """Convert sentiment score to label."""
    if score > 0.1:
        return "positive"
    elif score < -0.1:
        return "negative"
    else:
        return "neutral"


@router.get("/debug/stats")
async def debug_stats(db: Session = Depends(get_db)) -> dict:
    """Debug endpoint: show article statistics."""
    total = db.query(NewsArticle).count()
    analyzed = db.query(NewsArticle).filter(NewsArticle.sentiment_score.isnot(None)).count()
    
    return {
        "total_articles": total,
        "analyzed_articles": analyzed,
        "unanalyzed_articles": total - analyzed,
        "next_step": "POST /api/v1/news/analyze/batch to analyze unanalyzed articles"
    }


@router.get("")
async def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    company: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    """List recent articles, optionally filtered by company symbol."""
    
    if company:
        # Find company by symbol
        companies = db.query(Company).filter(Company.symbol.ilike(company)).all()
        if not companies:
            return {"items": [], "pagination": {"total": 0, "page": page, "page_size": page_size, "total_pages": 0}}
        
        company_ids = [c.id for c in companies]
        
        # Get articles linked to these companies
        articles = db.query(NewsArticle).join(
            NewsArticleCompany
        ).filter(NewsArticleCompany.company_id.in_(company_ids)).limit(limit).all()
    else:
        articles = db.query(NewsArticle).limit(limit).all()
    
    return {
        "items": [
            {
                "id": a.id,
                "headline": a.headline,
                "sentiment": {
                    "score": float(a.sentiment_score) if a.sentiment_score is not None else 0.0,
                    "confidence": float(a.sentiment_confidence) if a.sentiment_confidence is not None else 0.0,
                    "label": _score_to_label(float(a.sentiment_score) if a.sentiment_score is not None else 0.0),
                },
                "event": {
                    "category": a.event_category or "other",
                    "confidence": float(a.event_confidence) if a.event_confidence is not None else 0.0,
                },
                "market_impact_score": float(a.market_impact_score) if a.market_impact_score is not None else 0.0,
                "published_at": a.published_at.isoformat() if a.published_at else None,
            }
            for a in articles
        ],
        "pagination": {
            "total": len(articles),
            "page": page,
            "page_size": page_size,
            "total_pages": 1
        }
    }


@router.post("/refresh")
async def refresh_news(
    db: Session = Depends(get_db),
) -> dict:
    """Manually trigger news ingestion and analysis.
    
    Returns:
        Status of ingestion
    """
    from app.services.news.ingestion import ingest_all_active_sources
    
    try:
        results = ingest_all_active_sources()
        
        total_discovered = sum(r.articles_discovered for r in results)
        total_inserted = sum(r.articles_inserted for r in results)
        total_analyzed = total_inserted  # All inserted articles are analyzed during ingestion
        
        return {
            "status": "success",
            "message": f"Ingested {total_inserted} new articles",
            "discovered": total_discovered,
            "inserted": total_inserted,
            "analyzed": total_analyzed,
            "sources": len(results)
        }
    except Exception as e:
        logger.error(f"Error refreshing news: {e}")
        return {
            "status": "error",
            "message": str(e),
            "discovered": 0,
            "inserted": 0,
            "analyzed": 0,
            "sources": 0
        }

