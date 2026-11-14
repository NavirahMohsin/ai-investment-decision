"""Example usage of model training and evaluation.

Demonstrates:
1. Training individual models
2. Comparing multiple models
3. Hyperparameter tuning
4. Model selection
"""

import pandas as pd
import numpy as np

from app.ml.prediction_targets import TargetConfig, TargetGenerator
from app.ml.feature_engineering import FeatureConfig, DatasetGenerator
from app.ml.models import (
    ModelType,
    ModelConfig,
    ModelTrainer,
    ModelComparator,
    HyperparameterTuner,
)


def example_1_single_model():
    """Example 1: Train and evaluate a single model."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Train Single Model (Random Forest)")
    print("=" * 80)
    
    # Create synthetic data
    np.random.seed(42)
    X_train = pd.DataFrame(
        np.random.randn(150, 20),
        columns=[f"feature_{i}" for i in range(20)]
    )
    y_train = pd.Series(np.random.choice(["positive", "neutral", "negative"], 150))
    
    X_test = pd.DataFrame(
        np.random.randn(50, 20),
        columns=[f"feature_{i}" for i in range(20)]
    )
    y_test = pd.Series(np.random.choice(["positive", "neutral", "negative"], 50))
    
    # Train model
    config = ModelConfig(model_type=ModelType.RANDOM_FOREST)
    trainer = ModelTrainer(config)
    trainer.train(X_train, y_train)
    
    # Evaluate
    evaluation = trainer.evaluate(X_test, y_test)
    
    print(f"\nRandom Forest Results:")
    print(f"  Accuracy:  {evaluation.accuracy:.4f}")
    print(f"  Precision: {evaluation.precision:.4f}")
    print(f"  Recall:    {evaluation.recall:.4f}")
    print(f"  F1 Score:  {evaluation.f1:.4f}")
    print(f"  CV Accuracy: {evaluation.cv_accuracy_mean:.4f} ± {evaluation.cv_accuracy_std:.4f}")
    
    # Feature importance
    print("\nTop 5 Most Important Features:")
    importance = trainer.get_feature_importance(top_n=5)
    print(importance)


def example_2_compare_models():
    """Example 2: Compare multiple models."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Compare Multiple Models")
    print("=" * 80)
    
    # Create synthetic data
    np.random.seed(42)
    X_train = pd.DataFrame(
        np.random.randn(150, 20),
        columns=[f"feature_{i}" for i in range(20)]
    )
    y_train = pd.Series(np.random.choice(["positive", "neutral", "negative"], 150))
    
    X_test = pd.DataFrame(
        np.random.randn(50, 20),
        columns=[f"feature_{i}" for i in range(20)]
    )
    y_test = pd.Series(np.random.choice(["positive", "neutral", "negative"], 50))
    
    # Create comparator
    comparator = ModelComparator(random_state=42)
    
    # Train all models
    print("\nTraining models...")
    comparator.train_baseline(X_train, y_train)
    print("  [✓] Baseline (Logistic Regression)")
    
    comparator.train_random_forest(X_train, y_train, n_estimators=100)
    print("  [✓] Random Forest")
    
    comparator.train_xgboost(X_train, y_train, n_estimators=100)
    print("  [✓] XGBoost")
    
    comparator.train_lightgbm(X_train, y_train, n_estimators=100)
    print("  [✓] LightGBM")
    
    # Evaluate all
    print("\nEvaluating on test set...")
    comparator.evaluate_all(X_test, y_test)
    
    # Compare
    print("\nModel Comparison:")
    comparison_df = comparator.compare_models()
    print(comparison_df.to_string(index=False))
    
    # Best model
    best_name, best_model = comparator.get_best_model(metric="f1")
    print(f"\nBest Model (by F1): {best_name}")
    
    # Summary
    print("\n" + comparator.get_evaluation_summary())


