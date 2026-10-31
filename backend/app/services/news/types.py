from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field


class PersistenceValidationError(ValueError):
    """Raised when a normalized article cannot be persisted safely."""


class NormalizedNewsArticle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_key: str
    external_id: str | None = None
    headline: str | None = None
    summary: str | None = None
    author: str | None = None
    canonical_url: str | None = None
    published_at_raw: str | None = None
    published_at_utc: datetime | None = None
    language: str | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)


def validate_article_for_persistence(
    article: NormalizedNewsArticle,
) -> None:
    """Validate the fields required by the NewsArticle persistence model."""
    if not article.headline or not article.headline.strip():
        raise PersistenceValidationError("Article headline is required")
    if not article.canonical_url or not article.canonical_url.strip():
        raise PersistenceValidationError("Article canonical URL is required")
    try:
        parsed_url = urlsplit(article.canonical_url.strip())
        valid_url = (
            parsed_url.scheme.lower() in {"http", "https"}
            and bool(parsed_url.netloc)
            and parsed_url.username is None
            and parsed_url.password is None
        )
        parsed_url.port
    except ValueError:
        valid_url = False
    if not valid_url:
        raise PersistenceValidationError(
            "Article canonical URL must be an absolute HTTP or HTTPS URL "
            "without credentials"
        )
    from app.services.news.deduplication import url_hash

    if url_hash(article.canonical_url) is None:
        raise PersistenceValidationError(
            "Article canonical URL must produce a deterministic URL hash"
        )
