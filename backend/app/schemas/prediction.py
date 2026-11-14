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
