"""Background news ingestion scheduler with lifecycle management."""
from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Callable

from app.services.news.ingestion import ingest_all_active_sources

logger = logging.getLogger(__name__)


class NewsScheduler:
    """Background scheduler for news ingestion."""

    def __init__(self, interval_hours: int = 24):
        """Initialize the scheduler.
        
        Args:
            interval_hours: Hours between ingestion runs
        """
        self.interval_hours = max(1, interval_hours)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the scheduler in a background thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                logger.warning("News scheduler already running")
                return

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run, daemon=True, name="NewsScheduler"
            )
            self._thread.start()
            logger.info(
                f"News scheduler started (interval: {self.interval_hours} hours)"
            )

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the scheduler and wait for the thread to finish.

        Args:
            timeout: Seconds to wait for thread to finish
        """
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                logger.info("News scheduler not running")
                return

            logger.info("Stopping news scheduler...")
            self._stop_event.set()

        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            logger.warning("News scheduler thread did not stop gracefully")
        else:
            logger.info("News scheduler stopped")

    def is_running(self) -> bool:
        """Check if the scheduler is currently running."""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        """Main scheduler loop."""
        logger.info("News scheduler loop started")
        
        # Run ingestion immediately on startup
        try:
            logger.info("Running initial news ingestion on startup")
            ingest_all_active_sources()
            logger.info("Initial news ingestion completed")
        except Exception as e:
            logger.error(f"Error in initial news ingestion: {e}", exc_info=True)

        while not self._stop_event.is_set():
            try:
                logger.info("Starting scheduled news ingestion")
                ingest_all_active_sources()
                logger.info("Scheduled news ingestion completed")
            except Exception as e:
                logger.error(f"Error in news ingestion: {e}", exc_info=True)

            # Wait for interval or stop signal
            self._stop_event.wait(timeout=self.interval_hours * 3600)

        logger.info("News scheduler loop finished")


# Global scheduler instance
_scheduler: NewsScheduler | None = None
_scheduler_lock = threading.Lock()


def get_news_scheduler() -> NewsScheduler | None:
    """Get the global news scheduler instance."""
    with _scheduler_lock:
        return _scheduler


def initialize_news_scheduler(
    interval_hours: int = 24,
    auto_start: bool = True,
) -> NewsScheduler:
    """Initialize and optionally start the global news scheduler.

    Args:
        interval_hours: Hours between ingestion runs
        auto_start: Whether to start the scheduler immediately

    Returns:
        The initialized scheduler instance
    """
    global _scheduler

    with _scheduler_lock:
        if _scheduler is not None:
            logger.warning("News scheduler already initialized, stopping existing instance")
            _scheduler.stop()

        _scheduler = NewsScheduler(interval_hours=interval_hours)

        if auto_start:
            _scheduler.start()

        return _scheduler


def shutdown_news_scheduler(timeout: float = 5.0) -> None:
    """Shutdown the global news scheduler."""
    global _scheduler

    with _scheduler_lock:
        if _scheduler is not None:
            _scheduler.stop(timeout=timeout)
            _scheduler = None


@contextmanager
def news_scheduler_context(interval_hours: int = 24):
    """Context manager for news scheduler lifecycle.

    Usage:
        with news_scheduler_context():
            # Scheduler runs in background
            await app.run()
        # Scheduler automatically stopped
    """
    scheduler = initialize_news_scheduler(interval_hours=interval_hours)

    try:
        yield scheduler

    finally:
        shutdown_news_scheduler()
