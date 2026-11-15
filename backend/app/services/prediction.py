"""Prediction service for live stock price predictions.

Orchestrates the full prediction pipeline:
1. Fetch latest market data
2. Generate features
3. Make predictions
4. Store results

Features:
- Real-time predictions for single or multiple stocks
- Batch prediction support
- Feature preprocessing
- Result caching
- Prediction history tracking
- Error handling and validation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date, timezone, timedelta
from typing import Optional, Any
import logging
import uuid

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from app.db.models import Company, DailyMarketData
from app.ml.feature_engineering import FeatureConfig, DatasetGenerator
from app.ml.model_server import ModelServer, PredictionResult
from app.services.indicators import IndicatorParameters, calculate_indicators

logger = logging.getLogger(__name__)


@dataclass
class PredictionRequest:
    """Request for predictions.
    
    Attributes:
        symbol: Stock symbol
        model_id: Model to use
        model_version: Model version
        horizon_days: Prediction horizon (1, 5, or 20)
        include_features: Whether to include feature values in response
    """
    symbol: str
    model_id: str
    model_version: str
    horizon_days: int = 1
    include_features: bool = False


@dataclass
class PredictionResponse:
    """Response with prediction details.
    
    Attributes:
        symbol: Stock symbol
        predicted_class: Prediction (Positive, Negative, Neutral)
        confidence: Confidence (0-1)
        probabilities: Class probabilities
        horizon_days: Prediction horizon
        as_of_date: Latest market data date used
        model_id: Model used
        prediction_id: Unique prediction ID
        timestamp: Prediction timestamp
        features: Optional feature values
    """
    symbol: str
    predicted_class: str
    confidence: float
    probabilities: dict[str, float]
    horizon_days: int
    as_of_date: date
    model_id: str
    prediction_id: str
    timestamp: datetime
    features: Optional[dict[str, float]] = None
    current_price: Optional[float] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "predicted_class": self.predicted_class,
            "confidence": self.confidence,
            "probabilities": self.probabilities,
            "horizon_days": self.horizon_days,
            "as_of_date": self.as_of_date.isoformat(),
            "model_id": self.model_id,
            "prediction_id": self.prediction_id,
            "timestamp": self.timestamp.isoformat(),
            "current_price": self.current_price,
            "features": self.features,
        }


class PredictionService:
    """Orchestrates predictions from data to results."""
    
    def __init__(
        self,
        model_server: ModelServer,
        feature_config: FeatureConfig | None = None,
        indicator_params: IndicatorParameters | None = None,
    ):
        """Initialize prediction service.
        
        Args:
            model_server: ModelServer instance
            feature_config: Feature engineering configuration
            indicator_params: Indicator calculation parameters
        """
        self.model_server = model_server
        self.feature_config = feature_config or FeatureConfig()
        self.indicator_params = indicator_params or IndicatorParameters()
        self.dataset_gen = DatasetGenerator(self.feature_config, self.indicator_params)
    
    def predict_for_symbol(
        self,
        db: Session,
        request: PredictionRequest,
    ) -> PredictionResponse:
        """Generate prediction for a single stock.
        
        Args:
            db: Database session
            request: Prediction request
            
        Returns:
            PredictionResponse with results
            
        Raises:
            ValueError: If data unavailable or invalid
        """
        # Get company
        company = db.query(Company).filter(
            Company.symbol == request.symbol
        ).first()
        
        if not company:
            raise ValueError(f"Company not found: {request.symbol}")
        
        # Fetch market data
        market_data = db.query(DailyMarketData).filter(
            DailyMarketData.company_id == company.id
        ).order_by(DailyMarketData.trading_date.desc()).limit(500).all()
        
        if not market_data:
            raise ValueError(f"No market data for {request.symbol}")
        
        # Reverse to chronological order
        market_data = list(reversed(market_data))
        
        # Convert to DataFrame - format expected by FeatureEngineer
        data = pd.DataFrame([
            {
                "trading_date": row.trading_date,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": row.volume,
            }
            for row in market_data
        ])
        
        # Generate features
        try:
            features_df = self.dataset_gen.generate_features(data)
        except Exception as e:
            logger.error(f"Feature generation failed for {request.symbol}: {e}")
            raise ValueError(f"Feature generation failed: {e}")
        
        # Get latest features (most recent row)
        latest_features = features_df.iloc[-1:].dropna()
        
        if latest_features.empty:
            raise ValueError(f"Insufficient data for predictions: {request.symbol}")
        
        # Get feature values and order as expected by model
        feature_values = latest_features.values
        
        # Make prediction
        try:
            result = self.model_server.predict(
                model_id=request.model_id,
                version=request.model_version,
                features=feature_values,
            )
        except Exception as e:
            logger.error(f"Prediction failed for {request.symbol}: {e}")
            raise ValueError(f"Prediction failed: {e}")
        
        # Get current price
        current_price = float(market_data[-1].close) if market_data else None
        
        # Prepare features dict if requested
        features_dict = None
        if request.include_features:
            feature_names = latest_features.columns.tolist()
            features_dict = dict(zip(feature_names, feature_values[0]))
        
        # Create response
        response = PredictionResponse(
            symbol=request.symbol,
            predicted_class=result.predicted_class,
            confidence=result.confidence,
            probabilities=result.class_probabilities,
            horizon_days=request.horizon_days,
            as_of_date=market_data[-1].trading_date if market_data else date.today(),
            model_id=request.model_id,
            prediction_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            features=features_dict,
            current_price=current_price,
        )
        
        logger.info(f"Prediction for {request.symbol}: {result.predicted_class} ({result.confidence:.2%})")
        
        return response
    
    def predict_for_watchlist(
        self,
        db: Session,
        watchlist_id: int,
        model_id: str,
        model_version: str,
        horizon_days: int = 1,
    ) -> list[PredictionResponse]:
        """Generate predictions for all stocks in a watchlist.
        
        Args:
            db: Database session
            watchlist_id: Watchlist ID
            model_id: Model to use
            model_version: Model version
            horizon_days: Prediction horizon
            
        Returns:
            List of PredictionResponse objects
        """
        from app.db.models import Watchlist, WatchlistItem
        
        watchlist = db.query(Watchlist).filter(
            Watchlist.id == watchlist_id
        ).first()
        
        if not watchlist:
            raise ValueError(f"Watchlist not found: {watchlist_id}")
        
        items = db.query(WatchlistItem).filter(
            WatchlistItem.watchlist_id == watchlist_id
        ).all()
        
        results = []
        for item in items:
            try:
                request = PredictionRequest(
                    symbol=item.company.symbol,
                    model_id=model_id,
                    model_version=model_version,
                    horizon_days=horizon_days,
                )
                result = self.predict_for_symbol(db, request)
                results.append(result)
            except Exception as e:
                logger.warning(f"Prediction failed for {item.company.symbol}: {e}")
        
        return results
    
    def predict_batch(
        self,
        db: Session,
        symbols: list[str],
        model_id: str,
        model_version: str,
        horizon_days: int = 1,
    ) -> list[PredictionResponse]:
        """Generate predictions for multiple symbols.
        
        Args:
            db: Database session
            symbols: List of stock symbols
            model_id: Model to use
            model_version: Model version
            horizon_days: Prediction horizon
            
        Returns:
            List of PredictionResponse objects
        """
        results = []
        for symbol in symbols:
            try:
                request = PredictionRequest(
                    symbol=symbol,
                    model_id=model_id,
                    model_version=model_version,
                    horizon_days=horizon_days,
                )
                result = self.predict_for_symbol(db, request)
                results.append(result)
            except Exception as e:
                logger.warning(f"Prediction failed for {symbol}: {e}")
        
        return results
    
    def get_prediction_summary(self, predictions: list[PredictionResponse]) -> dict[str, Any]:
        """Summarize predictions.
        
        Args:
            predictions: List of predictions
            
        Returns:
            Summary statistics
        """
        if not predictions:
            return {}
        
        classes = [p.predicted_class for p in predictions]
        confidences = [p.confidence for p in predictions]
        
        return {
            "total_predictions": len(predictions),
            "positive_count": classes.count("Positive"),
            "negative_count": classes.count("Negative"),
            "neutral_count": classes.count("Neutral"),
            "average_confidence": float(np.mean(confidences)),
            "min_confidence": float(np.min(confidences)),
            "max_confidence": float(np.max(confidences)),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
