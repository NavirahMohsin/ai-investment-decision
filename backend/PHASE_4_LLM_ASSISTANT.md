# Phase 4: LLM-Powered Financial Assistant

## Overview

Phase 4 adds an intelligent conversational financial assistant to ArthAI, powered by large language models. This transforms ArthAI from a data dashboard into a full research platform where users can have natural conversations about Indian stocks.

## Architecture

### LLM Integration

**Primary:** Gemini 2.5 Flash (via Google AI Studio)
- 1M token context window (handles full annual reports)
- Native JSON schema support
- Ideal for structured outputs

**Fallback:** Llama 3.3 70B (via Groq)
- High-speed inference
- Activated if primary hits rate limits
- Ensures 99.9% availability

### Service Layer

```
┌─────────────────────┐
│   FastAPI Routes    │  /api/v1/assistant/*
└──────────┬──────────┘
           │
┌──────────▼──────────────┐
│ Financial Assistant    │  Orchestrates LLM + data access
└──────────┬──────────────┘
           │
      ┌────┴────┐
      │          │
┌─────▼───┐  ┌──▼─────────┐
│LLM      │  │Data Access │
│Service  │  │ (Company,  │
│         │  │  Market,   │
│Gemini/  │  │  News)     │
│Groq     │  └────────────┘
└─────────┘
```

## Capabilities

### 1. Conversational Q&A

Ask natural questions about stocks:
- "What is the PE ratio of TCS and is it undervalued?"
- "Should I buy Reliance Industries right now?"
- "Compare Infosys vs Wipro as investments"

The assistant:
- Identifies the company from the question
- Retrieves current market data
- Pulls fundamental metrics and ratios
- Checks technical indicators
- Reviews recent news
- Provides data-driven analysis

**Endpoint:** `POST /api/v1/assistant/ask`

```bash
curl -X POST http://localhost:8000/api/v1/assistant/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is TCS stock likely to do this year?",
    "include_history": true
  }'
```

Response:
```json
{
  "answer": "TCS is showing strong fundamentals... Based on the latest data...",
  "sources": ["Market Data (TCS)", "Fundamentals", "Technical Indicators"],
  "confidence": "high",
  "disclaimer": "This response contains model-generated interpretations...",
  "related_companies": ["TCS"]
}
```

### 2. Explain Fundamental Scores

Get explanations for why a stock received a particular fundamental score:

**Endpoint:** `POST /api/v1/assistant/explain/fundamental-score`

```bash
curl -X POST http://localhost:8000/api/v1/assistant/explain/fundamental-score \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "TCS",
    "type": "fundamental_score",
    "score_or_signal": 78.5,
    "factors": {
      "pe_ratio": 18.5,
      "pb_ratio": 3.2,
      "roe": 15.8,
      "debt_to_equity": 0.45
    }
  }'
```

The assistant explains:
- What the score means for investors
- Which factors are most important
- Whether it's strong/weak in context
- Investment implications

### 3. Explain Technical Signals

Understand technical trading signals:

**Endpoint:** `POST /api/v1/assistant/explain/technical-signal`

```bash
curl -X POST http://localhost:8000/api/v1/assistant/explain/technical-signal \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "HDFC",
    "type": "technical_signal",
    "score_or_signal": "BUY",
    "factors": {
      "rsi": 35,
      "macd": "bullish_crossover",
      "sma_20_above_50": true,
      "volume": "above_average"
    }
  }'
```

### 4. Stock Comparison

Compare multiple stocks side-by-side:

**Endpoint:** `POST /api/v1/assistant/compare`

```bash
curl -X POST http://localhost:8000/api/v1/assistant/compare \
  -H "Content-Type: application/json" \
  -d '{
    "tickers": ["TCS", "INFY", "WIPRO"]
  }'
```

Analyzes:
- Financial health (P/E, debt, profitability)
- Growth prospects
- Valuation vs peers
- Risk factors
- Investment suitability

### 5. Service Health

Check LLM provider availability:

**Endpoint:** `GET /api/v1/assistant/health`

