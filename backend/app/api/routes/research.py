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

from fastapi import APIRouter, Depends, HTTPException, Query
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
    SaveReportRequest,
    SavedReportResponse,
    SavedReportListResponse,
    ReportRetrieveResponse,
    DeleteReportResponse,
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
    summary="Generate and persist research report",
    description="Generate comprehensive research report combining overview, market data, technicals, fundamentals, news, and risk. Automatically persists to database.",
)
async def generate_research_report(
    request: ResearchReportRequest,
    db: Session = Depends(get_db),
):
    """
    Generate comprehensive research report using actual ArthAI services.
    """
    try:
        sym = request.ticker.strip().upper()
        logger.info(f"Generating research report for {sym}")
        assistant = get_research_assistant(db)
        dossier = assistant.generate_research_dossier(
            ticker=sym,
            report_type=request.report_type,
        )

        report_content = dossier.get("report", "")
        company_name = dossier.get("company_name", sym)
        structured_sections = dossier.get("structured_sections")
        sources = dossier.get("sources")
        report_id = None

        if getattr(request, "save_to_db", True):
            saved = assistant.save_report(
                ticker=sym,
                content=report_content,
                report_type=request.report_type,
                company_name=company_name,
                structured_sections=structured_sections,
                sources=sources,
                parameters={"requested_type": request.report_type},
            )
            report_id = saved.report_id

        return ResearchReportResponse(
            report=report_content,
            ticker=sym,
            company_name=company_name,
            report_type=request.report_type,
            report_id=report_id,
            structured_sections=structured_sections,
            sources=sources,
            generated_at=dossier.get("generated_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report: {str(e)}"
        )


@research_router.post(
    "/save",
    response_model=ResearchReportResponse,
    summary="Save research report manually",
    description="Explicitly save a research report to the persistent database.",
)
async def save_research_report(
    request: SaveReportRequest,
    db: Session = Depends(get_db),
):
    """Save an existing or customized research report."""
    try:
        sym = request.ticker.strip().upper()
        assistant = get_research_assistant(db)
        saved = assistant.save_report(
            ticker=sym,
            content=request.content,
            report_type=request.report_type,
            company_name=request.company_name,
            structured_sections=request.structured_sections,
            sources=request.sources,
        )

        return ResearchReportResponse(
            report=saved.content,
            ticker=saved.ticker,
            company_name=saved.company_name,
            report_type=saved.report_type,
            report_id=saved.report_id,
            structured_sections=saved.structured_sections,
            sources=saved.sources,
            generated_at=saved.generated_at.isoformat() if saved.generated_at else None,
        )
    except Exception as e:
        logger.error(f"Error saving report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save report: {str(e)}")


@research_router.get(
    "/reports",
    response_model=SavedReportListResponse,
    summary="List saved research reports",
    description="Retrieve paginated list of saved research reports with optional ticker and report_type filtering.",
)
async def list_saved_reports(
    ticker: Optional[str] = Query(None, description="Filter by stock ticker symbol"),
    report_type: Optional[str] = Query(None, description="Filter by report type"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
):
    """List persisted reports from database with pagination."""
    try:
        assistant = get_research_assistant(db)
        reports, total = assistant.list_reports(
            ticker=ticker,
            report_type=report_type,
            limit=limit,
            offset=offset,
        )

        items = []
        for r in reports:
            # Create brief preview of content (first 150 chars)
            preview = r.content[:150].replace("\n", " ") + "..." if len(r.content) > 150 else r.content
            items.append(
                SavedReportResponse(
                    id=r.id,
                    report_id=r.report_id,
                    ticker=r.ticker,
                    company_name=r.company_name,
                    report_type=r.report_type,
                    content_preview=preview,
                    generated_at=r.generated_at.isoformat() if r.generated_at else r.created_at.isoformat(),
                )
            )

        return SavedReportListResponse(
            reports=items,
            count=len(items),
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error(f"Error listing reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list reports: {str(e)}")


@research_router.get(
    "/reports/{report_id}",
    response_model=ReportRetrieveResponse,
    summary="Retrieve a specific saved research report",
    description="Fetch full details, content markdown, and structured sections of a saved report by report_id.",
)
async def get_saved_report(
    report_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve full details of a saved report."""
    try:
        assistant = get_research_assistant(db)
        report = assistant.get_report_by_id(report_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"Report with ID '{report_id}' not found")

        return ReportRetrieveResponse(
            id=report.id,
            report_id=report.report_id,
            ticker=report.ticker,
            company_name=report.company_name,
            report_type=report.report_type,
            content=report.content,
            structured_sections=report.structured_sections,
            sources=report.sources,
            generated_at=report.generated_at.isoformat() if report.generated_at else report.created_at.isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving report {report_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve report: {str(e)}")


@research_router.delete(
    "/reports/{report_id}",
    response_model=DeleteReportResponse,
    summary="Delete a saved research report",
    description="Remove a persisted research report from the database by report_id.",
)
async def delete_saved_report(
    report_id: str,
    db: Session = Depends(get_db),
):
    """Delete a saved report."""
    try:
        assistant = get_research_assistant(db)
        success = assistant.delete_report(report_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Report with ID '{report_id}' not found")

        return DeleteReportResponse(
            success=True,
            message="Report successfully deleted",
            report_id=report_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting report {report_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete report: {str(e)}")


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
                "research_report",
                "report_persistence",
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
