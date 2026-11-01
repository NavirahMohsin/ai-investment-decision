from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.schemas.news import NewsSourceCreate


class ContentPolicyStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED_METADATA_ONLY = "approved_metadata_only"
    APPROVED_CONTENT_STORAGE = "approved_content_storage"


@dataclass(frozen=True, slots=True)
class NewsSourceConfig:
    provider_key: str
    name: str
    source_type: str
    feed_url: str
    base_url: str
    language: str
    region: str
    is_enabled: bool
    description: str
    content_policy_status: ContentPolicyStatus
    attribution_text: str | None = None


_SOURCE_CONFIGS: tuple[NewsSourceConfig, ...] = (
    NewsSourceConfig(
        provider_key="google_news_search",
        name="Google News RSS Search",
        source_type="google_news_rss",
        feed_url="https://news.google.com/rss/search",
        base_url="https://news.google.com",
        language="en-IN",
        region="IN",
        is_enabled=True,
        description="Company-specific Indian financial news search results.",
        content_policy_status=ContentPolicyStatus.APPROVED_METADATA_ONLY,
        attribution_text="Source: Google News",
    ),
    NewsSourceConfig(
        provider_key="economic_times_markets",
        name="The Economic Times",
        source_type="rss",
        feed_url="https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        base_url="https://economictimes.indiatimes.com",
        language="en-IN",
        region="IN",
        is_enabled=True,
        description="Indian markets, stocks, earnings and financial news.",
        content_policy_status=ContentPolicyStatus.APPROVED_METADATA_ONLY,
        attribution_text="Source: The Economic Times",
    ),
    NewsSourceConfig(
        provider_key="rbi_press_releases",
        name="RBI Press Releases",
        source_type="rss",
        feed_url="https://www.rbi.org.in/pressreleases_rss.xml",
        base_url="https://www.rbi.org.in",
        language="en-IN",
        region="IN",
        is_enabled=False,
        description="Reserve Bank of India press releases.",
        content_policy_status=ContentPolicyStatus.PENDING_REVIEW,
    ),
    NewsSourceConfig(
        provider_key="rbi_notifications",
        name="RBI Notifications",
        source_type="rss",
        feed_url="https://rbi.org.in/notifications_rss.xml",
        base_url="https://rbi.org.in",
        language="en-IN",
        region="IN",
        is_enabled=False,
        description="Reserve Bank of India notifications.",
        content_policy_status=ContentPolicyStatus.PENDING_REVIEW,
    ),
    NewsSourceConfig(
        provider_key="rbi_speeches",
        name="RBI Speeches",
        source_type="rss",
        feed_url="https://www.rbi.org.in/speeches_rss.xml",
        base_url="https://www.rbi.org.in",
        language="en-IN",
        region="IN",
        is_enabled=False,
        description="Reserve Bank of India speeches and addresses.",
        content_policy_status=ContentPolicyStatus.PENDING_REVIEW,
    ),
    NewsSourceConfig(
        provider_key="sebi_official",
        name="SEBI Official Updates",
        source_type="rss",
        feed_url="https://www.sebi.gov.in/sebirss.xml",
        base_url="https://www.sebi.gov.in",
        language="en-IN",
        region="IN",
        is_enabled=False,
        description="Securities and Exchange Board of India official updates.",
        content_policy_status=ContentPolicyStatus.PENDING_REVIEW,
    ),
    NewsSourceConfig(
        provider_key="bse_notices",
        name="BSE Notices",
        source_type="rss",
        feed_url="https://www.bseindia.com/data/xml/notices.xml",
        base_url="https://www.bseindia.com",
        language="en-IN",
        region="IN",
        is_enabled=False,
        description="BSE notices and exchange disclosures.",
        content_policy_status=ContentPolicyStatus.PENDING_REVIEW,
    ),
)


def get_all_sources() -> tuple[NewsSourceConfig, ...]:
    return _SOURCE_CONFIGS


def get_source(provider_key: str) -> NewsSourceConfig | None:
    return next(
        (source for source in _SOURCE_CONFIGS if source.provider_key == provider_key),
        None,
    )


def get_enabled_sources() -> tuple[NewsSourceConfig, ...]:
    return tuple(source for source in _SOURCE_CONFIGS if source.is_enabled)


def get_source_configs_for_registration() -> tuple[NewsSourceConfig, ...]:
    return _SOURCE_CONFIGS


def to_news_source_create(source: NewsSourceConfig) -> NewsSourceCreate:
    return NewsSourceCreate(
        name=source.name,
        provider_key=source.provider_key,
        source_type=source.source_type,
        base_url=source.base_url,
        feed_url=source.feed_url,
        is_active=source.is_enabled,
    )
