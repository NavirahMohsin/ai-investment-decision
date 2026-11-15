"""Tests for news analysis module."""

import pytest
from app.services.news_analysis import (
    NewsAnalyzer,
    EventCategory,
    SentimentScore,
    EventClassification,
)


@pytest.fixture
def analyzer():
    """Create analyzer instance with lightweight (TextBlob) mode for fast tests."""
    return NewsAnalyzer(use_finbert=False)


class TestSentimentAnalysis:
    """Test sentiment analysis functionality."""
    
    def test_positive_sentiment(self, analyzer):
        """Test positive sentiment detection."""
        text = "The company reported record earnings and beat expectations"
        result = analyzer.analyze_sentiment(text)
        
        assert result.label in ["positive", "neutral"]
        assert result.score >= 0
        assert 0 <= result.confidence <= 1
    
    def test_negative_sentiment(self, analyzer):
        """Test negative sentiment detection."""
        text = "The company faces massive losses and bankruptcy concerns"
        result = analyzer.analyze_sentiment(text)
        
        assert result.label in ["negative", "neutral"]
        assert result.score <= 0 or result.label == "neutral"
        assert 0 <= result.confidence <= 1
    
    def test_neutral_sentiment(self, analyzer):
        """Test neutral sentiment detection."""
        text = "The company announced a new office location"
        result = analyzer.analyze_sentiment(text)
        
        assert isinstance(result, SentimentScore)
        assert -1 <= result.score <= 1
        assert 0 <= result.confidence <= 1
    
    def test_sentiment_with_headline(self, analyzer):
        """Test sentiment analysis with headline."""
        headline = "Stock Surges"
        text = "Following strong quarterly results"
        result = analyzer.analyze_sentiment(text, headline)
        
        assert isinstance(result, SentimentScore)
        assert -1 <= result.score <= 1


class TestEventClassification:
    """Test event category classification."""
    
    def test_earnings_classification(self, analyzer):
        """Test earnings event detection."""
        headline = "Apple Reports Record Quarterly Earnings"
        summary = "Apple Inc. announced Q4 earnings that beat analyst expectations with revenue of $89B"
        result = analyzer.classify_event(headline, summary)
        
        assert result.category == EventCategory.EARNINGS
        assert result.confidence > 0.5
    
    def test_acquisition_classification(self, analyzer):
        """Test acquisition event detection."""
        headline = "Microsoft Acquires GitHub"
        summary = "Microsoft announced the acquisition of GitHub in a deal valued at $7.5 billion"
        result = analyzer.classify_event(headline, summary)
        
        assert result.category == EventCategory.ACQUISITION
        assert result.confidence > 0.5
    
    def test_litigation_classification(self, analyzer):
        """Test litigation event detection."""
        headline = "Tesla Faces Major Lawsuit"
        summary = "Tesla faces a lawsuit alleging breach of contract and violation of antitrust laws"
        result = analyzer.classify_event(headline, summary)
        
        assert result.category == EventCategory.LITIGATION
        assert result.confidence > 0.5
    
    def test_regulatory_classification(self, analyzer):
        """Test regulatory event detection."""
        headline = "FDA Approves New Drug"
        summary = "The FDA approved the new pharmaceutical drug after successful clinical trials"
        result = analyzer.classify_event(headline, summary)
        
        assert result.category == EventCategory.REGULATORY
        assert result.confidence > 0.5
    
    def test_management_classification(self, analyzer):
        """Test management change detection."""
        headline = "CEO Steps Down"
        summary = "The company announced that CEO John Smith has resigned effective immediately"
        result = analyzer.classify_event(headline, summary)
        
        assert result.category == EventCategory.MANAGEMENT
        assert result.confidence > 0.5
    
    def test_partnership_classification(self, analyzer):
        """Test partnership event detection."""
        headline = "Strategic Partnership Announced"
        summary = "Company A and Company B announced a strategic partnership to develop new services"
        result = analyzer.classify_event(headline, summary)
        
        assert result.category == EventCategory.PARTNERSHIP
        assert result.confidence > 0.5
    
    def test_product_classification(self, analyzer):
        """Test product launch detection."""
        headline = "New Product Launch"
        summary = "The company launched a revolutionary new platform with advanced features"
        result = analyzer.classify_event(headline, summary)
        
        assert result.category == EventCategory.PRODUCT
        assert result.confidence > 0.5
    
    def test_unknown_classification(self, analyzer):
        """Test classification of non-specific news."""
        headline = "Company Opens New Office"
        summary = "The company established a presence in a new geographic market"
        result = analyzer.classify_event(headline, summary)
        
        assert result.category == EventCategory.OTHER
        assert 0 <= result.confidence <= 1


