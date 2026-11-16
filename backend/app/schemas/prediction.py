"""Pydantic schemas for prediction API endpoints."""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any

from pydantic import BaseModel, Field, field_validator


class PredictionRequestSchema(BaseModel):
    """Request for a single stock prediction."""
    symbol: str = Field(..., min_length=1, max_length=50, description="Stock symbol")
    model_id: str = Field(..., description="Model identifier")
    model_version: str = Field(default="latest", description="Model version")
    horizon_days: int = Field(default=1, description="Prediction horizon (1, 5, or 20)")
    include_features: bool = Field(default=False, description="Include feature values in response")
    
    @field_validator("horizon_days")
    @classmethod
    def validate_horizon(cls, v: int) -> int:
        """Ensure horizon is valid."""
        if v not in (1, 5, 20):
            raise ValueError("horizon_days must be 1, 5, or 20")
        return v


class BatchPredictionRequestSchema(BaseModel):
    """Request for batch predictions."""
    symbols: list[str] = Field(..., min_items=1, max_items=100, description="Stock symbols")
    model_id: str = Field(..., description="Model identifier")
    model_version: str = Field(default="latest", description="Model version")
    horizon_days: int = Field(default=1, description="Prediction horizon")
    
    @field_validator("horizon_days")
    @classmethod
    def validate_horizon(cls, v: int) -> int:
        if v not in (1, 5, 20):
            raise ValueError("horizon_days must be 1, 5, or 20")
        return v


class WatchlistPredictionRequestSchema(BaseModel):
    """Request for predictions on a watchlist."""
    watchlist_id: int = Field(..., description="Watchlist ID")
    model_id: str = Field(..., description="Model identifier")
    model_version: str = Field(default="latest", description="Model version")
    horizon_days: int = Field(default=1, description="Prediction horizon")


class PredictionResponseSchema(BaseModel):
    """Response with prediction details."""
    symbol: str
    predicted_class: str = Field(..., description="Positive, Negative, or Neutral")
    confidence: float = Field(..., ge=0, le=1, description="Confidence (0-1)")
    probabilities: dict[str, float] = Field(..., description="Class probabilities")
    horizon_days: int
    as_of_date: str = Field(..., description="Date of last market data")
    model_id: str
    prediction_id: str
    timestamp: str
    current_price: Optional[float] = None
    features: Optional[dict[str, float]] = None
    
    class Config:
        from_attributes = True


class ModelMetadataSchema(BaseModel):
    """Model metadata response."""
    model_id: str
    model_type: str
    version: str
    status: str
    created_at: str
    updated_at: str
    accuracy: Optional[float] = None
    f1_score: Optional[float] = None
    roc_auc: Optional[float] = None
    feature_count: int
    classes: list[str]
    description: Optional[str] = None
    
    class Config:
        from_attributes = True


class ModelListResponseSchema(BaseModel):
    """List of available models."""
    models: list[ModelMetadataSchema]
    total_count: int


class PredictionSummarySchema(BaseModel):
    """Summary statistics for multiple predictions."""
    total_predictions: int
    positive_count: int
    negative_count: int
    neutral_count: int
    average_confidence: float
    min_confidence: float
    max_confidence: float
    generated_at: str


class BatchPredictionResponseSchema(BaseModel):
    """Response for batch predictions."""
    predictions: list[PredictionResponseSchema]
    summary: PredictionSummarySchema


