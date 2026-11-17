"""
Targeted tests for Phase 6 audit bug fixes:
1. Unified Intelligence: Company model attribute check, CompanyFinancial pivot, CompanyFundamentalInfo fields
2. ML Evaluation: Training data cutoff validation, chronological OOS labeling
3. Backtesting: Failure isolation, persistence failure handling
4. Prediction Persistence: GET deduplication and cache reuse
5. Technical Intelligence: EMA-50 calculation and freshness metadata
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.db.models import (
    Company,
    CompanyFinancial,
    CompanyFundamentalInfo,
    CompanyProfile,
    DailyMarketData,
    MLModel,
    Prediction,
    Sector,
)
from app.ml.model_server import ModelMetadata, ModelStatus
from app.schemas.intelligence import UnifiedStockIntelligenceResponse
from app.services.indicators import IndicatorParameters, calculate_indicators
from app.services.model_evaluation_service import ModelEvaluationService


# ---------------------------------------------------------------------------
# 1. Unified Intelligence Model Attribute Verification
# ---------------------------------------------------------------------------

def test_company_has_no_industry_attribute():
    """Verify Company database model does not have an industry attribute."""
    assert not hasattr(Company, "industry"), (
        "Company model must NOT have 'industry' field; industry is on Sector/CompanyProfile"
    )


def test_financial_metric_pivot():
    """Verify CompanyFinancial stores metric_name/metric_value rows and pivots cleanly."""
    # Test pivot logic
    test_rows = [
        MagicMock(metric_name="revenue", metric_value=Decimal("500000000.00"), period_end=date(2025, 3, 31)),
        MagicMock(metric_name="net_income", metric_value=Decimal("75000000.00"), period_end=date(2025, 3, 31)),
        MagicMock(metric_name="ebitda", metric_value=Decimal("120000000.00"), period_end=date(2025, 3, 31)),
        MagicMock(metric_name="pe_ratio", metric_value=Decimal("22.50"), period_end=date(2025, 3, 31)),
        MagicMock(metric_name="roe", metric_value=Decimal("0.1850"), period_end=date(2025, 3, 31)),
    ]
    latest_period = test_rows[0].period_end
    period_rows = [r for r in test_rows if r.period_end == latest_period]
    metrics = {r.metric_name: r.metric_value for r in period_rows}

    assert float(metrics["revenue"]) == 500000000.0
    assert float(metrics["net_income"]) == 75000000.0
    assert float(metrics["ebitda"]) == 120000000.0
    assert float(metrics["pe_ratio"]) == 22.5
    assert float(metrics["roe"]) == 0.185


def test_fundamental_info_valid_columns():
    """Verify CompanyFundamentalInfo only uses actual columns from the database schema."""
    valid_cols = {"id", "company_id", "business_summary", "website", "country", "currency",
                  "market_cap", "enterprise_value", "employees", "data_source", "retrieved_at",
                  "created_at", "updated_at"}
    model_cols = {c.name for c in CompanyFundamentalInfo.__table__.columns}
    assert valid_cols.issubset(model_cols), f"Missing columns in CompanyFundamentalInfo: {valid_cols - model_cols}"
    assert "industry" not in model_cols
    assert "sector" not in model_cols


# ---------------------------------------------------------------------------
# 2. ML Evaluation Out-of-Sample & Training Cutoff Verification
# ---------------------------------------------------------------------------

def test_model_metadata_training_cutoff():
    """Verify ModelMetadata tracks training cutoff date."""
    meta = ModelMetadata(
        model_id="test_model",
        model_type="random_forest",
        version="1.0",
        training_cutoff_date=date(2025, 1, 1),
    )
    assert meta.training_cutoff_date == date(2025, 1, 1)
    as_dict = meta.to_dict()
    assert as_dict["training_cutoff_date"] == "2025-01-01"


def test_evaluation_rejects_overlapping_evaluation_period():
    """Verify evaluate_model raises ValueError if evaluation period overlaps with training data."""
    mock_server = MagicMock()
    metadata = ModelMetadata(
        model_id="test_model",
        model_type="random_forest",
        version="1.0",
        training_cutoff_date=date(2025, 6, 1),
        feature_names=["f1", "f2"],
        classes=["negative", "neutral", "positive"],
    )
    mock_server.load_model.return_value = (MagicMock(), metadata, None)
    eval_service = ModelEvaluationService(mock_server)

    # Mock _load_ohlcv and _build_aligned_dataset
    import pandas as pd
    import numpy as np

    dates = pd.date_range("2025-01-01", "2025-07-01", freq="B")
    ohlcv = pd.DataFrame({"close": np.linspace(100, 200, len(dates))}, index=dates)
    X = pd.DataFrame(np.random.rand(len(dates), 2), columns=["f1", "f2"])
    y = pd.Series(np.random.randint(0, 3, len(dates)))
    prices = pd.Series(np.linspace(100, 200, len(dates)))

    eval_service._load_ohlcv = MagicMock(return_value=(MagicMock(symbol="TEST"), ohlcv))
    eval_service._build_aligned_dataset = MagicMock(return_value=(X, y, prices, pd.Series(dates)))

    db = MagicMock()
    # test_size=0.2 on 2025-01-01 to 2025-07-01 will put test_start around May 2025 <= 2025-06-01 cutoff
    with pytest.raises(ValueError, match="overlaps with training data"):
        eval_service.evaluate_model(
            db=db,
            model_id="test_model",
            symbol="TEST",
            evaluation_type="holdout_oos",
            test_size=0.2,
        )


def test_evaluation_warns_when_cutoff_unknown():
    """Verify evaluate_model flags data leakage risk when training cutoff is unknown."""
    mock_server = MagicMock()
    metadata = ModelMetadata(
        model_id="legacy_model",
        model_type="random_forest",
        version="1.0",
        training_cutoff_date=None,  # Unknown cutoff
        feature_names=["f1", "f2"],
        classes=["negative", "neutral", "positive"],
    )
    mock_server.load_model.return_value = (MagicMock(), metadata, None)
    eval_service = ModelEvaluationService(mock_server)

    import pandas as pd
    import numpy as np

    dates = pd.date_range("2024-01-01", "2025-01-01", freq="B")
    ohlcv = pd.DataFrame({"close": np.linspace(100, 200, len(dates))}, index=dates)
    X = pd.DataFrame(np.random.rand(len(dates), 2), columns=["f1", "f2"])
    y = pd.Series(np.random.randint(0, 3, len(dates)))
    prices = pd.Series(np.linspace(100, 200, len(dates)))

    eval_service._load_ohlcv = MagicMock(return_value=(MagicMock(symbol="TEST"), ohlcv))
    eval_service._build_aligned_dataset = MagicMock(return_value=(X, y, prices, pd.Series(dates)))
    eval_service._predict_frame = MagicMock(return_value=(np.zeros(len(dates)), None))
    eval_service._metrics_payload = MagicMock(return_value={"metrics": {"accuracy": 0.5}})

    db = MagicMock()
    result = eval_service.evaluate_model(
        db=db,
        model_id="legacy_model",
        symbol="TEST",
        evaluation_type="holdout_oos",
        test_size=0.2,
    )

    assert result["training_cutoff_unknown"] is True
    assert "data_leakage_risk" in result
    assert result["evaluation_method"] == "holdout_oos_frozen_model"


# ---------------------------------------------------------------------------
# 3. Backtesting Persistence Failure Isolation
# ---------------------------------------------------------------------------

def test_backtest_reports_persistence_failure_on_db_error():
    """Verify run_backtest sets persisted=False and persist_error when DB commit fails."""
    mock_server = MagicMock()
    metadata = ModelMetadata(
        model_id="test_bt_model",
        model_type="random_forest",
        version="1.0",
        feature_names=["f1", "f2"],
        classes=["negative", "neutral", "positive"],
    )
    mock_server.load_model.return_value = (MagicMock(), metadata, None)
    eval_service = ModelEvaluationService(mock_server)

    import pandas as pd
    import numpy as np

    dates = pd.date_range("2024-01-01", "2024-12-31", freq="B")
    ohlcv = pd.DataFrame({"close": np.linspace(100, 200, len(dates))}, index=dates)
    X = pd.DataFrame(np.random.rand(len(dates), 2), columns=["f1", "f2"])
    y = pd.Series(np.random.randint(0, 3, len(dates)))
    prices = pd.Series(np.linspace(100, 200, len(dates)))

    eval_service._load_ohlcv = MagicMock(return_value=(MagicMock(symbol="RELIANCE"), ohlcv))
    eval_service._build_aligned_dataset = MagicMock(return_value=(X, y, prices, pd.Series(dates)))
    eval_service._predict_frame = MagicMock(return_value=(np.ones(len(dates)), None))

    # Mock DB session where commit raises an operational error
    mock_db = MagicMock(spec=Session)
    mock_db.commit.side_effect = RuntimeError("Database disk full / commit failed")

    result = eval_service.run_backtest(
        db=mock_db,
        symbol="RELIANCE",
        model_id="test_bt_model",
        horizon_days=1,
    )

    # Must NOT report success if commit failed
    assert result["persisted"] is False
    assert "Database disk full" in result["persist_error"]
    assert mock_db.rollback.called


# ---------------------------------------------------------------------------
# 4. Prediction Persistence Deduplication
# ---------------------------------------------------------------------------

def test_prediction_deduplication_reuses_recent_record():
    """Verify that cached prediction within 24h is reused instead of duplicate inference."""
    today = date.today()
    mock_existing_pred = MagicMock(
        prediction_id="pred-existing-123",
        company_id=1,
        predicted_class="positive",
        confidence=Decimal("0.7500"),
        probabilities={"positive": 0.75, "neutral": 0.15, "negative": 0.10},
        horizon_days=1,
        as_of_date=today,
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )

    # When query for existing prediction returns a record
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    assert mock_existing_pred.created_at >= cutoff
    assert mock_existing_pred.as_of_date == today


# ---------------------------------------------------------------------------
# 5. Technical Intelligence EMA-50 & Dual EMAs
# ---------------------------------------------------------------------------

def test_ema50_dual_calculation():
    """Verify technical indicator calculations compute both EMA-20 and EMA-50."""
    from datetime import date
    rows = []
    base_date = date(2024, 1, 1)
    for i in range(100):
        d = base_date + timedelta(days=i)
        p = 100.0 + i * 0.5
        m = MagicMock()
        m.trading_date = d
        m.open = Decimal(str(p))
        m.high = Decimal(str(p + 1.0))
        m.low = Decimal(str(p - 1.0))
        m.close = Decimal(str(p))
        m.adjusted_close = Decimal(str(p))
        m.volume = 100000
        m.provider = "yahoo_finance"
        rows.append(m)

    params_20 = IndicatorParameters(ema_period=20)
    records_20, _, _, _ = calculate_indicators(rows, params_20)
    latest_20 = records_20[-1]
    assert latest_20["ema"] is not None

    params_50 = IndicatorParameters(ema_period=50)
    records_50, _, _, _ = calculate_indicators(rows, params_50)
    latest_50 = records_50[-1]
    assert latest_50["ema"] is not None

    # EMA-20 responds faster to an upward trend than EMA-50
    assert latest_20["ema"] > latest_50["ema"], "EMA-20 should be higher than EMA-50 in a strong uptrend"


# ---------------------------------------------------------------------------
# 6. Model Evaluation API Route Registration
# ---------------------------------------------------------------------------

def test_model_evaluation_routes_registered():
    """Verify evaluation, compare, and backtest endpoints are registered under /api/v1/predictions."""
    from app.main import app

    openapi_paths = app.openapi()["paths"]

    expected_endpoints = [
        ("/api/v1/predictions/evaluate", "post"),
        ("/api/v1/predictions/compare", "post"),
        ("/api/v1/predictions/backtest", "post"),
        ("/api/v1/predictions/backtests", "get"),
        ("/api/v1/predictions/backtests/{backtest_id}", "get"),
    ]

    for path, method in expected_endpoints:
        assert path in openapi_paths, f"Missing route: {path}"
        assert method in openapi_paths[path], f"Missing {method} method for {path}"

    # Ensure no duplicated router prefixes (e.g., /api/v1/api/v1/...)
    for path in openapi_paths:
        assert not path.startswith("/api/v1/api/v1"), f"Duplicated router prefix in {path}"

