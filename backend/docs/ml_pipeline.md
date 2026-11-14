# ML Pipeline: Prediction Objectives and Feature Engineering

## Overview

The ML pipeline (Phase 2.1 & 2.2) implements two core components for training machine learning models:

1. **Prediction Objectives (2.1)**: Generate classification targets for multi-class prediction
2. **Feature Engineering (2.2)**: Build comprehensive feature sets from OHLCV data

## Phase 2.1: Prediction Objectives

### Concept

Prediction objectives convert continuous price movements into discrete classification targets:
- **Positive**: Forward return ≥ upper threshold (default: +1%)
- **Neutral**: Forward return between thresholds (default: -1% to +1%)
- **Negative**: Forward return ≤ lower threshold (default: -1%)

### Supported Horizons

- **1-day**: Next trading day return
- **5-day**: Return over next 5 trading days
- **20-day**: Return over next 20 trading days (~1 month)

### Key Design: No Forward Leakage

Targets are computed using forward returns **only**, ensuring no information from the target date or later leaks into features:

```python
# For observation at date T:
# Target = (Price[T+H] - Price[T]) / Price[T] × 100
# Where H = horizon (1, 5, 20 days)
```

### Usage Example

```python
from app.ml.prediction_targets import TargetConfig, TargetGenerator
import pandas as pd

# Load OHLCV data
ohlcv_df = pd.read_csv("historical_data.csv")

# Configure targets
config = TargetConfig(
    thresholds_pct=(-1.0, 1.0),  # ±1% thresholds
    horizons_days=[1, 5, 20],
)

# Generate targets
generator = TargetGenerator(config)
targets_df = generator.generate(ohlcv_df)

# Get baseline predictor (majority class)
baseline_1d = generator.get_baseline_predictor(targets_df, horizon_days=1)
print(f"Baseline for 1-day: {baseline_1d}")

# Output columns:
# - trading_date
# - {horizon}_day_return_pct (for each horizon)
# - {horizon}_day_target (Positive, Negative, or Neutral)
# - data_available (True if sufficient forward data)
```

### Configuration

```python
@dataclass
class TargetConfig:
    thresholds_pct: tuple[float, float] = (-1.0, 1.0)
    horizons_days: list[int] = [1, 5, 20]
    price_field: Literal["close", "adjusted_close"] = "close"
```

### Database Integration

**Note**: Targets are computed on-the-fly during dataset generation. No database tables are required—targets are deterministic from OHLCV data.

---

## Phase 2.2: Feature Engineering

### Feature Categories

#### 1. Price Returns
- **Periods**: 1, 5, 20 days (configurable)
- **Calculation**: Percentage or log returns
- **Columns**: `return_{period}d`

#### 2. Moving Averages
- **SMA** (Simple Moving Average): 20, 50, 200 periods
- **EMA** (Exponential Moving Average): 12, 26 periods
- **Columns**: `sma_{period}`, `ema_{period}`

#### 3. Momentum Indicators
- **RSI** (Relative Strength Index, 14-period)
- **MACD** (12/26/9): MACD line, signal line, histogram
- **Columns**: `rsi_14`, `macd`, `macd_signal`, `macd_histogram`

#### 4. Volatility Measures
- **ATR** (Average True Range, 14-period): Normalized volatility
- **Bollinger Bands** (20-period, 2 std dev): Upper, middle, lower bands
- **ADX** (Average Directional Index, 14-period): Trend strength
- **Columns**: `atr_14`, `bb_upper`, `bb_middle`, `bb_lower`, `adx_14`

#### 5. Volume Features
- **Volume Ratio**: Current volume / 20-day average volume
- **Volume Change**: Percentage change in volume
- **Columns**: `volume_ratio_20d`, `volume_change`

#### 6. Market Structure
- **VWAP** (Volume Weighted Average Price)
- **SuperTrend**: Trend-following indicator
- **Support/Resistance**: 20-period min/max
- **Columns**: `vwap`, `supertrend`

#### 7. Price Level Features
- **High-Low Ratio**: (High / Low)
- **Close-to-High**: (Close / High)
- **Close-to-Low**: (Close / Low)
- **Columns**: `high_low_ratio`, `close_to_high`, `close_to_low`

### Usage Example

```python
from app.ml.feature_engineering import FeatureConfig, DatasetGenerator
from app.ml.prediction_targets import TargetConfig, TargetGenerator

# Load OHLCV data
ohlcv_df = pd.read_csv("historical_data.csv")

# Configure features
feature_config = FeatureConfig(
    returns_periods=[1, 5, 20],
    sma_periods=[20, 50, 200],
    ema_periods=[12, 26],
)

# Generate features
dataset_gen = DatasetGenerator(feature_config)
features_df = dataset_gen.generate_features(ohlcv_df)

# Generate targets
target_config = TargetConfig()
target_gen = TargetGenerator(target_config)
targets_df = target_gen.generate(ohlcv_df)

# Merge for training
X, y = dataset_gen.get_training_set(
    features_df, targets_df,
    horizon_days=1,
    dropna=True,
)

print(f"Training set: {X.shape[0]} samples, {X.shape[1]} features")
print(f"Target distribution:\n{y.value_counts()}")
```

### Configuration

```python
@dataclass
class FeatureConfig:
    returns_periods: list[int] = [1, 5, 20]
    sma_periods: list[int] = [20, 50, 200]
    ema_periods: list[int] = [12, 26]
    use_normalized_features: bool = False      # Normalize to [0, 1]
    use_log_features: bool = False             # Log returns vs %
    handle_missing: str = "forward_fill"       # or "drop"
    validate_finite: bool = True               # Reject NaN/Inf
```

### Missing Value Handling

Two strategies:

