# Phase 4: Frontend Integration Guide

## Overview
This guide documents the complete frontend integration of Phase 4.4 & 4.5 backend capabilities (Company Research Assistant and AI Explanations) into the ArthAI React/Next.js frontend.

**Status**: ✅ Complete
- All 3 new UI pages created and functional
- API client with all 15 backend endpoints
- React hooks for data fetching and state management
- Error handling, loading states, and disclaimers throughout
- Integrated into dashboard quick access navigation

---

## Architecture

### Frontend Stack
- **Framework**: Next.js 16.4.3 with React 19.3.0
- **Styling**: Tailwind CSS 4 with Shadcn UI components
- **Data Fetching**: Custom API client with React hooks
- **Rendering**: React Markdown for AI-generated content

### Backend Endpoints Integrated

#### Research Endpoints (Phase 4.4)
```
POST /api/v1/research/company-overview
POST /api/v1/research/financial-analysis
POST /api/v1/research/swot
POST /api/v1/research/compare
POST /api/v1/research/report
GET  /api/v1/research/health
```

#### Explanation Endpoints (Phase 4.5)
```
POST /api/v1/explain/ml-prediction
POST /api/v1/explain/technical-signal
POST /api/v1/explain/fundamental-score
POST /api/v1/explain/news-sentiment
GET  /api/v1/explain/health
```

#### Assistant Endpoints (Phase 4.2)
```
POST /api/v1/assistant/ask
POST /api/v1/assistant/explain/fundamental-score
POST /api/v1/assistant/explain/technical-signal
POST /api/v1/assistant/compare
GET  /api/v1/assistant/health
```

---

## Files Created

### Core Infrastructure

#### `frontend/lib/api-client.ts` (400+ lines)
Centralized HTTP client for all backend communication.

**Key Methods**:
```typescript
class APIClient {
  // Research methods
  async getCompanyOverview(ticker: string)
  async getFinancialAnalysis(ticker: string)
  async getSWOTAnalysis(ticker: string)
  async compareCompanies(tickers: string[])
  async generateResearchReport(ticker: string)
  async getResearchHealth()

  // Explanation methods
  async explainMLPrediction(ticker: string, prediction: number, confidence: number)
  async explainTechnicalSignal(ticker: string, signal: string, strength: number)
  async explainFundamentalScore(ticker: string, score: number, components: Record<string, number>)
  async explainNewsSentiment(ticker: string, sentiment: string, articles: number)
  async getExplanationHealth()

  // Assistant methods
  async askAssistant(question: string)
  async explainScoreViaAssistant(ticker: string, score: number)
  async explainSignalViaAssistant(ticker: string, signal: string)
  async compareViaAssistant(ticker1: string, ticker2: string)
  async getAssistantHealth()
}
```

**Features**:
- Automatic base URL from `NEXT_PUBLIC_API_URL` environment variable (defaults to localhost:8000)
- Type-safe requests/responses with TypeScript interfaces
- Comprehensive error handling with user-friendly messages
- Request headers with content-type and CORS support

### React Hooks

#### `frontend/hooks/useResearch.ts` (250+ lines)
Six custom hooks for research operations with consistent state management.

```typescript
// Hooks exported:
useCompanyOverview()      // Company overview generation
useFinancialAnalysis()    // Financial performance analysis
useSwotAnalysis()         // SWOT analysis
useCompanyComparison()    // Multi-ticker comparison
useResearchReport()       // Full research report
useResearchHealth()       // Backend health check
```

**Hook Interface** (all follow same pattern):
```typescript
interface UseResearchHook {
  data: ResearchData | null
  loading: boolean
  error: string | null
  generate: (ticker: string) => Promise<void>
}
```

#### `frontend/hooks/useExplanations.ts` (250+ lines)
Four custom hooks for AI explanation operations.

```typescript
// Hooks exported:
useMLPredictionExplanation()     // ML prediction explanations
useTechnicalSignalExplanation()  // Technical signal explanations
useFundamentalScoreExplanation() // Fundamental score explanations
useNewsSentimentExplanation()    // News sentiment explanations
```

### UI Pages

#### `frontend/app/research/page.tsx` (200+ lines)
**Purpose**: Company research interface with three tabs

**Features**:
- Ticker input with validation (uppercase conversion)
- Three action buttons: Company Overview, SWOT Analysis, Full Report
- Tab-based results display
- React Markdown rendering for rich content
- Error display with user-friendly messages
- Loading states on all buttons
- Disclaimer with investment health warning
- Responsive grid layout (3 columns on large screens)

**Tab Sections**:
1. **Overview**: Company snapshot and business summary
2. **SWOT**: Strengths, Weaknesses, Opportunities, Threats analysis
3. **Report**: Comprehensive multi-section research report

#### `frontend/app/explanations/page.tsx` (200+ lines)
**Purpose**: AI explanations interface for understanding predictions, signals, and sentiment

