import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = ConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        case_sensitive=True,
    )
    
    DATABASE_URL: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'arthai.db').as_posix()}"
    DEFAULT_HISTORY_YEARS: int = 5
    
    # Scheduler settings
    ENABLE_MARKET_SCHEDULER: bool = True
    SCHEDULER_INTERVAL_MINUTES: int = 15

    # Fundamentals refresh (reporting cadence — not intraday)
    ENABLE_FUNDAMENTALS_SCHEDULER: bool = True
    FUNDAMENTALS_REFRESH_INTERVAL_HOURS: int = 24
    FUNDAMENTALS_FRESH_DAYS: int = 30
    FUNDAMENTALS_AGING_DAYS: int = 90
    FUNDAMENTALS_MAX_COMPANIES_PER_RUN: int = 25


settings = Settings()

# Legacy exports for backward compatibility
DATABASE_URL = settings.DATABASE_URL
DEFAULT_HISTORY_YEARS = settings.DEFAULT_HISTORY_YEARS
