"""
API routes for the Financial Assistant.

Endpoints for conversational AI-powered stock research and analysis.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.assistant import (
    AssistantQuestionRequest,
    AssistantResponseItem,
    ExplanationRequest,
    ExplanationResponse,
    StockComparisonRequest,
    StockComparisonResponse,
    HealthResponse,
)
from app.services.financial_assistant import get_financial_assistant
from app.services.llm_service import get_llm_service, LLMProvider

logger = logging.getLogger(__name__)

assistant_router = APIRouter(
    prefix="/api/v1/assistant",
    tags=["Financial Assistant"],
    responses={
        404: {"description": "Not found"},
        429: {"description": "Rate limited"},
    },
)


@assistant_router.post(
    "/ask",
    response_model=AssistantResponseItem,
    summary="Ask the financial assistant a question",
    description="Ask questions about Indian stocks, market trends, valuations, etc. The assistant uses real market data and fundamental analysis to provide informed answers.",
)
async def ask_question(
    request: AssistantQuestionRequest,
    db: Session = Depends(get_db),
):
    """
    Ask the financial assistant a question.
    
    The assistant will:
    - Search for relevant company data
    - Retrieve market prices and fundamentals
    - Check technical indicators
    - Review recent news
    - Provide a comprehensive, data-driven answer
    - Distinguish between facts and interpretations
    
    Example questions:
    - "What is the PE ratio of TCS and is it undervalued?"
    - "Should I buy Reliance Industries right now?"
    - "Compare Infosys vs Wipro as investments"
    - "Explain the technical signals for HDFC Bank"
    """
    try:
        logger.info(f"Received question: {request.question[:100]}...")
        
        assistant = get_financial_assistant(db)
        response = assistant.ask_question(
            question=request.question,
            include_history=request.include_history,
        )
        
        return AssistantResponseItem(
            answer=response.answer,
            sources=response.sources,
            confidence=response.confidence,
            disclaimer=response.disclaimer,
            related_companies=response.related_companies,
        )
        
    except Exception as e:
        logger.error(f"Error in ask_question: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process question: {str(e)}"
        )


@assistant_router.post(
    "/explain/fundamental-score",
    response_model=ExplanationResponse,
    summary="Explain a fundamental score",
    description="Get a detailed explanation of why a stock received a particular fundamental score.",
)
async def explain_fundamental_score(
    request: ExplanationRequest,
    db: Session = Depends(get_db),
):
    """
    Explain why a company received a particular fundamental score.
    
    Provides insights into:
    - What the score means for investors
    - Which factors are most important
    - Whether it's strong or weak in context
    - Investment implications
    """
    try:
        if request.type != "fundamental_score":
            raise HTTPException(
                status_code=400,
                detail="This endpoint is for fundamental_score explanations"
            )
        
        if not isinstance(request.score_or_signal, (int, float)):
            raise HTTPException(
                status_code=400,
                detail="score_or_signal must be a number for fundamental scores"
            )
        
        logger.info(f"Explaining fundamental score for {request.ticker}: {request.score_or_signal}")
        
        assistant = get_financial_assistant(db)
        explanation = assistant.explain_fundamental_score(
            ticker=request.ticker,
            score=float(request.score_or_signal),
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


@assistant_router.post(
    "/explain/technical-signal",
    response_model=ExplanationResponse,
    summary="Explain a technical signal",
    description="Get a detailed explanation of a technical trading signal.",
)
async def explain_technical_signal(
    request: ExplanationRequest,
    db: Session = Depends(get_db),
):
    """
    Explain a technical signal based on indicators.
    
    Provides insights into:
    - What the signal means
    - Key indicators driving it
    - Price levels to watch
    - Potential risks
    """
    try:
        if request.type != "technical_signal":
            raise HTTPException(
                status_code=400,
                detail="This endpoint is for technical_signal explanations"
            )
        
        if not isinstance(request.score_or_signal, str):
            raise HTTPException(
                status_code=400,
                detail="score_or_signal must be a string for technical signals (e.g., 'BUY', 'SELL')"
            )
        
        valid_signals = ["BUY", "SELL", "HOLD", "NEUTRAL"]
        if request.score_or_signal not in valid_signals:
            raise HTTPException(
                status_code=400,
                detail=f"Signal must be one of: {', '.join(valid_signals)}"
            )
        
        logger.info(f"Explaining technical signal for {request.ticker}: {request.score_or_signal}")
        
        assistant = get_financial_assistant(db)
        explanation = assistant.explain_technical_signal(
            ticker=request.ticker,
            signal=request.score_or_signal,
            indicators=request.factors,
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


@assistant_router.post(
    "/compare",
    response_model=StockComparisonResponse,
    summary="Compare multiple stocks",
    description="Get a comprehensive comparison of multiple Indian stocks.",
)
async def compare_stocks(
    request: StockComparisonRequest,
    db: Session = Depends(get_db),
):
    """
    Compare multiple stocks side by side.
    
    Analyzes:
    - Financial health (ratios, profitability)
    - Growth prospects
    - Valuation
    - Risk factors
    - Investment suitability for different profiles
    """
    try:
        if len(request.tickers) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least 2 tickers required for comparison"
            )
        if len(request.tickers) > 5:
            raise HTTPException(
                status_code=400,
                detail="Maximum 5 tickers for comparison"
            )
        
        logger.info(f"Comparing stocks: {', '.join(request.tickers)}")
        
        assistant = get_financial_assistant(db)
        comparison = assistant.compare_stocks(request.tickers)
        
        return StockComparisonResponse(
            comparison=comparison,
            tickers=request.tickers,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing stocks: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate comparison: {str(e)}"
        )


@assistant_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check LLM service health",
    description="Check availability of LLM providers and overall assistant health.",
)
async def health_check():
    """
    Check the health of the LLM service.
    
    Returns:
    - Overall status (healthy/degraded)
    - Availability of each LLM provider
    - Status message
    """
    try:
        llm_service = get_llm_service()
        
        gemini_ok = llm_service.gemini_available
        groq_ok = llm_service.groq_available
        
        if not (gemini_ok or groq_ok):
            status = "unhealthy"
            message = "No LLM providers available"
        elif not gemini_ok or not groq_ok:
            status = "degraded"
            message = "Fallback mode: using secondary provider"
        else:
            status = "healthy"
            message = "All LLM providers available"
        
        return HealthResponse(
            status=status,
            gemini_available=gemini_ok,
            groq_available=groq_ok,
            message=message,
        )
        
    except Exception as e:
        logger.error(f"Error in health check: {e}", exc_info=True)
        return HealthResponse(
            status="unhealthy",
            gemini_available=False,
            groq_available=False,
            message=f"Health check failed: {str(e)}",
        )