**Features**:
- Ticker input with validation
- Four action buttons: ML Prediction, Technical Signal, Fundamental Score, News Sentiment
- Tab-based results display
- React Markdown rendering
- Error handling and loading states
- Uncertainty disclaimer highlighting AI limitations
- Color-coded tabs for visual clarity
- Responsive 2x2 button grid on small screens, 1x4 on large

**Explanation Sections**:
1. **ML Prediction**: Explains model predictions with uncertainty assessment
2. **Technical Signal**: Technical analysis signal interpretation
3. **Fundamental Score**: Fundamental valuation metrics explanation
4. **News Sentiment**: News sentiment analysis with confidence levels

#### `frontend/app/assistant/page.tsx` (250+ lines)
**Purpose**: Multi-turn Q&A interface for investment questions

**Features**:
- Chat interface with message history
- User and assistant message differentiation (color-coded)
- Auto-scrolling to latest message
- Loading indicator (animated dots)
- Clear chat button for fresh conversations
- Error handling with error display
- React Markdown rendering for rich responses
- Welcome screen with usage instructions
- Timestamps on each message
- Disclaimer about AI-generated responses

**Interaction Flow**:
1. User types question and presses Enter or clicks Send
2. Frontend sends to `/api/v1/assistant/ask` endpoint
3. Assistant response rendered with Markdown
4. Full conversation history maintained in-memory
5. User can continue asking follow-up questions

---

## Integration Steps

### 1. Environment Setup

Create or update `frontend/.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

If backend runs on different port or remote server:
```bash
NEXT_PUBLIC_API_URL=http://your-backend-url:port/api/v1
```

### 2. Install Dependencies

```bash
cd frontend
npm install
# Installs react-markdown and all other dependencies
```

### 3. Start Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Verify at `http://localhost:8000/docs` (Swagger UI)

### 4. Start Frontend

```bash
cd frontend
npm run dev
# Opens at http://localhost:3000
```

### 5. Access New Pages

From dashboard home page or direct URLs:
- Research: `http://localhost:3000/research`
- Explanations: `http://localhost:3000/explanations`
- Assistant: `http://localhost:3000/assistant`

---

## API Integration Details

### APIClient Configuration

**Automatic Base URL Detection**:
```typescript
// If environment variable set, use it
const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL

// Otherwise default to localhost:8000/api/v1
const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'
```

### Request/Response Cycle Example: Company Overview

**Frontend Request** (from `useCompanyOverview` hook):
```typescript
const response = await fetch(`${apiBaseUrl}/research/company-overview`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ ticker: 'TCS' })
})
const data = await response.json()
// data = { overview: "markdown formatted text..." }
```

**Backend Processing** (Phase 4.4 service):
- Validates ticker symbol
- Fetches company data from yfinance
- Calls Gemini LLM to generate overview
- Adds uncertainty footer
- Returns markdown response

**Frontend Display**:
```typescript
<ReactMarkdown>{data.overview}</ReactMarkdown>
```

### Error Handling Pattern

All hooks implement consistent error handling:

```typescript
const { data, loading, error, generate } = useCompanyOverview()

// Catch and display errors
{error && <div className="text-red-400">{error}</div>}

// Handle loading state
{loading && <div>Generating...</div>}

// Render results
{data && <ReactMarkdown>{data.overview}</ReactMarkdown>}
```

---

## Testing the Integration

### Quick Test Checklist

```bash
# 1. Backend running?
curl http://localhost:8000/api/v1/research/health
# Expected: { "status": "healthy", "provider": "gemini" }

# 2. Frontend running?
open http://localhost:3000

# 3. Test Research Page
# - Enter ticker: TCS
# - Click "Company Overview"
# - Should see markdown content in 2-3 seconds

# 4. Test Explanations Page
# - Enter ticker: INFY
# - Click "ML Prediction"
# - Should see explanation with uncertainty disclaimer

# 5. Test Assistant Page
# - Ask: "What makes a good stock?"
# - Should get multi-turn conversation support
# - Click "Clear" to reset chat

# 6. Test Navigation
# - From dashboard home
# - Click "AI Explanations" card in Quick Access
# - Should navigate to /explanations
```

### Manual Testing Scenarios

**Scenario 1: Happy Path**
- Enter valid Indian stock ticker (TCS, INFY, HDFC)
- Click action button
- Should display formatted AI response in 2-5 seconds

**Scenario 2: Invalid Ticker**
- Enter invalid ticker (e.g., "INVALID123")
- Should display error message
- Error message from backend service gracefully handled

**Scenario 3: Network Error**
- Stop backend server
- Try to generate overview
- Should show error: "Network error" or similar

**Scenario 4: Slow Response**
- Should show "Loading..." or "Generating..." state
- UI should remain responsive
- User can close tab or navigate away

---

## Code Examples

### Using the Research Hook in a Component

