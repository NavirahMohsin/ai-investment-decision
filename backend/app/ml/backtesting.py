"""Historical backtesting framework for trading strategies.

Simulates trading strategies with realistic market conditions:
- Transaction costs and slippage
- Position sizing
- Risk management
- Multiple strategy comparison

Features:
- Chronological execution
- Drawdown tracking
- Performance analytics
- Clear simulation disclaimers
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

import numpy as np
import pandas as pd


@dataclass
class BacktestConfig:
    """Configuration for backtesting.
    
    Attributes:
        initial_capital: Starting capital in dollars
        commission: Commission per trade (percentage, 0.001 = 0.1%)
        slippage: Slippage per trade (percentage)
        max_position_size: Max % of capital per trade
        risk_per_trade: Risk per trade (percentage of capital)
        min_trade_size: Minimum trade amount
    """
    initial_capital: float = 100000.0
    commission: float = 0.001  # 0.1%
    slippage: float = 0.0005   # 0.05%
    max_position_size: float = 0.1  # 10% of capital
    risk_per_trade: float = 0.02  # 2% of capital
    min_trade_size: float = 100.0
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if not (0 <= self.commission < 0.1):
            raise ValueError("commission must be between 0 and 0.1")
        if not (0 <= self.slippage < 0.1):
            raise ValueError("slippage must be between 0 and 0.1")


@dataclass(frozen=True)
class Trade:
    """Single trade record.
    
    Attributes:
        date: Trade date
        direction: "BUY" or "SELL"
        price: Execution price
        quantity: Number of shares
        value: Total trade value
        commission: Commission paid
    """
    date: date
    direction: str
    price: float
    quantity: float
    value: float
    commission: float


@dataclass(frozen=True)
class BacktestResult:
    """Complete backtest result.
    
    Attributes:
        strategy_name: Name of strategy
        start_date: Backtest start date
        end_date: Backtest end date
        initial_capital: Starting capital
        final_value: Ending portfolio value
        total_return: Total return percentage
        annual_return: Annualized return
        max_drawdown: Maximum drawdown percentage
        sharpe_ratio: Sharpe ratio (annualized)
        win_rate: Percentage of winning trades
        profit_factor: Gross profit / Gross loss
        num_trades: Number of trades executed
        trades: List of Trade records
        equity_curve: Series of daily portfolio values
    """
    strategy_name: str
    start_date: date
    end_date: date
    initial_capital: float
    final_value: float
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    profit_factor: float
    num_trades: int
    trades: list[Trade]
    equity_curve: pd.Series


class BacktestEngine:
    """Execute historical backtest on price data."""
    
    def __init__(self, config: BacktestConfig | None = None) -> None:
        """Initialize backtest engine.
        
        Args:
            config: BacktestConfig instance
        """
        self.config = config or BacktestConfig()
        self.config.__post_init__()
    
    def backtest(
        self,
        prices: pd.Series,
        signals: pd.Series,
        strategy_name: str = "Strategy",
    ) -> BacktestResult:
        """Execute backtest on historical prices with trading signals.
        
        Args:
            prices: Series of prices (daily closing prices)
            signals: Series of trading signals:
                    0 = no action
                    1 = buy signal
                   -1 = sell signal
            strategy_name: Name of strategy
            
        Returns:
            BacktestResult with complete performance metrics
        """
        if len(prices) != len(signals):
            raise ValueError("prices and signals must have same length")
        
        # Initialize
        cash = self.config.initial_capital
        position = 0  # Shares held
        trades = []
        equity_values = []
        
        for i in range(len(prices)):
            price = prices.iloc[i]
            signal = signals.iloc[i]
            current_date = prices.index[i].date() if hasattr(prices.index[i], 'date') else date.today()
            
            # Calculate portfolio value
            portfolio_value = cash + position * price
            equity_values.append(portfolio_value)
            
            # Execute trades based on signals
            if signal == 1 and cash > 0:  # Buy signal
                # Calculate position size
                trade_value = min(
                    cash * self.config.max_position_size,
                    cash * self.config.risk_per_trade,
                )
                
                if trade_value >= self.config.min_trade_size:
                    # Apply slippage to buy price
                    execution_price = price * (1 + self.config.slippage)
                    commission = trade_value * self.config.commission
                    
                    quantity = (trade_value - commission) / execution_price
                    position += quantity
                    cash -= trade_value + commission
                    
                    trades.append(Trade(
                        date=current_date,
                        direction="BUY",
                        price=execution_price,
                        quantity=quantity,
                        value=trade_value,
                        commission=commission,
                    ))
            
            elif signal == -1 and position > 0:  # Sell signal
                # Apply slippage to sell price
                execution_price = price * (1 - self.config.slippage)
                trade_value = position * execution_price
                commission = trade_value * self.config.commission
                
                cash += trade_value - commission
                position = 0
                
                trades.append(Trade(
                    date=current_date,
                    direction="SELL",
                    price=execution_price,
                    quantity=position,
                    value=trade_value,
                    commission=commission,
                ))
        
        # Final portfolio value
        final_price = prices.iloc[-1]
        final_value = cash + position * final_price
        
        # Calculate metrics
        total_return = (final_value - self.config.initial_capital) / self.config.initial_capital
        
        # Annualized return
        days = len(prices)
        years = days / 252
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # Maximum drawdown
        equity_array = np.array(equity_values)
        running_max = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - running_max) / running_max
        max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0
        
        # Sharpe ratio
        returns = np.diff(equity_array) / equity_array[:-1]
        excess_returns = returns - 0.02 / 252
        sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(252) if excess_returns.std() > 0 else 0
        
        # Trade statistics
        if len(trades) > 0:
            trade_returns = []
            for j in range(0, len(trades) - 1, 2):
                if j + 1 < len(trades):
                    buy_trade = trades[j]
                    sell_trade = trades[j + 1]
                    ret = (sell_trade.price - buy_trade.price) / buy_trade.price
                    trade_returns.append(ret)
            
            if len(trade_returns) > 0:
                winning_trades = [r for r in trade_returns if r > 0]
                losing_trades = [r for r in trade_returns if r < 0]
                
                win_rate = len(winning_trades) / len(trade_returns)
                
                gross_profit = sum(winning_trades) if len(winning_trades) > 0 else 0
                gross_loss = abs(sum(losing_trades)) if len(losing_trades) > 0 else 0
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            else:
                win_rate = 0
                profit_factor = 0
        else:
            win_rate = 0
            profit_factor = 0
        
        # Get date range
        start_date = prices.index[0].date() if hasattr(prices.index[0], 'date') else date.today()
        end_date = prices.index[-1].date() if hasattr(prices.index[-1], 'date') else date.today()
        
        # Equity curve
        equity_curve = pd.Series(equity_values, index=prices.index)
        
        return BacktestResult(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.config.initial_capital,
            final_value=final_value,
            total_return=total_return * 100,
            annual_return=annual_return * 100,
            max_drawdown=max_drawdown * 100,
            sharpe_ratio=sharpe,
            win_rate=win_rate * 100,
            profit_factor=profit_factor,
            num_trades=len(trades),
            trades=trades,
            equity_curve=equity_curve,
        )


class BenchmarkStrategies:
    """Standard benchmark strategies for comparison."""
    
    @staticmethod
    def buy_and_hold(prices: pd.Series) -> BacktestResult:
        """Buy and hold strategy (buy on first day, hold until end).
        
        Args:
            prices: Series of prices
            
        Returns:
            BacktestResult for buy-and-hold strategy
        """
        signals = pd.Series(0, index=prices.index)
        signals.iloc[0] = 1  # Buy on first day
        
        engine = BacktestEngine(BacktestConfig(initial_capital=100000))
        return engine.backtest(prices, signals, strategy_name="Buy & Hold")
    
    @staticmethod
    def simple_moving_average(prices: pd.Series, short_window: int = 20, long_window: int = 50) -> BacktestResult:
        """Simple moving average crossover strategy.
        
        Args:
            prices: Series of prices
            short_window: Short-term moving average period
            long_window: Long-term moving average period
            
        Returns:
            BacktestResult for SMA strategy
        """
        sma_short = prices.rolling(window=short_window).mean()
        sma_long = prices.rolling(window=long_window).mean()
        
        signals = pd.Series(0, index=prices.index)
        
        # Buy when short MA > long MA
        signals[sma_short > sma_long] = 1
        # Sell when short MA < long MA
        signals[sma_short < sma_long] = -1
        
        engine = BacktestEngine(BacktestConfig(initial_capital=100000))
        return engine.backtest(prices, signals, strategy_name=f"SMA({short_window}/{long_window})")
    
    @staticmethod
    def random_signals(prices: pd.Series, trade_probability: float = 0.1) -> BacktestResult:
        """Random trading signals for baseline comparison.
        
        Args:
            prices: Series of prices
            trade_probability: Probability of trading on each day
            
        Returns:
            BacktestResult for random strategy
        """
        np.random.seed(42)
        signals = pd.Series(0, index=prices.index)
        
        for i in range(1, len(prices)):
            if np.random.random() < trade_probability:
                signals.iloc[i] = np.random.choice([-1, 1])
        
        engine = BacktestEngine(BacktestConfig(initial_capital=100000))
        return engine.backtest(prices, signals, strategy_name="Random Trading")


class BacktestComparator:
    """Compare multiple backtest results."""
    
    @staticmethod
    def compare_results(results: list[BacktestResult]) -> pd.DataFrame:
        """Create comparison DataFrame from backtest results.
        
        Args:
            results: List of BacktestResult
            
        Returns:
            Comparison DataFrame
        """
        data = []
        for result in results:
            data.append({
                "Strategy": result.strategy_name,
                "Period": f"{result.start_date} to {result.end_date}",
                "Total Return %": f"{result.total_return:.2f}",
                "Annual Return %": f"{result.annual_return:.2f}",
                "Max Drawdown %": f"{result.max_drawdown:.2f}",
                "Sharpe Ratio": f"{result.sharpe_ratio:.2f}",
                "Win Rate %": f"{result.win_rate:.2f}",
                "Profit Factor": f"{result.profit_factor:.2f}",
                "# Trades": result.num_trades,
            })
        
        return pd.DataFrame(data)
    
    @staticmethod
    def get_backtest_summary(result: BacktestResult) -> str:
        """Get human-readable backtest summary.
        
        Args:
            result: BacktestResult instance
            
        Returns:
            Formatted summary string
        """
        summary = f"\n{'='*80}\n"
        summary += f"BACKTEST RESULT: {result.strategy_name}\n"
        summary += f"{'='*80}\n\n"
        
        summary += f"Period: {result.start_date} to {result.end_date}\n"
        summary += f"Initial Capital: ${result.initial_capital:,.2f}\n"
        summary += f"Final Value: ${result.final_value:,.2f}\n\n"
        
        summary += "Performance Metrics:\n"
        summary += f"  Total Return:       {result.total_return:.2f}%\n"
        summary += f"  Annualized Return:  {result.annual_return:.2f}%\n"
        summary += f"  Maximum Drawdown:   {result.max_drawdown:.2f}%\n"
        summary += f"  Sharpe Ratio:       {result.sharpe_ratio:.2f}\n\n"
        
        summary += "Trading Statistics:\n"
        summary += f"  Number of Trades:   {result.num_trades}\n"
        summary += f"  Win Rate:           {result.win_rate:.2f}%\n"
        summary += f"  Profit Factor:      {result.profit_factor:.2f}\n\n"
        
        summary += "⚠️  DISCLAIMER\n"
        summary += "-" * 80 + "\n"
        summary += "These are SIMULATED RESULTS for backtesting purposes only.\n"
        summary += "Historical performance does not guarantee future results.\n"
        summary += "Actual trading results may differ significantly due to:\n"
        summary += "  • Market conditions and liquidity\n"
        summary += "  • Execution prices and timing\n"
        summary += "  • Transaction costs and taxes\n"
        summary += "  • Risk management constraints\n"
        summary += "  • Model overfitting to historical data\n"
        summary += "  • Unforeseen market events\n"
        summary += "-" * 80 + "\n"
        
        return summary
