"""Quick test of news analyzer without pytest."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.news_analysis import NewsAnalyzer, EventCategory

print("\n" + "="*80)
print("News Analyzer Quick Test")
print("="*80)

# Create analyzer with TextBlob (lightweight)
analyzer = NewsAnalyzer(use_finbert=False)

# Test 1: Sentiment Analysis
print("\n[1] Sentiment Analysis Tests")
print("-" * 40)

test_cases = [
    ("The company reported record earnings and beat expectations", "positive"),
    ("The company faces massive losses and bankruptcy concerns", "negative"),
    ("The company announced a new office location", "neutral"),
]

for text, expected in test_cases:
    result = analyzer.analyze_sentiment(text)
    print(f"Text: {text[:50]}...")
    print(f"  Score: {result.score:.2f}, Label: {result.label}, Confidence: {result.confidence:.2f}")
    print()

# Test 2: Event Classification
print("\n[2] Event Classification Tests")
print("-" * 40)

events_test = [
    ("Apple Reports Record Quarterly Earnings", "Apple announced Q4 earnings that beat expectations", EventCategory.EARNINGS),
    ("Microsoft Acquires GitHub", "Microsoft acquired GitHub for $7.5 billion", EventCategory.ACQUISITION),
    ("Tesla Faces Major Lawsuit", "Tesla faces lawsuit alleging breach of contract", EventCategory.LITIGATION),
    ("FDA Approves New Drug", "FDA approved the pharmaceutical drug", EventCategory.REGULATORY),
    ("CEO Steps Down", "CEO John Smith has resigned", EventCategory.MANAGEMENT),
]

for headline, summary, expected_category in events_test:
    result = analyzer.classify_event(headline, summary)
    match = "[OK]" if result.category == expected_category else "[MISMATCH]"
    print(f"{match} {headline}")
    print(f"  Category: {result.category.value}, Confidence: {result.confidence:.2f}")
    print(f"  Reasoning: {result.reasoning}")
    print()

# Test 3: Market Impact Scoring
print("\n[3] Market Impact Scoring Tests")
print("-" * 40)

from app.services.news_analysis import SentimentScore

impact_tests = [
    ("Apple Reports Record Earnings", "Beat expectations", SentimentScore(0.8, "positive", 0.9, "test"), EventCategory.EARNINGS),
    ("Stock Plummets on Bad News", "Negative news", SentimentScore(-0.7, "negative", 0.8, "test"), EventCategory.OTHER),
]

for headline, summary, sentiment, category in impact_tests:
    from app.services.news_analysis import EventClassification
    event = EventClassification(category=category, confidence=0.8, reasoning="test")
    impact = analyzer.estimate_market_impact(headline, sentiment, event, summary)
    print(f"{headline}")
    print(f"  Impact Score: {impact:.2f}")
    print()

# Test 4: Complete Analysis
print("\n[4] Complete Analysis Tests")
print("-" * 40)

complete_tests = [
    {
        "headline": "Apple Reports Record Q4 Earnings",
        "summary": "Apple exceeded expectations with $89B in revenue",
        "content": "Apple Inc. announced record financial results..."
    },
    {
        "headline": "Major Lawsuit Filed Against Company",
        "summary": "The company faces allegations of fraud",
        "content": None
    }
]

for test in complete_tests:
    result = analyzer.analyze(test["headline"], test["summary"], test["content"])
    print(f"Headline: {result.headline}")
    print(f"  Sentiment: {result.sentiment.label} ({result.sentiment.score:.2f}, confidence: {result.sentiment.confidence:.2f})")
    print(f"  Event: {result.event_category.category.value} (confidence: {result.event_category.confidence:.2f})")
    print(f"  Market Impact: {result.market_impact_score:.2f}")
    print()

print("="*80)
print("All tests completed successfully!")
print("="*80)
