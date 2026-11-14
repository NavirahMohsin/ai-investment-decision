# Model Development: Phase 2.3

Comprehensive machine learning model development pipeline with baseline, ensemble, and gradient boosting models.

## Overview

Phase 2.3 implements four classification models for stock price prediction:

1. **Logistic Regression** (Baseline)
2. **Random Forest** (Ensemble)
3. **XGBoost** (Gradient Boosting)
4. **LightGBM** (Gradient Boosting)

Features:
- Model training with configurable hyperparameters
- Cross-validation evaluation
- Hyperparameter tuning via grid search
- Model comparison and selection
- Feature importance analysis

---

## Models

### 1. Logistic Regression (Baseline)

**Purpose**: Simple, interpretable baseline for comparison

**Configuration**:
```python
LogisticRegressionConfig(
    C=1.0,              # Inverse regularization strength
    max_iter=1000,      # Maximum iterations
    solver="lbfgs",     # Solver algorithm
    penalty="l2",       # L2 regularization
)
```

**Strengths**:
- Fast training
- Interpretable coefficients
- Good baseline for comparison
- Scales well to large datasets

**Use Cases**:
- Baseline model
- Feature coefficient analysis
- Quick prototyping

### 2. Random Forest

**Purpose**: Robust ensemble model with feature importance

**Configuration**:
```python
RandomForestConfig(
    n_estimators=100,       # Number of trees
    max_depth=None,         # No depth limit
    min_samples_split=2,    # Min samples to split
    min_samples_leaf=1,     # Min samples in leaf
    max_features="sqrt",    # Features per split
)
```

**Strengths**:
- Handles non-linear relationships
- Feature importance readily available
- Robust to outliers
- No feature scaling required

**Use Cases**:
- Production baseline
- Feature importance analysis
- Medium-sized datasets

### 3. XGBoost

**Purpose**: High-performance gradient boosting for complex patterns

**Configuration**:
```python
XGBoostConfig(
    n_estimators=100,       # Boosting rounds
    max_depth=6,            # Tree depth
    learning_rate=0.1,      # Step size
    subsample=0.8,          # Row sampling
    colsample_bytree=0.8,   # Column sampling
    reg_alpha=0.0,          # L1 regularization
    reg_lambda=1.0,         # L2 regularization
)
```

**Strengths**:
- Excellent predictive performance
- Handles missing values
- Built-in feature importance
- Fast training

**Use Cases**:
- Production models
- Complex datasets
- Competition/benchmarking

### 4. LightGBM

**Purpose**: Fast gradient boosting for large datasets

**Configuration**:
```python
LightGBMConfig(
    n_estimators=100,       # Boosting rounds
    max_depth=7,            # Tree depth
    learning_rate=0.1,      # Step size
    num_leaves=31,          # Leaves per tree
    subsample=0.8,          # Row sampling
    colsample_bytree=0.8,   # Column sampling
    reg_alpha=0.0,          # L1 regularization
    reg_lambda=1.0,         # L2 regularization
)
```

**Strengths**:
- Fastest training speed
- Memory efficient
- Handles categorical features
- Excellent for large datasets

**Use Cases**:
- Large datasets
- Real-time predictions
- Speed-critical applications

---

## Usage

### 1. Train Single Model

```python
from app.ml.models import ModelConfig, ModelTrainer, ModelType

# Create trainer
config = ModelConfig(model_type=ModelType.RANDOM_FOREST)
trainer = ModelTrainer(config)

# Train
trainer.train(X_train, y_train)

# Predict
predictions = trainer.predict(X_test)
proba = trainer.predict_proba(X_test)

# Evaluate
evaluation = trainer.evaluate(X_test, y_test)
print(f"Accuracy: {evaluation.accuracy:.4f}")
print(f"F1 Score: {evaluation.f1:.4f}")

# Feature importance
importance = trainer.get_feature_importance(top_n=10)
print(importance)
```

### 2. Compare Multiple Models

