# Model Evaluation & Backtesting: Phases 2.4 & 2.5

Comprehensive framework for evaluating model performance and simulating historical trading strategies.

## Overview

### Phase 2.4: Model Evaluation
- Chronological train/validation/test splits
- Walk-forward validation to prevent overfitting
- Classification metrics (accuracy, precision, recall, F1, ROC-AUC)
- Financial performance metrics
- Strategy comparison framework

### Phase 2.5: Backtesting
- Historical strategy simulator
- Transaction costs and slippage
- Position sizing and risk management
- Drawdown and Sharpe ratio tracking
- Benchmark strategy comparison

---

## Phase 2.4: Model Evaluation

### Temporal Data Splits

Ensure no data leakage by splitting data **chronologically**, not randomly.

```python
from app.ml.evaluation import TemporalSplitter, EvaluationConfig

config = EvaluationConfig(
    train_size=0.6,  # 60% for training
    val_size=0.2,    # 20% for validation
    test_size=0.2,   # 20% for testing
)

splitter = TemporalSplitter(config)
(X_train, y_train), (X_val, y_val), (X_test, y_test) = splitter.split(X, y)
```

### Walk-Forward Validation

Simulate real-world model deployment where model is retrained periodically:

```python
splitter = TemporalSplitter(EvaluationConfig(walk_forward_step=20))
splits = splitter.walk_forward_splits(X, y, initial_train_size=100)

for (X_train, y_train), (X_val, y_val) in splits:
    # Train model on X_train
    # Validate on X_val (future data)
    # Training set expands with each fold
    pass
```

**Benefits**:
- Prevents overfitting to training period
- Tests model on truly unseen data
- More realistic performance estimates
- Matches production deployment pattern

### Classification Metrics

Evaluate model predictions with multiple metrics:

```python
from app.ml.evaluation import ClassificationEvaluator

metrics = ClassificationEvaluator.evaluate(
    y_true,
    y_pred,
    y_proba=y_pred_probabilities
)

print(f"Accuracy:  {metrics.accuracy:.4f}")
print(f"Precision: {metrics.precision:.4f}")
print(f"Recall:    {metrics.recall:.4f}")
print(f"F1 Score:  {metrics.f1:.4f}")
print(f"ROC-AUC:   {metrics.roc_auc:.4f}")
```

**Metrics**:
- **Accuracy**: Overall correctness
- **Precision**: Of predicted positives, how many are correct
- **Recall**: Of actual positives, how many we caught
- **F1 Score**: Harmonic mean of precision and recall
- **ROC-AUC**: Area under ROC curve (for binary classification)

### Financial Metrics

Evaluate trading performance separately from classification:

```python
from app.ml.evaluation import FinancialEvaluator

returns = price.pct_change()
trades = (predictions != 0).astype(int)

fin_metrics = FinancialEvaluator().evaluate(returns, trades)

print(f"Total Return:     {fin_metrics.total_return:.2f}%")
print(f"Annual Return:    {fin_metrics.annual_return:.2f}%")
print(f"Max Drawdown:     {fin_metrics.max_drawdown:.2f}%")
print(f"Sharpe Ratio:     {fin_metrics.sharpe_ratio:.2f}")
print(f"Win Rate:         {fin_metrics.win_rate:.2f}%")
print(f"Profit Factor:    {fin_metrics.profit_factor:.2f}")
```

**Financial Metrics**:
- **Total Return**: Percentage gain/loss
- **Annualized Return**: Yearly return estimate
- **Max Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted return
- **Win Rate**: % of profitable trades
- **Profit Factor**: Gross profit / Gross loss

### Complete Model Evaluation

```python
from app.ml.evaluation import ModelEvaluator

evaluator = ModelEvaluator()

# Single test set evaluation
result = evaluator.evaluate_on_test_set(
    trained_model,
    X_test,
    y_test,
    prices=test_prices,
    model_name="RandomForest"
)

print(evaluator.get_evaluation_summary(result))

# Walk-forward evaluation
def train_model(X_train, y_train):
    model = RandomForestClassifier(n_estimators=100)
    model.fit(X_train, y_train)
    return model

results = evaluator.walk_forward_validate(
    train_model,
    X, y,
    prices=prices,
    model_name="RandomForest"
)

# Compare results
comparison = ModelEvaluator.compare_evaluations(results)
print(comparison)
```