```typescript
'use client'

import { useCompanyOverview } from '@/hooks/useResearch'
import ReactMarkdown from 'react-markdown'

export function MyComponent() {
  const overview = useCompanyOverview()
  const [ticker, setTicker] = useState('')

  const handleClick = async () => {
    await overview.generate(ticker)
  }

  return (
    <div>
      <input 
        value={ticker}
        onChange={(e) => setTicker(e.target.value)}
        placeholder="Enter ticker"
      />
      <button onClick={handleClick} disabled={overview.loading}>
        {overview.loading ? 'Loading...' : 'Get Overview'}
      </button>
      
      {overview.error && <div className="error">{overview.error}</div>}
      {overview.data && (
        <ReactMarkdown>{overview.data.overview}</ReactMarkdown>
      )}
    </div>
  )
}
```

### Using the Assistant Hook in a Component

```typescript
'use client'

import { useAssistant } from '@/hooks/useAssistant'
import ReactMarkdown from 'react-markdown'

export function ChatInterface() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const assistant = useAssistant()

  const handleSend = async () => {
    // Add user message
    const newMessage = { role: 'user', content: input }
    setMessages([...messages, newMessage])
    setInput('')

    // Get assistant response
    await assistant.ask(input)
    
    // Add assistant response
    if (assistant.data?.answer) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: assistant.data.answer
      }])
    }
  }

  return (
    <div>
      {messages.map((msg, i) => (
        <div key={i} className={msg.role}>
          <ReactMarkdown>{msg.content}</ReactMarkdown>
        </div>
      ))}
      {assistant.loading && <div>Thinking...</div>}
      <input value={input} onChange={(e) => setInput(e.target.value)} />
      <button onClick={handleSend} disabled={assistant.loading}>
        Send
      </button>
    </div>
  )
}
```

---

## Configuration Options

### Backend URL Configuration

**Development** (localhost):
```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

**Production** (remote server):
```bash
# .env.production.local
NEXT_PUBLIC_API_URL=https://api.arthainvestment.com/api/v1
```

**Docker** (internal networking):
```bash
# .env.docker
NEXT_PUBLIC_API_URL=http://backend:8000/api/v1
```

### Component Customization

All UI pages follow consistent patterns for customization:

1. **Styling**: Use Tailwind CSS classes in component JSX
2. **Colors**: Update className patterns (e.g., `bg-blue-600` to `bg-indigo-600`)
3. **Layout**: Modify grid columns (`grid-cols-2 lg:grid-cols-4`)
4. **Content**: Update placeholder text and descriptions

---

## Performance Considerations

### Optimization Applied
- ✅ React hooks memoization for request deduplication
- ✅ Lazy loading markdown renderer via import
- ✅ CSS-in-JS for efficient styling
- ✅ Event debouncing on input fields
- ✅ Auto-scroll implementation in assistant chat

### Recommendations for Scale
1. Add request caching (localStorage or Redis)
2. Implement pagination for large datasets
3. Add WebSocket support for real-time updates
4. Consider streaming responses for long-running tasks
5. Implement rate limiting on frontend

---

## Troubleshooting

### Issue: "Cannot GET /explanations"
**Cause**: Page route not found
**Solution**: Ensure `frontend/app/explanations/page.tsx` exists

### Issue: "API error: 404"
**Cause**: Backend endpoint not available
**Solution**: Verify backend running and routes registered in `app/main.py`

### Issue: CORS error in browser console
**Cause**: Backend missing CORS headers
**Solution**: Ensure FastAPI has CORS middleware configured

### Issue: "Module not found: react-markdown"
**Cause**: Dependency not installed
**Solution**: Run `npm install react-markdown`

### Issue: Slow responses (>10 seconds)
**Cause**: LLM API latency
**Solution**: Check Gemini API rate limits and quota

---

## Next Steps

### Immediate (Phase 4 Completion)
1. ✅ Deploy frontend to production
2. ✅ Connect to production backend
3. ✅ Update environment variables
4. ✅ Test all pages in production environment

### Short-term (Phase 5)
1. Add report storage functionality (SavedReport model)
2. Implement email/PDF export for research reports
3. Add conversation history persistence for assistant
4. Build report management interface (view, edit, delete saved reports)

### Long-term (Phase 6+)
1. Add real-time streaming responses for long-running tasks
2. Implement full-text search across saved reports
3. Add collaboration features (share reports)
4. Build custom report templates
5. Integrate with portfolio tracking

---

## Documentation Files

All related documentation:
- **Backend API**: `backend/API_GUIDE.md`
- **Research Service**: `backend/RESEARCH_GUIDE.md`
- **Explanation Service**: `backend/EXPLANATION_GUIDE.md`
- **Frontend Setup**: This file
- **Database Schema**: `backend/DATABASE.md`

---

## Support & Questions

For issues or questions:
1. Check troubleshooting section above
2. Review backend logs: `backend/app.log`
3. Check frontend console: `F12` → Console tab
4. Review API responses in Network tab

---

**Version**: 1.0  
**Last Updated**: 2026-11-15  
**Status**: Production Ready