def example_3_hyperparameter_tuning():
    """Example 3: Hyperparameter tuning."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Hyperparameter Tuning")
    print("=" * 80)
    
    # Create synthetic data
    np.random.seed(42)
    X_train = pd.DataFrame(
        np.random.randn(200, 20),
        columns=[f"feature_{i}" for i in range(20)]
    )
    y_train = pd.Series(np.random.choice(["positive", "neutral", "negative"], 200))
    
    # Tune hyperparameters
    tuner = HyperparameterTuner(random_state=42)
    
    print("\nTuning Logistic Regression...")
    lr_params = tuner.tune_logistic_regression(X_train, y_train, cv_folds=3)
    print(f"  Best C: {lr_params['C']}")
    
    print("\nTuning Random Forest...")
    rf_params = tuner.tune_random_forest(X_train, y_train, cv_folds=3)
    print(f"  Best n_estimators: {rf_params['n_estimators']}")
    print(f"  Best max_depth: {rf_params['max_depth']}")
    print(f"  Best max_features: {rf_params['max_features']}")
    
    print("\nTuning XGBoost...")
    xgb_params = tuner.tune_xgboost(X_train, y_train, cv_folds=3)
    print(f"  Best n_estimators: {xgb_params['n_estimators']}")
    print(f"  Best max_depth: {xgb_params['max_depth']}")
    print(f"  Best learning_rate: {xgb_params['learning_rate']}")
    
    print("\nTuning LightGBM...")
    lgb_params = tuner.tune_lightgbm(X_train, y_train, cv_folds=3)
    print(f"  Best n_estimators: {lgb_params['n_estimators']}")
    print(f"  Best learning_rate: {lgb_params['learning_rate']}")
    print(f"  Best num_leaves: {lgb_params['num_leaves']}")


def example_4_complete_pipeline():
    """Example 4: Complete ML pipeline with real data structure."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Complete Pipeline (Targets + Features + Models)")
    print("=" * 80)
    
    # Create synthetic OHLCV data
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=150)
    prices = 100 * (1.01 ** np.arange(150))
    
    ohlcv_df = pd.DataFrame({
        "trading_date": dates,
        "open": prices - 0.5,
        "high": prices + 2,
        "low": prices - 2,
        "close": prices,
        "adjusted_close": prices,
        "volume": np.random.randint(1000000, 10000000, 150),
    })
    
    # Step 1: Generate targets
    print("\nStep 1: Generating targets...")
    target_gen = TargetGenerator(TargetConfig())
    targets_df = target_gen.generate(ohlcv_df)
    print(f"  Generated {len(targets_df)} target rows")
    
    # Step 2: Generate features
    print("Step 2: Generating features...")
    dataset_gen = DatasetGenerator(FeatureConfig())
    features_df = dataset_gen.generate_features(ohlcv_df)
    print(f"  Generated {features_df.shape[1]} features")
    
    # Step 3: Create training set
    print("Step 3: Creating training dataset...")
    X, y = dataset_gen.get_training_set(
        features_df, targets_df,
        horizon_days=1,
        dropna=True,
    )
    print(f"  Training set: {X.shape[0]} samples, {X.shape[1]} features")
    
    # Split into train/test
    split = int(0.8 * len(X))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    # Step 4: Train and compare models
    print("\nStep 4: Training and comparing models...")
    comparator = ModelComparator(random_state=42)
    
    comparator.train_baseline(X_train, y_train)
    comparator.train_random_forest(X_train, y_train, n_estimators=100)
    comparator.train_xgboost(X_train, y_train, n_estimators=100)
    comparator.train_lightgbm(X_train, y_train, n_estimators=100)
    
    evaluations = comparator.evaluate_all(X_test, y_test)
    
    # Show results
    print("\nModel Comparison Results:")
    comparison = comparator.compare_models()
    print(comparison.to_string(index=False))
    
    best_name, _ = comparator.get_best_model(metric="f1")
    print(f"\nBest model: {best_name}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("ArthAI Model Development - Examples")
    print("=" * 80)
    
    example_1_single_model()
    example_2_compare_models()
    example_3_hyperparameter_tuning()
    example_4_complete_pipeline()
    
    print("\n" + "=" * 80)
    print("All examples completed!")
    print("=" * 80)
