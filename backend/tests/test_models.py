"""Tests for model training and evaluation."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.ml.models import (
    ModelType,
    ModelConfig,
    ModelTrainer,
    ModelComparator,
    HyperparameterTuner,
    LogisticRegressionConfig,
    RandomForestConfig,
    XGBoostConfig,
    LightGBMConfig,
)


@pytest.fixture
def sample_classification_data():
    """Create sample classification dataset."""
    np.random.seed(42)
    
    # Generate synthetic data with 3 classes
    n_samples = 200
    n_features = 20
    
    X = np.random.randn(n_samples, n_features)
    # Create target with numeric labels (required by XGBoost)
    y = np.random.choice([0, 1, 2], size=n_samples, p=[0.4, 0.3, 0.3])
    
    # Create DataFrames
    feature_cols = [f"feature_{i}" for i in range(n_features)]
    X_df = pd.DataFrame(X, columns=feature_cols)
    y_series = pd.Series(y, name="target")
    
    # Split into train/test
    split_idx = int(0.8 * n_samples)
    X_train = X_df.iloc[:split_idx]
    y_train = y_series.iloc[:split_idx]
    X_test = X_df.iloc[split_idx:]
    y_test = y_series.iloc[split_idx:]
    
    return X_train, y_train, X_test, y_test


class TestModelConfig:
    """Test ModelConfig validation."""
    
    def test_valid_config(self):
        """Valid config should not raise."""
        config = ModelConfig()
        assert config.model_type == ModelType.RANDOM_FOREST
        assert config.cv_folds == 5
    
    def test_invalid_model_type(self):
        """Invalid model type should raise."""
        with pytest.raises(ValueError):
            ModelConfig(model_type="invalid_model")
    
    def test_invalid_test_size(self):
        """Invalid test_size should raise."""
        with pytest.raises(ValueError):
            ModelConfig(test_size=0.0)
        
        with pytest.raises(ValueError):
            ModelConfig(test_size=1.5)
    
    def test_invalid_cv_folds(self):
        """Invalid cv_folds should raise."""
        with pytest.raises(ValueError):
            ModelConfig(cv_folds=1)


class TestModelTrainer:
    """Test ModelTrainer class."""
    
    def test_logistic_regression_training(self, sample_classification_data):
        """Should train logistic regression."""
        X_train, y_train, X_test, y_test = sample_classification_data
        
        config = ModelConfig(model_type=ModelType.LOGISTIC_REGRESSION)
        trainer = ModelTrainer(config)
        trainer.train(X_train, y_train)
        
        # Should be able to predict
        predictions = trainer.predict(X_test)
        assert len(predictions) == len(X_test)
        assert all(p in [0, 1, 2] for p in predictions)
    
    def test_random_forest_training(self, sample_classification_data):
        """Should train random forest."""
        X_train, y_train, X_test, y_test = sample_classification_data
        
        config = ModelConfig(model_type=ModelType.RANDOM_FOREST)
        trainer = ModelTrainer(config)
        trainer.train(X_train, y_train)
        
        predictions = trainer.predict(X_test)
        assert len(predictions) == len(X_test)
    
    def test_xgboost_training(self, sample_classification_data):
        """Should train XGBoost."""
        X_train, y_train, X_test, y_test = sample_classification_data
        
        config = ModelConfig(model_type=ModelType.XGBOOST)
        trainer = ModelTrainer(config)
        trainer.train(X_train, y_train)
        
        predictions = trainer.predict(X_test)
        assert len(predictions) == len(X_test)
    
    def test_lightgbm_training(self, sample_classification_data):
        """Should train LightGBM."""
        X_train, y_train, X_test, y_test = sample_classification_data
        
        config = ModelConfig(model_type=ModelType.LIGHTGBM)
        trainer = ModelTrainer(config)
        trainer.train(X_train, y_train)
        
        predictions = trainer.predict(X_test)
        assert len(predictions) == len(X_test)
    
    def test_predict_before_training_raises(self, sample_classification_data):
        """Predicting before training should raise."""
        _, _, X_test, _ = sample_classification_data
        
        config = ModelConfig(model_type=ModelType.RANDOM_FOREST)
        trainer = ModelTrainer(config)
        
        with pytest.raises(ValueError):
            trainer.predict(X_test)
    
    def test_feature_scaling(self, sample_classification_data):
        """Should scale features when configured."""
        X_train, y_train, X_test, y_test = sample_classification_data
        
        config = ModelConfig(model_type=ModelType.LOGISTIC_REGRESSION, scale_features=True)
        trainer = ModelTrainer(config)
        trainer.train(X_train, y_train)
        
        # Scaler should be set
        assert trainer.scaler is not None
        
        # Should still be able to predict
        predictions = trainer.predict(X_test)
        assert len(predictions) == len(X_test)
    
    def test_predict_proba(self, sample_classification_data):
        """Should return probability predictions."""
        X_train, y_train, X_test, y_test = sample_classification_data
        
        config = ModelConfig(model_type=ModelType.RANDOM_FOREST)
        trainer = ModelTrainer(config)
        trainer.train(X_train, y_train)
        
        proba = trainer.predict_proba(X_test)
        assert proba.shape[0] == len(X_test)
        assert proba.shape[1] == 3  # 3 classes
        assert np.allclose(proba.sum(axis=1), 1.0)  # Probabilities sum to 1
    
    def test_evaluate(self, sample_classification_data):
        """Should evaluate model."""
        X_train, y_train, X_test, y_test = sample_classification_data
        
        config = ModelConfig(model_type=ModelType.RANDOM_FOREST)
        trainer = ModelTrainer(config)
        trainer.train(X_train, y_train)
        
        evaluation = trainer.evaluate(X_test, y_test)
        
        # Check metrics exist and are in valid range
        assert 0 <= evaluation.accuracy <= 1
        assert 0 <= evaluation.precision <= 1
        assert 0 <= evaluation.recall <= 1
        assert 0 <= evaluation.f1 <= 1
        assert 0 <= evaluation.cv_accuracy_mean <= 1
        
        # Check confusion matrix
        assert evaluation.confusion_matrix.shape == (3, 3)
    
    def test_feature_importance(self, sample_classification_data):
        """Should extract feature importance."""
        X_train, y_train, _, _ = sample_classification_data
        
        # Random Forest has feature_importances_
        config = ModelConfig(model_type=ModelType.RANDOM_FOREST)
        trainer = ModelTrainer(config)
        trainer.train(X_train, y_train)
        
        importance_df = trainer.get_feature_importance(top_n=10)
        
        assert len(importance_df) == 10
        assert "feature" in importance_df.columns
        assert "importance" in importance_df.columns
        assert importance_df["importance"].is_monotonic_decreasing
    
    def test_mismatched_data_shapes_raises(self, sample_classification_data):
        """Mismatched X and y shapes should raise."""
        X_train, y_train, _, _ = sample_classification_data
        
        config = ModelConfig(model_type=ModelType.RANDOM_FOREST)
        trainer = ModelTrainer(config)
        
        with pytest.raises(ValueError):
            trainer.train(X_train, y_train[:-1])


class TestModelComparator:
    """Test ModelComparator class."""
    
    def test_train_baseline(self, sample_classification_data):
        """Should train baseline model."""
        X_train, y_train, _, _ = sample_classification_data
        
        comparator = ModelComparator()
        eval_result = comparator.train_baseline(X_train, y_train)
        
        assert eval_result.model_name == ModelType.LOGISTIC_REGRESSION
        assert "baseline" in comparator.models
    
    def test_train_random_forest(self, sample_classification_data):
        """Should train random forest."""
        X_train, y_train, _, _ = sample_classification_data
        
        comparator = ModelComparator()
        eval_result = comparator.train_random_forest(X_train, y_train, n_estimators=50)
        
        assert eval_result.model_name == ModelType.RANDOM_FOREST
        assert "random_forest" in comparator.models
    
    def test_train_xgboost(self, sample_classification_data):
        """Should train XGBoost."""
        X_train, y_train, _, _ = sample_classification_data
        
        comparator = ModelComparator()
        eval_result = comparator.train_xgboost(X_train, y_train, n_estimators=50)
        
        assert eval_result.model_name == ModelType.XGBOOST
        assert "xgboost" in comparator.models
    
    def test_train_lightgbm(self, sample_classification_data):
        """Should train LightGBM."""
        X_train, y_train, _, _ = sample_classification_data
        
        comparator = ModelComparator()
        eval_result = comparator.train_lightgbm(X_train, y_train, n_estimators=50)
        
        assert eval_result.model_name == ModelType.LIGHTGBM
        assert "lightgbm" in comparator.models
    
    def test_evaluate_all(self, sample_classification_data):
        """Should evaluate all models."""
        X_train, y_train, X_test, y_test = sample_classification_data
        
        comparator = ModelComparator()
        comparator.train_baseline(X_train, y_train)
        comparator.train_random_forest(X_train, y_train, n_estimators=50)
        
        evaluations = comparator.evaluate_all(X_test, y_test)
        
        assert len(evaluations) == 2
        assert "baseline" in evaluations
        assert "random_forest" in evaluations
    
    def test_compare_models(self, sample_classification_data):
        """Should create comparison DataFrame."""
        X_train, y_train, X_test, y_test = sample_classification_data
        
        comparator = ModelComparator()
        comparator.train_baseline(X_train, y_train)
        comparator.train_random_forest(X_train, y_train, n_estimators=50)
        comparator.evaluate_all(X_test, y_test)
        
        comparison = comparator.compare_models()
        
        assert len(comparison) == 2
        assert "Model" in comparison.columns
        assert "Accuracy" in comparison.columns
        assert "F1" in comparison.columns
    
    def test_get_best_model(self, sample_classification_data):
        """Should get best model."""
        X_train, y_train, X_test, y_test = sample_classification_data
        
        comparator = ModelComparator()
        comparator.train_baseline(X_train, y_train)
        comparator.train_random_forest(X_train, y_train, n_estimators=50)
        comparator.evaluate_all(X_test, y_test)
        
        best_name, best_trainer = comparator.get_best_model(metric="f1")
        
        assert best_name in ["baseline", "random_forest"]
        assert best_trainer is not None
    
    def test_get_evaluation_summary(self, sample_classification_data):
        """Should get evaluation summary."""
        X_train, y_train, X_test, y_test = sample_classification_data
        
        comparator = ModelComparator()
        comparator.train_baseline(X_train, y_train)
        comparator.train_random_forest(X_train, y_train, n_estimators=50)
        comparator.evaluate_all(X_test, y_test)
        
        summary = comparator.get_evaluation_summary()
        
        assert "Model Comparison Results" in summary
        assert "BASELINE" in summary
        assert "RANDOM_FOREST" in summary
        assert "Accuracy" in summary


class TestHyperparameterTuner:
    """Test HyperparameterTuner class."""
    
    def test_tune_logistic_regression(self, sample_classification_data):
        """Should tune logistic regression."""
        X_train, y_train, _, _ = sample_classification_data
        
        tuner = HyperparameterTuner()
        best_params = tuner.tune_logistic_regression(X_train, y_train, cv_folds=3)
        
        assert "C" in best_params
        assert best_params["C"] in [0.01, 0.1, 1, 10, 100]
    
    def test_tune_random_forest(self, sample_classification_data):
        """Should tune random forest."""
        X_train, y_train, _, _ = sample_classification_data
        
        tuner = HyperparameterTuner()
        best_params = tuner.tune_random_forest(X_train, y_train, cv_folds=3)
        
        assert "n_estimators" in best_params
        assert "max_depth" in best_params
        assert "min_samples_split" in best_params
    
    def test_tune_xgboost(self, sample_classification_data):
        """Should tune XGBoost."""
        X_train, y_train, _, _ = sample_classification_data
        
        tuner = HyperparameterTuner()
        best_params = tuner.tune_xgboost(X_train, y_train, cv_folds=3)
        
        assert "n_estimators" in best_params
        assert "max_depth" in best_params
        assert "learning_rate" in best_params
    
    def test_tune_lightgbm(self, sample_classification_data):
        """Should tune LightGBM."""
        X_train, y_train, _, _ = sample_classification_data
        
        tuner = HyperparameterTuner()
        best_params = tuner.tune_lightgbm(X_train, y_train, cv_folds=3)
        
        assert "n_estimators" in best_params
        assert "learning_rate" in best_params
        assert "num_leaves" in best_params
