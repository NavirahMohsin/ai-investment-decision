"""Model serving infrastructure for live predictions.

Handles loading, caching, and serving trained ML models for real-time inference.

Features:
- Model loading from disk/memory
- Model caching to reduce I/O
- Batch and single prediction support
- Feature preprocessing
- Prediction confidence and metadata
- Model versioning and tracking
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import pickle
import logging

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class ModelStatus(str, Enum):
    """Model lifecycle status."""
    TRAINING = "training"
    READY = "ready"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class ModelMetadata:
    """Metadata about a trained model.
    
    Attributes:
        model_id: Unique identifier
        model_type: Type of model (logistic_regression, random_forest, xgboost, lightgbm)
        version: Version number
        status: Current status (training, ready, deprecated, archived)
        created_at: When the model was trained
        updated_at: Last update timestamp
        accuracy: Training accuracy score
        f1_score: Training F1 score
        roc_auc: ROC AUC score if applicable
        feature_names: List of expected features
        feature_count: Number of features
        classes: Target classes for classification
        hyperparameters: Model hyperparameters used
        training_data_size: Number of samples trained on
        description: Human-readable description
    """
    model_id: str
    model_type: str
    version: str
    status: ModelStatus = ModelStatus.READY
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    accuracy: Optional[float] = None
    f1_score: Optional[float] = None
    roc_auc: Optional[float] = None
    
    feature_names: list[str] = field(default_factory=list)
    feature_count: int = 0
    classes: list[str] = field(default_factory=list)
    
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    training_data_size: int = 0
    description: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "model_id": self.model_id,
            "model_type": self.model_type,
            "version": self.version,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "accuracy": self.accuracy,
            "f1_score": self.f1_score,
            "roc_auc": self.roc_auc,
            "feature_names": self.feature_names,
            "feature_count": self.feature_count,
            "classes": self.classes,
            "hyperparameters": self.hyperparameters,
            "training_data_size": self.training_data_size,
            "description": self.description,
        }


@dataclass
@dataclass
class PredictionResult:
    """Result of a single prediction.
    
    Attributes:
        predicted_class: The predicted class
        class_probabilities: Probability for each class
        confidence: Maximum probability (confidence in prediction)
        prediction_id: Unique identifier for this prediction
        model_id: Which model generated this
        timestamp: When prediction was made
        features_used: Feature values used for prediction
    """
    predicted_class: str
    class_probabilities: dict[str, float]
    confidence: float
    prediction_id: str
    model_id: str
    timestamp: datetime
    features_used: Optional[dict[str, float]] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "predicted_class": self.predicted_class,
            "class_probabilities": self.class_probabilities,
            "confidence": self.confidence,
            "prediction_id": self.prediction_id,
            "model_id": self.model_id,
            "timestamp": self.timestamp.isoformat(),
            "features_used": self.features_used,
        }


class ModelServer:
    """Manages model loading, caching, and inference."""
    
    def __init__(self, model_dir: Path | str | None = None, cache_size: int = 10):
        """Initialize model server.
        
        Args:
            model_dir: Directory where trained models are stored
            cache_size: Maximum number of models to keep in memory
        """
        self.model_dir = Path(model_dir) if model_dir else Path("models")
        self.cache_size = cache_size
        self.model_cache: dict[str, tuple[Any, ModelMetadata]] = {}
        self.scaler_cache: dict[str, StandardScaler] = {}
        self.prediction_counter: int = 0
    
    def save_model(
        self,
        model: Any,
        model_metadata: ModelMetadata,
        scaler: Optional[StandardScaler] = None,
    ) -> str:
        """Save trained model to disk.
        
        Args:
            model: Trained sklearn/xgboost/lightgbm model
            model_metadata: Metadata about the model
            scaler: Optional feature scaler
            
        Returns:
            Path to saved model
        """
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        model_path = self.model_dir / f"{model_metadata.model_id}_{model_metadata.version}.pkl"
        metadata_path = self.model_dir / f"{model_metadata.model_id}_{model_metadata.version}_metadata.pkl"
        
        try:
            with open(model_path, "wb") as f:
                pickle.dump(model, f)
            
            with open(metadata_path, "wb") as f:
                pickle.dump(model_metadata, f)
            
            if scaler:
                scaler_path = self.model_dir / f"{model_metadata.model_id}_{model_metadata.version}_scaler.pkl"
                with open(scaler_path, "wb") as f:
                    pickle.dump(scaler, f)
            
            logger.info(f"Saved model {model_metadata.model_id} v{model_metadata.version}")
            return str(model_path)
        
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
            raise
    
    def load_model(
        self,
        model_id: str,
        version: str,
    ) -> tuple[Any, ModelMetadata, Optional[StandardScaler]]:
        """Load model from disk or cache.
        
        Special handling: if model_id is "stock_prediction_xgboost_all" and version is "latest",
        tries to load "best_model" first (production best model), then falls back to latest version.
        
        Args:
            model_id: Model identifier
            version: Model version ("latest" or specific version)
            
        Returns:
            Tuple of (model, metadata, scaler)
            
        Raises:
            FileNotFoundError: If model not found
        """
        # Try best_model first if looking for latest xgboost
        if model_id == "stock_prediction_xgboost_all" and version == "latest":
            best_model_path = self.model_dir / "best_model.pkl"
            if best_model_path.exists():
                logger.info("Loading best_model (production model)")
                try:
                    with open(best_model_path, "rb") as f:
                        model = pickle.load(f)
                    
                    best_metadata_path = self.model_dir / "best_model_metadata.pkl"
                    with open(best_metadata_path, "rb") as f:
                        metadata = pickle.load(f)
                    
                    scaler = None
                    best_scaler_path = self.model_dir / "best_model_scaler.pkl"
                    if best_scaler_path.exists():
                        with open(best_scaler_path, "rb") as f:
                            scaler = pickle.load(f)
                    
                    return model, metadata, scaler
                except Exception as e:
                    logger.warning(f"Failed to load best_model, falling back to latest: {e}")
        
        cache_key = f"{model_id}_{version}"
        
        # Check cache first
        if cache_key in self.model_cache:
            logger.debug(f"Loading model {cache_key} from cache")
            model, metadata = self.model_cache[cache_key]
            scaler = self.scaler_cache.get(cache_key)
            return model, metadata, scaler
        
        # Load from disk
        model_path = self.model_dir / f"{cache_key}.pkl"
        metadata_path = self.model_dir / f"{cache_key}_metadata.pkl"
        scaler_path = self.model_dir / f"{cache_key}_scaler.pkl"
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        try:
            with open(model_path, "rb") as f:
                model = pickle.load(f)
            
            with open(metadata_path, "rb") as f:
                metadata = pickle.load(f)
            
            scaler = None
            if scaler_path.exists():
                with open(scaler_path, "rb") as f:
                    scaler = pickle.load(f)
            
            # Cache the model
            if len(self.model_cache) >= self.cache_size:
                # Remove oldest entry (simple FIFO)
                oldest_key = next(iter(self.model_cache))
                del self.model_cache[oldest_key]
                if oldest_key in self.scaler_cache:
                    del self.scaler_cache[oldest_key]
            
            self.model_cache[cache_key] = (model, metadata)
            if scaler:
                self.scaler_cache[cache_key] = scaler
            
            logger.info(f"Loaded model {cache_key} from disk")
            return model, metadata, scaler
        
        except Exception as e:
            logger.error(f"Failed to load model {cache_key}: {e}")
            raise
    
    def predict(
        self,
        model_id: str,
        version: str,
        features: np.ndarray | pd.DataFrame,
    ) -> PredictionResult | list[PredictionResult]:
        """Generate predictions.
        
        Args:
            model_id: Model identifier
            version: Model version
            features: Feature array (1D for single sample, 2D for batch)
            
        Returns:
            PredictionResult for single sample or list for batch
        """
        model, metadata, scaler = self.load_model(model_id, version)
        
        # Handle DataFrame input
        if isinstance(features, pd.DataFrame):
            features = features.values
        
        # Ensure 2D array
        is_single = features.ndim == 1
        if is_single:
            features = features.reshape(1, -1)
        
        # Apply scaling if available
        if scaler:
            features = scaler.transform(features)
        
        # Get predictions
        try:
            predictions = model.predict(features)
            
            # Get probabilities
            if hasattr(model, "predict_proba"):
                probabilities = model.predict_proba(features)
            else:
                # For models without predict_proba, create binary probabilities
                probabilities = np.column_stack([
                    1 - predictions,
                    predictions
                ])
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise
        
        # Create results
        results = []
        for i, (pred, probs) in enumerate(zip(predictions, probabilities)):
            pred_class = metadata.classes[pred] if metadata.classes else str(pred)
            class_probs = {
                cls: float(prob)
                for cls, prob in zip(
                    metadata.classes or [str(j) for j in range(len(probs))],
                    probs
                )
            }
            confidence = float(np.max(probs))
            
            self.prediction_counter += 1
            result = PredictionResult(
                predicted_class=pred_class,
                class_probabilities=class_probs,
                confidence=confidence,
                prediction_id=f"pred_{self.prediction_counter}",
                model_id=model_id,
                timestamp=datetime.now(timezone.utc),
            )
            results.append(result)
        
        return results[0] if is_single else results
    
    def list_models(self) -> list[dict[str, Any]]:
        """List all available models.
        
        Returns:
            List of model metadata dictionaries
        """
        models = []
        if not self.model_dir.exists():
            return models
        
        for metadata_path in self.model_dir.glob("*_metadata.pkl"):
            try:
                with open(metadata_path, "rb") as f:
                    metadata = pickle.load(f)
                models.append(metadata.to_dict())
            except Exception as e:
                logger.warning(f"Failed to load metadata from {metadata_path}: {e}")
        
        return models
    
    def get_model_info(self, model_id: str, version: str) -> dict[str, Any]:
        """Get metadata for a specific model.
        
        Args:
            model_id: Model identifier
            version: Model version
            
        Returns:
            Model metadata as dictionary
        """
        _, metadata, _ = self.load_model(model_id, version)
        return metadata.to_dict()
    
    def deprecate_model(self, model_id: str, version: str) -> None:
        """Mark a model as deprecated.
        
        Args:
            model_id: Model identifier
            version: Model version
        """
        model, metadata, scaler = self.load_model(model_id, version)
        metadata.status = ModelStatus.DEPRECATED
        metadata.updated_at = datetime.now(timezone.utc)
        self.save_model(model, metadata, scaler)
        logger.info(f"Deprecated model {model_id} v{version}")


class PredictionCache:
    """Cache predictions to avoid redundant inference.
    
    Useful for batch predictions on the same feature set.
    """
    
    def __init__(self, max_size: int = 1000):
        """Initialize cache.
        
        Args:
            max_size: Maximum number of cached predictions
        """
        self.cache: dict[str, PredictionResult] = {}
        self.max_size = max_size
    
    def get_cache_key(self, features: np.ndarray, model_id: str) -> str:
        """Generate cache key from features and model.
        
        Args:
            features: Feature array
            model_id: Model identifier
            
        Returns:
            Cache key
        """
        feature_hash = hash(tuple(features.flatten()))
        return f"{model_id}_{feature_hash}"
    
    def get(self, key: str) -> Optional[PredictionResult]:
        """Retrieve cached prediction.
        
        Args:
            key: Cache key
            
        Returns:
            Cached result or None
        """
        return self.cache.get(key)
    
    def set(self, key: str, result: PredictionResult) -> None:
        """Cache prediction result.
        
        Args:
            key: Cache key
            result: Prediction result
        """
        if len(self.cache) >= self.max_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        self.cache[key] = result
    
    def clear(self) -> None:
        """Clear all cached predictions."""
        self.cache.clear()