```python
from app.ml.models import ModelComparator

# Create comparator
comparator = ModelComparator(random_state=42)

# Train all models
comparator.train_baseline(X_train, y_train)
comparator.train_random_forest(X_train, y_train, n_estimators=100)
comparator.train_xgboost(X_train, y_train, n_estimators=100)
comparator.train_lightgbm(X_train, y_train, n_estimators=100)

# Evaluate on test set
comparator.evaluate_all(X_test, y_test)

# Compare models
comparison = comparator.compare_models()
print(comparison)

# Get best model
best_name, best_trainer = comparator.get_best_model(metric="f1")
print(f"Best model: {best_name}")

# Summary
print(comparator.get_evaluation_summary())
```

### 3. Hyperparameter Tuning

```python
from app.ml.models import HyperparameterTuner

# Create tuner
tuner = HyperparameterTuner(random_state=42)

# Tune each model
lr_params = tuner.tune_logistic_regression(X_train, y_train, cv_folds=5)
rf_params = tuner.tune_random_forest(X_train, y_train, cv_folds=5)
xgb_params = tuner.tune_xgboost(X_train, y_train, cv_folds=5)
lgb_params = tuner.tune_lightgbm(X_train, y_train, cv_folds=5)

# Use tuned parameters
print(f"Best LR C: {lr_params['C']}")
print(f"Best RF n_estimators: {rf_params['n_estimators']}")
print(f"Best XGB max_depth: {xgb_params['max_depth']}")
print(f"Best LGB learning_rate: {lgb_params['learning_rate']}")
```

### 4. Complete Pipeline

```python
from app.ml.prediction_targets import TargetGenerator, TargetConfig
from app.ml.feature_engineering import DatasetGenerator, FeatureConfig
from app.ml.models import ModelComparator

# 1. Generate targets
target_gen = TargetGenerator(TargetConfig())
targets_df = target_gen.generate(ohlcv_df)

# 2. Generate features
dataset_gen = DatasetGenerator(FeatureConfig())
features_df = dataset_gen.generate_features(ohlcv_df)

# 3. Create training set
X, y = dataset_gen.get_training_set(features_df, targets_df, horizon_days=1)

# 4. Split train/test
split = int(0.8 * len(X))
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]

# 5. Train and compare models
comparator = ModelComparator()
comparator.train_baseline(X_train, y_train)
comparator.train_random_forest(X_train, y_train)
comparator.train_xgboost(X_train, y_train)
comparator.train_lightgbm(X_train, y_train)

# 6. Evaluate
comparator.evaluate_all(X_test, y_test)
comparison = comparator.compare_models()
best_name, best_model = comparator.get_best_model()

print(comparison)
print(f"Best model: {best_name}")
```

---

## Evaluation Metrics

All models are evaluated using:

- **Accuracy**: Fraction of correct predictions
- **Precision**: True positives / (true positives + false positives)
- **Recall**: True positives / (true positives + false negatives)
- **F1 Score**: Harmonic mean of precision and recall
- **Cross-Validation**: K-fold stratified cross-validation (default: 5 folds)
- **Confusion Matrix**: Detailed per-class performance

---

## Hyperparameter Tuning Grid

### Logistic Regression
```
C: [0.1, 1, 10]
```

### Random Forest
```
n_estimators: [50, 100]
max_depth: [10, 20]
min_samples_split: [2, 5]
```

### XGBoost
```
n_estimators: [50, 100]
max_depth: [5, 7]
learning_rate: [0.1, 0.3]
```

### LightGBM
```
n_estimators: [50, 100]
max_depth: [5, 7]
learning_rate: [0.1, 0.3]
num_leaves: [20, 30]
```

---

## Configuration

### ModelConfig

```python
@dataclass
class ModelConfig:
    model_type: str = ModelType.RANDOM_FOREST
    random_state: int = 42
    test_size: float = 0.2
    cv_folds: int = 5
    scale_features: bool = True
    class_weight: str | None = "balanced"
```

