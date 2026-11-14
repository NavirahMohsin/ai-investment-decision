"""Machine learning pipeline module for ArthAI.

Provides prediction target generation, feature engineering, dataset creation,
and model training/evaluation for stock price prediction.
"""

from .prediction_targets import (
    PredictionObjective,
    PredictionTarget,
    TargetConfig,
    TargetGenerator,
    calculate_forward_returns,
)

from .feature_engineering import (
    FeatureConfig,
    FeatureEngineer,
    DatasetGenerator,
)

from .models import (
    ModelType,
    ModelConfig,
    ModelTrainer,
    ModelComparator,
    HyperparameterTuner,
    ModelEvaluation,
    LogisticRegressionConfig,
    RandomForestConfig,
    XGBoostConfig,
    LightGBMConfig,
)

from .evaluation import (
    EvaluationConfig,
    TemporalSplitter,
    ClassificationEvaluator,
    FinancialEvaluator,
    ModelEvaluator,
    ClassificationMetrics,
    FinancialMetrics,
    ModelEvaluationResult,
)

from .backtesting import (
    BacktestConfig,
    BacktestEngine,
    BenchmarkStrategies,
    BacktestComparator,
    Trade,
    BacktestResult,
)

from .model_server import (
    ModelServer,
    ModelMetadata,
    PredictionResult,
    PredictionCache,
    ModelStatus,
)

__all__ = [
    # Targets
    "TargetConfig",
    "TargetGenerator",
    "PredictionTarget",
    "PredictionObjective",
    "calculate_forward_returns",
    # Features
    "FeatureConfig",
    "FeatureEngineer",
    "DatasetGenerator",
    # Models
    "ModelType",
    "ModelConfig",
    "ModelTrainer",
    "ModelComparator",
    "HyperparameterTuner",
    "ModelEvaluation",
    "LogisticRegressionConfig",
    "RandomForestConfig",
    "XGBoostConfig",
    "LightGBMConfig",
    # Evaluation
    "EvaluationConfig",
    "TemporalSplitter",
    "ClassificationEvaluator",
    "FinancialEvaluator",
    "ModelEvaluator",
    "ClassificationMetrics",
    "FinancialMetrics",
    "ModelEvaluationResult",
    # Backtesting
    "BacktestConfig",
    "BacktestEngine",
    "BenchmarkStrategies",
    "BacktestComparator",
    "Trade",
    "BacktestResult",
    # Model Serving
    "ModelServer",
    "ModelMetadata",
    "PredictionResult",
    "PredictionCache",
    "ModelStatus",
]
