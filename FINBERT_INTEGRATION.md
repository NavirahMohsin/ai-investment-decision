# FinBERT Integration Status

## Overview
FinBERT (Financial BERT) sentiment analysis is already integrated into the news intelligence system and is currently downloading/caching on first use.

## What's Already Implemented

### 1. **NewsAnalyzer Class** (`backend/app/services/news_analysis.py`)
The `NewsAnalyzer` class provides:
- **Automatic model selection**: Uses FinBERT by default, falls back to TextBlob if unavailable
- **Lazy loading**: Models are loaded on first use to optimize startup time
- **Graceful degradation**: If FinBERT fails, automatically switches to TextBlob

```python
analyzer = NewsAnalyzer(use_finbert=True, cache_models=True)
sentiment = analyzer.analyze_sentiment(text, headline)
```

### 2. **FinBERT Sentiment Analysis**
- Model: `ProsusAI/finbert` (438MB, pre-trained on financial documents)
- Output: Positive, Negative, or Neutral with confidence scores
- Converts to -1 to 1 score range for consistency
- Optimized for financial news/earnings reports

### 3. **Event Classification**
- 8 event categories: earnings, acquisition, litigation, regulatory, management, partnership, product, other
- Keyword-based matching with configurable weights
- Returns confidence scores for each classification

### 4. **Market Impact Scoring**
- Combines sentiment + event category + keyword urgency
- Range: 0-1 (higher = more likely to move stock price)
- Category weights:
  - Earnings: 0.95 (highest impact)
  - Acquisition: 0.90
  - Regulatory: 0.75
  - Litigation: 0.70
  - Partnership: 0.65
  - Product: 0.55

## Frontend Integration

### 5. **News Components with Sentiment Display**
- `SentimentBadge`: Shows sentiment label + color + icon
- `EventCategoryBadge`: Shows event type
- `NewsArticleCard`: Displays headline, sentiment, event, impact score
- `CompanyNewsPanel`: Full news panel with sentiment stats and filtering
- `SentimentChart`: Timeline visualization (line chart for trends + bar chart for counts)

### 6. **API Endpoints for News Data**
```
GET /api/v1/news/company/{id}/sentiment?days=30
  → avg_sentiment, sentiment_trend, positive/negative/neutral counts

GET /api/v1/news/company/{id}/sentiment-timeline?period=week
  → Weekly/daily sentiment trends

GET /api/v1/news/company/{id}/articles
  → All articles with sentiment/event/impact filters

GET /api/v1/news/company/{id}/news-price-correlation
  → Correlation between news events and price movements
```

## Performance Characteristics

### FinBERT Performance
- **First run**: ~30-60 seconds (model download + cache)
- **Subsequent runs**: <100ms per article (GPU/CPU inference)
- **Memory**: ~438MB model + ~200MB cache
- **Accuracy**: ~85-90% on financial text (better than VADER/TextBlob)

### TextBlob Fallback
- **Speed**: ~5-10ms per article
- **Memory**: Minimal (<10MB)
- **Accuracy**: ~70-75% (good for non-financial text)

## Usage Examples

### Backend: Analyze News Article
```python
from app.services.news_analysis import NewsAnalyzer

analyzer = NewsAnalyzer(use_finbert=True)
result = analyzer.analyze(
    headline="Apple Reports Q1 Earnings Beat",
    summary="Revenue exceeded expectations by 5%",
    content="Full article content..."
)

print(result.sentiment.label)           # "positive"
print(result.sentiment.score)           # 0.87
print(result.event_category.category)   # "earnings"
print(result.market_impact_score)       # 0.92
```

### Frontend: Display News with Sentiment
```tsx
import { CompanyNewsPanel } from '@/components/news/company-news-panel';

export default function StockDetail() {
  return (
    <CompanyNewsPanel 
      companyId={123}
      companySymbol="AAPL"
      maxItems={20}
      showFilters={true}
    />
  );
}
```

## Configuration

### Enable/Disable FinBERT
```python
# Use FinBERT (default)
analyzer = NewsAnalyzer(use_finbert=True)

# Force TextBlob (faster, less accurate)
analyzer = NewsAnalyzer(use_finbert=False)

# Cache models in memory between calls
analyzer = NewsAnalyzer(cache_models=True)
```

### Environment Variables
```
# Optional: Hugging Face token for higher rate limits
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxx

# Optional: Disable symlink warnings on Windows
HF_HUB_DISABLE_SYMLINKS_WARNING=1
```

## Testing

Run the FinBERT test:
```bash
cd backend
. ./venv/Scripts/Activate.ps1
python test_finbert.py
```

Output will show:
- Model loading status
- Sample sentiment predictions
- Performance metrics

## Next Steps

1. **Optimize model loading**: Cache FinBERT on startup vs. lazy load on first article
2. **GPU support**: Enable CUDA for faster inference on GPUs
3. **Batch processing**: Analyze multiple articles in parallel
4. **Custom fine-tuning**: Optionally fine-tune FinBERT on company-specific data
5. **Sentiment trends**: Add historical sentiment tracking per company/sector

## Dependencies

Already installed in `requirements.txt`:
```
transformers==4.45.2
torch==2.4.0
textblob==0.18.0
nltk==3.8.1
```

Frontend (`package.json`):
```
recharts==2.15.4  ✓ Installed
```

## Troubleshooting

### Issue: "Cannot find module 'recharts'"
**Solution**: Already fixed. Run `npm install` in frontend directory.

### Issue: FinBERT download stuck
**Solution**: Model is ~438MB. Wait 1-2 minutes first time. Cached after that.

### Issue: "No module named 'transformers'"
**Solution**: Ensure venv is activated: `. ./venv/Scripts/Activate.ps1`

### Issue: FinBERT too slow
**Solution**: Use TextBlob instead: `NewsAnalyzer(use_finbert=False)`

