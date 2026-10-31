from __future__ import annotations

from app.services.news.providers import NewsProvider, RssAtomProvider
from app.services.news.source_registry import NewsSourceConfig


class UnsupportedNewsSourceTypeError(ValueError):
    """Raised when a source has no provider adapter implementation."""


def build_news_provider(source_config: NewsSourceConfig) -> NewsProvider:
    if source_config.source_type != "rss":
        raise UnsupportedNewsSourceTypeError(
            f"Unsupported news source type: {source_config.source_type}"
        )
    return RssAtomProvider(
        provider_key=source_config.provider_key,
        name=source_config.name,
        feed_url=source_config.feed_url,
        source_metadata={
            "source_name": source_config.name,
            "language": source_config.language,
            "region": source_config.region,
            "content_policy_status": source_config.content_policy_status.value,
        },
    )
