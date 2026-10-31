"""Background market data scheduler with lifecycle management."""
from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime, time as dt_time, timezone
from typing import Callable

from app.services.calendar import MarketSession, get_market_session, IST

logger = logging.getLogger(__name__)


class MarketDataScheduler:
    """
    Background scheduler for market data refreshes.
    
    Respects market hours and holidays using the Indian exchange calendar.
    """
    
    def __init__(
        self,
        quote_callback: Callable[[], None],
        historical_callback: Callable[[], None] | None = None,
        interval_minutes: int = 15,
        check_market_hours: bool = True,
    ):
        """
        Initialize the scheduler.
        
        Args:
            quote_callback: Function to call for live quote updates
            historical_callback: Optional function to call for historical data updates
            interval_minutes: Minutes between refreshes during market hours
            check_market_hours: Whether to respect market hours (False for testing)
        """
        self.quote_callback = quote_callback
        self.historical_callback = historical_callback
        self.interval_minutes = interval_minutes
        self.check_market_hours = check_market_hours
        
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_historical_date: datetime | None = None
    
    def start(self) -> None:
        """Start the scheduler in a background thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                logger.warning("Scheduler already running")
                return
            
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True, name="MarketDataScheduler")
            self._thread.start()
            logger.info(f"Market data scheduler started (interval: {self.interval_minutes} minutes)")
    
    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the scheduler and wait for the thread to finish.
        
        Args:
            timeout: Maximum seconds to wait for graceful shutdown
        """
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                logger.info("Scheduler not running")
                return
            
            logger.info("Stopping market data scheduler...")
            self._stop_event.set()
        
        # Wait for thread to finish outside the lock
        if self._thread:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("Scheduler thread did not stop gracefully")
            else:
                logger.info("Market data scheduler stopped")
    
    def is_running(self) -> bool:
        """Check if the scheduler is currently running."""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()
    
    def _should_refresh(self) -> bool:
        """Determine if refresh should run based on market status."""
        if not self.check_market_hours:
            return True
        
        session = get_market_session()
        current = datetime.now(timezone.utc).astimezone(IST)
        current_time = current.time()
        
        # Run during market hours
        if session in {MarketSession.PRE_OPEN, MarketSession.OPEN}:
            return True
        
        # Run once after market close (within 30 minutes)
        if session == MarketSession.CLOSED:
            if dt_time(15, 30) <= current_time <= dt_time(16, 0):
                return True
        
        return False
    
    def _run(self) -> None:
        """Main scheduler loop."""
        logger.info("Scheduler loop started")
        
        while not self._stop_event.is_set():
            try:
                current_time = datetime.now(timezone.utc).astimezone(IST)
                session = get_market_session()
                
                if self._should_refresh():
                    logger.info(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S IST')}] Market: {session.value}")
                    
                    # Refresh live quotes
                    try:
                        logger.debug("Refreshing live quotes...")
                        self.quote_callback()
                        logger.debug("Live quotes refreshed successfully")
                    except Exception as e:
                        logger.error(f"Error refreshing live quotes: {e}", exc_info=True)
                    
                    # Refresh historical data once per day
                    if self.historical_callback:
                        today = current_time.date()
                        if self._last_historical_date != today:
                            try:
                                logger.debug("Refreshing historical data...")
                                self.historical_callback()
                                self._last_historical_date = today
                                logger.debug("Historical data refreshed successfully")
                            except Exception as e:
                                logger.error(f"Error refreshing historical data: {e}", exc_info=True)
                else:
                    logger.debug(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S IST')}] Market: {session.value} - Skipping refresh")
            
            except Exception as e:
                logger.error(f"Unexpected error in scheduler loop: {e}", exc_info=True)
            
            # Wait for interval or stop signal
            self._stop_event.wait(timeout=self.interval_minutes * 60)
        
        logger.info("Scheduler loop finished")


# Global scheduler instance
_scheduler: MarketDataScheduler | None = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> MarketDataScheduler | None:
    """Get the global scheduler instance."""
    with _scheduler_lock:
        return _scheduler


def initialize_scheduler(
    quote_callback: Callable[[], None],
    historical_callback: Callable[[], None] | None = None,
    interval_minutes: int = 15,
    check_market_hours: bool = True,
    auto_start: bool = True,
) -> MarketDataScheduler:
    """
    Initialize and optionally start the global scheduler.
    
    Args:
        quote_callback: Function to call for live quote updates
        historical_callback: Optional function to call for historical data updates
        interval_minutes: Minutes between refreshes during market hours
        check_market_hours: Whether to respect market hours
        auto_start: Whether to start the scheduler immediately
    
    Returns:
        The initialized scheduler instance
    """
    global _scheduler
    
    with _scheduler_lock:
        if _scheduler is not None:
            logger.warning("Scheduler already initialized, stopping existing instance")
            _scheduler.stop()
        
        _scheduler = MarketDataScheduler(
            quote_callback=quote_callback,
            historical_callback=historical_callback,
            interval_minutes=interval_minutes,
            check_market_hours=check_market_hours,
        )
        
        if auto_start:
            _scheduler.start()
        
        return _scheduler


def shutdown_scheduler(timeout: float = 5.0) -> None:
    """Shutdown the global scheduler."""
    global _scheduler
    
    with _scheduler_lock:
        if _scheduler is not None:
            _scheduler.stop(timeout=timeout)
            _scheduler = None


@contextmanager
def scheduler_context(
    quote_callback: Callable[[], None],
    historical_callback: Callable[[], None] | None = None,
    interval_minutes: int = 15,
    check_market_hours: bool = True,
):
    """
    Context manager for scheduler lifecycle.
    
    Usage:
        with scheduler_context(quote_fn, hist_fn):
            # Scheduler runs in background
            await app.run()
        # Scheduler automatically stopped
    """
    scheduler = initialize_scheduler(
        quote_callback=quote_callback,
        historical_callback=historical_callback,
        interval_minutes=interval_minutes,
        check_market_hours=check_market_hours,
        auto_start=True,
    )
    
    try:
        yield scheduler
    finally:
        shutdown_scheduler()
