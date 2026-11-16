"""Prediction API routes for live stock predictions."""

from __future__ import annotations

from pathlib import Path
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ml.model_server import ModelServer
from app.services.prediction import PredictionService, PredictionRequest
from app.schemas.prediction import (
    PredictionRequestSchema,
    PredictionResponseSchema,
    BatchPredictionRequestSchema,
    BatchPredictionResponseSchema,
    WatchlistPredictionRequestSchema,
    ModelListResponseSchema,
    ModelMetadataSchema,
    HealthCheckResponseSchema,
    PredictionHistoryResponseSchema,
    ModelEvaluationRequestSchema,
    ModelEvaluationResponseSchema,
    ModelComparisonRequestSchema,
    ModelComparisonResponseSchema,
    BacktestRequestSchema,
    BacktestResponseSchema,
    BacktestListResponseSchema,
)
from app.services.model_evaluation_service import ModelEvaluationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])

# Initialize model server and prediction service
# In production, these should be initialized once and reused
_model_server: ModelServer | None = None
_prediction_service: PredictionService | None = None


def get_model_server() -> ModelServer:
    """Get or initialize model server."""
    global _model_server
    if _model_server is None:
        model_dir = Path("models")
        _model_server = ModelServer(model_dir=model_dir)
    return _model_server


def get_prediction_service(
    model_server: ModelServer = Depends(get_model_server),
) -> PredictionService:
    """Get or initialize prediction service."""
    global _prediction_service
    if _prediction_service is None:
        _prediction_service = PredictionService(model_server)
    return _prediction_service


@router.get("/health", response_model=HealthCheckResponseSchema)
async def health_check(
    model_server: ModelServer = Depends(get_model_server),
) -> dict:
    """Check prediction service health.
    
    Returns:
        Health status and available models
    """
    try:
        models = model_server.list_models()
        return {
            "status": "healthy",
            "models_available": len(models),
            "service_ready": True,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "models_available": 0,
            "service_ready": False,
        }


@router.get("/models", response_model=ModelListResponseSchema)
async def list_models(
    model_server: ModelServer = Depends(get_model_server),
) -> dict:
    """List all available models.
    
    Returns:
        List of model metadata
    """
    try:
        models = model_server.list_models()
        return {
            "models": models,
            "total_count": len(models),
        }
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail="Failed to list models")


@router.get("/models/{model_id}", response_model=ModelMetadataSchema)
async def get_model_info(
    model_id: str,
    version: str = Query(default="latest"),
    model_server: ModelServer = Depends(get_model_server),
) -> dict:
    """Get metadata for a specific model.
    
    Args:
        model_id: Model identifier
        version: Model version (default: latest)
        
    Returns:
        Model metadata
    """
    try:
        return model_server.get_model_info(model_id, version)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Model not found")
    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get model info")


@router.post("/predict", response_model=PredictionResponseSchema)
async def predict_single(
    request: PredictionRequestSchema,
    db: Session = Depends(get_db),
    prediction_service: PredictionService = Depends(get_prediction_service),
    model_server: ModelServer = Depends(get_model_server),
) -> dict:
    """Generate prediction for a single stock.
    
    Args:
        request: Prediction request
        db: Database session
        prediction_service: Prediction service
        model_server: Model server
        
    Returns:
        Prediction result
    """
    try:
        # If model_id not specified or is 'latest', use best model
        model_id = request.model_id
        if not model_id or model_id == 'latest':
            models = model_server.list_models()
            if not models:
                raise ValueError("No trained models available")
            # Select model with highest accuracy
            best_model = max(models, key=lambda m: m.get('accuracy', 0))
            model_id = best_model['model_id']
            logger.info(f"Auto-selected best model: {model_id} (accuracy: {best_model.get('accuracy', 'N/A')})")
        
        pred_request = PredictionRequest(
            symbol=request.symbol,
            model_id=model_id,
            model_version=request.model_version,
            horizon_days=request.horizon_days,
            include_features=request.include_features,
        )
        result = prediction_service.predict_for_symbol(db, pred_request)
        return result.to_dict()
    
    except ValueError as e:
        logger.warning(f"Prediction validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/predict/batch", response_model=BatchPredictionResponseSchema)
