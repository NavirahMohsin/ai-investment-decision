
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import fundamentals_router, sectors_router, v1_router
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.refresh import refresh_live_quotes, refresh_market_data
from app.services.scheduler import initialize_scheduler, shutdown_scheduler
from app.services.fundamentals_scheduler import (
    initialize_fundamentals_scheduler,
    shutdown_fundamentals_scheduler,
)
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    logger.info("Starting ArthAI application...")
    
    # Initialize market data scheduler if enabled
    if settings.ENABLE_MARKET_SCHEDULER:
        logger.info("Initializing market data scheduler...")
        
        def quote_refresh():
            """Callback for quote refreshes."""
            with SessionLocal() as db:
                refresh_live_quotes(db, store_snapshots=True)
        
        def historical_refresh():
            """Callback for historical data refreshes."""
            with SessionLocal() as db:
                refresh_market_data(db)
        
        initialize_scheduler(
            quote_callback=quote_refresh,
            historical_callback=historical_refresh,
            interval_minutes=settings.SCHEDULER_INTERVAL_MINUTES,
            check_market_hours=True,
            auto_start=True,
        )
        logger.info("Market data scheduler initialized")

    # Fundamentals refresh uses a separate low-frequency scheduler (reporting cycles)
    if settings.ENABLE_FUNDAMENTALS_SCHEDULER:
        logger.info("Initializing fundamentals scheduler...")
        initialize_fundamentals_scheduler(
            interval_hours=settings.FUNDAMENTALS_REFRESH_INTERVAL_HOURS,
            auto_start=True,
        )
        logger.info("Fundamentals scheduler initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down ArthAI application...")
    if settings.ENABLE_MARKET_SCHEDULER:
        logger.info("Stopping market data scheduler...")
        shutdown_scheduler(timeout=5.0)
    if settings.ENABLE_FUNDAMENTALS_SCHEDULER:
        logger.info("Stopping fundamentals scheduler...")
        shutdown_fundamentals_scheduler(timeout=5.0)
    logger.info("Shutdown complete")


app = FastAPI(
    title="ArthAI API",
    description="Backend API for the ArthAI Financial Intelligence Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow our Next.js frontend to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)
app.include_router(fundamentals_router)
app.include_router(sectors_router)


@app.get("/")
def home():
    return {
        "message": "Welcome to ArthAI API",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": "ArthAI"
    }