```bash
curl http://localhost:8000/api/v1/assistant/health
```

Response:
```json
{
  "status": "healthy",
  "gemini_available": true,
  "groq_available": true,
  "message": "All LLM providers available"
}
```

## Configuration

### API Keys

Set in `backend/.env`:
```
GEMINI=your_gemini_api_key_here
GROQ=your_groq_api_key_here
```

Both are required for full functionality. If one is missing:
- Primary provider: Requires at least one API key
- Fallback: If primary fails, automatically uses fallback
- Degraded mode: If both missing, service becomes unavailable

### Core Settings

Edit `app/core/config.py` to configure:
```python
# Temperature: 0.0 (deterministic) to 1.0 (creative)
ASSISTANT_TEMPERATURE = 0.7

# Max tokens per response (lower = faster, cheaper)
ASSISTANT_MAX_TOKENS = 2048

# Include conversation history for context
INCLUDE_CONVERSATION_HISTORY = True

# Max history messages to include
MAX_HISTORY_MESSAGES = 5
```

## Implementation Details

### LLM Service (`app/services/llm_service.py`)

Reusable service layer for LLM operations:

```python
from app.services.llm_service import get_llm_service

service = get_llm_service()

# Simple text generation
response = service.generate(
    prompt="What is a PE ratio?",
    system_prompt="You are a financial analyst",
    temperature=0.5,
    max_tokens=1024,
    provider=LLMProvider.GEMINI,  # Optional
    fallback_to_groq=True,
)

print(response.content)  # Generated text
print(response.provider)  # Which provider was used
print(response.usage)    # Token usage stats
```

Features:
- **Automatic fallback:** If primary fails, tries fallback
- **Retry logic:** Automatic retries with exponential backoff
- **Structured outputs:** Native support for Pydantic JSON schemas
- **Token tracking:** Monitor usage for cost optimization
- **Provider abstraction:** Switch providers without code changes

### Financial Assistant (`app/services/financial_assistant.py`)

High-level assistant with data access:

```python
from app.services.financial_assistant import get_financial_assistant

assistant = get_financial_assistant(db)

# Ask a question
response = assistant.ask_question(
    "What about TCS stock?",
    include_history=True,
)

print(response.answer)
print(response.sources)  # Which data was used
print(response.confidence)  # Confidence level
print(response.related_companies)  # Companies mentioned
```

Features:
- **Ticker extraction:** Automatically finds company symbols in questions
- **Data retrieval:** Fetches market prices, fundamentals, news
- **Conversation context:** Remembers previous messages
- **Source tracking:** Shows which data was used
- **Confidence levels:** Indicates reliability of answer

### API Routes (`app/api/routes/assistant.py`)

FastAPI endpoints for frontend integration:

```python
@assistant_router.post("/ask")
async def ask_question(
    request: AssistantQuestionRequest,
    db: Session = Depends(get_db),
) -> AssistantResponseItem:
    """Ask the assistant a question."""
    # Implementation handles error cases gracefully
```

All endpoints:
- Return structured JSON responses
- Include detailed error messages
- Support rate limiting (future enhancement)
- Have OpenAPI/Swagger documentation

### Schemas (`app/schemas/assistant.py`)

Pydantic models for request/response validation:

```python
class AssistantQuestionRequest(BaseModel):
    question: str  # Min 5 chars
    include_history: bool = True

class AssistantResponseItem(BaseModel):
    answer: str
    sources: list[str]
    confidence: str  # low, medium, high
    disclaimer: str
    related_companies: list[str]
```

## Best Practices

### For Accurate Responses

1. **Be specific:** "What is TCS?" → "Is TCS undervalued based on P/E ratio?"
2. **Include context:** "Should I buy HDFC at ₹2500?" (with price)
3. **Use recent data:** System always pulls latest prices and fundamentals
4. **Ask about one company:** Single-stock questions are most accurate

### For Cost Optimization