**Options**:
- `model_type`: One of LOGISTIC_REGRESSION, RANDOM_FOREST, XGBOOST, LIGHTGBM
- `random_state`: Seed for reproducibility
- `scale_features`: Whether to standardize features (required for logistic regression)
- `class_weight`: How to weight classes (None or "balanced")
- `cv_folds`: Number of cross-validation folds

---

## Performance Characteristics

### Training Speed (on 1000 samples, 50 features)

- **Logistic Regression**: <100ms
- **Random Forest**: 100-500ms
- **XGBoost**: 500-2000ms
- **LightGBM**: 200-1000ms

### Memory Usage

- **Logistic Regression**: ~1MB
- **Random Forest**: ~5-10MB (depending on n_estimators)
- **XGBoost**: ~10-20MB
- **LightGBM**: ~5-15MB

### Prediction Speed (per 1000 samples)

- **Logistic Regression**: ~10ms
- **Random Forest**: ~20-50ms
- **XGBoost**: ~30-100ms
- **LightGBM**: ~20-60ms

---

## Feature Importance

All models support feature importance extraction:

```python
# For tree-based models (Random Forest, XGBoost, LightGBM)
importance_df = trainer.get_feature_importance(top_n=20)

# For logistic regression (coefficients)
importance_df = trainer.get_feature_importance(top_n=20)
```

Returns DataFrame with columns:
- `feature`: Feature name
- `importance`: Importance score (varies by model)

---

## Best Practices

### 1. Feature Scaling
- **Required**: Logistic Regression
- **Optional**: Tree-based models (set `scale_features=False`)
- **Automatic**: Handled by ModelTrainer when `scale_features=True`

### 2. Class Imbalance
- Use `class_weight="balanced"` for imbalanced datasets
- Evaluate with F1 score instead of accuracy
- Consider metric="f1_macro" in model selection

### 3. Hyperparameter Tuning
- Start with default hyperparameters
- Perform grid search on smaller grid for speed
- Use cross-validation for reliable estimates
- Select based on F1 or appropriate metric

### 4. Model Selection
- Compare multiple models
- Use cross-validation for robust evaluation
- Select based on business requirements (speed vs accuracy)
- Consider feature importance for interpretability

### 5. Cross-Validation
- Use stratified k-fold for classification
- Minimum 5 folds recommended
- More folds for small datasets

---

## Troubleshooting

### Model Not Training
```python
# Check data shape
assert X_train.shape[0] == len(y_train)

# Check for NaN values
assert not X_train.isnull().any().any()
assert not y_train.isnull().any()

# Check for valid classes
assert len(y_train.unique()) > 1
```

### Poor Performance
- Check feature quality and alignment
- Verify no data leakage
- Increase model complexity (more estimators, deeper trees)
- Tune hyperparameters
- Collect more data

### Slow Training
- Reduce cv_folds in hyperparameter tuning
- Use LightGBM instead of XGBoost for large datasets
- Reduce feature count
- Use n_jobs=-1 for parallel processing

---

## Integration with Pipeline

The model development pipeline integrates with:

1. **Feature Engineering**: `DatasetGenerator` for reproducible features
2. **Prediction Targets**: `TargetGenerator` for multi-class labels
3. **Model Comparison**: Built-in comparison framework
4. **Hyperparameter Tuning**: Grid search with cross-validation

---

## Examples

See `app/ml/model_examples.py` for complete examples:

```bash
python -m app.ml.model_examples
```

Includes:
- Single model training
- Multi-model comparison
- Hyperparameter tuning
- Complete end-to-end pipeline

---

## Testing

Run comprehensive test suite:

```bash
pytest tests/test_models.py -v
```

Coverage includes:
- Configuration validation
- Model training and prediction
- Evaluation metrics
- Cross-validation
- Feature importance
- Hyperparameter tuning
- Model comparison

---

## Next Steps (Phase 3)

1. **Backtesting**: Simulate trading with model predictions
2. **Feature Selection**: Analyze feature importance across models
3. **Ensemble Methods**: Combine predictions from multiple models
4. **Production Deployment**: API endpoint for live predictions
5. **Model Monitoring**: Track prediction performance over time

