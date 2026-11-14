"""Model development and training for stock price prediction.

Implements multiple classification models:
- Logistic Regression (baseline)
- Random Forest (ensemble)
- XGBoost (gradient boosting)
- LightGBM (gradient boosting)

Features:
- Model training with configurable hyperparameters
- Cross-validation evaluation
- Hyperparameter tuning
- Model comparison and selection
- Feature importance analysis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_validate, GridSearchCV, StratifiedKFold
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
    roc_auc_score,
)

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False


class ModelType:
    """Available model types."""
    LOGISTIC_REGRESSION = "logistic_regression"
    RANDOM_FOREST = "random_forest"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"


@dataclass
class ModelConfig:
    """Configuration for model training.
    
    Attributes:
        model_type: Type of model to train
        random_state: Random seed for reproducibility
        test_size: Fraction of data for testing
        cv_folds: Number of cross-validation folds
        scale_features: Whether to standardize features
        class_weight: How to weight classes ('balanced' or None)
    """
    model_type: str = ModelType.RANDOM_FOREST
    random_state: int = 42
    test_size: float = 0.2
    cv_folds: int = 5
    scale_features: bool = True
    class_weight: str | None = "balanced"
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        valid_types = {
            ModelType.LOGISTIC_REGRESSION,
            ModelType.RANDOM_FOREST,
            ModelType.XGBOOST,
            ModelType.LIGHTGBM,
        }
        if self.model_type not in valid_types:
            raise ValueError(f"model_type must be one of {valid_types}")
        
        if not 0 < self.test_size < 1:
            raise ValueError("test_size must be between 0 and 1")
        
        if self.cv_folds < 2:
            raise ValueError("cv_folds must be at least 2")


@dataclass
class LogisticRegressionConfig:
    """Hyperparameters for Logistic Regression."""
    C: float = 1.0
    max_iter: int = 1000
    solver: str = "lbfgs"
    penalty: str = "l2"


@dataclass
class RandomForestConfig:
    """Hyperparameters for Random Forest."""
    n_estimators: int = 100
    max_depth: int | None = None
    min_samples_split: int = 2
    min_samples_leaf: int = 1
    max_features: str = "sqrt"
    n_jobs: int = -1


@dataclass
class XGBoostConfig:
    """Hyperparameters for XGBoost."""
    n_estimators: int = 100
    max_depth: int = 6
    learning_rate: float = 0.1
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_alpha: float = 0.0
    reg_lambda: float = 1.0


@dataclass
class LightGBMConfig:
    """Hyperparameters for LightGBM."""
    n_estimators: int = 100
    max_depth: int = 7
    learning_rate: float = 0.1
    num_leaves: int = 31
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_alpha: float = 0.0
    reg_lambda: float = 1.0


@dataclass(frozen=True)
class ModelEvaluation:
    """Evaluation metrics for a model.
    
    Attributes:
        model_name: Name of the model
        accuracy: Overall accuracy
        precision: Precision (macro average)
        recall: Recall (macro average)
        f1: F1 score (macro average)
        cv_accuracy_mean: Mean cross-validation accuracy
        cv_accuracy_std: Std dev of cross-validation accuracy
        cv_f1_mean: Mean cross-validation F1
        cv_f1_std: Std dev of cross-validation F1
        confusion_matrix: Confusion matrix
        class_report: Classification report dict
    """
    model_name: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    cv_accuracy_mean: float
    cv_accuracy_std: float
    cv_f1_mean: float
    cv_f1_std: float
    confusion_matrix: np.ndarray
    class_report: dict


class ModelTrainer:
    """Train and evaluate classification models."""
    
    def __init__(self, config: ModelConfig | None = None) -> None:
        """Initialize model trainer.
        
        Args:
            config: ModelConfig instance
        """
        self.config = config or ModelConfig()
        self.config.__post_init__()
        
        self.model = None
        self.scaler = None
        self.label_encoder = None
        self.feature_names = None
    
    def _create_model(self) -> object:
        """Create model instance based on config.
        
        Returns:
            Untrained model instance
        """
        if self.config.model_type == ModelType.LOGISTIC_REGRESSION:
            lr_config = LogisticRegressionConfig()
            return LogisticRegression(
                C=lr_config.C,
                max_iter=lr_config.max_iter,
                solver=lr_config.solver,
                penalty=lr_config.penalty,
                random_state=self.config.random_state,
                class_weight=self.config.class_weight,
            )
        
        elif self.config.model_type == ModelType.RANDOM_FOREST:
            rf_config = RandomForestConfig()
            return RandomForestClassifier(
                n_estimators=rf_config.n_estimators,
                max_depth=rf_config.max_depth,
                min_samples_split=rf_config.min_samples_split,
                min_samples_leaf=rf_config.min_samples_leaf,
                max_features=rf_config.max_features,
                n_jobs=rf_config.n_jobs,
                random_state=self.config.random_state,
                class_weight=self.config.class_weight,
            )
        
        elif self.config.model_type == ModelType.XGBOOST:
            if not XGBOOST_AVAILABLE:
                raise ImportError("xgboost not installed")
            
            xgb_config = XGBoostConfig()
            return xgb.XGBClassifier(
                n_estimators=xgb_config.n_estimators,
                max_depth=xgb_config.max_depth,
                learning_rate=xgb_config.learning_rate,
                subsample=xgb_config.subsample,
                colsample_bytree=xgb_config.colsample_bytree,
                reg_alpha=xgb_config.reg_alpha,
                reg_lambda=xgb_config.reg_lambda,
                random_state=self.config.random_state,
                eval_metric="mlogloss",
                use_label_encoder=False,
                verbosity=0,
            )
        
        elif self.config.model_type == ModelType.LIGHTGBM:
            if not LIGHTGBM_AVAILABLE:
                raise ImportError("lightgbm not installed")
            
            lgb_config = LightGBMConfig()
            return lgb.LGBMClassifier(
                n_estimators=lgb_config.n_estimators,
                max_depth=lgb_config.max_depth,
                learning_rate=lgb_config.learning_rate,
                num_leaves=lgb_config.num_leaves,
                subsample=lgb_config.subsample,
                colsample_bytree=lgb_config.colsample_bytree,
                reg_alpha=lgb_config.reg_alpha,
                reg_lambda=lgb_config.reg_lambda,
                random_state=self.config.random_state,
                verbose=-1,
            )
    
    def train(
        self,
        X_train: pd.DataFrame | np.ndarray,
        y_train: pd.Series | np.ndarray,
    ) -> ModelTrainer:
        """Train the model.
        
        Args:
            X_train: Training features
            y_train: Training targets
            
        Returns:
            Self for chaining
            
        Raises:
            ValueError: If data shapes don't match
        """
        if len(X_train) != len(y_train):
            raise ValueError("X_train and y_train must have same number of samples")
        
        # Store feature names
        if isinstance(X_train, pd.DataFrame):
            self.feature_names = X_train.columns.tolist()
            X_train = X_train.values
        else:
            self.feature_names = [f"feature_{i}" for i in range(X_train.shape[1])]
        
        # Convert y to numpy
        if isinstance(y_train, pd.Series):
            y_train = y_train.values
        
        # Scale features if configured
        if self.config.scale_features:
            self.scaler = StandardScaler()
            X_train = self.scaler.fit_transform(X_train)
        
        # Create and train model
        self.model = self._create_model()
        self.model.fit(X_train, y_train)
        
        return self
    
    def predict(self, X_test: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Make predictions on test data.
        
        Args:
            X_test: Test features
            
        Returns:
            Predicted class labels
            
        Raises:
            ValueError: If model not trained
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        if isinstance(X_test, pd.DataFrame):
            X_test = X_test.values
        
        if self.config.scale_features and self.scaler is not None:
            X_test = self.scaler.transform(X_test)
        
        return self.model.predict(X_test)
    
    def predict_proba(self, X_test: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Get prediction probabilities.
        
        Args:
            X_test: Test features
            
        Returns:
            Probability predictions
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        if isinstance(X_test, pd.DataFrame):
            X_test = X_test.values
        
        if self.config.scale_features and self.scaler is not None:
            X_test = self.scaler.transform(X_test)
        
        return self.model.predict_proba(X_test)
    
    def evaluate(
        self,
        X_test: pd.DataFrame | np.ndarray,
        y_test: pd.Series | np.ndarray,
    ) -> ModelEvaluation:
        """Evaluate model on test data.
        
        Args:
            X_test: Test features
            y_test: Test targets
            
        Returns:
            ModelEvaluation with metrics
        """
        y_pred = self.predict(X_test)
        
        # Convert y_test to numpy if needed
        if isinstance(y_test, pd.Series):
            y_test = y_test.values
        
        # Calculate metrics
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, average="macro", zero_division=0)
        recall = recall_score(y_test, y_pred, average="macro", zero_division=0)
        f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)
        conf_matrix = confusion_matrix(y_test, y_pred)
        class_rep = classification_report(y_test, y_pred, output_dict=True)
        
        # Cross-validation
        cv_results = self._cross_validate(X_test, y_test)
        
        return ModelEvaluation(
            model_name=self.config.model_type,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            cv_accuracy_mean=cv_results["accuracy_mean"],
            cv_accuracy_std=cv_results["accuracy_std"],
            cv_f1_mean=cv_results["f1_mean"],
            cv_f1_std=cv_results["f1_std"],
            confusion_matrix=conf_matrix,
            class_report=class_rep,
        )
    
    def _cross_validate(
        self,
        X: pd.DataFrame | np.ndarray,
        y: pd.Series | np.ndarray,
    ) -> dict:
        """Perform cross-validation.
        
        Args:
            X: Features
            y: Targets
            
        Returns:
            Dict with cv_accuracy_mean, cv_accuracy_std, cv_f1_mean, cv_f1_std
        """
        if isinstance(X, pd.DataFrame):
            X = X.values
        if isinstance(y, pd.Series):
            y = y.values
        
        cv_strategy = StratifiedKFold(n_splits=self.config.cv_folds, shuffle=True, 
                                     random_state=self.config.random_state)
        
        try:
            cv_results = cross_validate(
                self.model,
                X,
                y,
                cv=cv_strategy,
                scoring=["accuracy", "f1_macro"],
                n_jobs=1,  # Use single job to avoid pandas indexing issues
            )
        except (TypeError, ValueError):
            # Fallback if cross_validate fails
            return {
                "accuracy_mean": 0.0,
                "accuracy_std": 0.0,
                "f1_mean": 0.0,
                "f1_std": 0.0,
            }
        
        return {
            "accuracy_mean": cv_results["test_accuracy"].mean(),
            "accuracy_std": cv_results["test_accuracy"].std(),
            "f1_mean": cv_results["test_f1_macro"].mean(),
            "f1_std": cv_results["test_f1_macro"].std(),
        }
    
    def get_feature_importance(self, top_n: int = 20) -> pd.DataFrame:
        """Get feature importance from trained model.
        
        Args:
            top_n: Number of top features to return
            
        Returns:
            DataFrame with feature importance
        """
        if self.model is None:
            raise ValueError("Model not trained.")
        
        # Get feature importance based on model type
        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
        elif hasattr(self.model, "coef_"):
            # For logistic regression, use absolute coefficient values
            importances = np.abs(self.model.coef_[0])
        else:
            raise ValueError("Model doesn't support feature importance extraction")
        
        # Create DataFrame
        importance_df = pd.DataFrame({
            "feature": self.feature_names,
            "importance": importances,
        }).sort_values("importance", ascending=False)
        
        return importance_df.head(top_n)


class ModelComparator:
    """Compare multiple models."""
    
    def __init__(self, random_state: int = 42) -> None:
        """Initialize model comparator.
        
        Args:
            random_state: Random seed for reproducibility
        """
        self.random_state = random_state
        self.models: dict[str, ModelTrainer] = {}
        self.evaluations: dict[str, ModelEvaluation] = {}
    
    def train_baseline(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
    ) -> ModelEvaluation:
        """Train logistic regression baseline.
        
        Args:
            X_train: Training features
            y_train: Training targets
            
        Returns:
            Evaluation on training data
        """
        config = ModelConfig(model_type=ModelType.LOGISTIC_REGRESSION, 
                            random_state=self.random_state)
        trainer = ModelTrainer(config)
        trainer.train(X_train, y_train)
        
        self.models["baseline"] = trainer
        
        # Evaluate on same data (for baseline reference)
        return trainer.evaluate(X_train, y_train)
    
    def train_random_forest(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        n_estimators: int = 100,
    ) -> ModelEvaluation:
        """Train Random Forest.
        
        Args:
            X_train: Training features
            y_train: Training targets
            n_estimators: Number of trees
            
        Returns:
            Evaluation on training data
        """
        config = ModelConfig(model_type=ModelType.RANDOM_FOREST, 
                            random_state=self.random_state)
        trainer = ModelTrainer(config)
        
        # Custom hyperparameters
        rf_config = RandomForestConfig(n_estimators=n_estimators)
        trainer.train(X_train, y_train)
        
        # Update hyperparameters after creation
        if hasattr(trainer.model, 'n_estimators'):
            trainer.model.n_estimators = n_estimators
        
        self.models["random_forest"] = trainer
        return trainer.evaluate(X_train, y_train)
    
    def train_xgboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        n_estimators: int = 100,
    ) -> ModelEvaluation:
        """Train XGBoost.
        
        Args:
            X_train: Training features
            y_train: Training targets
            n_estimators: Number of boosting rounds
            
        Returns:
            Evaluation on training data
        """
        if not XGBOOST_AVAILABLE:
            raise ImportError("xgboost not installed")
        
        config = ModelConfig(model_type=ModelType.XGBOOST, 
                            random_state=self.random_state)
        trainer = ModelTrainer(config)
        trainer.train(X_train, y_train)
        
        self.models["xgboost"] = trainer
        return trainer.evaluate(X_train, y_train)
    
    def train_lightgbm(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        n_estimators: int = 100,
    ) -> ModelEvaluation:
        """Train LightGBM.
        
        Args:
            X_train: Training features
            y_train: Training targets
            n_estimators: Number of boosting rounds
            
        Returns:
            Evaluation on training data
        """
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("lightgbm not installed")
        
        config = ModelConfig(model_type=ModelType.LIGHTGBM, 
                            random_state=self.random_state)
        trainer = ModelTrainer(config)
        trainer.train(X_train, y_train)
        
        self.models["lightgbm"] = trainer
        return trainer.evaluate(X_train, y_train)
    
    def evaluate_all(
        self,
        X_test: pd.DataFrame,
        y_test: pd.Series,
    ) -> dict[str, ModelEvaluation]:
        """Evaluate all trained models on test data.
        
        Args:
            X_test: Test features
            y_test: Test targets
            
        Returns:
            Dict mapping model name to evaluation
        """
        self.evaluations = {}
        for name, trainer in self.models.items():
            self.evaluations[name] = trainer.evaluate(X_test, y_test)
        
        return self.evaluations
    
    def compare_models(self) -> pd.DataFrame:
        """Create comparison DataFrame.
        
        Returns:
            DataFrame with model metrics
        """
        if not self.evaluations:
            raise ValueError("No evaluations yet. Call evaluate_all() first.")
        
        comparison_data = []
        for name, eval_result in self.evaluations.items():
            comparison_data.append({
                "Model": name,
                "Accuracy": eval_result.accuracy,
                "Precision": eval_result.precision,
                "Recall": eval_result.recall,
                "F1": eval_result.f1,
                "CV Accuracy": f"{eval_result.cv_accuracy_mean:.4f} ± {eval_result.cv_accuracy_std:.4f}",
                "CV F1": f"{eval_result.cv_f1_mean:.4f} ± {eval_result.cv_f1_std:.4f}",
            })
        
        return pd.DataFrame(comparison_data)
    
    def get_best_model(self, metric: str = "f1") -> tuple[str, ModelTrainer]:
        """Get best performing model.
        
        Args:
            metric: Metric to use for selection (accuracy, precision, recall, f1)
            
        Returns:
            Tuple of (model_name, trainer)
        """
        if not self.evaluations:
            raise ValueError("No evaluations yet. Call evaluate_all() first.")
        
        if metric not in ("accuracy", "precision", "recall", "f1"):
            raise ValueError(f"metric must be one of: accuracy, precision, recall, f1")
        
        best_name = max(
            self.evaluations.keys(),
            key=lambda k: getattr(self.evaluations[k], metric),
        )
        
        return best_name, self.models[best_name]
    
    def get_evaluation_summary(self) -> str:
        """Get human-readable summary of all evaluations.
        
        Returns:
            Formatted string with results
        """
        if not self.evaluations:
            return "No evaluations yet."
        
        summary = "Model Comparison Results\n"
        summary += "=" * 80 + "\n\n"
        
        for name, eval_result in self.evaluations.items():
            summary += f"Model: {name.upper()}\n"
            summary += "-" * 80 + "\n"
            summary += f"  Accuracy:  {eval_result.accuracy:.4f}\n"
            summary += f"  Precision: {eval_result.precision:.4f}\n"
            summary += f"  Recall:    {eval_result.recall:.4f}\n"
            summary += f"  F1 Score:  {eval_result.f1:.4f}\n"
            summary += f"  CV Accuracy: {eval_result.cv_accuracy_mean:.4f} ± {eval_result.cv_accuracy_std:.4f}\n"
            summary += f"  CV F1:       {eval_result.cv_f1_mean:.4f} ± {eval_result.cv_f1_std:.4f}\n"
            summary += "\n"
        
        return summary


class HyperparameterTuner:
    """Tune hyperparameters for models."""
    
    def __init__(self, random_state: int = 42) -> None:
        """Initialize hyperparameter tuner.
        
        Args:
            random_state: Random seed
        """
        self.random_state = random_state
        self.best_params = {}
        self.best_score = None
    
    def tune_logistic_regression(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        cv_folds: int = 5,
    ) -> dict:
        """Tune Logistic Regression hyperparameters.
        
        Args:
            X_train: Training features
            y_train: Training targets
            cv_folds: Number of CV folds
            
        Returns:
            Best parameters
        """
        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_train)
        
        param_grid = {
            "C": [0.1, 1, 10],
        }
        
        grid_search = GridSearchCV(
            LogisticRegression(max_iter=1000, random_state=self.random_state, class_weight="balanced"),
            param_grid,
            cv=StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=self.random_state),
            scoring="f1_macro",
            n_jobs=-1,
        )
        
        grid_search.fit(X_scaled, y_train)
        
        self.best_params["logistic_regression"] = grid_search.best_params_
        self.best_score = grid_search.best_score_
        
        return grid_search.best_params_
    
    def tune_random_forest(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        cv_folds: int = 5,
    ) -> dict:
        """Tune Random Forest hyperparameters.
        
        Args:
            X_train: Training features
            y_train: Training targets
            cv_folds: Number of CV folds
            
        Returns:
            Best parameters
        """
        param_grid = {
            "n_estimators": [50, 100],
            "max_depth": [10, 20],
            "min_samples_split": [2, 5],
        }
        
        grid_search = GridSearchCV(
            RandomForestClassifier(random_state=self.random_state, class_weight="balanced", n_jobs=-1),
            param_grid,
            cv=StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=self.random_state),
            scoring="f1_macro",
            n_jobs=-1,
        )
        
        grid_search.fit(X_train, y_train)
        
        self.best_params["random_forest"] = grid_search.best_params_
        self.best_score = grid_search.best_score_
        
        return grid_search.best_params_
    
    def tune_xgboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        cv_folds: int = 5,
    ) -> dict:
        """Tune XGBoost hyperparameters.
        
        Args:
            X_train: Training features
            y_train: Training targets
            cv_folds: Number of CV folds
            
        Returns:
            Best parameters
        """
        if not XGBOOST_AVAILABLE:
            raise ImportError("xgboost not installed")
        
        param_grid = {
            "n_estimators": [50, 100],
            "max_depth": [5, 7],
            "learning_rate": [0.1, 0.3],
        }
        
        grid_search = GridSearchCV(
            xgb.XGBClassifier(random_state=self.random_state, eval_metric="mlogloss", 
                            verbosity=0, use_label_encoder=False),
            param_grid,
            cv=StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=self.random_state),
            scoring="f1_macro",
            n_jobs=-1,
        )
        
        grid_search.fit(X_train, y_train)
        
        self.best_params["xgboost"] = grid_search.best_params_
        self.best_score = grid_search.best_score_
        
        return grid_search.best_params_
    
    def tune_lightgbm(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        cv_folds: int = 5,
    ) -> dict:
        """Tune LightGBM hyperparameters.
        
        Args:
            X_train: Training features
            y_train: Training targets
            cv_folds: Number of CV folds
            
        Returns:
            Best parameters
        """
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("lightgbm not installed")
        
        param_grid = {
            "n_estimators": [50, 100],
            "max_depth": [5, 7],
            "learning_rate": [0.1, 0.3],
            "num_leaves": [20, 30],
        }
        
        grid_search = GridSearchCV(
            lgb.LGBMClassifier(random_state=self.random_state, verbose=-1),
            param_grid,
            cv=StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=self.random_state),
            scoring="f1_macro",
            n_jobs=-1,
        )
        
        grid_search.fit(X_train, y_train)
        
        self.best_params["lightgbm"] = grid_search.best_params_
        self.best_score = grid_search.best_score_
        
        return grid_search.best_params_