1. **Shorter max_tokens:** "100 tokens" for summaries, "2048" for detailed analysis
2. **Lower temperature:** Use 0.5 for factual questions, 0.7 for analysis
3. **Batch questions:** Fewer API calls = lower cost
4. **Check health:** Use `/assistant/health` to detect provider issues early

### For Better User Experience

1. **Show sources:** Tell users which data powered the answer
2. **Include disclaimers:** Remind that model-generated insights aren't guarantees
3. **Offer explanations:** Use `/explain` endpoints when users ask "why?"
4. **Handle errors gracefully:** Show friendly messages, never expose API errors

## Error Handling

### Service Unavailable

All endpoints return 503 if:
- Both LLM APIs are unreachable
- Database is down
- Invalid API keys

Check `/assistant/health` before critical operations.

### Rate Limiting (Future)

Expected to be added:
- 10 requests/min for free tier
- Exponential backoff for retries
- Queue system for excess traffic

### Graceful Degradation

If a data source fails:
- Question still answered with available data
- Sources list shows what was unavailable
- Confidence level is adjusted downward

## Testing

Run the test suite:

```bash
cd backend
pytest test_llm_service.py -v
```

Tests cover:
- LLM service initialization and provider selection
- Financial assistant setup and data retrieval
- API schema validation
- Conversation history management
- Error handling

Integration tests (requires API keys):
```bash
pytest test_llm_service.py::TestLLMServiceIntegration -v
```

## Monitoring & Observability

### Logging

All operations are logged with appropriate levels:
```python
logger.info("Question received: ...")
logger.warning("Primary provider failed, using fallback")
logger.error("Both LLM providers unavailable")
```

### Metrics to Track

1. **Provider usage:** Which LLM is being used most
2. **Fallback rate:** How often backup is needed
3. **Response latency:** Time to generate answers
4. **Error rate:** Failed requests vs total
5. **Token usage:** Cost tracking across providers

## Future Enhancements

### Planned for Phase 4.1

1. **Streaming responses:** Real-time token generation
2. **Multi-turn conversations:** Full chat history with database persistence
3. **Follow-up questions:** Context-aware refinement
4. **Voice interface:** "Ask me about TCS" via audio
5. **Watchlist integration:** "How are my 5 stocks doing?"

### Planned for Phase 4.2

1. **Scheduled analysis:** Daily/weekly stock briefings
2. **Alert system:** "Notify me if TCS drops 5%"
3. **Portfolio optimization:** "Best 10-stock portfolio for me?"
4. **Scenario analysis:** "What if interest rates rise 1%?"
5. **Citation system:** Link to specific news/reports

## Troubleshooting

### "No LLM providers available"

**Check:**
1. API keys set in `.env`
2. Internet connectivity
3. API key validity (test in Google AI Studio / Groq console)

**Solution:**
```bash
# Test Gemini
python -c "import google.generativeai as genai; genai.configure(api_key='YOUR_KEY'); print('OK')"

# Test Groq
python -c "from groq import Groq; Groq(api_key='YOUR_KEY'); print('OK')"
```

### Slow responses

**Likely causes:**
1. Primary LLM is overloaded → Check `/assistant/health`
2. Network latency → Try different time
3. Large context → Reduce `MAX_HISTORY_MESSAGES`

**Solution:** Reduce `max_tokens` or switch providers manually

### Inaccurate answers

1. **Data issue:** Check if market data is fresh (should be <1hr old)
2. **Ticker ambiguity:** "What about HDFC?" (Bank? Limited?)
3. **Model limitation:** LLM may not know current quarter results

**Solution:** Ask more specific questions with ticker suffix (.NS/.BO)

## References

- [Gemini API Documentation](https://ai.google.dev/)
- [Groq API Documentation](https://console.groq.com/)
- [Financial Ratios Guide](https://www.investopedia.com)
- [Technical Analysis Indicators](https://www.investopedia.com/terms/t/technicalanalysis.asp)

## Support

For issues or questions:
1. Check `/assistant/health` endpoint
2. Review logs in `backend/logs/`
3. Test with sample questions first
4. Verify API keys and permissions