1. **forward_fill** (default): Forward-fill NaN values, then backward-fill at start
   - Preserves temporal structure
   - Assumes missing values are temporary

2. **drop**: Remove rows with any NaN values
   - More conservative
   - Reduces dataset size

### Data Quality Features

- **Validation**: Checks for finite values (no NaN, Inf, -Inf)
- **Alignment**: Ensures features are sorted by trading_date
- **Warmup Period**: Early rows may have NaN (warming up indicators)

---

## Complete Pipeline: End-to-End Example

```python
from datetime import date
from app.db.session import SessionLocal
from app.db.models import Company, DailyMarketData
from sqlalchemy import select
import pandas as pd

from app.ml.prediction_targets import TargetConfig, TargetGenerator
from app.ml.feature_engineering import FeatureConfig, DatasetGenerator

# 1. Load historical data from database
def load_ohlcv_from_db(symbol: str, min_date: date, max_date: date) -> pd.DataFrame:
    with SessionLocal() as db:
        company = db.scalar(select(Company).where(Company.symbol == symbol))
        if not company:
            raise ValueError(f"Unknown symbol: {symbol}")
        
        data = db.scalars(
            select(DailyMarketData)
            .where(DailyMarketData.company_id == company.id)
            .where(DailyMarketData.trading_date >= min_date)
            .where(DailyMarketData.trading_date <= max_date)
            .order_by(DailyMarketData.trading_date)
        )
        
        records = []
        for row in data:
            records.append({
                "trading_date": row.trading_date,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "adjusted_close": float(row.adjusted_close or row.close),
                "volume": row.volume,
            })
        
        return pd.DataFrame(records)

# 2. Load data
ohlcv_df = load_ohlcv_from_db("AAPL", date(2023, 1, 1), date(2025, 1, 1))

# 3. Generate targets
target_config = TargetConfig()
target_gen = TargetGenerator(target_config)
targets_df = target_gen.generate(ohlcv_df)

# 4. Generate features
feature_config = FeatureConfig()
dataset_gen = DatasetGenerator(feature_config)
features_df = dataset_gen.generate_features(ohlcv_df)

# 5. Get training set for 1-day prediction
X_train, y_train = dataset_gen.get_training_set(
    features_df, targets_df,
    horizon_days=1,
    min_date=date(2023, 1, 1),
    max_date=date(2024, 12, 31),
    dropna=True,
)

print(f"Training set:")
print(f"  Samples: {X_train.shape[0]}")
print(f"  Features: {X_train.shape[1]}")
print(f"  Target distribution:\n{y_train.value_counts()}")

# 6. (Later) Pass X_train, y_train to ML model
```

---

## Key Design Principles

### 1. No Data Leakage
- Forward returns computed at time T only use prices up to T
- Features computed at time T never reference T+1 or later
- Temporal alignment strictly enforced

### 2. Modular & Reusable
- Pipeline operates on generic DataFrames, not tied to database
- Configurable via dataclasses (thresholds, periods, indicators)
- Can be used with any OHLCV source (CSV, API, database)

### 3. Deterministic
- No randomness in feature/target calculation
- Identical inputs produce identical outputs
- Reproducible for all training runs

### 4. Production-Ready
- Comprehensive input validation
- Missing value handling strategies
- Finite value checks
- Proper error messages

---

## Integration with Existing Code

### Indicators Engine
Feature engineering reuses existing `app.services.indicators.calculate_indicators()`:
- RSI, MACD, Bollinger Bands, ATR, ADX, SuperTrend, VWAP
- No duplicate indicator code

### Database Models
Data is loaded from `DailyMarketData` table:
- No new database tables required
- Targets/features computed on-the-fly

### Testing
Comprehensive test suites:
- `tests/test_prediction_targets.py`: 40+ test cases
- `tests/test_feature_engineering.py`: 50+ test cases
- Edge cases, validation, temporal alignment covered

---

## Performance Considerations

### Memory Usage
- Feature generation is pandas-native (vectorized operations)
- Scales efficiently to 10+ years of daily data per symbol
- Typical memory: ~100MB for 10 years × 100 symbols

### Computation Time
- Feature generation: ~1-2 seconds per 5 years of data
- Indicator calculation: ~2-5 seconds (bottleneck)
- Target generation: <100ms per 5 years of data

### Optimization Tips
1. Pre-compute features for common instruments (cache)
2. Use `include_indicators=False` if indicators not needed
3. Batch process multiple instruments in parallel

---

## Limitations & Future Work

### Current Limitations
1. Single price field (no multi-timeframe features)
2. No external features (macro, sentiment, news)
3. No sector/market features
4. No survivorship bias handling

### Future Enhancements
1. Multi-timeframe features (hourly, 4H candles)
2. News sentiment integration
3. Sector/industry momentum
4. Volatility regime detection
5. Cross-asset correlations

---

## Testing & Validation

### Test Coverage
- **Targets**: Configuration validation, classification logic, forward return calculation, temporal alignment
- **Features**: Configuration, feature generation, missing value handling, leakage prevention, completeness

### Running Tests
```bash
# All tests
pytest tests/test_prediction_targets.py tests/test_feature_engineering.py -v

# Specific test class
pytest tests/test_prediction_targets.py::TestTargetGenerator -v

# With coverage
pytest --cov=app.ml tests/test_prediction_targets.py tests/test_feature_engineering.py
```

---

## Next Steps (Phase 3)

Once features and targets are ready:

1. **Dataset Validation Report**: Statistical summary of features/targets
2. **Model Training**: Implement baseline models (logistic regression, random forest)
3. **Cross-Validation**: K-fold validation on historical data
4. **Backtest**: Simulate trading with model predictions
5. **Live Prediction**: Deploy model via API endpoint
