"""Controlled fundamental data refresh with retries and run tracking."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Company, FundamentalDataUpdateRun
from app.services.fundamentals import IngestionResult, ingest_company_fundamentals
from app.services.fundamentals_cache import analysis_cache
from app.services.providers.yahoo import YahooFinanceProvider

logger = logging.getLogger(__name__)

_refresh_lock = threading.Lock()


class RefreshInProgressError(RuntimeError):
    """Raised when a refresh is already running."""


def _retry(
    fn: Callable[[], IngestionResult],
    *,
    retries: int = 2,
    backoff_seconds: float = 1.0,
) -> IngestionResult:
    last: IngestionResult | None = None
    for attempt in range(retries + 1):
        try:
            result = fn()
            if result["success"]:
                return result
            last = result
        except Exception as exc:  # noqa: BLE001
            last = {
                "company_symbol": "unknown",
                "success": False,
                "company_info_updated": False,
                "financials_inserted": 0,
                "financials_updated": 0,
                "ratios_inserted": 0,
                "error": str(exc),
            }
        if attempt < retries:
            time.sleep(backoff_seconds * (attempt + 1))
    assert last is not None
    return last


def refresh_companies(
    db: Session,
    *,
    symbols: list[str] | None = None,
    refresh_all: bool = False,
    include_info: bool = True,
    include_statements: bool = True,
    include_ratios: bool = True,
    max_companies: int = 25,
    trigger_source: str = "manual",
    provider: YahooFinanceProvider | None = None,
    retries: int = 2,
) -> tuple[FundamentalDataUpdateRun, list[IngestionResult]]:
    """
    Refresh fundamentals for selected companies with per-company isolation.

    Does not report success until the run completes. Concurrent refresh attempts
    are rejected via a process-level lock.
    """
    if not _refresh_lock.acquire(blocking=False):
        raise RefreshInProgressError("A fundamentals refresh is already in progress.")

    try:
        if refresh_all and symbols:
            raise ValueError("Specify either symbols or refresh_all, not both.")
        if not refresh_all and not symbols:
            raise ValueError("Provide symbols or set refresh_all=true.")

        if refresh_all:
            companies = list(
                db.scalars(
                    select(Company).where(
                        Company.is_active.is_(True),
                        Company.instrument_type.ilike("company"),
                    )
                )
            )
        else:
            assert symbols is not None
            normalized = []
            seen = set()
            for s in symbols:
                sym = s.strip().upper()
                if not sym or sym in seen:
                    continue
                seen.add(sym)
                normalized.append(sym)
            companies = []
            for sym in normalized:
                company = db.scalar(select(Company).where(Company.symbol == sym))
                if company is None:
                    company = db.scalar(select(Company).where(Company.symbol.ilike(sym)))
                if company is None:
                    continue
                if company.instrument_type.lower() not in {"company", "equity", "stock"}:
                    continue
                companies.append(company)

        if len(companies) > max_companies:
            raise ValueError(
                f"Requested {len(companies)} companies exceeds max_companies={max_companies}."
            )
        if not companies:
            raise ValueError("No matching active companies to refresh.")

        run_type_parts = []
        if include_info:
            run_type_parts.append("info")
        if include_statements:
            run_type_parts.append("statements")
        if include_ratios:
            run_type_parts.append("ratios")
        run_type = "+".join(run_type_parts) or "all"

        run = FundamentalDataUpdateRun(
            run_type=run_type,
            status="running",
            companies_processed=0,
            successful_count=0,
            failed_count=0,
            failed_symbols=None,
            trigger_source=trigger_source,
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        yahoo = provider or YahooFinanceProvider()
        results: list[IngestionResult] = []
        successful = 0
        failed = 0
        failed_symbols: list[str] = []

        for company in companies:
            run.companies_processed += 1
            db.commit()

            def _do_ingest(c: Company = company) -> IngestionResult:
                return ingest_company_fundamentals(
                    db,
                    c,
                    yahoo,
                    include_info=include_info,
                    include_statements=include_statements,
                    include_ratios=include_ratios,
                )

            try:
                result = _retry(_do_ingest, retries=retries)
                # Ensure symbol is set
                result["company_symbol"] = company.symbol
                results.append(result)
                if result["success"]:
                    successful += 1
                else:
                    failed += 1
                    failed_symbols.append(company.symbol)
                    logger.warning(
                        "Fundamentals refresh failed for %s: %s",
                        company.symbol,
                        result.get("error"),
                    )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                failed_symbols.append(company.symbol)
                results.append(
                    {
                        "company_symbol": company.symbol,
                        "success": False,
                        "company_info_updated": False,
                        "financials_inserted": 0,
                        "financials_updated": 0,
                        "ratios_inserted": 0,
                        "error": str(exc),
                    }
                )
                logger.exception("Unexpected error refreshing %s", company.symbol)

        run.successful_count = successful
        run.failed_count = failed
        run.failed_symbols = ",".join(failed_symbols) if failed_symbols else None
        if failed == 0:
            run.status = "completed"
        elif successful > 0:
            run.status = "partial"
        else:
            run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        analysis_cache.invalidate_all()
        return run, results
    finally:
        _refresh_lock.release()
