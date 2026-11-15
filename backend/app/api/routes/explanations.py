"""
API Routes for AI Explanations - Interpret Model Outputs

Endpoints for:
- ML prediction explanations
- Technical signal explanations
- Fundamental score explanations
- News sentiment explanations
- All with uncertainty communication
"""

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from fastapi import Depends

from app.db.session import get_db
from app.schemas.research import (
    MLPredictionExplanationRequest,
    TechnicalSignalExplanationRequest,
    FundamentalScoreExplanationRequest,
    NewsSentimentExplanationRequest,
    ExplanationResponse,
    HealthResponse,
)
from app.services.explanations import get_explanation_service

logger = logging.getLogger(__name__)

explanations_router = APIRouter(
    prefix="/api/v1/explain",
    tags=["AI Explanations"],
    responses={
        400: {"description": "Bad request"},
        500: {"description": "Internal server error"},
    },
)


@explanations_router.post(
    "/ml-prediction",
    response_model=ExplanationResponse,
    summary="Explain ML prediction",
    description="Get human-readable explanation of why ML model predicts UP/DOWN.",
)
async def explain_ml_prediction(
    request: MLPredictionExplanationRequest,
):
    """
    Explain an ML prediction.

    Returns:
    - What the prediction means
    - Confidence interpretation
    - Key contributing factors
    - Important limitations
    - How to use properly

    Includes strong disclaimers about uncertainty and proper usage.
    """
    try:
        if request.direction not in ["UP", "DOWN"]:
            raise HTTPException(
                status_code=400,
                detail="Direction must be UP or DOWN"
            )

        if not 0 <= request.confidence <= 1:
            raise HTTPException(
                status_code=400,
                detail="Confidence must be between 0 and 1"
            )

        logger.info(
            f"Explaining ML prediction for {request.ticker}: "
            f"{request.direction} with {request.confidence*100:.0f}% confidence"
        )

        service = get_explanation_service()
        prediction_data = {
            "direction": request.direction,
            "confidence": request.confidence,
            "current_price": request.current_price,
            "prediction_price": request.prediction_price,
        }

        explanation = service.explain_ml_prediction(
            ticker=request.ticker,
            prediction=prediction_data,
        )

        return ExplanationResponse(
            explanation=explanation,
            ticker=request.ticker,
            type="ml_prediction",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error explaining ML prediction: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate explanation: {str(e)}"
        )


@explanations_router.post(
    "/technical-signal",
    response_model=ExplanationResponse,
    summary="Explain technical signal",
    description="Explain why a technical trading signal (BUY/SELL/HOLD) was generated.",
)
async def explain_technical_signal(
    request: TechnicalSignalExplanationRequest,
):
    """
    Explain a technical signal.

    Returns:
    - Signal interpretation
    - Supporting indicators
    - Price levels to watch
    - Risks and reversals
    - Proper usage guidelines

    Explains what each indicator means and how they work together.
    """
    try:
        valid_signals = ["BUY", "SELL", "HOLD", "NEUTRAL"]
        if request.signal not in valid_signals:
            raise HTTPException(
                status_code=400,
                detail=f"Signal must be one of: {', '.join(valid_signals)}"
            )

        logger.info(f"Explaining technical signal for {request.ticker}: {request.signal}")

        service = get_explanation_service()
        explanation = service.explain_technical_signal(
            ticker=request.ticker,
            signal=request.signal,
            indicators=request.indicators,
        )

        return ExplanationResponse(
            explanation=explanation,
            ticker=request.ticker,
            type="technical_signal",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error explaining technical signal: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate explanation: {str(e)}"
        )


@explanations_router.post(
    "/fundamental-score",
    response_model=ExplanationResponse,
    summary="Explain fundamental score",
    description="Explain why a company received a particular fundamental score.",
)
async def explain_fundamental_score(
    request: FundamentalScoreExplanationRequest,
):
    """
    Explain a fundamental score.

    Returns:
    - What the score means
    - Contributing factors
    - Strongest/weakest areas
    - Investment implications
    - What could change the score

    Helps investors understand how scores are calculated and interpreted.
    """
    try:
        if not 0 <= request.score <= 100:
            raise HTTPException(
                status_code=400,
                detail="Score must be between 0 and 100"
            )

        logger.info(f"Explaining fundamental score for {request.ticker}: {request.score}")

        service = get_explanation_service()
        explanation = service.explain_fundamental_score(
            ticker=request.ticker,
            score=request.score,
            factors=request.factors,
        )

        return ExplanationResponse(
            explanation=explanation,
            ticker=request.ticker,
            type="fundamental_score",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error explaining fundamental score: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate explanation: {str(e)}"
        )


@explanations_router.post(
    "/news-sentiment",
    response_model=ExplanationResponse,
    summary="Explain news sentiment",
    description="Explain what news sentiment means and implications for the stock.",
)
async def explain_news_sentiment(
    request: NewsSentimentExplanationRequest,
):
    """
    Explain news sentiment.

    Returns:
    - Sentiment interpretation
    - Key themes in news
    - Possible market impact
    - Context and caveats
    - Proper usage guidelines

    Explains that sentiment is backward-looking, not predictive.
    Emphasizes the importance of combining with fundamentals.
    """
    try:
        if not 0 <= request.sentiment_score <= 1:
            raise HTTPException(
                status_code=400,
                detail="Sentiment score must be between 0 and 1"
            )

        valid_categories = ["positive", "negative", "neutral"]
        if request.sentiment_category not in valid_categories:
            raise HTTPException(
                status_code=400,
                detail=f"Category must be: {', '.join(valid_categories)}"
            )

        logger.info(
            f"Explaining news sentiment for {request.ticker}: "
            f"{request.sentiment_category} ({request.sentiment_score:.2f})"
        )

        service = get_explanation_service()
        explanation = service.explain_news_sentiment(
            ticker=request.ticker,
            sentiment_score=request.sentiment_score,
            sentiment_category=request.sentiment_category,
            key_themes=request.themes,
        )

        return ExplanationResponse(
            explanation=explanation,
            ticker=request.ticker,
            type="news_sentiment",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error explaining news sentiment: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate explanation: {str(e)}"
        )


@explanations_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check explanations service health",
)
async def health_check():
    """
    Check health of explanations service.

    Returns operational status and available explanation types.
    """
    try:
        return HealthResponse(
            status="healthy",
            services_ready=[
                "ml_prediction_explanation",
                "technical_signal_explanation",
                "fundamental_score_explanation",
                "news_sentiment_explanation",
            ],
            message="All explanation services operational"
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="degraded",
            services_ready=[],
            message=f"Health check failed: {str(e)}"
        )
