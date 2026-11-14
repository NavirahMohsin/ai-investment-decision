"""Example usage of the ML pipeline for prediction objectives and feature engineering.

This script demonstrates how to:
1. Generate prediction targets (Positive, Negative, Neutral)
2. Generate features from OHLCV data
3. Create training datasets

Note: This is for demonstration only. Requires historical OHLCV data.
"""

import pandas as pd
from datetime import date

from app.ml.prediction_targets import TargetConfig, TargetGenerator
from app.ml.feature_engineering import FeatureConfig, DatasetGenerator


def example_generate_targets():
    """Example 1: Generate classification targets."""
    # Load or create OHLCV data
    ohlcv_df = pd.DataFrame({
        "trading_date": pd.date_range("2024-01-01", periods=100),
        "open": 100.0,
        "high": 102.0,
        "low": 98.0,
        "close": 101.0 + (0.01 * pd.Series(range(100))),  # Uptrend
        "adjusted_close": 101.0 + (0.01 * pd.Series(range(100))),
        "volume": 1000000,
    })
    
    # Configure targets with ±1% thresholds for 1, 5, 20-day horizons
    config = TargetConfig(
        thresholds_pct=(-1.0, 1.0),
        horizons_days=[1, 5, 20],
    )
    
    # Generate targets
    generator = TargetGenerator(config)
    targets_df = generator.generate(ohlcv_df)
    
    # Inspect results
    print("Targets DataFrame:")
    print(targets_df[["trading_date", "1_day_return_pct", "1_day_target", "data_available"]].head(10))
    print()
    
    # Get baseline predictor (majority class)
    baseline = generator.get_baseline_predictor(targets_df, horizon_days=1)
    print(f"Baseline predictor (1-day horizon): {baseline}")
    print()
    
    return targets_df


def example_generate_features():
    """Example 2: Generate feature set."""
    # Create sample OHLCV data
    ohlcv_df = pd.DataFrame({
        "trading_date": pd.date_range("2024-01-01", periods=100),
        "open": 100.0,
        "high": 102.0,
        "low": 98.0,
        "close": 101.0 + (0.01 * pd.Series(range(100))),
        "adjusted_close": 101.0 + (0.01 * pd.Series(range(100))),
        "volume": 1000000 + (10000 * pd.Series(range(100))),
    })
    
    # Configure feature engineering
    feature_config = FeatureConfig(
        returns_periods=[1, 5, 20],
        sma_periods=[20, 50, 200],
        ema_periods=[12, 26],
    )
    
    # Generate features
    dataset_gen = DatasetGenerator(feature_config)
    features_df = dataset_gen.generate_features(ohlcv_df)
    
    # Inspect results
    print("Features DataFrame (first 5 columns):")
    print(features_df[["trading_date", "return_1d", "return_5d", "sma_20", "ema_12"]].head(10))
    print()
    
    print(f"Feature shape: {features_df.shape}")
    print(f"Feature columns: {list(features_df.columns[:15])}")  # First 15 columns
    print()
    
    return features_df


def example_complete_pipeline():
    """Example 3: Complete end-to-end pipeline."""
    # Create sample OHLCV data
    ohlcv_df = pd.DataFrame({
        "trading_date": pd.date_range("2024-01-01", periods=100),
        "open": 100.0,
        "high": 102.0,
        "low": 98.0,
        "close": 101.0 + (0.01 * pd.Series(range(100))),
        "adjusted_close": 101.0 + (0.01 * pd.Series(range(100))),
        "volume": 1000000 + (10000 * pd.Series(range(100))),
    })
    
    # Step 1: Generate targets
    target_config = TargetConfig()
    target_gen = TargetGenerator(target_config)
    targets_df = target_gen.generate(ohlcv_df)
    
    # Step 2: Generate features
    feature_config = FeatureConfig()
    dataset_gen = DatasetGenerator(feature_config)
    features_df = dataset_gen.generate_features(ohlcv_df)
    
    # Step 3: Create training dataset for 1-day prediction
    X_train, y_train = dataset_gen.get_training_set(
        features_df,
        targets_df,
        horizon_days=1,
        dropna=True,
    )
    
    print("Training Dataset Summary:")
    print(f"  Samples: {X_train.shape[0]}")
    print(f"  Features: {X_train.shape[1]}")
    print(f"  Target distribution:\n{y_train.value_counts()}")
    print()
    
    # Ready for ML training
    print("X_train shape:", X_train.shape)
    print("y_train shape:", y_train.shape)
    print("First 5 rows of X_train:")
    print(X_train.head())
    print()
    print("First 5 targets:")
    print(y_train.head())


if __name__ == "__main__":
    print("=" * 60)
    print("ArthAI ML Pipeline - Example Usage")
    print("=" * 60)
    print()
    
    print("EXAMPLE 1: Generate Classification Targets")
    print("-" * 60)
    example_generate_targets()
    
    print("\nEXAMPLE 2: Generate Features")
    print("-" * 60)
    example_generate_features()
    
    print("\nEXAMPLE 3: Complete End-to-End Pipeline")
    print("-" * 60)
    example_complete_pipeline()
    
    print("\n" + "=" * 60)
    print("Examples completed successfully!")
    print("=" * 60)
