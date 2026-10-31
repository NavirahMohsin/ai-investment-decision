import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{(BACKEND_DIR / 'data' / 'arthai.db').as_posix()}",
)
DEFAULT_HISTORY_YEARS = int(os.getenv("DEFAULT_HISTORY_YEARS", "5"))
