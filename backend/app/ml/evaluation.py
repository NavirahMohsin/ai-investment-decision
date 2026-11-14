"""Model evaluation with walk-forward validation and financial metrics.

Provides comprehensive evaluation framework:
- Chronological train/validation/test splits
- Walk-forward validation
- Classification metrics (accuracy, precision, recall, F1, ROC-AUC)
- Financial performance metrics
- Strategy comparison

Features:
- No data leakage via temporal ordering
- Multiple evaluation windows
- Financial returns calculation
- Baseline strategy comparison
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)


@dataclass
class EvaluationConfig:
    """Configuration for model evaluation.
    
    Attributes:
        train_size: Fraction of data for training (default: 0.6)
        val_size: Fraction of data for validation (default: 0.2)
        test_size: Fraction of data for testing (default: 0.2)
        walk_forward_step: Days to step forward in walk-forward validation
        min_train_size: Minimum training samples required
    """
    train_size: float = 0.6
    val_size: float = 0.2
    test_size: float = 0.2
    walk_forward_step: int = 20  # Days
    min_train_size: int = 50
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        total = self.train_size + self.val_size + self.test_size
        if not np.isclose(total, 1.0, atol=0.01):
            raise ValueError(f"train_size + val_size + test_size must equal 1.0, got {total}")
        
        if self.min_train_size < 10:
            raise ValueError("min_train_size must be at least 10")


@dataclass(frozen=True)
class ClassificationMetrics:
    """Classification evaluation metrics.
    
    Attributes:
        accuracy: Overall accuracy
        precision: Precision (macro average)
        recall: Recall (macro average)
        f1: F1 score (macro average)
        roc_auc: ROC-AUC score
        confusion_matrix: Confusion matrix
        class_report: Per-class metrics
    """
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float | None
    confusion_matrix: np.ndarray
    class_report: dict


@dataclass(frozen=True)
class FinancialMetrics:
    """Financial performance metrics.
    
    Attributes:
        total_return: Total return percentage
        annual_return: Annualized return
        max_drawdown: Maximum drawdown percentage
        sharpe_ratio: Sharpe ratio (annualized)
        win_rate: Percentage of winning trades
        avg_win: Average winning trade return
        avg_loss: Average losing trade return
        profit_factor: Gross profit / Gross loss
        num_trades: Number of trades
    """
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    num_trades: int


@dataclass(frozen=True)
class ModelEvaluationResult:
    """Complete model evaluation result.
    
    Attributes:
        model_name: Name of evaluated model
        dates: Date range of evaluation
        classification_metrics: Classification metrics
        financial_metrics: Financial metrics
        predictions: Array of predictions
        actual: Array of actual values
        predictions_proba: Probability predictions
    """
    model_name: str
    dates: tuple[date, date]
    classification_metrics: ClassificationMetrics
    financial_metrics: FinancialMetrics
    predictions: np.ndarray
    actual: np.ndarray
    predictions_proba: np.ndarray | None = None


class TemporalSplitter:
    """Create chronological train/validation/test splits."""
    
    def __init__(self, config: EvaluationConfig | None = None) -> None:
        """Initialize temporal splitter.
        
        Args:
            config: EvaluationConfig instance
        """
        self.config = config or EvaluationConfig()
        self.config.__post_init__()
    
    def split(
        self,
        X: pd.DataFrame,
        y: pd.Series,
    ) -> tuple[tuple[pd.DataFrame, pd.Series],
                tuple[pd.DataFrame, pd.Series],
                tuple[pd.DataFrame, pd.Series]]:
        """Split data chronologically into train/validation/test.
        
        Args:
            X: Feature DataFrame with dates (index or column)
            y: Target Series
            
        Returns:
            Tuple of ((X_train, y_train), (X_val, y_val), (X_test, y_test))
        """
        n = len(X)
        
        # Calculate split indices
        train_idx = int(n * self.config.train_size)
        val_idx = train_idx + int(n * self.config.val_size)
        
        # Split maintaining temporal order
        X_train, X_val, X_test = X[:train_idx], X[train_idx:val_idx], X[val_idx:]
        y_train, y_val, y_test = y[:train_idx], y[train_idx:val_idx], y[val_idx:]
        
        return (X_train, y_train), (X_val, y_val), (X_test, y_test)
    
    def walk_forward_splits(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        initial_train_size: int | None = None,
    ) -> list[tuple[tuple[pd.DataFrame, pd.Series],
                     tuple[pd.DataFrame, pd.Series]]]:
        """Generate walk-forward validation splits.
        
        Each fold expands training set and validates on subsequent period.
        
        Args:
            X: Feature DataFrame
            y: Target Series
            initial_train_size: Initial training set size (default: calculated from config)
            
        Returns:
            List of ((X_train, y_train), (X_val, y_val)) tuples
        """
        if initial_train_size is None:
            initial_train_size = max(
                int(len(X) * self.config.train_size),
                self.config.min_train_size,
            )
        
        splits = []
        train_end = initial_train_size
        
        while train_end + self.config.walk_forward_step <= len(X):
            val_start = train_end
            val_end = train_end + self.config.walk_forward_step
            
            X_train, y_train = X[:train_end], y[:train_end]
            X_val, y_val = X[val_start:val_end], y[val_start:val_end]
            
            splits.append(((X_train, y_train), (X_val, y_val)))
            
            # Move window forward
            train_end = val_end
        
        return splits


class ClassificationEvaluator:
    """Evaluate classification metrics."""
    
    @staticmethod
    def evaluate(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: np.ndarray | None = None,
    ) -> ClassificationMetrics:
        """Calculate classification metrics.
        
        Args:
            y_true: True labels
            y_pred: Predicted labels
            y_proba: Probability predictions (optional, for ROC-AUC)
            
        Returns:
            ClassificationMetrics instance
        """
        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred, average="macro", zero_division=0)
        recall = recall_score(y_true, y_pred, average="macro", zero_division=0)
        f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
        conf_matrix = confusion_matrix(y_true, y_pred)
        class_rep = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
        
        # ROC-AUC for binary/multi-class if probabilities available
        roc_auc = None
        if y_proba is not None and len(np.unique(y_true)) == 2:
            try:
                roc_auc = roc_auc_score(y_true, y_proba[:, 1])
            except (IndexError, ValueError):
                pass
        
        return ClassificationMetrics(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            roc_auc=roc_auc,
            confusion_matrix=conf_matrix,
            class_report=class_rep,
        )


class FinancialEvaluator:
    """Evaluate financial performance metrics."""
    
    def __init__(
        self,
        risk_free_rate: float = 0.02,  # 2% annual
        trading_days: int = 252,
    ) -> None:
        """Initialize financial evaluator.
        
        Args:
            risk_free_rate: Annual risk-free rate for Sharpe ratio
            trading_days: Number of trading days per year
        """
        self.risk_free_rate = risk_free_rate
        self.trading_days = trading_days
    
    def evaluate(
        self,
        returns: pd.Series,
        trades: pd.Series | None = None,
    ) -> FinancialMetrics:
        """Calculate financial metrics.
        
        Args:
            returns: Series of daily returns (percentage or decimal)
            trades: Series indicating trading days (1 for trade, 0 for hold)
            
        Returns:
            FinancialMetrics instance
        """
        # Ensure returns are in decimal form
        if returns.max() > 10:  # Assume percentage if > 10
            returns = returns / 100
        
        # Total and annualized return
        total_return = (1 + returns).prod() - 1
        days = len(returns)
        years = days / self.trading_days
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # Maximum drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Sharpe ratio
        excess_returns = returns - (self.risk_free_rate / self.trading_days)
        sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(self.trading_days) if excess_returns.std() > 0 else 0
        
        # Trade statistics
        if trades is not None:
            trade_returns = returns[trades == 1]
            num_trades = (trades == 1).sum()
            
            if len(trade_returns) > 0:
                winning_trades = trade_returns[trade_returns > 0]
                losing_trades = trade_returns[trade_returns < 0]
                
                win_rate = len(winning_trades) / len(trade_returns) if len(trade_returns) > 0 else 0
                avg_win = winning_trades.mean() if len(winning_trades) > 0 else 0
                avg_loss = losing_trades.mean() if len(losing_trades) > 0 else 0
                
                gross_profit = winning_trades.sum() if len(winning_trades) > 0 else 0
                gross_loss = abs(losing_trades.sum()) if len(losing_trades) > 0 else 0
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            else:
                win_rate = 0
                avg_win = 0
                avg_loss = 0
                profit_factor = 0
        else:
            num_trades = 0
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
        
        return FinancialMetrics(
            total_return=total_return * 100,  # Convert to percentage
            annual_return=annual_return * 100,
            max_drawdown=max_drawdown * 100,
            sharpe_ratio=sharpe,
            win_rate=win_rate * 100,
            avg_win=avg_win * 100,
            avg_loss=avg_loss * 100,
            profit_factor=profit_factor,
            num_trades=int(num_trades),
        )


class ModelEvaluator:
    """Complete model evaluation framework."""
    
    def __init__(
        self,
        eval_config: EvaluationConfig | None = None,
        risk_free_rate: float = 0.02,
    ) -> None:
        """Initialize model evaluator.
        
        Args:
            eval_config: EvaluationConfig instance
            risk_free_rate: Annual risk-free rate
        """
        self.eval_config = eval_config or EvaluationConfig()
        self.temporal_splitter = TemporalSplitter(self.eval_config)
        self.financial_evaluator = FinancialEvaluator(risk_free_rate=risk_free_rate)
    
    def evaluate_on_test_set(
        self,
        model,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        prices: pd.Series | None = None,
        model_name: str = "model",
    ) -> ModelEvaluationResult:
        """Evaluate model on test set.
        
        Args:
            model: Trained model with predict() and predict_proba() methods
            X_test: Test features
            y_test: Test targets
            prices: Price series for financial metrics (optional)
            model_name: Name of model
            
        Returns:
            ModelEvaluationResult
        """
        # Get predictions
        y_pred = model.predict(X_test)
        
        try:
            y_proba = model.predict_proba(X_test)
        except (AttributeError, TypeError):
            y_proba = None
        
        # Classification metrics
        class_metrics = ClassificationEvaluator.evaluate(y_test.values, y_pred, y_proba)
        
        # Financial metrics (if prices available)
        if prices is not None:
            # Calculate returns based on predictions
            returns = prices.pct_change() * 100
            trades = (y_pred != 0).astype(int)  # Assume trading on non-neutral predictions
            fin_metrics = self.financial_evaluator.evaluate(returns, trades)
        else:
            fin_metrics = FinancialMetrics(
                total_return=0, annual_return=0, max_drawdown=0,
                sharpe_ratio=0, win_rate=0, avg_win=0, avg_loss=0,
                profit_factor=0, num_trades=0,
            )
        
        # Get date range
        if hasattr(X_test, 'index') and isinstance(X_test.index, pd.DatetimeIndex):
            start_date = X_test.index[0].date()
            end_date = X_test.index[-1].date()
        else:
            start_date = date.today()
            end_date = date.today()
        
        return ModelEvaluationResult(
            model_name=model_name,
            dates=(start_date, end_date),
            classification_metrics=class_metrics,
            financial_metrics=fin_metrics,
            predictions=y_pred,
            actual=y_test.values,
            predictions_proba=y_proba,
        )
    
    def walk_forward_validate(
        self,
        model_builder,
        X: pd.DataFrame,
        y: pd.Series,
        prices: pd.Series | None = None,
        model_name: str = "model",
    ) -> list[ModelEvaluationResult]:
        """Perform walk-forward validation.
        
        Args:
            model_builder: Function that takes (X_train, y_train) and returns trained model
            X: Feature DataFrame
            y: Target Series
            prices: Price series for financial metrics
            model_name: Name of model
            
        Returns:
            List of ModelEvaluationResult for each validation window
        """
        splits = self.temporal_splitter.walk_forward_splits(X, y)
        results = []
        
        for train_data, val_data in splits:
            X_train, y_train = train_data
            X_val, y_val = val_data
            
            # Train model
            try:
                trained_model = model_builder(X_train, y_train)
            except Exception as e:
                print(f"Error training model on fold: {e}")
                continue
            
            # Get validation price window
            val_prices = None
            if prices is not None:
                val_prices = prices[len(X_train):len(X_train) + len(X_val)]
            
            # Evaluate
            result = self.evaluate_on_test_set(
                trained_model,
                X_val,
                y_val,
                prices=val_prices,
                model_name=model_name,
            )
            results.append(result)
        
        return results
    
    @staticmethod
    def compare_evaluations(results: list[ModelEvaluationResult]) -> pd.DataFrame:
        """Create comparison DataFrame from multiple evaluations.
        
        Args:
            results: List of ModelEvaluationResult
            
        Returns:
            Comparison DataFrame
        """
        data = []
        for result in results:
            data.append({
                "Model": result.model_name,
                "Period": f"{result.dates[0]} to {result.dates[1]}",
                "Accuracy": f"{result.classification_metrics.accuracy:.4f}",
                "F1": f"{result.classification_metrics.f1:.4f}",
                "Total Return %": f"{result.financial_metrics.total_return:.2f}",
                "Sharpe Ratio": f"{result.financial_metrics.sharpe_ratio:.2f}",
                "Max Drawdown %": f"{result.financial_metrics.max_drawdown:.2f}",
                "Win Rate %": f"{result.financial_metrics.win_rate:.2f}",
            })
        
        return pd.DataFrame(data)
    
    @staticmethod
    def get_evaluation_summary(result: ModelEvaluationResult) -> str:
        """Get human-readable evaluation summary.
        
        Args:
            result: ModelEvaluationResult
            
        Returns:
            Formatted summary string
        """
        summary = f"\nModel Evaluation Summary: {result.model_name}\n"
        summary += f"{'='*80}\n"
        summary += f"Period: {result.dates[0]} to {result.dates[1]}\n\n"
        
        # Classification metrics
        summary += "Classification Metrics:\n"
        summary += f"  Accuracy:  {result.classification_metrics.accuracy:.4f}\n"
        summary += f"  Precision: {result.classification_metrics.precision:.4f}\n"
        summary += f"  Recall:    {result.classification_metrics.recall:.4f}\n"
        summary += f"  F1 Score:  {result.classification_metrics.f1:.4f}\n"
        if result.classification_metrics.roc_auc is not None:
            summary += f"  ROC-AUC:   {result.classification_metrics.roc_auc:.4f}\n"
        
        # Financial metrics
        summary += "\nFinancial Metrics:\n"
        summary += f"  Total Return:    {result.financial_metrics.total_return:.2f}%\n"
        summary += f"  Annualized:      {result.financial_metrics.annual_return:.2f}%\n"
        summary += f"  Max Drawdown:    {result.financial_metrics.max_drawdown:.2f}%\n"
        summary += f"  Sharpe Ratio:    {result.financial_metrics.sharpe_ratio:.2f}\n"
        summary += f"  Win Rate:        {result.financial_metrics.win_rate:.2f}%\n"
        summary += f"  Avg Win:         {result.financial_metrics.avg_win:.2f}%\n"
        summary += f"  Avg Loss:        {result.financial_metrics.avg_loss:.2f}%\n"
        summary += f"  Profit Factor:   {result.financial_metrics.profit_factor:.2f}\n"
        summary += f"  Number of Trades:{result.financial_metrics.num_trades}\n"
        
        return summary
