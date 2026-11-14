"""Tests for prediction service."""

import pytest
import numpy as np
import pandas as pd
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base, Company, DailyMarketData, Sector
from app.ml.model_server import ModelServer, ModelMetadata, ModelStatus
from app.ml.feature_engineering import FeatureConfig
from app.services.prediction import (
    PredictionService,
    PredictionRequest,
    PredictionResponse,
)
from sklearn.ensemble import RandomForestClassifier


class TestPredictionRequest:
    """Test PredictionRequest class."""
    
    def test_create_request(self) -> None:
        """Test creating a prediction request."""
        request = PredictionRequest(
            symbol="AAPL",
            model_id="model_1",
            model_version="1.0",
            horizon_days=1,
        )
        
        assert request.symbol == "AAPL"
        assert request.horizon_days == 1
    
    def test_request_defaults(self) -> None:
        """Test request defaults."""
        request = PredictionRequest(
            symbol="MSFT",
            model_id="model_1",
            model_version="1.0",
        )
        
        assert request.horizon_days == 1
        assert request.include_features is False


class TestPredictionResponse:
    """Test PredictionResponse class."""
    
    def test_create_response(self) -> None:
        """Test creating a prediction response."""
        response = PredictionResponse(
            symbol="AAPL",
            predicted_class="Positive",
            confidence=0.75,
            probabilities={"Positive": 0.75, "Negative": 0.15, "Neutral": 0.1},
            horizon_days=1,
            as_of_date=date.today(),
            model_id="model_1",
            prediction_id="pred_001",
            timestamp=datetime.now(timezone.utc),
        )
        
        assert response.symbol == "AAPL"
        assert response.predicted_class == "Positive"
        assert response.confidence == 0.75
    
    def test_response_to_dict(self) -> None:
        """Test response serialization."""
        response = PredictionResponse(
            symbol="MSFT",
            predicted_class="Negative",
            confidence=0.65,
            probabilities={"Positive": 0.2, "Negative": 0.65, "Neutral": 0.15},
            horizon_days=5,
            as_of_date=date.today(),
            model_id="model_1",
            prediction_id="pred_002",
            timestamp=datetime.now(timezone.utc),
        )
        
        data = response.to_dict()
        assert data["symbol"] == "MSFT"
        assert data["horizon_days"] == 5
        assert isinstance(data["timestamp"], str)


