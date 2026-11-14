"""Tests for prediction target generation."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.ml.prediction_targets import (
    PredictionObjective,
    TargetConfig,
    TargetGenerator,
    classify_return,
    calculate_forward_returns,
    generate_targets_for_instruments,
)


@pytest.fixture
def sample_ohlcv():
    """Create a simple OHLCV DataFrame for testing."""
    dates = pd.date_range("2025-01-01", periods=30, freq="D")
    # Prices trending upward with ~1% per day move to easily exceed 1% threshold
    prices = 100 * (1.015 ** np.arange(30))
    
    return pd.DataFrame({
        "trading_date": dates,
        "open": prices - 0.5,
        "high": prices + 2,
        "low": prices - 2,
        "close": prices,
        "adjusted_close": prices,
        "volume": np.full(30, 1000000),
    })


@pytest.fixture
def target_config():
    """Default target configuration."""
    return TargetConfig(thresholds_pct=(-1.0, 1.0), horizons_days=[1, 5, 20])


class TestTargetConfig:
    """Test TargetConfig validation."""
    
    def test_valid_config(self):
        """Valid config should not raise."""
        config = TargetConfig()
        assert config.thresholds_pct == (-1.0, 1.0)
        assert config.horizons_days == [1, 5, 20]
    
    def test_invalid_thresholds_order(self):
        """Lower threshold >= upper threshold should raise."""
        with pytest.raises(ValueError):
            TargetConfig(thresholds_pct=(1.0, -1.0))
    
    def test_invalid_thresholds_equal(self):
        """Equal thresholds should raise."""
        with pytest.raises(ValueError):
            TargetConfig(thresholds_pct=(1.0, 1.0))
    
    def test_invalid_horizons_empty(self):
        """Empty horizons should raise."""
        with pytest.raises(ValueError):
            TargetConfig(horizons_days=[])
    
    def test_invalid_horizons_negative(self):
        """Negative horizon should raise."""
        with pytest.raises(ValueError):
            TargetConfig(horizons_days=[-1, 1, 5])
    
    def test_invalid_price_field(self):
        """Invalid price field should raise."""
        with pytest.raises(ValueError):
            TargetConfig(price_field="bid")  # type: ignore


class TestClassifyReturn:
    """Test return classification logic."""
    
    def test_positive_classification(self):
        """Return >= upper threshold should be positive."""
        result = classify_return(1.5, thresholds=(-1.0, 1.0))
        assert result == PredictionObjective.POSITIVE
    
    def test_negative_classification(self):
        """Return <= lower threshold should be negative."""
        result = classify_return(-1.5, thresholds=(-1.0, 1.0))
        assert result == PredictionObjective.NEGATIVE
    
    def test_neutral_classification(self):
        """Return between thresholds should be neutral."""
        result = classify_return(0.5, thresholds=(-1.0, 1.0))
        assert result == PredictionObjective.NEUTRAL
    
    def test_threshold_boundary_positive(self):
        """Return at upper threshold should be positive."""
        result = classify_return(1.0, thresholds=(-1.0, 1.0))
        assert result == PredictionObjective.POSITIVE
    
    def test_threshold_boundary_negative(self):
        """Return at lower threshold should be negative."""
        result = classify_return(-1.0, thresholds=(-1.0, 1.0))
        assert result == PredictionObjective.NEGATIVE
    
    def test_none_return(self):
        """None return should return None classification."""
        result = classify_return(None, thresholds=(-1.0, 1.0))
        assert result is None
    
    def test_nan_return(self):
        """NaN return should return None classification."""
        result = classify_return(np.nan, thresholds=(-1.0, 1.0))
        assert result is None
    
    def test_inf_return(self):
        """Inf return should return None classification."""
        result = classify_return(np.inf, thresholds=(-1.0, 1.0))
        assert result is None


class TestCalculateForwardReturns:
    """Test forward return calculation."""
    
    def test_basic_forward_returns(self):
        """Forward returns should be calculated correctly."""
        prices = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0])
        dates = pd.Series(pd.date_range("2025-01-01", periods=5))
        
        returns = calculate_forward_returns(prices, dates, horizons_days=[1, 2])
        
        # 1-day returns
        ret_1d = returns[1]
        assert np.isclose(ret_1d.iloc[0], 1.0)  # (101-100)/100 * 100
        assert np.isclose(ret_1d.iloc[1], 0.99, rtol=1e-2)  # (102-101)/101 * 100
        assert np.isnan(ret_1d.iloc[4])  # Last value should be NaN (no future)
        
        # 2-day returns
        ret_2d = returns[2]
        assert np.isclose(ret_2d.iloc[0], 2.0)  # (102-100)/100 * 100
        assert np.isnan(ret_2d.iloc[3])  # Last 2 should be NaN
        assert np.isnan(ret_2d.iloc[4])
    
    def test_forward_returns_no_future_data(self):
        """Last N rows should have NaN for N-day horizon."""
        prices = pd.Series([100.0, 101.0, 102.0])
        dates = pd.Series(pd.date_range("2025-01-01", periods=3))
        
        returns = calculate_forward_returns(prices, dates, horizons_days=[5])
        
        # All should be NaN (no 5-day forward data)
        assert returns[5].isna().all()
    
    def test_length_mismatch_raises(self):
        """Mismatched lengths should raise ValueError."""
        prices = pd.Series([100.0, 101.0])
        dates = pd.Series(pd.date_range("2025-01-01", periods=3))
        
        with pytest.raises(ValueError):
            calculate_forward_returns(prices, dates, horizons_days=[1])


class TestTargetGenerator:
    """Test TargetGenerator class."""
    
    def test_generate_basic(self, sample_ohlcv, target_config):
        """Generate should produce correctly shaped output."""
        gen = TargetGenerator(target_config)
        targets = gen.generate(sample_ohlcv)
        
        # Should have same number of rows
        assert len(targets) == len(sample_ohlcv)
        
        # Should have target columns for each horizon
        for horizon in target_config.horizons_days:
            assert f"{horizon}_day_return_pct" in targets.columns
            assert f"{horizon}_day_target" in targets.columns
        
        # Should have data_available column
        assert "data_available" in targets.columns
    
    def test_generate_missing_column_raises(self, sample_ohlcv, target_config):
        """Missing trading_date column should raise."""
        gen = TargetGenerator(target_config)
        bad_df = sample_ohlcv.drop(columns=["trading_date"])
        
        with pytest.raises(ValueError):
            gen.generate(bad_df)
    
    def test_generate_missing_price_column_raises(self, sample_ohlcv, target_config):
        """Missing price column should raise."""
        gen = TargetGenerator(target_config)
        bad_df = sample_ohlcv.drop(columns=["close"])
        
        with pytest.raises(ValueError):
            gen.generate(bad_df)
    
    def test_data_available_last_rows_false(self, sample_ohlcv, target_config):
        """Last N rows should have data_available=False."""
        gen = TargetGenerator(target_config)
        targets = gen.generate(sample_ohlcv)
        
        max_horizon = max(target_config.horizons_days)
        assert not targets.iloc[-max_horizon:]["data_available"].any()
    
    def test_data_available_earlier_rows_true(self, sample_ohlcv, target_config):
        """Earlier rows should have data_available=True."""
        gen = TargetGenerator(target_config)
        targets = gen.generate(sample_ohlcv)
        
        max_horizon = max(target_config.horizons_days)
        # At least one early row should be available
        assert targets.iloc[:len(targets) - max_horizon]["data_available"].any()
    
    def test_classification_distribution(self, sample_ohlcv, target_config):
        """Uptrending data should produce mostly positive classifications."""
        gen = TargetGenerator(target_config)
        targets = gen.generate(sample_ohlcv)
        
        # For 1-day horizon (uptrend ~1% per day)
        target_col = "1_day_target"
        target_dist = targets[target_col].value_counts()
        
        # Should have mostly positive
        assert target_dist.get(PredictionObjective.POSITIVE, 0) > 10
    
    def test_get_baseline_predictor(self, sample_ohlcv, target_config):
        """Baseline should return most common class."""
        gen = TargetGenerator(target_config)
        targets = gen.generate(sample_ohlcv)
        
        baseline = gen.get_baseline_predictor(targets, horizon_days=1)
        
        # For uptrending data, should be positive
        assert baseline == PredictionObjective.POSITIVE
    
    def test_custom_thresholds(self, sample_ohlcv):
        """Custom thresholds should affect classification."""
        config_strict = TargetConfig(thresholds_pct=(-0.1, 0.1), horizons_days=[1])
        config_loose = TargetConfig(thresholds_pct=(-5.0, 5.0), horizons_days=[1])
        
        gen_strict = TargetGenerator(config_strict)
        gen_loose = TargetGenerator(config_loose)
        
        targets_strict = gen_strict.generate(sample_ohlcv)
        targets_loose = gen_loose.generate(sample_ohlcv)
        
        # With very loose thresholds, should have mostly neutral or more spread
        # With very strict thresholds, should have more positive/negative
        strict_positive = (targets_strict["1_day_target"] == PredictionObjective.POSITIVE).sum()
        strict_negative = (targets_strict["1_day_target"] == PredictionObjective.NEGATIVE).sum()
        strict_extreme = strict_positive + strict_negative
        
        loose_positive = (targets_loose["1_day_target"] == PredictionObjective.POSITIVE).sum()
        loose_negative = (targets_loose["1_day_target"] == PredictionObjective.NEGATIVE).sum()
        loose_extreme = loose_positive + loose_negative
        
        # Strict thresholds should have more extreme classifications
        assert strict_extreme >= loose_extreme
    
    def test_adjusted_close_field(self, sample_ohlcv):
        """Should work with adjusted_close price field."""
        config = TargetConfig(price_field="adjusted_close")
        gen = TargetGenerator(config)
        targets = gen.generate(sample_ohlcv)
        
        assert len(targets) == len(sample_ohlcv)
        assert "1_day_target" in targets.columns


class TestGenerateTargetsForInstruments:
    """Test batch target generation."""
    
    def test_batch_generation(self, sample_ohlcv, target_config):
        """Should generate targets for multiple instruments."""
        instrument_data = {
            "AAPL": sample_ohlcv.copy(),
            "MSFT": sample_ohlcv.copy(),
        }
        
        results = generate_targets_for_instruments(instrument_data, target_config)
        
        assert len(results) == 2
        assert "AAPL" in results
        assert "MSFT" in results
        assert len(results["AAPL"]) == len(sample_ohlcv)
    
    def test_batch_generation_with_bad_data(self, sample_ohlcv, target_config):
        """Should skip instruments with bad data."""
        bad_df = pd.DataFrame({"col": [1, 2, 3]})
        
        instrument_data = {
            "AAPL": sample_ohlcv.copy(),
            "BAD": bad_df,
        }
        
        results = generate_targets_for_instruments(instrument_data, target_config)
        
        # Should have only AAPL
        assert len(results) == 1
        assert "AAPL" in results
        assert "BAD" not in results


class TestForwardReturnAlignment:
    """Integration tests for temporal alignment."""
    
    def test_no_forward_leak(self):
        """Features at date T should never use price at T+1 or later."""
        dates = pd.date_range("2025-01-01", periods=10)
        prices = pd.Series(range(100, 110))
        
        returns = calculate_forward_returns(prices, pd.Series(dates), horizons_days=[1])
        
        # The return at index 0 should only depend on prices[0] and prices[1]
        # return[0] = (price[1] - price[0]) / price[0] * 100
        expected = (prices.iloc[1] - prices.iloc[0]) / prices.iloc[0] * 100
        assert np.isclose(returns[1].iloc[0], expected)
        
        # At last index, return should be NaN (no future price)
        assert np.isnan(returns[1].iloc[-1])
