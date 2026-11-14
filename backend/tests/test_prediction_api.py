"""Tests for prediction API endpoints."""

import pytest
from fastapi.testclient import TestClient
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from app.main import app
from app.db.models import Base, Company, DailyMarketData
from app.db.session import get_db
from app.ml.model_server import ModelServer, ModelMetadata, ModelStatus


@pytest.fixture
def temp_model_dir() -> Path:
    """Create temporary model directory."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_model() -> RandomForestClassifier:
    """Create mock trained model."""
    X = np.random.rand(100, 28)
    y = np.random.randint(0, 3, 100)
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X, y)
    return model


@pytest.fixture
def model_server(temp_model_dir: Path, mock_model) -> ModelServer:
    """Create model server with sample model."""
    server = ModelServer(model_dir=temp_model_dir)
    metadata = ModelMetadata(
        model_id="test_model",
        model_type="random_forest",
        version="1.0",
        status=ModelStatus.READY,
        classes=["Positive", "Negative", "Neutral"],
        feature_count=28,
        accuracy=0.85,
        f1_score=0.82,
    )
    server.save_model(mock_model, metadata)
    return server


@pytest.fixture
def db_session():
    """Create in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    # Add sample company and data
    company = Company(
        name="Apple Inc.",
        symbol="AAPL",
        provider_symbol="AAPL",
        exchange="NASDAQ",
        sector="Technology",
        instrument_type="equity",
        is_active=True,
    )
    session.add(company)
    session.commit()
    
    # Add market data
    today = date.today()
    for i in range(500):
        trading_date = today - timedelta(days=500-i)
        row = DailyMarketData(
            company_id=company.id,
            trading_date=trading_date,
            open=150.0 + i * 0.1,
            high=152.0 + i * 0.1,
            low=149.0 + i * 0.1,
            close=151.0 + i * 0.1,
            adjusted_close=151.0 + i * 0.1,
            volume=1000000,
            provider="test",
        )
        session.add(row)
    session.commit()
    
    yield session
    session.close()


@pytest.fixture
def client(model_server: ModelServer, db_session: Session) -> TestClient:
    """Create test client with overridden dependencies."""
    def override_get_db():
        yield db_session
    
    def override_get_model_server():
        return model_server
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Override model server dependency
    from app.api.routes.predictions import get_model_server
    app.dependency_overrides[get_model_server] = override_get_model_server
    
    client = TestClient(app)
    yield client
    
    app.dependency_overrides.clear()


class TestPredictionHealthCheck:
    """Test health check endpoint."""
    
    def test_health_check_success(self, client: TestClient) -> None:
        """Test successful health check."""
        response = client.get("/api/v1/predictions/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["models_available"] == 1
        assert data["service_ready"] is True


class TestModelList:
    """Test model listing endpoints."""
    
    def test_list_models(self, client: TestClient) -> None:
        """Test listing available models."""
        response = client.get("/api/v1/predictions/models")
        
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert data["total_count"] >= 1
    
    def test_get_model_info(self, client: TestClient) -> None:
        """Test getting model metadata."""
        response = client.get(
            "/api/v1/predictions/models/test_model",
            params={"version": "1.0"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["model_id"] == "test_model"
        assert data["model_type"] == "random_forest"
    
    def test_get_nonexistent_model(self, client: TestClient) -> None:
        """Test getting nonexistent model."""
        response = client.get(
            "/api/v1/predictions/models/nonexistent",
            params={"version": "1.0"}
        )
        
        assert response.status_code == 404


class TestSinglePrediction:
    """Test single prediction endpoint."""
    
    def test_predict_single_stock(self, client: TestClient) -> None:
        """Test predicting for single stock."""
        request_data = {
            "symbol": "AAPL",
            "model_id": "test_model",
            "model_version": "1.0",
            "horizon_days": 1,
        }
        
        response = client.post(
            "/api/v1/predictions/predict",
            json=request_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert "predicted_class" in data
        assert "confidence" in data
        assert "probabilities" in data
    
    def test_predict_with_invalid_horizon(self, client: TestClient) -> None:
        """Test prediction with invalid horizon."""
        request_data = {
            "symbol": "AAPL",
            "model_id": "test_model",
            "model_version": "1.0",
            "horizon_days": 99,
        }
        
        response = client.post(
            "/api/v1/predictions/predict",
            json=request_data
        )
        
        assert response.status_code == 422
    
    def test_predict_nonexistent_symbol(self, client: TestClient) -> None:
        """Test prediction for nonexistent symbol."""
        request_data = {
            "symbol": "NONEXISTENT",
            "model_id": "test_model",
            "model_version": "1.0",
        }
        
        response = client.post(
            "/api/v1/predictions/predict",
            json=request_data
        )
        
        assert response.status_code == 422


class TestBatchPrediction:
    """Test batch prediction endpoint."""
    
    def test_predict_batch(self, client: TestClient) -> None:
        """Test batch predictions."""
        request_data = {
            "symbols": ["AAPL"],
            "model_id": "test_model",
            "model_version": "1.0",
            "horizon_days": 1,
        }
        
        response = client.post(
            "/api/v1/predictions/predict/batch",
            json=request_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data
        assert "summary" in data
        assert data["summary"]["total_predictions"] >= 0
    
    def test_predict_batch_empty(self, client: TestClient) -> None:
        """Test batch predictions with empty symbols."""
        request_data = {
            "symbols": [],
            "model_id": "test_model",
            "model_version": "1.0",
        }
        
        response = client.post(
            "/api/v1/predictions/predict/batch",
            json=request_data
        )
        
        assert response.status_code == 422
    
    def test_predict_batch_many_symbols(self, client: TestClient) -> None:
        """Test batch predictions with too many symbols."""
        request_data = {
            "symbols": [f"SYM{i}" for i in range(150)],
            "model_id": "test_model",
            "model_version": "1.0",
        }
        
        response = client.post(
            "/api/v1/predictions/predict/batch",
            json=request_data
        )
        
        assert response.status_code == 422


class TestPredictionResponse:
    """Test prediction response format."""
    
    def test_response_has_required_fields(self, client: TestClient) -> None:
        """Test response contains all required fields."""
        request_data = {
            "symbol": "AAPL",
            "model_id": "test_model",
            "model_version": "1.0",
            "horizon_days": 1,
        }
        
        response = client.post(
            "/api/v1/predictions/predict",
            json=request_data
        )
        
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "symbol",
            "predicted_class",
            "confidence",
            "probabilities",
            "horizon_days",
            "as_of_date",
            "model_id",
            "prediction_id",
            "timestamp",
        ]
        
        for field in required_fields:
            assert field in data
    
    def test_confidence_range(self, client: TestClient) -> None:
        """Test confidence is in valid range."""
        request_data = {
            "symbol": "AAPL",
            "model_id": "test_model",
            "model_version": "1.0",
        }
        
        response = client.post(
            "/api/v1/predictions/predict",
            json=request_data
        )
        
        data = response.json()
        assert 0 <= data["confidence"] <= 1
    
    def test_probabilities_sum_to_one(self, client: TestClient) -> None:
        """Test probabilities sum to approximately 1."""
        request_data = {
            "symbol": "AAPL",
            "model_id": "test_model",
            "model_version": "1.0",
        }
        
        response = client.post(
            "/api/v1/predictions/predict",
            json=request_data
        )
        
        data = response.json()
        prob_sum = sum(data["probabilities"].values())
        assert abs(prob_sum - 1.0) < 0.01