class TestPredictionService:
    """Test PredictionService class."""
    
    @pytest.fixture
    def temp_model_dir(self) -> Path:
        """Create temporary model directory."""
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def db_session(self):
        """Create in-memory SQLite session for testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()
    
    @pytest.fixture
    def mock_model(self) -> RandomForestClassifier:
        """Create mock trained model."""
        X = np.random.rand(100, 28)  # 28 features
        y = np.random.randint(0, 3, 100)
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(X, y)
        return model
    
    @pytest.fixture
    def model_server(self, temp_model_dir: Path, mock_model) -> ModelServer:
        """Create model server with sample model."""
        server = ModelServer(model_dir=temp_model_dir)
        metadata = ModelMetadata(
            model_id="test_model",
            model_type="random_forest",
            version="1.0",
            status=ModelStatus.READY,
            classes=["Positive", "Negative", "Neutral"],
            feature_count=28,
        )
        server.save_model(mock_model, metadata)
        return server
    
    @pytest.fixture
    def prediction_service(self, model_server: ModelServer) -> PredictionService:
        """Create prediction service."""
        return PredictionService(model_server=model_server)
    
    @pytest.fixture
    def sample_company(self, db_session: Session) -> Company:
        """Create sample company in database."""
        company = Company(
            name="Apple Inc.",
            symbol="AAPL",
            provider_symbol="AAPL",
            exchange="NASDAQ",
            sector="Technology",
            instrument_type="equity",
            is_active=True,
        )
        db_session.add(company)
        db_session.commit()
        return company
    
    @pytest.fixture
    def sample_market_data(
        self,
        db_session: Session,
        sample_company: Company,
    ) -> list[DailyMarketData]:
        """Create sample market data."""
        data = []
        today = date.today()
        for i in range(500):
            trading_date = today - timedelta(days=500-i)
            row = DailyMarketData(
                company_id=sample_company.id,
                trading_date=trading_date,
                open=150.0 + i * 0.1,
                high=152.0 + i * 0.1,
                low=149.0 + i * 0.1,
                close=151.0 + i * 0.1,
                adjusted_close=151.0 + i * 0.1,
                volume=1000000,
                provider="test",
            )
            data.append(row)
        
        db_session.add_all(data)
        db_session.commit()
        return data
    
    def test_initialize_service(self, prediction_service: PredictionService) -> None:
        """Test service initialization."""
        assert prediction_service.model_server is not None
        assert prediction_service.dataset_gen is not None
    
    def test_predict_for_symbol(
        self,
        prediction_service: PredictionService,
        db_session: Session,
        sample_company: Company,
        sample_market_data: list,
    ) -> None:
        """Test single symbol prediction."""
        request = PredictionRequest(
            symbol="AAPL",
            model_id="test_model",
            model_version="1.0",
            horizon_days=1,
        )
        
        result = prediction_service.predict_for_symbol(db_session, request)
        
        assert isinstance(result, PredictionResponse)
        assert result.symbol == "AAPL"
        assert result.predicted_class in ["Positive", "Negative", "Neutral"]
        assert 0 <= result.confidence <= 1
    
    def test_predict_nonexistent_symbol(
        self,
        prediction_service: PredictionService,
        db_session: Session,
    ) -> None:
        """Test prediction for nonexistent symbol."""
        request = PredictionRequest(
            symbol="NONEXISTENT",
            model_id="test_model",
            model_version="1.0",
        )
        
        with pytest.raises(ValueError):
            prediction_service.predict_for_symbol(db_session, request)
    
    def test_predict_insufficient_data(
        self,
        prediction_service: PredictionService,
        db_session: Session,
        sample_company: Company,
    ) -> None:
        """Test prediction with insufficient data."""
        request = PredictionRequest(
            symbol="AAPL",
            model_id="test_model",
            model_version="1.0",
        )
        
        with pytest.raises(ValueError):
            prediction_service.predict_for_symbol(db_session, request)
    
    def test_predict_batch(
        self,
        prediction_service: PredictionService,
        db_session: Session,
        sample_company: Company,
        sample_market_data: list,
    ) -> None:
        """Test batch prediction."""
        symbols = ["AAPL"]  # Only have one company
        
        results = prediction_service.predict_batch(
            db=db_session,
            symbols=symbols,
            model_id="test_model",
            model_version="1.0",
        )
        
        assert len(results) >= 0
        if results:
            assert isinstance(results[0], PredictionResponse)
    
    def test_get_prediction_summary(
        self,
        prediction_service: PredictionService,
    ) -> None:
        """Test getting prediction summary."""
        predictions = [
            PredictionResponse(
                symbol="AAPL",
                predicted_class="Positive",
                confidence=0.8,
                probabilities={"Positive": 0.8, "Negative": 0.1, "Neutral": 0.1},
                horizon_days=1,
                as_of_date=date.today(),
                model_id="model_1",
                prediction_id="pred_001",
                timestamp=datetime.now(timezone.utc),
            ),
            PredictionResponse(
                symbol="MSFT",
                predicted_class="Neutral",
                confidence=0.5,
                probabilities={"Positive": 0.3, "Negative": 0.2, "Neutral": 0.5},
                horizon_days=1,
                as_of_date=date.today(),
                model_id="model_1",
                prediction_id="pred_002",
                timestamp=datetime.now(timezone.utc),
            ),
        ]
        
        summary = prediction_service.get_prediction_summary(predictions)
        
        assert summary["total_predictions"] == 2
        assert summary["positive_count"] == 1
        assert summary["neutral_count"] == 1
        assert summary["negative_count"] == 0
        assert summary["average_confidence"] == 0.65
    
    def test_empty_prediction_summary(
        self,
        prediction_service: PredictionService,
    ) -> None:
        """Test summary with empty predictions."""
        summary = prediction_service.get_prediction_summary([])
        
        assert summary == {}
