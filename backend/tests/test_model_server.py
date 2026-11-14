"""Tests for model serving infrastructure."""

import pytest
import numpy as np
import pickle
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone

from sklearn.ensemble import RandomForestClassifier

from app.ml.model_server import (
    ModelServer,
    ModelMetadata,
    PredictionResult,
    PredictionCache,
    ModelStatus,
)


class TestModelMetadata:
    """Test ModelMetadata class."""
    
    def test_create_metadata(self) -> None:
        """Test metadata creation."""
        metadata = ModelMetadata(
            model_id="test_model",
            model_type="random_forest",
            version="1.0",
            status=ModelStatus.READY,
            accuracy=0.85,
            f1_score=0.82,
            classes=["Positive", "Negative", "Neutral"],
        )
        
        assert metadata.model_id == "test_model"
        assert metadata.model_type == "random_forest"
        assert metadata.status == ModelStatus.READY
        assert len(metadata.classes) == 3
    
    def test_metadata_to_dict(self) -> None:
        """Test metadata serialization."""
        metadata = ModelMetadata(
            model_id="test_model",
            model_type="xgboost",
            version="2.0",
            classes=["Positive", "Negative"],
        )
        
        data = metadata.to_dict()
        assert data["model_id"] == "test_model"
        assert data["status"] == "ready"
        assert isinstance(data["created_at"], str)


class TestPredictionResult:
    """Test PredictionResult class."""
    
    def test_create_result(self) -> None:
        """Test result creation."""
        result = PredictionResult(
            predicted_class="Positive",
            class_probabilities={"Positive": 0.7, "Negative": 0.2, "Neutral": 0.1},
            confidence=0.7,
            prediction_id="pred_001",
            model_id="model_1",
            timestamp=datetime.now(timezone.utc),
        )
        
        assert result.predicted_class == "Positive"
        assert result.confidence == 0.7
        assert result.class_probabilities["Positive"] == 0.7
    
    def test_result_to_dict(self) -> None:
        """Test result serialization."""
        result = PredictionResult(
            predicted_class="Negative",
            class_probabilities={"Positive": 0.3, "Negative": 0.6, "Neutral": 0.1},
            confidence=0.6,
            prediction_id="pred_002",
            model_id="model_1",
            timestamp=datetime.now(timezone.utc),
        )
        
        data = result.to_dict()
        assert data["predicted_class"] == "Negative"
        assert isinstance(data["timestamp"], str)


