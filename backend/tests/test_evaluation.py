"""Tests for model evaluation framework."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.ml.evaluation import (
    EvaluationConfig,
    TemporalSplitter,
    ClassificationEvaluator,
    FinancialEvaluator,
    ModelEvaluator,
)


@pytest.fixture
def sample_data():
    """Create sample evaluation data."""
    dates = pd.date_range("2024-01-01", periods=200, freq="D")
    X = pd.DataFrame(
        np.random.randn(200, 10),
        columns=[f"feature_{i}" for i in range(10)],
        index=dates
    )
    y = pd.Series(np.random.choice([0, 1, 2], 200), index=dates, name="target")
    prices = pd.Series(100 * (1.01 ** np.arange(200)), index=dates)
    
    return X, y, prices


class TestEvaluationConfig:
    """Test EvaluationConfig validation."""
    
    def test_valid_config(self):
        """Valid config should not raise."""
        config = EvaluationConfig()
        assert config.train_size == 0.6
        assert config.val_size == 0.2
        assert config.test_size == 0.2
    
    def test_invalid_split_sum(self):
        """Split sum != 1.0 should raise."""
        with pytest.raises(ValueError):
            EvaluationConfig(train_size=0.5, val_size=0.3, test_size=0.1)
    
    def test_invalid_min_train_size(self):
        """Min train size < 10 should raise."""
        with pytest.raises(ValueError):
            EvaluationConfig(min_train_size=5)


class TestTemporalSplitter:
    """Test TemporalSplitter class."""
    
    def test_split(self, sample_data):
        """Should split data chronologically."""
        X, y, _ = sample_data
        
        splitter = TemporalSplitter()
        (X_train, y_train), (X_val, y_val), (X_test, y_test) = splitter.split(X, y)
        
        # Check sizes
        assert len(X_train) == 120
        assert len(X_val) == 40
        assert len(X_test) == 40
        
        # Check order is maintained
        assert X_train.index[0] < X_val.index[0] < X_test.index[0]
    
    def test_walk_forward_splits(self, sample_data):
        """Should generate walk-forward validation splits."""
        X, y, _ = sample_data
        
        splitter = TemporalSplitter(EvaluationConfig(walk_forward_step=20))
        splits = splitter.walk_forward_splits(X, y, initial_train_size=50)
        
        # Should have multiple splits
        assert len(splits) > 0
        
        # Each split should expand training set
        for i, ((X_train, y_train), (X_val, y_val)) in enumerate(splits):
            assert len(X_train) >= 50
            assert len(X_val) == 20
            
            # Training sets should be expanding
            if i > 0:
                prev_train_len = len(splits[i-1][0][0])
                assert len(X_train) >= prev_train_len


class TestClassificationEvaluator:
    """Test ClassificationEvaluator class."""
    
    def test_evaluate(self):
        """Should calculate classification metrics."""
        y_true = np.array([0, 1, 2, 0, 1, 2, 0, 1, 2, 0])
        y_pred = np.array([0, 1, 2, 0, 1, 1, 0, 0, 2, 0])
        
        metrics = ClassificationEvaluator.evaluate(y_true, y_pred)
        
        assert 0 <= metrics.accuracy <= 1
        assert 0 <= metrics.precision <= 1
        assert 0 <= metrics.recall <= 1
        assert 0 <= metrics.f1 <= 1
        assert metrics.confusion_matrix.shape == (3, 3)
    
    def test_evaluate_with_probabilities(self):
        """Should calculate ROC-AUC with probabilities."""
        y_true = np.array([0, 0, 1, 1, 0, 1])
        y_pred = np.array([0, 0, 1, 1, 0, 1])
        y_proba = np.array([[0.9, 0.1], [0.8, 0.2], [0.2, 0.8], 
                           [0.1, 0.9], [0.7, 0.3], [0.3, 0.7]])
        
        metrics = ClassificationEvaluator.evaluate(y_true, y_pred, y_proba)
        
        assert metrics.roc_auc is not None
        assert 0 <= metrics.roc_auc <= 1


class TestFinancialEvaluator:
    """Test FinancialEvaluator class."""
    
    def test_evaluate(self):
        """Should calculate financial metrics."""
        returns = pd.Series(np.random.normal(0.001, 0.02, 252))  # ~1% annual
        
        evaluator = FinancialEvaluator()
        metrics = evaluator.evaluate(returns)
        
        assert metrics.total_return is not None
        assert metrics.annual_return is not None
        assert metrics.max_drawdown <= 0
        assert metrics.sharpe_ratio is not None
    
    def test_evaluate_with_trades(self):
        """Should calculate trade statistics."""
        returns = pd.Series(np.random.normal(0.001, 0.02, 252))
        trades = pd.Series(np.random.choice([0, 1], 252, p=[0.8, 0.2]))
        
        evaluator = FinancialEvaluator()
        metrics = evaluator.evaluate(returns, trades)
        
        assert 0 <= metrics.win_rate <= 100
        assert metrics.num_trades >= 0
        assert metrics.profit_factor >= 0


class TestModelEvaluator:
    """Test ModelEvaluator class."""
    
    def test_evaluate_on_test_set(self, sample_data):
        """Should evaluate model on test set."""
        X, y, prices = sample_data
        
        # Create simple predictor
        class SimplePredictor:
            def predict(self, X):
                return np.zeros(len(X), dtype=int)
            
            def predict_proba(self, X):
                proba = np.zeros((len(X), 3))
                proba[:, 0] = 1.0
                return proba
        
        model = SimplePredictor()
        evaluator = ModelEvaluator()
        
        result = evaluator.evaluate_on_test_set(
            model, X, y, prices=prices,
            model_name="test_model"
        )
        
        assert result.model_name == "test_model"
        assert result.classification_metrics.accuracy is not None
        assert result.financial_metrics.total_return is not None