---

## Phase 2.5: Backtesting

### Backtest Engine

Execute historical trading strategies with realistic market conditions:

```python
from app.ml.backtesting import BacktestEngine, BacktestConfig

config = BacktestConfig(
    initial_capital=100000.0,
    commission=0.001,      # 0.1% per trade
    slippage=0.0005,       # 0.05% slippage
    max_position_size=0.1, # 10% max per trade
)

engine = BacktestEngine(config)
result = engine.backtest(prices, signals, strategy_name="MyStrategy")
```

### Backtest Configuration

```python
BacktestConfig(
    initial_capital=100000.0,      # Starting capital
    commission=0.001,              # Commission per trade (%)
    slippage=0.0005,               # Execution slippage (%)
    max_position_size=0.1,         # Max position (% of capital)
    risk_per_trade=0.02,           # Risk per trade (% of capital)
    min_trade_size=100.0,          # Minimum trade amount ($)
)
```

### Trading Signals

Create trading signals for the backtest:

```python
# 0 = no action, 1 = buy, -1 = sell
signals = pd.Series(0, index=prices.index)
signals.iloc[0] = 1       # Buy on first day
signals.iloc[50] = -1     # Sell on day 50
signals.iloc[100] = 1     # Buy again
```

### Backtest Results

```python
result = engine.backtest(prices, signals, "MyStrategy")

print(f"Strategy: {result.strategy_name}")
print(f"Period: {result.start_date} to {result.end_date}")
print(f"Initial Capital: ${result.initial_capital:,.2f}")
print(f"Final Value: ${result.final_value:,.2f}")
print(f"Total Return: {result.total_return:.2f}%")
print(f"Annualized Return: {result.annual_return:.2f}%")
print(f"Max Drawdown: {result.max_drawdown:.2f}%")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Win Rate: {result.win_rate:.2f}%")
print(f"Trades: {result.num_trades}")
```

### Benchmark Strategies

Compare your strategy against standard benchmarks:

```python
from app.ml.backtesting import BenchmarkStrategies, BacktestComparator

# Run benchmarks
buy_hold = BenchmarkStrategies.buy_and_hold(prices)
sma = BenchmarkStrategies.simple_moving_average(prices, 20, 50)
random = BenchmarkStrategies.random_signals(prices)

# Your strategy
my_result = engine.backtest(prices, my_signals, "MyStrategy")

# Compare
results = [buy_hold, sma, random, my_result]
comparison = BacktestComparator.compare_results(results)
print(comparison)
```

**Benchmark Strategies**:
- **Buy & Hold**: Buy first day, hold until end
- **SMA Crossover**: Buy when short MA > long MA
- **Random Trading**: Random buy/sell signals

---

## Real vs. Simulated Results

### Important Disclaimer

Backtesting results are **SIMULATIONS** and may not reflect real-world performance:

⚠️ **Simulated Results Assume**:
- Perfect trade execution at prices
- No slippage or latency
- Instant order fills
- No market impact
- Constant parameters over time
- Sufficient liquidity

**Real Trading May Experience**:
- Worse execution prices
- Slippage and spreads
- Order rejections/partial fills
- Market impact
- Changing market conditions
- Transaction costs and taxes
- Psychological factors

### Good Practices

1. **Separate Metrics**: Track classification metrics AND financial performance
2. **Walk-Forward Validation**: Use expanding window to test robustness
3. **Out-of-Sample Testing**: Always hold back test set
4. **Multiple Strategies**: Compare against benchmarks
5. **Realistic Costs**: Include slippage, commissions, taxes
6. **Sensitivity Analysis**: Test different market conditions

---

## Complete Example