class TestMarketImpactScoring:
    """Test market impact scoring."""
    
    def test_earnings_high_impact(self, analyzer):
        """Test that earnings have high market impact."""
        headline = "Apple Reports Record Earnings"
        summary = "Apple beat earnings expectations by 20%"
        sentiment = SentimentScore(score=0.8, label="positive", confidence=0.9, model_used="test")
        event = analyzer.classify_event(headline, summary)
        
        impact = analyzer.estimate_market_impact(headline, sentiment, event, summary)
        
        assert impact > 0.7
    
    def test_low_impact_neutral(self, analyzer):
        """Test that neutral events have lower impact."""
        headline = "Company Hosts Investor Conference"
        summary = "The company will hold its annual investor conference next month"
        sentiment = SentimentScore(score=0.0, label="neutral", confidence=0.5, model_used="test")
        event = analyzer.classify_event(headline, summary)
        
        impact = analyzer.estimate_market_impact(headline, sentiment, event, summary)
        
        assert 0 <= impact <= 1
    
    def test_urgent_language_increases_impact(self, analyzer):
        """Test that urgent language increases market impact score."""
        headline1 = "Stock Plummets on Bad News"
        headline2 = "Stock Declines on Bad News"
        
        sentiment = SentimentScore(score=-0.7, label="negative", confidence=0.8, model_used="test")
        event = analyzer.classify_event(headline1, "Negative news")
        
        impact1 = analyzer.estimate_market_impact(headline1, sentiment, event, "Negative news")
        impact2 = analyzer.estimate_market_impact(headline2, sentiment, event, "Negative news")
        
        # Urgent language should increase impact
        assert impact1 > impact2


class TestCompleteAnalysis:
    """Test complete news analysis."""
    
    def test_complete_analysis_earnings(self, analyzer):
        """Test complete analysis of earnings news."""
        result = analyzer.analyze(
            headline="Apple Reports Record Q4 Earnings",
            summary="Apple exceeded expectations with $89B in revenue",
            content="Apple Inc. today announced record financial results for Q4..."
        )
        
        assert result.headline == "Apple Reports Record Q4 Earnings"
        assert result.summary == "Apple exceeded expectations with $89B in revenue"
        assert result.sentiment.score >= 0  # Positive news
        assert result.event_category.category == EventCategory.EARNINGS
        assert result.market_impact_score > 0.7
        assert result.analysis_version == "v1.0"
    
    def test_complete_analysis_litigation(self, analyzer):
        """Test complete analysis of litigation news."""
        result = analyzer.analyze(
            headline="Major Lawsuit Filed Against Company",
            summary="The company faces allegations of fraud and misconduct"
        )
        
        assert result.event_category.category == EventCategory.LITIGATION
        assert result.sentiment.score <= 0 or result.sentiment.label == "neutral"
        assert result.market_impact_score > 0.6
    
    def test_analysis_returns_valid_scores(self, analyzer):
        """Test that analysis returns valid score ranges."""
        result = analyzer.analyze(
            headline="News Headline",
            summary="News summary"
        )
        
        assert -1 <= result.sentiment.score <= 1
        assert 0 <= result.sentiment.confidence <= 1
        assert 0 <= result.market_impact_score <= 1
        assert 0 <= result.event_category.confidence <= 1


class TestFallbackBehavior:
    """Test fallback behavior when models fail."""
    
    def test_textblob_fallback_works(self):
        """Test that TextBlob fallback works when FinBERT unavailable."""
        analyzer = NewsAnalyzer(use_finbert=False)
        result = analyzer.analyze_sentiment("Great news!")
        
        assert result.label in ["positive", "neutral", "negative"]
        assert result.model_used == "textblob"
        assert 0 <= result.confidence <= 1
    
    def test_invalid_text_returns_neutral(self):
        """Test that invalid/empty text returns neutral sentiment."""
        analyzer = NewsAnalyzer(use_finbert=False)
        result = analyzer.analyze_sentiment("")
        
        assert result.label == "neutral"
        assert 0 <= result.confidence <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
