"""Tests for backtesting framework."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.ml.backtesting import (
    BacktestConfig,
    BacktestEngine,
    BenchmarkStrategies,
    BacktestComparator,
)


@pytest.fixture
def sample_prices():
    """Create sample price data."""
    dates = pd.date_range("2024-01-01", periods=252, freq="D")
    prices = pd.Series(
        100 * (1.01 ** np.arange(252)),
        index=dates,
        name="price"
    )
    return prices


class TestBacktestConfig:
    """Test BacktestConfig validation."""
    
    def test_valid_config(self):
        """Valid config should not raise."""
        config = BacktestConfig()
        assert config.initial_capital == 100000.0
        assert config.commission == 0.001
    
    def test_invalid_capital(self):
        """Non-positive capital should raise."""
        with pytest.raises(ValueError):
            BacktestConfig(initial_capital=-1000)
    
    def test_invalid_commission(self):
        """Commission outside bounds should raise."""
        with pytest.raises(ValueError):
            BacktestConfig(commission=0.5)


class TestBacktestEngine:
    """Test BacktestEngine class."""
    
    def test_buy_and_hold_signal(self, sample_prices):
        """Should execute buy and hold strategy."""
        signals = pd.Series(0, index=sample_prices.index)
        signals.iloc[0] = 1  # Buy on first day
        
        engine = BacktestEngine()
        result = engine.backtest(sample_prices, signals, strategy_name="Test")
        
        assert result.strategy_name == "Test"
        assert result.final_value > 0
        assert result.num_trades > 0
    
    def test_no_signals(self, sample_prices):
        """No signals should result in no trades."""
        signals = pd.Series(0, index=sample_prices.index)
        
        engine = BacktestEngine()
        result = engine.backtest(sample_prices, signals)
        
        assert result.num_trades == 0
        assert result.final_value == result.initial_capital
    
    def test_buy_sell_signal(self, sample_prices):
        """Should execute buy and sell signals."""
        signals = pd.Series(0, index=sample_prices.index)
        signals.iloc[10] = 1   # Buy
        signals.iloc[50] = -1  # Sell
        
        engine = BacktestEngine()
        result = engine.backtest(sample_prices, signals)
        
        assert result.num_trades > 0
        assert result.total_return is not None
    
    def test_mismatched_lengths_raises(self, sample_prices):
        """Mismatched lengths should raise."""
        signals = pd.Series(0, index=sample_prices.index[:-10])
        
        engine = BacktestEngine()
        with pytest.raises(ValueError):
            engine.backtest(sample_prices, signals)


class TestBenchmarkStrategies:
    """Test BenchmarkStrategies class."""
    
    def test_buy_and_hold(self, sample_prices):
        """Should implement buy and hold strategy."""
        result = BenchmarkStrategies.buy_and_hold(sample_prices)
        
        assert result.strategy_name == "Buy & Hold"
        assert result.num_trades > 0
        assert result.total_return is not None
    
    def test_sma_strategy(self, sample_prices):
        """Should implement SMA crossover strategy."""
        result = BenchmarkStrategies.simple_moving_average(
            sample_prices,
            short_window=20,
            long_window=50
        )
        
        assert "SMA" in result.strategy_name
        assert result.num_trades >= 0
    
    def test_random_strategy(self, sample_prices):
        """Should implement random strategy."""
        result = BenchmarkStrategies.random_signals(
            sample_prices,
            trade_probability=0.05
        )
        
        assert result.strategy_name == "Random Trading"
        assert result.num_trades >= 0


class TestBacktestComparator:
    """Test BacktestComparator class."""
    
    def test_compare_results(self, sample_prices):
        """Should compare multiple backtest results."""
        result1 = BenchmarkStrategies.buy_and_hold(sample_prices)
        result2 = BenchmarkStrategies.simple_moving_average(sample_prices, 20, 50)
        
        comparison = BacktestComparator.compare_results([result1, result2])
        
        assert len(comparison) == 2
        assert "Strategy" in comparison.columns
        assert "Total Return %" in comparison.columns
    
    def test_backtest_summary(self, sample_prices):
        """Should generate backtest summary."""
        result = BenchmarkStrategies.buy_and_hold(sample_prices)
        summary = BacktestComparator.get_backtest_summary(result)
        
        assert "Buy & Hold" in summary
        assert "DISCLAIMER" in summary
        assert "Total Return" in summary


class TestBacktestMetrics:
    """Test backtest metrics calculation."""
    
    def test_positive_return(self, sample_prices):
        """Uptrend should produce positive returns."""
        result = BenchmarkStrategies.buy_and_hold(sample_prices)
        
        assert result.total_return > 0
        assert result.final_value > result.initial_capital
    
    def test_drawdown_calculation(self):
        """Should calculate maximum drawdown correctly."""
        # Create prices with drawdown
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        prices = pd.Series([100 + i if i < 50 else 150 - i for i in range(100)], index=dates)
        
        signals = pd.Series(0, index=prices.index)
        signals.iloc[0] = 1
        signals.iloc[99] = -1
        
        engine = BacktestEngine()
        result = engine.backtest(prices, signals)
        
        # Should have negative drawdown
        assert result.max_drawdown <= 0
    
    def test_sharpe_ratio_calculation(self, sample_prices):
        """Should calculate Sharpe ratio."""
        result = BenchmarkStrategies.buy_and_hold(sample_prices)
        
        # Sharpe ratio should be a number
        assert isinstance(result.sharpe_ratio, (int, float))
    
    def test_win_rate_calculation(self, sample_prices):
        """Should calculate win rate from trades."""
        signals = pd.Series(0, index=sample_prices.index)
        for i in range(5, 250, 20):
            signals.iloc[i] = 1
            if i + 10 < len(sample_prices):
                signals.iloc[i + 10] = -1
        
        engine = BacktestEngine()
        result = engine.backtest(sample_prices, signals)
        
        if result.num_trades > 0:
            assert 0 <= result.win_rate <= 100
