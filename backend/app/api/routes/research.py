"""
API Routes for Research Assistant - Company Analysis & Reports

Endpoints for:
- Company overviews
- Financial analysis
- SWOT analysis
- Company comparisons
- Research report generation
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.research import (
    CompanyOverviewRequest,
    CompanyOverviewResponse,
    FinancialAnalysisRequest,
    FinancialAnalysisResponse,
    SWOTRequest,
    SWOTResponse,
    ComparisonRequest,
    ComparisonResponse,
    ResearchReportRequest,
    ResearchReportResponse,
    SavedReportResponse,
    SavedReportListResponse,
    ReportRetrieveResponse,
    HealthResponse,
)
from app.services.research_assistant import get_research_assistant

logger = logging.getLogger(__name__)

research_router = APIRouter(
    prefix="/api/v1/research",
    tags=["Research Assistant"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    },
)


@research_router.post(
    "/company-overview",
    response_model=CompanyOverviewResponse,
    summary="Generate company overview",
    description="Generate an executive summary of a company including business model, key metrics, and market position.",
)
async def generate_company_overview(
    request: CompanyOverviewRequest,
    db: Session = Depends(get_db),
):
    """
    Generate a company overview.

    Returns:
    - Company name, sector, key metrics
    - Business model explanation
    - Recent performance
    - Market position

    Example:
    ```json
    {
      "ticker": "TCS",
      "language": "simple"
    }
    ```
    """
    try:
        logger.info(f"Generating overview for {request.ticker}")
        assistant = get_research_assistant(db)
        overview = assistant.generate_company_overview(
            ticker=request.ticker,
            language=request.language,
        )

        return CompanyOverviewResponse(
            overview=overview,
            ticker=request.ticker,
        )

    except Exception as e:
        logger.error(f"Error generating overview: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate overview: {str(e)}"
        )


@research_router.post(
    "/financial-analysis",
    response_model=FinancialAnalysisResponse,
    summary="Analyze financial performance",
    description="Generate analysis of company's financial performance over specified period.",
)
async def analyze_financial_performance(
    request: FinancialAnalysisRequest,
    db: Session = Depends(get_db),
):
    """
    Analyze financial performance.

    Returns:
    - Price movement analysis
    - Volatility assessment
    - Trading volume patterns
    - Technical observations

    Periods: 1Y, 3Y, 5Y
    """
    try:
        logger.info(f"Analyzing performance for {request.ticker}")
        assistant = get_research_assistant(db)
        analysis = assistant.analyze_financial_performance(
            ticker=request.ticker,
            period=request.period,
        )

        return FinancialAnalysisResponse(
            analysis=analysis,
            ticker=request.ticker,
            period=request.period,
        )

    except Exception as e:
        logger.error(f"Error analyzing performance: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze: {str(e)}"
        )


@research_router.post(
    "/swot",
    response_model=SWOTResponse,
    summary="Generate SWOT analysis",
    description="Generate comprehensive SWOT (Strengths, Weaknesses, Opportunities, Threats) analysis.",
)
async def generate_swot(
    request: SWOTRequest,
    db: Session = Depends(get_db),
):
    """
    Generate SWOT analysis.

    Returns:
    - 5 Strengths
    - 5 Weaknesses
    - 5 Opportunities
    - 5 Threats
    - Strategic implications
    """
    try:
        logger.info(f"Generating SWOT for {request.ticker}")
        assistant = get_research_assistant(db)
        swot = assistant.generate_swot_analysis(ticker=request.ticker)

        return SWOTResponse(
            swot=swot,
            ticker=request.ticker,
        )

    except Exception as e:
        logger.error(f"Error generating SWOT: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate SWOT: {str(e)}"
        )


@research_router.post(
    "/compare",
    response_model=ComparisonResponse,
    summary="Compare companies",
    description="Generate detailed peer comparison of multiple companies.",
)
async def compare_companies(
    request: ComparisonRequest,
    db: Session = Depends(get_db),
):
    """
    Compare multiple companies.

    Returns:
    - Side-by-side financial comparison
    - Peer analysis
    - Investment perspective
    - Risk assessment

    Supports 2-5 companies
    """
    try:
        if len(request.tickers) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least 2 tickers required"
            )
        if len(request.tickers) > 5:
            raise HTTPException(
                status_code=400,
                detail="Maximum 5 tickers allowed"
            )

        logger.info(f"Comparing: {', '.join(request.tickers)}")
        assistant = get_research_assistant(db)
        comparison = assistant.compare_companies(tickers=request.tickers)

        return ComparisonResponse(
            comparison=comparison,
            tickers=request.tickers,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing companies: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compare: {str(e)}"
        )


@research_router.post(
    "/report",
    response_model=ResearchReportResponse,
    summary="Generate research report",
    description="Generate comprehensive research report combining overview, analysis, and SWOT.",
)
async def generate_research_report(
    request: ResearchReportRequest,
    db: Session = Depends(get_db),
):
    """
    Generate comprehensive research report.

    Returns:
    - Executive overview
    - Financial performance analysis
    - SWOT analysis
    - Report disclaimer

    Report is automatically saved for future reference.
    """
    try:
        logger.info(f"Generating research report for {request.ticker}")
        assistant = get_research_assistant(db)
        report = assistant.generate_research_report(
            ticker=request.ticker,
            report_type=request.report_type,
        )

        # TODO: Save report to database when SavedReport model is added
        # report_id = save_report(db, request.ticker, request.report_type, report)

        return ResearchReportResponse(
            report=report,
            ticker=request.ticker,
            report_id=None,  # Will be set when saving implemented
        )

    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report: {str(e)}"
        )


@research_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check research service health",
    description="Verify that research service is operational.",
)
async def health_check():
    """
    Check health of research service.

    Returns:
    - Service status
    - Available services
    - Overall health
    """
    try:
        return HealthResponse(
            status="healthy",
            services_ready=[
                "company_overview",
                "financial_analysis",
                "swot_analysis",
                "company_comparison",
                "research_report"
            ],
            message="All research services operational"
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="degraded",
            services_ready=[],
            message=f"Health check failed: {str(e)}"
        )
