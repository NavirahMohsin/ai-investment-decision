from dataclasses import FrozenInstanceError, replace

import pytest

from app.services.news import (
    ContentPolicyStatus,
    RssAtomProvider,
    UnsupportedNewsSourceTypeError,
    build_news_provider,
    get_all_sources,
    get_enabled_sources,
    get_source,
    get_source_configs_for_registration,
    to_news_source_create,
)


RSS_FIXTURE = b"""<rss version="2.0"><channel><item>
<title>Example source article</title>
<link>https://example.com/article</link>
</item></channel></rss>"""

ATOM_FIXTURE = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>Example Atom article</title>
<id>atom-1</id><link rel="alternate" href="https://example.com/atom-1" />
</entry></feed>"""


EXPECTED_FEEDS = {
    "economic_times_markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "rbi_press_releases": "https://www.rbi.org.in/pressreleases_rss.xml",
    "rbi_notifications": "https://rbi.org.in/notifications_rss.xml",
    "rbi_speeches": "https://www.rbi.org.in/speeches_rss.xml",
    "sebi_official": "https://www.sebi.gov.in/sebirss.xml",
    "bse_notices": "https://www.bseindia.com/data/xml/notices.xml",
}


def test_registry_contains_configured_sources():
    sources = get_all_sources()

    assert tuple(source.provider_key for source in sources) == tuple(EXPECTED_FEEDS)
    assert {source.provider_key: source.feed_url for source in sources} == EXPECTED_FEEDS
    economic_times = get_source("economic_times_markets")
    assert economic_times is not None
    assert economic_times.is_enabled is True
    assert economic_times.content_policy_status == ContentPolicyStatus.APPROVED_METADATA_ONLY
    assert all(
        not source.is_enabled
        and source.content_policy_status == ContentPolicyStatus.PENDING_REVIEW
        for source in sources
        if source.provider_key != "economic_times_markets"
    )
    assert tuple(source.provider_key for source in get_enabled_sources()) == (
        "economic_times_markets",
    )


def test_registry_unknown_key_and_immutable_configs():
    assert get_source("unknown") is None
    source = get_source("rbi_press_releases")
    assert source is not None
    with pytest.raises(FrozenInstanceError):
        source.is_enabled = True
    with pytest.raises(TypeError):
        get_all_sources()[0] = source


def test_registration_mapping_preserves_disabled_state():
    source = get_source("sebi_official")
    assert source is not None

    registration = to_news_source_create(source)

    assert registration.provider_key == source.provider_key
    assert registration.name == source.name
    assert registration.source_type == source.source_type
    assert registration.base_url == source.base_url
    assert registration.feed_url == source.feed_url
    assert registration.is_active is False
    assert source.content_policy_status == ContentPolicyStatus.PENDING_REVIEW
    assert get_source_configs_for_registration() == get_all_sources()


@pytest.mark.parametrize("provider_key", EXPECTED_FEEDS)
def test_each_registered_source_builds_rss_provider(provider_key):
    source = get_source(provider_key)
    assert source is not None

    provider = build_news_provider(source)

    assert isinstance(provider, RssAtomProvider)
    assert provider.provider_key == source.provider_key
    assert provider.feed_url == source.feed_url
    assert provider.source_type == "rss"


def test_provider_parses_rss_with_source_metadata():
    source = get_source("rbi_press_releases")
    assert source is not None
    article = build_news_provider(source).parse(RSS_FIXTURE)[0]

    assert article.provider_key == source.provider_key
    assert article.source_metadata["source_name"] == source.name
    assert article.source_metadata["region"] == "IN"
    assert article.source_metadata["content_policy_status"] == "pending_review"


def test_provider_parses_atom_without_network_access():
    source = get_source("bse_notices")
    assert source is not None

    article = build_news_provider(source).parse(ATOM_FIXTURE)[0]

    assert article.headline == "Example Atom article"
    assert article.external_id == "atom-1"
    assert article.source_metadata["source_name"] == "BSE Notices"


def test_unsupported_source_type_raises_typed_error():
    source = get_source("rbi_press_releases")
    assert source is not None
    unsupported = replace(source, source_type="api")

    with pytest.raises(UnsupportedNewsSourceTypeError, match="api"):
        build_news_provider(unsupported)


def test_unknown_provider_configuration_is_handled_clearly():
    unknown = replace(
        get_all_sources()[0],
        provider_key="unknown",
        source_type="rss",
    )

    provider = build_news_provider(unknown)

    assert provider.provider_key == "unknown"
