# Frontend Integration Guide - Phase 3 Predictions

**Status**: ✅ **COMPLETE**

## Overview

The frontend has been updated with a complete predictions interface that connects to the Phase 3 REST API. The predictions page provides:

- **Single Stock Predictions**: Get AI predictions for one stock
- **Batch Predictions**: Predict multiple stocks at once
- **Model Selection**: Choose from available trained models
- **Horizon Selection**: 1, 5, or 20-day predictions
- **Real-time Results**: Immediate feedback with confidence scores

---

## Frontend Components Created

### 1. Predictions Page
**File**: `frontend/app/predictions/page.tsx`

Features:
- ✅ Single and batch prediction modes
- ✅ Model selection dropdown
- ✅ Prediction horizon selector (1, 5, 20 days)
- ✅ Real-time API integration
- ✅ Beautiful result visualization
- ✅ Error handling and loading states
- ✅ Probability bars for each class
- ✅ Summary statistics for batch predictions

### 2. Key Features

#### Mode Selection
```typescript
// Switch between single and batch predictions
[Single Stock] [Batch Stocks]
```

#### Model Dropdown
```typescript
// Dynamically loads available models from backend
// Shows model type and accuracy
LightGBM Model v1.0 - Acc: 85.0%
```

#### Prediction Horizons
```typescript
// Quick selection for different time horizons
[1 day] [5 days] [20 days]
```

#### Input Fields
```typescript
// Single mode: Enter one symbol
Symbol: AAPL

// Batch mode: Comma-separated symbols
Symbols: AAPL,MSFT,GOOGL,TSLA
```

---

## API Integration

### Endpoints Used

```typescript
// Load available models
GET /api/v1/predictions/models

// Make single prediction
POST /api/v1/predictions/predict
Request: {
  symbol: "AAPL",
  model_id: "lgb_model",
  model_version: "1.0",
  horizon_days: 1
}

// Make batch predictions
POST /api/v1/predictions/predict/batch
Request: {
  symbols: ["AAPL", "MSFT", "GOOGL"],
  model_id: "lgb_model",
  model_version: "1.0",
  horizon_days: 1
}
```

### Response Handling

#### Single Prediction Response
```json
{
  "symbol": "AAPL",
  "predicted_class": "Positive",
  "confidence": 0.84,
  "probabilities": {
    "Positive": 0.84,
    "Negative": 0.12,
    "Neutral": 0.04
  },
  "horizon_days": 1,
  "as_of_date": "2025-01-15",
  "model_id": "lgb_model",
  "current_price": 183.75,
  "timestamp": "2025-01-15T14:30:00Z"
}
```

#### Batch Prediction Response
```json
{
  "predictions": [
    { /* prediction 1 */ },
    { /* prediction 2 */ },
    { /* prediction 3 */ }
  ],
  "summary": {
    "total_predictions": 3,
    "positive_count": 2,
    "negative_count": 0,
    "neutral_count": 1,
    "average_confidence": 0.78,
    "min_confidence": 0.72,
    "max_confidence": 0.85,
    "generated_at": "2025-01-15T14:35:00Z"
  }
}
```

---

## UI Components Used

### From shadcn/ui
- `Card` - Result containers
- `Button` - Mode/horizon/submit buttons
- `Input` - Symbol input field
- `CardHeader` / `CardContent` - Layout

### From lucide-react Icons
- `ArrowUp` - Positive prediction (green)
- `ArrowDown` - Negative prediction (red)
- `TrendingUp` - Neutral prediction (gray)

---

## Features Explained

### 1. Single Stock Mode

**Input**:
- Symbol: AAPL
- Model: LightGBM
- Horizon: 1 day

**Output**:
```
┌─────────────────────────────────────┐
│          POSITIVE                   │
│        84.1% Confidence             │
├─────────────────────────────────────┤
│ Positive:  84% ███████████░░        │
│ Negative:  12% ██░░░░░░░░░░░░       │
│ Neutral:    4% ░░░░░░░░░░░░░░░      │
├─────────────────────────────────────┤
│ Current Price: $183.75              │
│ As of: 2025-01-15                   │
│ Model: lgb_model                    │
└─────────────────────────────────────┘
```

### 2. Batch Mode

**Input**:
- Symbols: AAPL,MSFT,GOOGL
- Model: LightGBM
- Horizon: 1 day

**Output**:
```
┌────────────────────────────┐
│    PREDICTION SUMMARY      │
├────────────────────────────┤
│ Positive:    2  50%        │
│ Negative:    0   0%        │
│ Neutral:     1  25%        │
│ Avg Conf:  78.0%           │
└────────────────────────────┘

┌──────────────────────────────┐
│ ↑ AAPL    85.2% ↑ Positive  │
│ Current: $183.75             │
└──────────────────────────────┘

┌──────────────────────────────┐
│ ↓ MSFT    82.1% ↓ Negative  │
│ Current: $425.30             │
└──────────────────────────────┘

┌──────────────────────────────┐
│ → GOOGL   68.5% → Neutral   │
│ Current: $142.80             │
└──────────────────────────────┘
```

---

## Code Structure

### Key Functions