class HealthCheckResponseSchema(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    models_available: int = Field(..., description="Number of available models")
    latest_prediction_timestamp: Optional[str] = None
    service_ready: bool


class PredictionHistoryItemSchema(BaseModel):
    """Item in prediction history log."""
    id: int
    prediction_id: str
    company_id: int
    symbol: str
    model_id: Optional[Any] = None
    horizon_days: int
    predicted_class: str
    confidence: float
    probabilities: Optional[dict[str, float]] = None
    as_of_date: str
    current_price: Optional[float] = None
    prediction_date: str
    created_at: str


class PredictionHistoryResponseSchema(BaseModel):
    """Paginated prediction history response."""
    predictions: list[PredictionHistoryItemSchema]
    count: int
    total: int
    limit: int
    offset: int


class ModelEvaluationRequestSchema(BaseModel):
    """Request to evaluate a registered model out-of-sample."""
    model_id: str = Field(..., min_length=1, description="Registered model identifier")
    symbol: str = Field(..., min_length=1, max_length=50, description="Evaluation symbol")
    horizon_days: int = Field(default=1, description="Prediction horizon (1, 5, or 20)")
    version: str = Field(default="latest", description="Model version")
    evaluation_type: str = Field(
        default="holdout_oos",
        description="holdout_oos or walk_forward",
    )
    test_size: float = Field(default=0.2, ge=0.1, le=0.5, description="Holdout fraction")
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @field_validator("horizon_days")
    @classmethod
    def validate_eval_horizon(cls, v: int) -> int:
        if v not in (1, 5, 20):
            raise ValueError("horizon_days must be 1, 5, or 20")
        return v

    @field_validator("evaluation_type")
    @classmethod
    def validate_eval_type(cls, v: str) -> str:
        allowed = {"holdout_oos", "walk_forward"}
        if v not in allowed:
            raise ValueError(f"evaluation_type must be one of {sorted(allowed)}")
        return v


class ModelEvaluationResponseSchema(BaseModel):
    """Detailed model evaluation response."""
    model_id: str
    model_type: str
    version: str
    symbol: Optional[str] = None
    horizon_days: Optional[int] = None
    evaluation_type: str
    metrics: dict[str, Any]
    confusion_matrix: Optional[list[list[int]]] = None
    confusion_matrix_labels: Optional[list[str]] = None
    class_metrics: Optional[dict[str, Any]] = None
    financial_metrics: Optional[dict[str, Any]] = None
    validation_window: dict[str, Any]
    disclaimer: str


class ModelComparisonRequestSchema(BaseModel):
    """Request to compare multiple models on a shared evaluation set."""
    model_ids: list[str] = Field(..., min_length=2, max_length=8)
    symbol: str = Field(..., min_length=1, max_length=50)
    horizon_days: int = Field(default=1)
    version: str = Field(default="latest")
    test_size: float = Field(default=0.2, ge=0.1, le=0.5)

    @field_validator("horizon_days")
    @classmethod
    def validate_cmp_horizon(cls, v: int) -> int:
        if v not in (1, 5, 20):
            raise ValueError("horizon_days must be 1, 5, or 20")
        return v


class ModelComparisonResponseSchema(BaseModel):
    """Multi-model comparison response."""
    symbol: Optional[str] = None
    horizon_days: Optional[int] = None
    comparable_dataset: Optional[bool] = None
    models: list[dict[str, Any]]
    benchmark_model_id: Optional[str] = None
    comparison_table: list[dict[str, Any]]
    errors: Optional[list[dict[str, Any]]] = None
    disclaimer: str


class BacktestRequestSchema(BaseModel):
    """Request to execute trading strategy backtest."""
    symbol: str = Field(..., description="Stock symbol to backtest")
    model_id: Optional[str] = Field(default="latest", description="Model ID or strategy")
    horizon_days: int = Field(default=1, description="Prediction horizon (1, 5, or 20)")
    initial_capital: float = Field(default=100000.0, gt=0, description="Starting capital in INR")
    commission: float = Field(default=0.001, ge=0, le=0.05, description="Brokerage commission rate (0.001 = 0.1%)")
    slippage: float = Field(default=0.0005, ge=0, le=0.05, description="Execution slippage (0.0005 = 0.05%)")
    start_date: Optional[date] = Field(None, description="Backtest start date")
    end_date: Optional[date] = Field(None, description="Backtest end date")

    @field_validator("horizon_days")
    @classmethod
    def validate_backtest_horizon(cls, v: int) -> int:
        if v not in (1, 5, 20):
            raise ValueError("horizon_days must be 1, 5, or 20")
        return v

    @field_validator("symbol")
    @classmethod
    def validate_backtest_symbol(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("symbol is required")
        return cleaned


class BacktestTradeSchema(BaseModel):
    """Record of an individual executed backtest trade."""
    date: str
    direction: str
    price: float
    quantity: float
    value: float
    commission: float


class BacktestResponseSchema(BaseModel):
    """Complete result of a strategy backtest."""
    backtest_id: str
    symbol: str
    model_id: Optional[str] = None
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: Optional[float] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    num_trades: int
    equity_curve: list[dict[str, Any]]
    trades: list[BacktestTradeSchema]
    disclaimer: str


class BacktestListResponseSchema(BaseModel):
    """List of persisted backtest runs."""
    backtests: list[dict[str, Any]]
    total: int