class TestModelServer:
    """Test ModelServer class."""
    
    @pytest.fixture
    def temp_model_dir(self) -> Path:
        """Create temporary directory for models."""
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def mock_model(self) -> RandomForestClassifier:
        """Create a mock trained model."""
        X = np.random.rand(100, 10)
        y = np.random.randint(0, 3, 100)
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(X, y)
        return model
    
    @pytest.fixture
    def model_metadata(self) -> ModelMetadata:
        """Create model metadata."""
        return ModelMetadata(
            model_id="test_model",
            model_type="random_forest",
            version="1.0",
            accuracy=0.85,
            f1_score=0.82,
            classes=["Positive", "Negative", "Neutral"],
            feature_count=10,
        )
    
    def test_initialize_server(self, temp_model_dir: Path) -> None:
        """Test server initialization."""
        server = ModelServer(model_dir=temp_model_dir)
        assert server.model_dir == temp_model_dir
        assert server.cache_size == 10
        assert len(server.model_cache) == 0
    
    def test_save_model(
        self,
        temp_model_dir: Path,
        mock_model,
        model_metadata: ModelMetadata,
    ) -> None:
        """Test saving a model."""
        server = ModelServer(model_dir=temp_model_dir)
        
        path = server.save_model(mock_model, model_metadata)
        
        assert Path(path).exists()
        metadata_path = temp_model_dir / f"{model_metadata.model_id}_{model_metadata.version}_metadata.pkl"
        assert metadata_path.exists()
    
    def test_load_model(
        self,
        temp_model_dir: Path,
        mock_model,
        model_metadata: ModelMetadata,
    ) -> None:
        """Test loading a model."""
        server = ModelServer(model_dir=temp_model_dir)
        
        # Save first
        server.save_model(mock_model, model_metadata)
        
        # Load
        loaded_model, loaded_metadata, scaler = server.load_model("test_model", "1.0")
        
        assert loaded_model is not None
        assert loaded_metadata.model_id == "test_model"
        assert scaler is None
    
    def test_predict_single_sample(
        self,
        temp_model_dir: Path,
        mock_model,
        model_metadata: ModelMetadata,
    ) -> None:
        """Test single sample prediction."""
        server = ModelServer(model_dir=temp_model_dir)
        server.save_model(mock_model, model_metadata)
        
        X = np.random.rand(10)
        result = server.predict("test_model", "1.0", X)
        
        assert isinstance(result, PredictionResult)
        assert result.predicted_class in model_metadata.classes
        assert 0 <= result.confidence <= 1
    
    def test_predict_batch(
        self,
        temp_model_dir: Path,
        mock_model,
        model_metadata: ModelMetadata,
    ) -> None:
        """Test batch prediction."""
        server = ModelServer(model_dir=temp_model_dir)
        server.save_model(mock_model, model_metadata)
        
        X = np.random.rand(5, 10)
        results = server.predict("test_model", "1.0", X)
        
        assert isinstance(results, list)
        assert len(results) == 5
        assert all(isinstance(r, PredictionResult) for r in results)
    
    def test_list_models(
        self,
        temp_model_dir: Path,
        mock_model,
        model_metadata: ModelMetadata,
    ) -> None:
        """Test listing models."""
        server = ModelServer(model_dir=temp_model_dir)
        server.save_model(mock_model, model_metadata)
        
        models = server.list_models()
        
        assert len(models) == 1
        assert models[0]["model_id"] == "test_model"
    
    def test_get_model_info(
        self,
        temp_model_dir: Path,
        mock_model,
        model_metadata: ModelMetadata,
    ) -> None:
        """Test getting model info."""
        server = ModelServer(model_dir=temp_model_dir)
        server.save_model(mock_model, model_metadata)
        
        info = server.get_model_info("test_model", "1.0")
        
        assert info["model_id"] == "test_model"
        assert info["accuracy"] == 0.85
    
    def test_deprecate_model(
        self,
        temp_model_dir: Path,
        mock_model,
        model_metadata: ModelMetadata,
    ) -> None:
        """Test deprecating a model."""
        server = ModelServer(model_dir=temp_model_dir)
        server.save_model(mock_model, model_metadata)
        
        server.deprecate_model("test_model", "1.0")
        
        info = server.get_model_info("test_model", "1.0")
        assert info["status"] == "deprecated"
    
    def test_model_not_found(self, temp_model_dir: Path) -> None:
        """Test error when model not found."""
        server = ModelServer(model_dir=temp_model_dir)
        
        with pytest.raises(FileNotFoundError):
            server.load_model("nonexistent", "1.0")


class TestPredictionCache:
    """Test PredictionCache class."""
    
    @pytest.fixture
    def cache(self) -> PredictionCache:
        """Create cache instance."""
        return PredictionCache(max_size=10)
    
    def test_initialize_cache(self, cache: PredictionCache) -> None:
        """Test cache initialization."""
        assert cache.max_size == 10
        assert len(cache.cache) == 0
    
    def test_set_and_get(self, cache: PredictionCache) -> None:
        """Test setting and getting cached results."""
        result = PredictionResult(
            predicted_class="Positive",
            class_probabilities={"Positive": 0.8, "Negative": 0.2},
            confidence=0.8,
            prediction_id="pred_001",
            model_id="model_1",
            timestamp=datetime.now(timezone.utc),
        )
        
        key = "test_key"
        cache.set(key, result)
        
        cached = cache.get(key)
        assert cached is not None
        assert cached.predicted_class == "Positive"
    
    def test_cache_key_generation(self, cache: PredictionCache) -> None:
        """Test cache key generation."""
        features = np.array([1.0, 2.0, 3.0])
        key1 = cache.get_cache_key(features, "model_1")
        key2 = cache.get_cache_key(features, "model_1")
        
        assert key1 == key2
    
    def test_cache_eviction(self, cache: PredictionCache) -> None:
        """Test cache eviction when full."""
        cache.max_size = 2
        
        for i in range(3):
            result = PredictionResult(
                predicted_class="Positive",
                class_probabilities={"Positive": 0.8},
                confidence=0.8,
                prediction_id=f"pred_{i:03d}",
                model_id="model_1",
                timestamp=datetime.now(timezone.utc),
            )
            cache.set(f"key_{i}", result)
        
        # Should only have 2 items
        assert len(cache.cache) == 2
    
    def test_clear_cache(self, cache: PredictionCache) -> None:
        """Test clearing cache."""
        result = PredictionResult(
            predicted_class="Positive",
            class_probabilities={"Positive": 0.8},
            confidence=0.8,
            prediction_id="pred_001",
            model_id="model_1",
            timestamp=datetime.now(timezone.utc),
        )
        
        cache.set("key_1", result)
        assert len(cache.cache) == 1
        
        cache.clear()
        assert len(cache.cache) == 0
