"""Low-frequency fundamentals refresh scheduler (single-process, no Celery)."""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.fundamentals_refresh import RefreshInProgressError, refresh_companies

logger = logging.getLogger(__name__)


class FundamentalsScheduler:
    def __init__(self, interval_hours: int = 24):
        self.interval_hours = max(1, interval_hours)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_run_at: datetime | None = None

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                logger.warning("Fundamentals scheduler already running")
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run, daemon=True, name="FundamentalsScheduler"
            )
            self._thread.start()
            logger.info(
                "Fundamentals scheduler started (interval: %s hours)", self.interval_hours
            )

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                return
            self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        # Initial delay: wait one full interval before first scheduled run so startup
        # is not blocked on Yahoo Finance availability.
        while not self._stop_event.wait(timeout=self.interval_hours * 3600):
            try:
                with SessionLocal() as db:
                    refresh_companies(
                        db,
                        refresh_all=True,
                        max_companies=settings.FUNDAMENTALS_MAX_COMPANIES_PER_RUN,
                        trigger_source="scheduled",
                        retries=1,
                    )
                self._last_run_at = datetime.now(timezone.utc)
                logger.info("Scheduled fundamentals refresh completed")
            except RefreshInProgressError:
                logger.info("Skipping scheduled fundamentals refresh — already running")
            except Exception as exc:  # noqa: BLE001
                logger.error("Scheduled fundamentals refresh failed: %s", exc, exc_info=True)


_scheduler: FundamentalsScheduler | None = None
_scheduler_lock = threading.Lock()


def initialize_fundamentals_scheduler(
    interval_hours: int = 24,
    auto_start: bool = True,
) -> FundamentalsScheduler:
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            _scheduler.stop()
        _scheduler = FundamentalsScheduler(interval_hours=interval_hours)
        if auto_start:
            _scheduler.start()
        return _scheduler


def shutdown_fundamentals_scheduler(timeout: float = 5.0) -> None:
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            _scheduler.stop(timeout=timeout)
            _scheduler = None