```python
from app.ml.prediction_targets import TargetGenerator, TargetConfig
from app.ml.feature_engineering import DatasetGenerator, FeatureConfig
from app.ml.models import ModelComparator
from app.ml.evaluation import ModelEvaluator, TemporalSplitter
from app.ml.backtesting import BacktestEngine, BacktestConfig, BenchmarkStrategies, BacktestComparator

# Step 1: Prepare data
targets = TargetGenerator(TargetConfig()).generate(ohlcv_df)
features = DatasetGenerator(FeatureConfig()).generate_features(ohlcv_df)
X, y = DatasetGenerator().get_training_set(features, targets, horizon_days=1)

# Step 2: Temporal split
splitter = TemporalSplitter()
(X_train, y_train), (X_val, y_val), (X_test, y_test) = splitter.split(X, y)

# Step 3: Train models
comparator = ModelComparator()
comparator.train_baseline(X_train, y_train)
comparator.train_random_forest(X_train, y_train)
comparator.train_xgboost(X_train, y_train)

# Step 4: Evaluate models
evaluator = ModelEvaluator()
results = []
for name, trainer in comparator.models.items():
    result = evaluator.evaluate_on_test_set(
        trainer, X_test, y_test,
        prices=test_prices,
        model_name=name
    )
    results.append(result)

# Step 5: Compare evaluations
comparison = ModelEvaluator.compare_evaluations(results)
print(comparison)

# Step 6: Select best model
best_name, best_model = comparator.get_best_model(metric="f1")

# Step 7: Generate trading signals
predictions = best_model.predict(X_test)
signals = pd.Series(0, index=X_test.index)
signals[predictions != 0] = 1

# Step 8: Backtest strategy
backtest_config = BacktestConfig(initial_capital=100000)
engine = BacktestEngine(backtest_config)
strategy_result = engine.backtest(test_prices, signals, best_name)

# Step 9: Compare with benchmarks
buy_hold = BenchmarkStrategies.buy_and_hold(test_prices)
sma = BenchmarkStrategies.simple_moving_average(test_prices, 20, 50)

# Step 10: Final comparison
backtest_results = [strategy_result, buy_hold, sma]
final_comparison = BacktestComparator.compare_results(backtest_results)
print(final_comparison)

# Print summary
print(BacktestComparator.get_backtest_summary(strategy_result))
```

---

## Key Insights

### Classification vs. Financial Metrics
- High accuracy ≠ High returns
- Model must predict profitable movements
- Need to account for costs and execution

### Walk-Forward Validation
- Prevents overfitting to specific periods
- Tests on unseen future data
- Matches production deployment

### Temporal Alignment
- Always split chronologically
- Avoid lookahead bias
- Train on past, validate/test on future

### Realistic Simulation
- Include commissions and slippage
- Limit position sizes
- Manage risk per trade

### Benchmark Comparison
- Compare against buy-and-hold
- Compare against simple strategies
- Determine if model adds value

---

## API Reference

### TemporalSplitter
- `split(X, y)`: Split into train/val/test
- `walk_forward_splits(X, y, initial_train_size)`: Generate walk-forward folds

### ClassificationEvaluator
- `evaluate(y_true, y_pred, y_proba)`: Calculate classification metrics

### FinancialEvaluator
- `evaluate(returns, trades)`: Calculate financial metrics

### ModelEvaluator
- `evaluate_on_test_set(model, X_test, y_test, prices)`: Full evaluation
- `walk_forward_validate(model_builder, X, y, prices)`: Walk-forward evaluation
- `compare_evaluations(results)`: Create comparison table

### BacktestEngine
- `backtest(prices, signals, strategy_name)`: Execute backtest

### BenchmarkStrategies
- `buy_and_hold(prices)`: Buy and hold strategy
- `simple_moving_average(prices, short, long)`: SMA crossover
- `random_signals(prices, probability)`: Random trading

### BacktestComparator
- `compare_results(results)`: Create comparison table
- `get_backtest_summary(result)`: Formatted summary

---

## Testing

Run comprehensive tests:

```bash
pytest tests/test_evaluation.py tests/test_backtesting.py -v
```

---

## Files

- **Evaluation**: `app/ml/evaluation.py`
- **Backtesting**: `app/ml/backtesting.py`
- **Tests**: `tests/test_evaluation.py`, `tests/test_backtesting.py`
- **Documentation**: This file

