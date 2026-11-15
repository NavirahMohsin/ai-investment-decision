# Phase 4: Quick Start Guide

## What's New?

ArthAI now has a conversational AI assistant powered by Gemini and Groq. Ask questions about Indian stocks in natural language and get intelligent, data-driven answers.

## Setup (2 minutes)

### 1. Verify API Keys
```bash
cat backend/.env
```
Should contain:
```
GEMINI=...  # Already set
GROQ=...    # Already set
```

### 2. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

The new packages are already in `requirements.txt`:
- `google-generativeai==0.6.0`
- `groq==0.4.2`

### 3. Start the Server
```bash
cd backend
uvicorn app.main:app --reload
```

Server starts at `http://localhost:8000`

## Quick Test

### Option A: Via curl
```bash
# Check health
curl http://localhost:8000/api/v1/assistant/health

# Ask a question
curl -X POST http://localhost:8000/api/v1/assistant/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the current market sentiment on Indian tech stocks?",
    "include_history": false
  }'
```

### Option B: Via Python test script
```bash
# In another terminal
python backend/test_assistant_api.py
```

### Option C: Via API docs
Open `http://localhost:8000/docs` in your browser
- Try the `/assistant/ask` endpoint
- Input: `{"question": "Tell me about TCS", "include_history": false}`
- Click "Execute"

## Main Endpoints

### 1. Ask Questions
```
POST /api/v1/assistant/ask
```
**Input:**
```json
{
  "question": "Is Reliance Industries a good buy?",
  "include_history": true
}
```

**Output:**
```json
{
  "answer": "Based on current market data...",
  "sources": ["Market Data", "Fundamentals"],
  "confidence": "high",
  "related_companies": ["RELIANCE"]
}
```

### 2. Explain Scores
```
POST /api/v1/assistant/explain/fundamental-score
```
Understand why a stock got a score:
```json
{
  "ticker": "TCS",
  "type": "fundamental_score",
  "score_or_signal": 78,
  "factors": {
    "pe_ratio": 18.5,
    "roe": 15.8
  }
}
```

### 3. Explain Signals
```
POST /api/v1/assistant/explain/technical-signal
```
Understand trading signals:
```json
{
  "ticker": "HDFC",
  "type": "technical_signal",
  "score_or_signal": "BUY",
  "factors": {
    "rsi": 35,
    "macd": "bullish"
  }
}
```

### 4. Compare Stocks
```
POST /api/v1/assistant/compare
```
```json
{
  "tickers": ["TCS", "INFY", "WIPRO"]
}
```

### 5. Health Check
```
GET /api/v1/assistant/health
```
Returns LLM provider status.

## Example Questions

Try asking the assistant:

### General Market
- "What's happening in the Indian tech sector?"
- "Which sectors are performing well recently?"
- "What are the key market trends?"

### Specific Stocks
- "What is TCS stock doing?"
- "Is HDFC Bank undervalued?"
- "Should I invest in Reliance?"

### Analysis
- "Compare Infosys and Wipro"
- "What makes a good software stock?"
- "Explain the PE ratio and why it matters"

### With Data
- "Is INFY a good buy at P/E of 22?"
- "Compare TCS vs INFY in the IT sector"
- "Why did HDFC get a score of 78?"

## Key Features

✅ **Smart Ticker Extraction** - Automatically finds company symbols in questions

✅ **Real Data Integration** - Uses live market prices, fundamentals, and news

✅ **Source Tracking** - Shows which data sources powered the answer

✅ **Confidence Levels** - Indicates answer reliability (high/medium/low)

✅ **AI Disclaimers** - Clear that answers are model-generated

✅ **Automatic Fallback** - If Gemini is slow, switches to Groq

✅ **Error Handling** - Graceful degradation if data is missing

## Files Reference

| File | Purpose |
|------|---------|
| `app/services/llm_service.py` | LLM integration (Gemini + Groq) |
| `app/services/financial_assistant.py` | Assistant logic + data access |
| `app/api/routes/assistant.py` | API endpoints |
| `app/schemas/assistant.py` | Request/response models |
| `test_llm_service.py` | Unit tests |
| `test_assistant_api.py` | Integration tests |
| `PHASE_4_LLM_ASSISTANT.md` | Full documentation |

## Troubleshooting

### Server doesn't start
```bash
# Check Python version
python --version  # Should be 3.9+

# Check dependencies
pip list | grep genai  # Should show google-generativeai

# Try port 8001 instead
uvicorn app.main:app --port 8001
```

### "No LLM providers available"
```bash
# Check .env file
cat backend/.env

# Test Gemini key
python -c "import google.generativeai as genai; genai.configure(api_key='YOUR_KEY'); print('OK')"

# Test Groq key
python -c "from groq import Groq; c = Groq(api_key='YOUR_KEY'); print('OK')"
```

### Slow responses
- Normal: First response takes 2-3 seconds
- Slow: >10 seconds means LLM is busy
- Check health: `curl http://localhost:8000/api/v1/assistant/health`
- Groq is faster, so fallback will help

### Wrong company name
- Question: "Tell me about HDFC"
- Ambiguous: Could be HDFC Bank or HDFC Limited
- Solution: Use full ticker "HDFC.NS" or "HDFCBANK.NS"

## Integration with Frontend

### Sample React Component
```jsx
import axios from 'axios';

function StockAssistant() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleAsk = async () => {
    setLoading(true);
    try {
      const response = await axios.post(
        'http://localhost:8000/api/v1/assistant/ask',
        { question, include_history: false }
      );
      setAnswer(response.data);
    } catch (error) {
      console.error('Error:', error);
    }
    setLoading(false);
  };

  return (
    <div>
      <input
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask about stocks..."
      />
      <button onClick={handleAsk} disabled={loading}>
        {loading ? 'Thinking...' : 'Ask'}
      </button>
      {answer && (
        <div>
          <p>{answer.answer}</p>
          <p>Sources: {answer.sources.join(', ')}</p>
          <p>Confidence: {answer.confidence}</p>
          {answer.disclaimer && <p style={{fontSize: '0.8em'}}>{answer.disclaimer}</p>}
        </div>
      )}
    </div>
  );
}
```

## Performance Expectations

| Action | Time | Notes |
|--------|------|-------|
| Health check | <100ms | Very fast |
| Ask question | 2-5s | Depends on LLM |
| Explain score | 1-3s | Usually faster |
| Compare stocks | 3-8s | Larger response |
| Fallback | +2-3s | Automatic if needed |

## Cost Optimization

Both APIs have free tiers:

**Gemini (Google AI Studio)**
- 60 requests/min free
- 1M token context
- Great for longer context

**Groq (Free tier)**
- 30 requests/min free
- Faster inference
- Good for quick questions

**Tips:**
- Use smaller `max_tokens` for summaries
- Batch related questions
- Monitor with health endpoint
- Check response.usage for tracking

## What's Next?

### Phase 4.1 (Coming Soon)
- Streaming responses (real-time)
- Persistent conversation storage
- Rate limiting
- Voice interface

### Phase 4.2 (Later)
- Scheduled analysis emails
- Price alerts
- Portfolio optimization
- Scenario analysis

## Support

For detailed info:
- Full guide: `PHASE_4_LLM_ASSISTANT.md`
- Architecture: See diagrams in full guide
- Examples: Check `test_assistant_api.py`

For issues:
1. Check `/assistant/health`
2. Review console logs
3. Try test script: `python test_assistant_api.py`
4. Read troubleshooting section above

---

**Happy analyzing!** 🚀

Try asking the assistant about your favorite stocks and see how it combines real market data with intelligent analysis.
