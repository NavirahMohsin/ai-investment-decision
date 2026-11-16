"""
ML Analyst Agent Node.

Responsibilities:
- Discover available trained models in the ArthAI model registry (ModelServer).
- Retrieve live predictions using the existing prediction infrastructure (PredictionService).
- Analyse prediction direction (Positive, Negative, Neutral), class probabilities, and confidence.
- Surface model metadata and evaluation metrics (accuracy, F1, ROC-AUC, hyperparameters).
- Explain technical and statistical limitations of model predictions.
- Identify unavailable models and unsupported prediction horizons.
- Reuse: prediction.py, model_server.py.
- Strict constraint: If no trained model is available, return unavailable with an explanation.
  Never fabricate predictions, probabilities, or confidence scores.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db.models import Company, DailyMarketData
from app.agents.state import AgentName, AgentResult, GraphState
from app.agents.prompts import ML_ANALYST_SYSTEM
from app.agents.nodes.base import merge_agent_result
from app.agents.dependencies import get_agent_db_session, get_agent_llm_service
from app.ml.model_server import ModelServer
from app.services.prediction import PredictionService, PredictionRequest

logger = logging.getLogger(__name__)


def ml_analyst_node(state: GraphState) -> GraphState:
    """
    ML Analyst node. Operates safely whether trained models exist on disk or not.
    """
    result = AgentResult(agent_name=AgentName.ML_ANALYST)

    selected = state.get("selected_agents", [])
    if AgentName.ML_ANALYST.value not in selected:
        result.mark_skipped("Not selected for this run.")
        return merge_agent_result(state, result)

    result.mark_running()
    tickers = state.get("tickers", [])

    model_dir = Path("models")
    model_server = ModelServer(model_dir=model_dir)

    try:
        available_models = model_server.list_models()
    except Exception as e:
        logger.warning("Failed to list models from model server: %s", e)
        available_models = []

    result.evidence_sources = ["ModelServer", "PredictionService"]

    # 1. Handle case: No trained models available
    if not available_models:
        result.summary = (
            "No trained machine learning models are currently available in the model registry. "
            "Directional price predictions and probability estimates are unavailable."
        )
        result.key_findings = [
            "Model discovery returned 0 ready models in the registry.",
            "Directional return forecasts and class probabilities cannot be calculated.",
            "Standard supported prediction horizons when models are trained: 1-day, 5-day, and 20-day horizons.",
        ]
        result.supporting_metrics = {
            "models_discovered": 0,
            "status": "UNAVAILABLE",
            "supported_horizons": [1, 5, 20],
        }
        result.missing_information = [
            "Trained prediction models (e.g. XGBoost, Random Forest, Logistic Regression)",
            "Model training metadata and validation performance metrics",
            "Feature importance and predictive weights",
        ]
        result.warnings = [
            "Machine learning predictions are unavailable. No fabricated forecasts or probabilities were generated.",
            "ML forecasts should only be consulted after models are trained and validated on out-of-sample data.",
        ]
        result.confidence = "low"
        result.mark_completed()
        return merge_agent_result(state, result)

    # 2. Handle case: Models ARE available -> Run predictions
    pred_svc = PredictionService(model_server=model_server)
    predictions: dict[str, Any] = {}
    model_metadata_map: dict[str, Any] = {}
    missing: list[str] = []
    warnings: list[str] = [
        "ML predictions are probabilistic estimates based on historical statistical patterns. "
        "They do not guarantee future returns or account for sudden regime shifts."
    ]

    # Select primary model
    primary_model_meta = available_models[0]
    model_id = primary_model_meta.get("model_id")
    model_version = primary_model_meta.get("version", "latest")

    with get_agent_db_session() as db:
        for ticker in tickers:
            symbol = ticker.upper()
            try:
                req = PredictionRequest(
                    symbol=symbol,
                    model_id=model_id,
                    model_version=model_version,
                    horizon_days=1,
                    include_features=True,
                )
                resp = pred_svc.predict_for_symbol(db, req)
                predictions[symbol] = resp.to_dict()
                result.data_timestamps[f"{symbol}_ml_prediction"] = resp.timestamp.isoformat()
            except Exception as e:
                logger.warning("Prediction generation failed for %s: %s", symbol, e)
                missing.append(f"Prediction failed for {symbol}: {e}")

    model_metadata_map[model_id] = {
        "model_type": primary_model_meta.get("model_type"),
        "version": model_version,
        "accuracy": primary_model_meta.get("accuracy"),
        "f1_score": primary_model_meta.get("f1_score"),
        "features": primary_model_meta.get("feature_names", []),
    }

    result.supporting_metrics = {
        "models_discovered": len(available_models),
        "primary_model": model_metadata_map,
        "predictions": predictions,
    }
    result.missing_information = missing

    # Build key findings
    findings = []
    for sym, p in predictions.items():
        findings.append(
            f"{sym}: Predicted direction is {p.get('predicted_class')} with "
            f"{round(p.get('confidence', 0.0) * 100, 1)}% confidence over 1-day horizon."
        )
    if not findings:
        findings.append("Models were discovered but prediction inference failed for the requested tickers.")

    result.key_findings = findings
    result.summary = (
        f"Generated ML predictions for {len(predictions)} asset(s) using {model_id} (v{model_version})."
    )
    result.confidence = "medium" if predictions else "low"
    result.warnings = warnings
    result.mark_completed()

    return merge_agent_result(state, result)