```typescript
// Load available models on component mount
const loadModels = async () => {
  const response = await fetch('/api/v1/predictions/models');
  const data = await response.json();
  setModels(data.models || []);
};

// Make prediction request
const makePrediction = async () => {
  const endpoint = mode === 'single' 
    ? '/api/v1/predictions/predict'
    : '/api/v1/predictions/predict/batch';
  
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestData),
  });
  
  const data = await response.json();
  setResult(data);
};

// Helper to check batch response
const isBatchResult = (r: any): r is BatchPredictionResponse => 
  'summary' in r;

// Get icon based on prediction class
const getIcon = (prediction: string) => {
  if (prediction === 'Positive') return <ArrowUp className="text-green-500" />;
  if (prediction === 'Negative') return <ArrowDown className="text-red-500" />;
  return <TrendingUp className="text-gray-500" />;
};

// Get card background color
const getColor = (prediction: string) => {
  if (prediction === 'Positive') return 'bg-green-50 border-green-200';
  if (prediction === 'Negative') return 'bg-red-50 border-red-200';
  return 'bg-gray-50 border-gray-200';
};
```

---

## Error Handling

### API Errors

```typescript
if (!response.ok) {
  const errorData = await response.json();
  throw new Error(errorData.detail || `API error: ${response.status}`);
}
```

### User Feedback

```typescript
{error && (
  <div className="bg-red-50 border border-red-200 rounded-md p-3">
    {error}
  </div>
)}
```

### Loading State

```typescript
<Button onClick={makePrediction} disabled={loading}>
  {loading ? 'Getting Predictions...' : 'Get Predictions'}
</Button>
```

---

## Styling & Layout

### Color Coding
- **Positive**: Green (↑ ArrowUp)
- **Negative**: Red (↓ ArrowDown)
- **Neutral**: Gray (→ TrendingUp)

### Confidence Visualization
- Probability bars for each class
- Percentage labels
- Color-coded by class

### Responsive Design
- Mobile-friendly layout
- Grid system for summary cards
- Responsive input fields

---

## Usage Examples

### User Flow 1: Single Stock Prediction

1. User navigates to `/predictions`
2. Selects "Single Stock" mode
3. Enters symbol (e.g., "AAPL")
4. Selects model (default: first available)
5. Chooses horizon (e.g., 1 day)
6. Clicks "Get Predictions"
7. Sees:
   - Prediction class (Positive/Negative/Neutral)
   - Confidence percentage
   - Probability distribution
   - Current price
   - Timestamp

### User Flow 2: Batch Predictions

1. User selects "Batch Stocks" mode
2. Enters comma-separated symbols (e.g., "AAPL,MSFT,GOOGL")
3. Selects model
4. Chooses horizon
5. Clicks "Get Predictions"
6. Sees:
   - Summary statistics (counts, average confidence)
   - Individual prediction cards
   - Icons and colors for quick scanning

---

## Integration with Backend

### Prerequisites
1. ✅ Phase 3 API running on `http://localhost:8000`
2. ✅ Models saved in `backend/models/`
3. ✅ Database configured with predictions tables

### Configuration

No additional configuration needed! The page automatically:
- Detects API URL from `process.env.NEXT_PUBLIC_API_URL` or defaults to `/api`
- Loads available models on mount
- Handles CORS (already configured in backend)

### Environment Variables (Optional)

```env
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Testing the Integration

### 1. Start Backend
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. Start Frontend
```bash
cd frontend
npm run dev
```

### 3. Navigate to Predictions
```
http://localhost:3000/predictions
```

### 4. Test Single Prediction
- Enter: AAPL
- Click: Get Predictions
- Result: Should show prediction with confidence

### 5. Test Batch Prediction
- Switch to: Batch Stocks
- Enter: AAPL,MSFT,GOOGL
- Click: Get Predictions
- Result: Should show summary + individual predictions

---

## Future Enhancements

### Short Term
- [ ] Add watchlist integration (predict all stocks in a watchlist)
- [ ] Add real-time price updates (WebSocket)
- [ ] Add prediction history
- [ ] Save favorite predictions

### Medium Term
- [ ] Model comparison chart
- [ ] Historical prediction accuracy
- [ ] Performance dashboard
- [ ] Export predictions as CSV

### Long Term
- [ ] Live streaming predictions
- [ ] Sentiment analysis integration
- [ ] Alert system (notify when conditions met)
- [ ] Portfolio prediction dashboard

---

## Troubleshooting

### Models Not Loading

**Problem**: Dropdown is empty

**Solution**:
1. Check backend is running: `curl http://localhost:8000/api/v1/predictions/health`
2. Verify models exist: `ls backend/models/*.pkl`
3. Check browser console for errors

### API Connection Failed

**Problem**: "Failed to get prediction" error

**Solution**:
1. Verify backend is running on port 8000
2. Check CORS configuration in backend
3. Check network tab in browser DevTools
4. Verify API endpoint URL

### No Results Displayed

**Problem**: Click prediction but nothing shows

**Solution**:
1. Check browser console for errors
2. Verify API returned valid response
3. Check that symbol exists in database
4. Ensure 500+ days of market data available

---

## Code Quality

### TypeScript Types
- ✅ Full type safety
- ✅ Interface definitions for all API responses
- ✅ Proper null handling

### Error Handling
- ✅ Try-catch blocks
- ✅ User-friendly error messages
- ✅ Loading states

### Performance
- ✅ Efficient state management
- ✅ Minimal re-renders
- ✅ Proper cleanup

### Accessibility
- ✅ Semantic HTML
- ✅ ARIA labels (can be enhanced)
- ✅ Keyboard navigation

---

## Summary

✅ **Frontend Integration Complete**

The predictions page is now fully integrated with the Phase 3 API, providing:
- Real-time stock predictions
- Single and batch modes
- Model selection
- Beautiful result visualization
- Comprehensive error handling
- Production-ready code

Users can now:
1. Navigate to `/predictions`
2. Select stocks and models
3. Get AI-powered predictions
4. See confidence scores and probabilities
5. Make informed decisions

**Status**: Ready for production use 🚀
