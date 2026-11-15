"""Financial news analysis and intelligence extraction.

Provides sentiment analysis, event classification, and market impact scoring
for news articles using transformers and heuristic methods.

Features:
- Financial sentiment analysis (FinBERT-based)
- Event category classification (earnings, M&A, litigation, regulatory, management)
- Market impact scoring
- Confidence score estimation
- Fallback to lightweight analysis for speed
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

# Optional imports for better models
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

logger = logging.getLogger(__name__)


class EventCategory(str, Enum):
    """News article event categories."""
    EARNINGS = "earnings"
    ACQUISITION = "acquisition"
    LITIGATION = "litigation"
    REGULATORY = "regulatory"
    MANAGEMENT = "management"
    PARTNERSHIP = "partnership"
    PRODUCT = "product"
    OTHER = "other"


@dataclass
class SentimentScore:
    """Sentiment analysis result."""
    score: float  # -1.0 (negative) to 1.0 (positive)
    label: str  # "negative", "neutral", "positive"
    confidence: float  # 0-1
    model_used: str  # "finbert" or "textblob"


@dataclass
class EventClassification:
    """Event category classification result."""
    category: EventCategory
    confidence: float  # 0-1
    reasoning: str  # Why this category was chosen


@dataclass
class NewsAnalysis:
    """Complete analysis of a news article."""
    headline: str
    summary: Optional[str]
    sentiment: SentimentScore
    event_category: EventClassification
    market_impact_score: float  # 0-1, relevance to stock price
    analysis_version: str  # Model version for reproducibility


class NewsAnalyzer:
    """Analyzes news articles for sentiment, events, and market impact."""
    
    def __init__(self, use_finbert: bool = True, cache_models: bool = True):
        """Initialize news analyzer.
        
        Args:
            use_finbert: Use fine-tuned FinBERT for sentiment (slower, more accurate)
                        Falls back to TextBlob if False or if model fails
            cache_models: Keep models in memory between calls
        """
        self.use_finbert = use_finbert
        self.cache_models = cache_models
        self.sentiment_pipeline = None
        self.finbert_tokenizer = None
        self.finbert_model = None
        
        # Event classification keywords
        self.event_keywords = {
            EventCategory.EARNINGS: [
                "earnings", "revenue", "profit", "quarterly", "q1", "q2", "q3", "q4",
                "fiscal", "eps", "dividend", "ebitda", "guidance", "forecast",
                "results", "announces", "reported", "beat", "miss", "margin"
            ],
            EventCategory.ACQUISITION: [
                "acquisition", "acquired", "acquire", "merger", "merged", "merge",
                "takeover", "buyout", "bought", "purchase", "deal", "stake"
            ],
            EventCategory.LITIGATION: [
                "lawsuit", "litigation", "sued", "sue", "court", "legal", "charges",
                "settlement", "complaint", "verdict", "breach", "violation"
            ],
            EventCategory.REGULATORY: [
                "regulatory", "regulation", "compliance", "fda", "sec", "approval",
                "license", "permit", "investigation", "sanction", "penalty", "fine"
            ],
            EventCategory.MANAGEMENT: [
                "ceo", "cfo", "executive", "resigned", "retired", "appointed",
                "promoted", "replaced", "leaves", "stepping down", "departure"
            ],
            EventCategory.PARTNERSHIP: [
                "partnership", "partner", "collaboration", "alliance", "joint venture",
                "agreement", "strategic", "cooperation", "venture"
            ],
            EventCategory.PRODUCT: [
                "product", "launch", "release", "announce", "new", "innovation",
                "platform", "service", "feature", "version", "upgrade"
            ],
        }
        
        self._load_sentiment_model()
    
    def _load_sentiment_model(self):
        """Load sentiment analysis model (lazy loading)."""
        if not self.use_finbert:
            logger.info("Using TextBlob for sentiment analysis (lightweight mode)")
            return
        
        if not HAS_TRANSFORMERS:
            logger.warning("transformers not installed. Using TextBlob for sentiment analysis.")
            self.use_finbert = False
            return
        
        try:
            logger.info("Loading FinBERT model...")
            model_name = "ProsusAI/finbert"
            self.finbert_tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.finbert_model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model=self.finbert_model,
                tokenizer=self.finbert_tokenizer,
                device=-1  # CPU
            )
            logger.info("FinBERT model loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load FinBERT model: {e}. Falling back to TextBlob.")
            self.use_finbert = False
    
    def analyze_sentiment(self, text: str, headline: Optional[str] = None) -> SentimentScore:
        """Analyze sentiment of text using FinBERT or TextBlob.
        
        Args:
            text: Article text to analyze (summary preferred)
            headline: Article headline (optionally combined with text)
            
        Returns:
            SentimentScore with score, label, and confidence
        """
        # Combine headline and text for context
        combined_text = text
        if headline:
            combined_text = f"{headline}. {text}" if text else headline
        
        # Truncate to 512 tokens for BERT models
        combined_text = combined_text[:2000]
        
        if self.use_finbert and self.sentiment_pipeline:
            return self._analyze_sentiment_finbert(combined_text)
        else:
            return self._analyze_sentiment_textblob(combined_text)
    
    def _analyze_sentiment_finbert(self, text: str) -> SentimentScore:
        """Analyze sentiment using FinBERT model.
        
        Args:
            text: Text to analyze
            
        Returns:
            SentimentScore
        """
        try:
            results = self.sentiment_pipeline(text)
            
            if not results:
                logger.warning("FinBERT returned empty results")
                return self._analyze_sentiment_textblob(text)
            
            result = results[0]
            label = result["label"].lower()  # "positive", "negative", "neutral"
            confidence = result["score"]
            
            # Convert label to score (-1 to 1)
            if label == "positive":
                score = confidence
            elif label == "negative":
                score = -confidence
            else:  # neutral
                score = 0.0
            
            return SentimentScore(
                score=float(score),
                label=label,
                confidence=float(confidence),
                model_used="finbert"
            )
        
        except Exception as e:
            logger.error(f"FinBERT analysis failed: {e}. Falling back to TextBlob.")
            return self._analyze_sentiment_textblob(text)
    
    def _analyze_sentiment_textblob(self, text: str) -> SentimentScore:
        """Analyze sentiment using TextBlob (lightweight fallback).
        
        Args:
            text: Text to analyze
            
        Returns:
            SentimentScore
        """
        try:
            from textblob import TextBlob
            
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity  # -1 to 1
            
            # Assign label based on polarity
            if polarity > 0.1:
                label = "positive"
            elif polarity < -0.1:
                label = "negative"
            else:
                label = "neutral"
            
            # Confidence based on magnitude of polarity
            confidence = min(0.95, 0.5 + abs(polarity) * 0.45)
            
            return SentimentScore(
                score=float(polarity),
                label=label,
                confidence=float(confidence),
                model_used="textblob"
            )
        
        except Exception as e:
            logger.error(f"TextBlob analysis failed: {e}. Returning neutral.")
            return SentimentScore(
                score=0.0,
                label="neutral",
                confidence=0.3,
                model_used="textblob"
            )
    
    def classify_event(self, headline: str, summary: Optional[str] = None) -> EventClassification:
        """Classify news article into event category.
        
        Args:
            headline: Article headline
            summary: Article summary/body
            
        Returns:
            EventClassification with category and confidence
        """
        # Combine headline and summary
        combined_text = (headline + " " + (summary or "")).lower()
        
        # Score each category based on keyword matches
        category_scores = {}
        
        for category, keywords in self.event_keywords.items():
            matches = sum(1 for kw in keywords if kw in combined_text)
            category_scores[category] = matches
        
        # Find best match
        best_category = max(category_scores, key=category_scores.get)
        best_score = category_scores[best_category]
        
        # Calculate confidence
        if best_score == 0:
            # No keywords matched, default to OTHER with low confidence
            return EventClassification(
                category=EventCategory.OTHER,
                confidence=0.2,
                reasoning="No specific event keywords detected"
            )
        
        # Confidence based on keyword match count and text length
        max_possible_score = len(self.event_keywords[best_category])
        confidence = min(0.95, best_score / max(3.0, max_possible_score / 2))
        
        # Get reasoning
        matched_keywords = [kw for kw in self.event_keywords[best_category] if kw in combined_text]
        reasoning = f"Detected keywords: {', '.join(matched_keywords[:3])}"
        
        return EventClassification(
            category=best_category,
            confidence=float(confidence),
            reasoning=reasoning
        )
    
    def estimate_market_impact(
        self,
        headline: str,
        sentiment: SentimentScore,
        event_category: EventClassification,
        summary: Optional[str] = None,
    ) -> float:
        """Estimate market impact score (0-1) for the article.
        
        Higher score = more likely to affect stock price.
        
        Args:
            headline: Article headline
            sentiment: Sentiment analysis result
            event_category: Event classification result
            summary: Article summary
            
        Returns:
            Market impact score (0-1)
        """
        impact_score = 0.5  # Start at neutral
        
        # Event category impact
        category_impact_weights = {
            EventCategory.EARNINGS: 0.95,      # Very likely to move market
            EventCategory.ACQUISITION: 0.90,   # Very likely
            EventCategory.LITIGATION: 0.70,    # Moderately likely
            EventCategory.REGULATORY: 0.75,    # Likely
            EventCategory.MANAGEMENT: 0.60,    # Somewhat likely
            EventCategory.PARTNERSHIP: 0.65,   # Likely
            EventCategory.PRODUCT: 0.55,       # Moderately likely
            EventCategory.OTHER: 0.40,         # Less likely
        }
        
        impact_score = category_impact_weights.get(event_category.category, 0.5)
        
        # Adjust based on event category confidence
        impact_score = impact_score * (0.7 + 0.3 * event_category.confidence)
        
        # Adjust based on sentiment strength (extremes are more impactful)
        sentiment_magnitude = abs(sentiment.score)
        if sentiment_magnitude > 0.5:
            # Strong sentiment increases impact potential
            impact_score = min(1.0, impact_score + 0.1 * sentiment_magnitude)
        
        # Check for strong language indicating urgency
        combined_text = (headline + " " + (summary or "")).lower()
        urgent_words = ["surge", "plunge", "crash", "soar", "collapse", "shocked",
                       "unprecedented", "scandal", "alert", "critical"]
        
        if any(word in combined_text for word in urgent_words):
            impact_score = min(1.0, impact_score + 0.15)
        
        # Apply ceiling based on event classification confidence
        if event_category.confidence < 0.3:
            impact_score = min(0.6, impact_score)
        
        return float(np.clip(impact_score, 0.0, 1.0))
    
    def analyze(
        self,
        headline: str,
        summary: Optional[str] = None,
        content: Optional[str] = None,
    ) -> NewsAnalysis:
        """Perform complete analysis on a news article.
        
        Args:
            headline: Article headline
            summary: Article summary/description
            content: Full article content (optional, uses summary if not provided)
            
        Returns:
            NewsAnalysis with all metrics
        """
        # Use content for sentiment if available, otherwise summary
        sentiment_text = content or summary or headline
        
        # Analyze sentiment
        sentiment = self.analyze_sentiment(sentiment_text, headline)
        
        # Classify event
        event = self.classify_event(headline, summary)
        
        # Estimate market impact
        impact = self.estimate_market_impact(
            headline=headline,
            sentiment=sentiment,
            event_category=event,
            summary=summary
        )
        
        return NewsAnalysis(
            headline=headline,
            summary=summary,
            sentiment=sentiment,
            event_category=event,
            market_impact_score=impact,
            analysis_version="v1.0"
        )
    
    def cleanup(self):
        """Free up memory if not caching models."""
        if not self.cache_models:
            self.sentiment_pipeline = None
            self.finbert_tokenizer = None
            self.finbert_model = None
