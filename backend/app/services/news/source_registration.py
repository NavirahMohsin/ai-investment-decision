from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import NewsSource
from app.services.news.source_registry import (
    ContentPolicyStatus,
    NewsSourceConfig,
)


class NewsSourceActivationError(ValueError):
    """Raised when a source does not satisfy explicit activation requirements."""


@dataclass(frozen=True, slots=True)
class NewsSourceRegistrationResult:
    provider_key: str
    source_id: int
    created: bool
    is_active: bool


def register_news_source(
    db: Session,
    config: NewsSourceConfig,
) -> NewsSourceRegistrationResult:
    """Register or refresh source metadata without changing existing activation."""
    source = db.scalar(
        select(NewsSource).where(NewsSource.provider_key == config.provider_key)
    )
    created = source is None
    if source is None:
        source = NewsSource(
            name=config.name,
            provider_key=config.provider_key,
            source_type=config.source_type,
            base_url=config.base_url,
            feed_url=config.feed_url,
            attribution_text=config.attribution_text,
            is_active=False,
        )
        db.add(source)
    else:
        source.name = config.name
        source.source_type = config.source_type
        source.base_url = config.base_url
        source.feed_url = config.feed_url
        if config.attribution_text:
            source.attribution_text = config.attribution_text
    db.commit()
    db.refresh(source)
    return NewsSourceRegistrationResult(
        provider_key=config.provider_key,
        source_id=source.id,
        created=created,
        is_active=source.is_active,
    )


def register_news_sources(
    db: Session,
    configs: Iterable[NewsSourceConfig],
) -> list[NewsSourceRegistrationResult]:
    results = [register_news_source(db, config) for config in configs]
    return results


def activate_news_source(
    db: Session,
    config: NewsSourceConfig,
    *,
    feed_verified: bool,
    attribution_text: str | None,
    explicitly_approved: bool,
    allow_metadata_only: bool = False,
) -> NewsSourceRegistrationResult:
    if not config.is_enabled:
        raise NewsSourceActivationError("Source configuration is disabled")
    allowed_policies = {ContentPolicyStatus.APPROVED_CONTENT_STORAGE}
    if allow_metadata_only:
        allowed_policies.add(ContentPolicyStatus.APPROVED_METADATA_ONLY)
    if config.content_policy_status not in allowed_policies:
        raise NewsSourceActivationError(
            "Source policy does not approve content storage"
        )
    if not feed_verified:
        raise NewsSourceActivationError("Source feed has not been verified")
    if not attribution_text or not attribution_text.strip():
        raise NewsSourceActivationError("Source attribution is required")
    if not explicitly_approved:
        raise NewsSourceActivationError("Explicit source approval is required")

    result = register_news_source(db, config)
    source = db.get(NewsSource, result.source_id)
    if source is None:
        raise NewsSourceActivationError("Registered source could not be reloaded")
    source.is_active = True
    source.attribution_text = attribution_text.strip()
    db.commit()
    return NewsSourceRegistrationResult(
        provider_key=result.provider_key,
        source_id=source.id,
        created=result.created,
        is_active=True,
    )
