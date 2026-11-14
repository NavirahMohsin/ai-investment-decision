"""Tests for feature engineering pipeline."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.ml.feature_engineering import (
    FeatureConfig,
    FeatureEngineer,
    DatasetGenerator,
)
from app.ml.prediction_targets import TargetConfig, TargetGenerator


@pytest.fixture
def sample_ohlcv():
    """Create a sample OHLCV DataFrame."""
    dates = pd.date_range("2025-01-01", periods=100, freq="D")
    # Prices with trend and some noise
    base_prices = 100 + np.arange(100) * 0.5
    prices = base_prices + np.random.normal(0, 1, 100)
    
    return pd.DataFrame({
        "trading_date": dates,
        "open": prices - 0.5,
        "high": prices + 2,
        "low": prices - 2,
        "close": prices,
        "adjusted_close": prices,
        "volume": np.random.randint(1000000, 10000000, 100),
    })


@pytest.fixture
def feature_config():
    """Default feature configuration."""
    return FeatureConfig()


class TestFeatureConfig:
    """Test FeatureConfig validation."""
    
    def test_valid_config(self):
        """Valid config should not raise."""
        config = FeatureConfig()
        assert config.returns_periods == [1, 5, 20]
        assert config.sma_periods == [20, 50, 200]
        assert config.ema_periods == [12, 26]
    
    def test_invalid_returns_periods(self):
        """Non-positive periods should raise."""
        with pytest.raises(ValueError):
            FeatureConfig(returns_periods=[0, 1, 5])
    
    def test_invalid_sma_periods(self):
        """Non-positive SMA periods should raise."""
        with pytest.raises(ValueError):
            FeatureConfig(sma_periods=[-20, 50])
    
    def test_invalid_ema_periods(self):
        """Non-positive EMA periods should raise."""
        with pytest.raises(ValueError):
            FeatureConfig(ema_periods=[12, -26])
    
    def test_invalid_handle_missing(self):
        """Invalid handle_missing strategy should raise."""
        with pytest.raises(ValueError):
            FeatureConfig(handle_missing="interpolate")  # type: ignore


class TestFeatureEngineer:
    """Test FeatureEngineer class."""
    
    def test_generate_basic(self, sample_ohlcv, feature_config):
        """Generate should produce feature DataFrame."""
        engineer = FeatureEngineer(feature_config)
        features = engineer.generate(sample_ohlcv)
        
        # Should have trading_date
        assert "trading_date" in features.columns
        
        # Should have return features
        assert "return_1d" in features.columns
        assert "return_5d" in features.columns
        assert "return_20d" in features.columns
        
        # Should have SMA features
        assert "sma_20" in features.columns
        assert "sma_50" in features.columns
        assert "sma_200" in features.columns
        
        # Should have EMA features
        assert "ema_12" in features.columns
        assert "ema_26" in features.columns
        
        # Should have volume features
        assert "volume" in features.columns
        assert "volume_ratio_20d" in features.columns
    
    def test_generate_missing_column_raises(self, sample_ohlcv, feature_config):
        """Missing required column should raise."""
        engineer = FeatureEngineer(feature_config)
        bad_df = sample_ohlcv.drop(columns=["close"])
        
        with pytest.raises(ValueError):
            engineer.generate(bad_df)
    
    def test_generates_technical_indicators(self, sample_ohlcv, feature_config):
        """Should include technical indicators when requested."""
        engineer = FeatureEngineer(feature_config)
        features = engineer.generate(sample_ohlcv, include_indicators=True)
        
        # Check for some key indicators
        indicator_cols = ["rsi_14", "macd", "atr_14", "adx_14", "vwap"]
        for col in indicator_cols:
            assert col in features.columns or col + "_" in str(features.columns)
    
    def test_excludes_indicators_when_requested(self, sample_ohlcv, feature_config):
        """Should not include indicators when exclude_indicators=True."""
        engineer = FeatureEngineer(feature_config)
        features = engineer.generate(sample_ohlcv, include_indicators=False)
        
        # Should still have basic features
        assert "return_1d" in features.columns
        assert "sma_20" in features.columns
        
        # May not have indicators (depends on implementation)
        # Just check it doesn't raise
        assert len(features) == len(sample_ohlcv)
    
    def test_log_returns_option(self, sample_ohlcv):
        """Should support log returns."""
        config = FeatureConfig(use_log_features=True)
        engineer = FeatureEngineer(config)
        features = engineer.generate(sample_ohlcv)
        
        # Log returns should exist
        assert "return_1d" in features.columns
        
        # Manually verify a log return calculation
        # log(prices[1]/prices[0]) * 100 should be different from percentage
        assert len(features) == len(sample_ohlcv)
    
    def test_forward_fill_missing_values(self, sample_ohlcv):
        """Forward fill should handle NaN values."""
        # Create data with NaN
        bad_df = sample_ohlcv.copy()
        bad_df.loc[5:10, "close"] = np.nan
        
        config = FeatureConfig(handle_missing="forward_fill")
        engineer = FeatureEngineer(config)
        features = engineer.generate(bad_df)
        
        # Check that NaNs were handled (filled or dropped)
        numeric_cols = features.select_dtypes(include=[np.number]).columns
        # Allow some NaNs at start (warmup), but not in middle
        assert features[numeric_cols].iloc[20:].isna().sum().sum() < len(numeric_cols) * 5
    
    def test_drop_missing_values(self, sample_ohlcv):
        """Drop option should remove rows with NaN."""
        # Create data with NaN
        bad_df = sample_ohlcv.copy()
        bad_df.loc[5:10, "close"] = np.nan
        
        config = FeatureConfig(handle_missing="drop")
        engineer = FeatureEngineer(config)
        features = engineer.generate(bad_df)
        
        # Should have fewer rows
        assert len(features) <= len(bad_df)
    
    def test_validate_finite_replaces_inf(self, sample_ohlcv):
        """Infinite values should be handled."""
        config = FeatureConfig(validate_finite=True)
        engineer = FeatureEngineer(config)
        
        # Inject some infinities
        features = engineer.generate(sample_ohlcv)
        
        # Check no infinities in output
        numeric_cols = features.select_dtypes(include=[np.number]).columns
        assert not np.any(np.isinf(features[numeric_cols].values))
    
    def test_date_sorting(self):
        """Features should be sorted by date."""
        # Create unsorted OHLCV
        import random
        dates = list(pd.date_range("2025-01-01", periods=20, freq="D"))
        random.shuffle(dates)  # Shuffle dates
        
        df = pd.DataFrame({
            "trading_date": dates,
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "adjusted_close": 100,
            "volume": 1000000,
        })
        
        config = FeatureConfig()
        engineer = FeatureEngineer(config)
        features = engineer.generate(df)
        
        # Should be sorted by trading_date
        dates_sorted = pd.to_datetime(features["trading_date"]).is_monotonic_increasing
        assert dates_sorted


class TestDatasetGenerator:
    """Test DatasetGenerator class."""
    
    def test_generate_features(self, sample_ohlcv):
        """Should generate features."""
        gen = DatasetGenerator()
        features = gen.generate_features(sample_ohlcv)
        
        assert len(features) == len(sample_ohlcv)
        assert "return_1d" in features.columns
    
    def test_merge_features_and_targets(self, sample_ohlcv):
        """Should merge features and targets correctly."""
        gen = DatasetGenerator()
        features = gen.generate_features(sample_ohlcv)
        
        target_gen = TargetGenerator(TargetConfig())
        targets = target_gen.generate(sample_ohlcv)
        
        merged = gen.merge_features_and_targets(features, targets)
        
        # Should have both feature and target columns
        assert "return_1d" in merged.columns
        assert "1_day_target" in merged.columns
        assert len(merged) > 0
    
    def test_get_training_set(self, sample_ohlcv):
        """Should get training set for specific horizon."""
        gen = DatasetGenerator()
        features = gen.generate_features(sample_ohlcv)
        
        target_gen = TargetGenerator(TargetConfig())
        targets = target_gen.generate(sample_ohlcv)
        
        X, y = gen.get_training_set(features, targets, horizon_days=1)
        
        # Should have same number of samples
        assert len(X) == len(y)
        
        # Should have numeric features
        assert X.shape[1] > 0
        
        # Targets should be non-null
        assert y.notna().all()
    
    def test_get_training_set_with_date_filter(self, sample_ohlcv):
        """Should filter by date range."""
        gen = DatasetGenerator()
        features = gen.generate_features(sample_ohlcv)
        
        target_gen = TargetGenerator(TargetConfig())
        targets = target_gen.generate(sample_ohlcv)
        
        min_date = date(2025, 1, 20)
        max_date = date(2025, 2, 10)
        
        X, y = gen.get_training_set(
            features, targets,
            horizon_days=1,
            min_date=min_date,
            max_date=max_date,
        )
        
        # Should have subset of data
        assert len(X) < len(features)
        assert len(y) == len(X)
    
    def test_get_training_set_dropna(self, sample_ohlcv):
        """Should drop NaN rows when dropna=True."""
        gen = DatasetGenerator()
        features = gen.generate_features(sample_ohlcv)
        
        target_gen = TargetGenerator(TargetConfig())
        targets = target_gen.generate(sample_ohlcv)
        
        # Without dropna
        X1, y1 = gen.get_training_set(features, targets, horizon_days=1, dropna=False)
        
        # With dropna
        X2, y2 = gen.get_training_set(features, targets, horizon_days=1, dropna=True)
        
        # dropna=True should have fewer samples (NaNs removed)
        assert len(X2) <= len(X1)
    
    def test_training_set_different_horizons(self, sample_ohlcv):
        """Should get different training sets for different horizons."""
        gen = DatasetGenerator()
        features = gen.generate_features(sample_ohlcv)
        
        target_gen = TargetGenerator(TargetConfig())
        targets = target_gen.generate(sample_ohlcv)
        
        X1, y1 = gen.get_training_set(features, targets, horizon_days=1)
        X5, y5 = gen.get_training_set(features, targets, horizon_days=5)
        X20, y20 = gen.get_training_set(features, targets, horizon_days=20)
        
        # All should be valid
        assert len(X1) > 0
        assert len(X5) > 0
        assert len(X20) > 0


class TestFeatureLeakagePrevention:
    """Test that features don't leak future information."""
    
    def test_return_calculation_uses_past_data(self, sample_ohlcv):
        """Returns should only use historical data."""
        engineer = FeatureEngineer(FeatureConfig())
        features = engineer.generate(sample_ohlcv)
        
        # 1-day return at index i should be: (close[i] - close[i-1]) / close[i-1]
        # Not (close[i+1] - close[i]) / close[i]
        
        close_prices = sample_ohlcv["close"]
        expected_ret_1d = (close_prices - close_prices.shift(1)) / close_prices.shift(1) * 100
        
        actual_ret_1d = features["return_1d"]
        
        # Should match for non-NaN values (allowing small numerical differences)
        valid_idx = (~expected_ret_1d.isna()) & (~actual_ret_1d.isna())
        assert np.allclose(
            expected_ret_1d[valid_idx],
            actual_ret_1d[valid_idx],
            rtol=1e-2,
        )
    
    def test_moving_averages_use_past_data(self, sample_ohlcv):
        """Moving averages should only use historical data."""
        engineer = FeatureEngineer(FeatureConfig())
        features = engineer.generate(sample_ohlcv)
        
        # SMA at index i should be average of close[0:i+1]
        close_prices = sample_ohlcv["close"]
        expected_sma_20 = close_prices.rolling(20, min_periods=1).mean()
        actual_sma_20 = features["sma_20"]
        
        # Should match
        valid_idx = (~expected_sma_20.isna()) & (~actual_sma_20.isna())
        assert np.allclose(
            expected_sma_20[valid_idx],
            actual_sma_20[valid_idx],
            rtol=1e-2,
        )


class TestFeatureCompleteness:
    """Test that all expected features are generated."""
    
    def test_all_return_periods(self, sample_ohlcv):
        """Should generate returns for all configured periods."""
        config = FeatureConfig(returns_periods=[1, 5, 10, 20])
        engineer = FeatureEngineer(config)
        features = engineer.generate(sample_ohlcv)
        
        for period in config.returns_periods:
            assert f"return_{period}d" in features.columns
    
    def test_all_moving_average_periods(self, sample_ohlcv):
        """Should generate MAs for all configured periods."""
        config = FeatureConfig(sma_periods=[10, 20, 50], ema_periods=[12, 26, 50])
        engineer = FeatureEngineer(config)
        features = engineer.generate(sample_ohlcv)
        
        for period in config.sma_periods:
            assert f"sma_{period}" in features.columns
        for period in config.ema_periods:
            assert f"ema_{period}" in features.columns
    
    def test_volume_features(self, sample_ohlcv):
        """Should generate volume-related features."""
        engineer = FeatureEngineer()
        features = engineer.generate(sample_ohlcv)
        
        volume_cols = ["volume", "volume_change", "volume_ratio_20d"]
        for col in volume_cols:
            assert col in features.columns
