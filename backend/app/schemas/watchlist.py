from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ── Request bodies ────────────────────────────────────────────────────────────

class WatchlistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, strip_whitespace=True)
    description: str | None = Field(None, max_length=500, strip_whitespace=True)


class WatchlistUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100, strip_whitespace=True)
    description: str | None = Field(None, max_length=500, strip_whitespace=True)


class WatchlistItemAdd(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=50, strip_whitespace=True)


# ── Response shapes ───────────────────────────────────────────────────────────

class WatchlistItemRead(BaseModel):
    """A stock entry with live quote data attached."""
    id: int
    watchlist_id: int
    symbol: str
    added_at: datetime

    # Live market data – nullable when quote is unavailable
    name: str | None = None
    exchange: str | None = None
    price: Decimal | None = None
    previous_close: Decimal | None = None
    absolute_change: Decimal | None = None
    percentage_change: Decimal | None = None
    freshness: str | None = None

    model_config = {"from_attributes": True}


class WatchlistRead(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    item_count: int = 0

    model_config = {"from_attributes": True}


class WatchlistDetail(WatchlistRead):
    items: list[WatchlistItemRead] = []