async def predict_batch(
    request: BatchPredictionRequestSchema,
    db: Session = Depends(get_db),
    prediction_service: PredictionService = Depends(get_prediction_service),
    model_server: ModelServer = Depends(get_model_server),
) -> dict:
    """Generate predictions for multiple stocks.
    
    Args:
        request: Batch prediction request
        db: Database session
        prediction_service: Prediction service
        model_server: Model server
        
    Returns:
        List of predictions and summary statistics
    """
    try:
        # If model_id not specified or is 'latest', use best model
        model_id = request.model_id
        if not model_id or model_id == 'latest':
            models = model_server.list_models()
            if not models:
                raise ValueError("No trained models available")
            # Select model with highest accuracy
            best_model = max(models, key=lambda m: m.get('accuracy', 0))
            model_id = best_model['model_id']
            logger.info(f"Auto-selected best model: {model_id} (accuracy: {best_model.get('accuracy', 'N/A')})")
        
        predictions = prediction_service.predict_batch(
            db=db,
            symbols=request.symbols,
            model_id=model_id,
            model_version=request.model_version,
            horizon_days=request.horizon_days,
        )
        
        if not predictions:
            raise HTTPException(status_code=422, detail="No valid predictions generated")
        
        summary = prediction_service.get_prediction_summary(predictions)
        
        return {
            "predictions": [p.to_dict() for p in predictions],
            "summary": summary,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {str(e)}")


@router.post("/predict/watchlist", response_model=BatchPredictionResponseSchema)
async def predict_watchlist(
    request: WatchlistPredictionRequestSchema,
    db: Session = Depends(get_db),
    prediction_service: PredictionService = Depends(get_prediction_service),
) -> dict:
    """Generate predictions for all stocks in a watchlist.
    
    Args:
        request: Watchlist prediction request
        db: Database session
        prediction_service: Prediction service
        
    Returns:
        List of predictions and summary statistics
    """
    try:
        predictions = prediction_service.predict_for_watchlist(
            db=db,
            watchlist_id=request.watchlist_id,
            model_id=request.model_id,
            model_version=request.model_version,
            horizon_days=request.horizon_days,
        )
        
        if not predictions:
            raise HTTPException(status_code=422, detail="No valid predictions generated")
        
        summary = prediction_service.get_prediction_summary(predictions)
        
        return {
            "predictions": [p.to_dict() for p in predictions],
            "summary": summary,
        }
    
    except ValueError as e:
        logger.warning(f"Watchlist prediction error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Watchlist prediction failed: {e}")
        raise HTTPException(status_code=500, detail="Watchlist prediction failed")


def get_evaluation_service(
    model_server: ModelServer = Depends(get_model_server),
) -> ModelEvaluationService:
    """Build evaluation/backtesting service."""
    return ModelEvaluationService(model_server)


@router.get("/history", response_model=PredictionHistoryResponseSchema)
async def prediction_history(
    symbol: str | None = Query(default=None),
    model_id: str | None = Query(default=None, description="Unused filter reserved for string model ids"),
    horizon_days: int | None = Query(default=None, ge=1, le=20),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    prediction_service: PredictionService = Depends(get_prediction_service),
) -> dict:
    """Return paginated persisted prediction history."""
    try:
        items, total = prediction_service.get_prediction_history(
            db=db,
            symbol=symbol,
            model_id=model_id,
            horizon_days=horizon_days,
            limit=limit,
            offset=offset,
        )
        return {
            "predictions": items,
            "count": len(items),
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"Prediction history failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve prediction history")


@router.post("/evaluate", response_model=ModelEvaluationResponseSchema)
async def evaluate_model(
    request: ModelEvaluationRequestSchema,
    db: Session = Depends(get_db),
    evaluation_service: ModelEvaluationService = Depends(get_evaluation_service),
) -> dict:
    """Evaluate a registered model with genuine out-of-sample metrics."""
    try:
        return evaluation_service.evaluate_model(
            db=db,
            model_id=request.model_id,
            symbol=request.symbol,
            horizon_days=request.horizon_days,
            version=request.version,
            evaluation_type=request.evaluation_type,  # type: ignore[arg-type]
            test_size=request.test_size,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Model not found: {request.model_id}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Model evaluation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Model evaluation failed: {str(e)}")


@router.post("/compare", response_model=ModelComparisonResponseSchema)
async def compare_models(
    request: ModelComparisonRequestSchema,
    db: Session = Depends(get_db),
    evaluation_service: ModelEvaluationService = Depends(get_evaluation_service),
) -> dict:
    """Compare multiple registered models on a shared holdout window."""
    try:
        return evaluation_service.compare_models(
            db=db,
            model_ids=request.model_ids,
            symbol=request.symbol,
            horizon_days=request.horizon_days,
            version=request.version,
            test_size=request.test_size,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Model comparison failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Model comparison failed: {str(e)}")


@router.post("/backtest", response_model=BacktestResponseSchema)
async def run_backtest(
    request: BacktestRequestSchema,
    db: Session = Depends(get_db),
    evaluation_service: ModelEvaluationService = Depends(get_evaluation_service),
) -> dict:
    """Execute and persist an ML strategy backtest."""
    try:
        return evaluation_service.run_backtest(
            db=db,
            symbol=request.symbol,
            model_id=request.model_id or "latest",
            horizon_days=request.horizon_days,
            initial_capital=request.initial_capital,
            commission=request.commission,
            slippage=request.slippage,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")


@router.get("/backtests", response_model=BacktestListResponseSchema)
async def list_backtests(
    symbol: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    evaluation_service: ModelEvaluationService = Depends(get_evaluation_service),
) -> dict:
    """List persisted backtest runs."""
    try:
        items, total = evaluation_service.list_backtests(
            db=db, symbol=symbol, limit=limit, offset=offset
        )
        return {"backtests": items, "total": total}
    except Exception as e:
        logger.error(f"List backtests failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list backtests")


@router.get("/backtests/{backtest_id}", response_model=BacktestResponseSchema)
async def get_backtest(
    backtest_id: str,
    db: Session = Depends(get_db),
    evaluation_service: ModelEvaluationService = Depends(get_evaluation_service),
) -> dict:
    """Retrieve a single persisted backtest."""
    try:
        return evaluation_service.get_backtest(db, backtest_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Get backtest failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve backtest")
