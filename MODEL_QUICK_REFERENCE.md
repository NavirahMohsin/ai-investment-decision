# Model Training - Quick Reference

Fast reference for Phase 2.3 model development.

## Import

```python
from app.ml.models import (
    ModelType, ModelConfig, ModelTrainer,
    ModelComparator, HyperparameterTuner,
)
```

## 1. Single Model

### Train
```python
config = ModelConfig(model_type=ModelType.RANDOM_FOREST)
trainer = ModelTrainer(config)
trainer.train(X_train, y_train)
```

### Predict
```python
predictions = trainer.predict(X_test)
probabilities = trainer.predict_proba(X_test)
```

### Evaluate
```python
evaluation = trainer.evaluate(X_test, y_test)
print(f"F1: {evaluation.f1:.4f}")
print(f"Accuracy: {evaluation.accuracy:.4f}")
```

### Feature Importance
```python
importance = trainer.get_feature_importance(top_n=10)
print(importance)
```

## 2. Multiple Models

### Train All
```python
comp = ModelComparator()
comp.train_baseline(X_train, y_train)
comp.train_random_forest(X_train, y_train, n_estimators=100)
comp.train_xgboost(X_train, y_train, n_estimators=100)
comp.train_lightgbm(X_train, y_train, n_estimators=100)
```

### Compare
```python
comp.evaluate_all(X_test, y_test)
comparison = comp.compare_models()
print(comparison)
```

### Best Model
```python
name, trainer = comp.get_best_model(metric="f1")
print(f"Best: {name}")
```

## 3. Hyperparameter Tuning

```python
tuner = HyperparameterTuner()

lr_params = tuner.tune_logistic_regression(X_train, y_train)
rf_params = tuner.tune_random_forest(X_train, y_train)
xgb_params = tuner.tune_xgboost(X_train, y_train)
lgb_params = tuner.tune_lightgbm(X_train, y_train)
```

## 4. Model Types

| Model | Speed | Accuracy | Use |
|-------|-------|----------|-----|
| `LOGISTIC_REGRESSION` | ⚡⚡⚡ | ⭐⭐ | Baseline |
| `RANDOM_FOREST` | ⚡⚡ | ⭐⭐⭐ | Production |
| `XGBOOST` | ⚡ | ⭐⭐⭐⭐ | Best accuracy |
| `LIGHTGBM` | ⚡⚡ | ⭐⭐⭐⭐ | Large data |

## 5. Configuration

```python
config = ModelConfig(
    model_type=ModelType.RANDOM_FOREST,
    random_state=42,
    cv_folds=5,
    scale_features=True,
    class_weight="balanced",
)
```

## 6. Evaluation Metrics

- **Accuracy**: Overall correctness
- **Precision**: True positives / predictions
- **Recall**: True positives / actual positives
- **F1**: Harmonic mean of precision & recall (primary)
- **CV**: K-fold cross-validation (default: 5)

## 7. Complete Example

```python
from app.ml.models import ModelComparator

# Load/prepare data
X_train, y_train = ...  # 80% of data
X_test, y_test = ...    # 20% of data

# Train models
comp = ModelComparator()
comp.train_baseline(X_train, y_train)
comp.train_random_forest(X_train, y_train)
comp.train_xgboost(X_train, y_train)

# Evaluate
comp.evaluate_all(X_test, y_test)
print(comp.compare_models())

# Select best
name, model = comp.get_best_model(metric="f1")
print(f"Best model: {name}")

# Make predictions
predictions = model.predict(X_test)
```

## 8. Key Methods

### ModelTrainer
- `train(X, y)`: Train model
- `predict(X)`: Get predictions
- `predict_proba(X)`: Get probabilities
- `evaluate(X_test, y_test)`: Get metrics
- `get_feature_importance(top_n)`: Feature importance

### ModelComparator
- `train_baseline()`: Train LR
- `train_random_forest()`: Train RF
- `train_xgboost()`: Train XGB
- `train_lightgbm()`: Train LGB
- `evaluate_all(X, y)`: Evaluate all
- `compare_models()`: Comparison table
- `get_best_model()`: Best model
- `get_evaluation_summary()`: Text summary

### HyperparameterTuner
- `tune_logistic_regression()`: Tune LR
- `tune_random_forest()`: Tune RF
- `tune_xgboost()`: Tune XGB
- `tune_lightgbm()`: Tune LGB

## 9. Common Issues

### Model Training
```python
# Check data
assert X_train.shape[0] == len(y_train)
assert not X_train.isnull().any().any()
assert not y_train.isnull().any()
```

### Poor Performance
- Check feature quality
- Verify no data leakage
- Tune hyperparameters
- Collect more data

### Slow Training
- Use LightGBM for large datasets
- Reduce cv_folds in tuning
- Use fewer features

## 10. Files

| File | Purpose |
|------|---------|
| `app/ml/models.py` | Core models |
| `tests/test_models.py` | Tests |
| `app/ml/model_examples.py` | Examples |
| `docs/model_development.md` | Full docs |

## 11. Run Tests

```bash
pytest tests/test_models.py -v
```

## 12. Run Examples

```bash
python -m app.ml.model_examples
```

---

**For full documentation, see `docs/model_development.md`**
