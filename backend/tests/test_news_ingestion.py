from datetime import datetime, timezone

import pytest

from app.services.news import (
    FeedParseError,
    NormalizedNewsArticle,
    PersistenceValidationError,
    RssAtomProvider,
    content_hash,
    normalize_url,
    parse_feed,
    validate_article_for_persistence,
    url_hash,
)


RSS_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Example feed</title>
    <language>en-IN</language>
    <item>
      <title> Reliance announces a Unicode-first update </title>
      <link>articles/reliance?utm_source=feed&amp;id=7#fragment</link>
      <guid>article-7</guid>
      <description>A useful summary.</description>
      <dc:creator>Author Name</dc:creator>
      <pubDate>Sat, 31 Oct 2026 10:30:00 +0530</pubDate>
    </item>
  </channel>
</rss>"""

ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="hi-IN">
  <title>Example Atom</title>
  <entry>
    <title>भारतीय बाजार अपडेट</title>
    <id>tag:example.com,2026:atom-1</id>
    <link rel="self" href="/self/atom-1" />
    <link rel="alternate" href="/articles/atom-1" />
    <summary>Atom summary</summary>
    <author><name>लेखक</name></author>
    <updated>2026-10-31T05:00:00Z</updated>
  </entry>
</feed>""".encode("utf-8")


class FakeClient:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.requested_url: str | None = None

    def get(self, url: str) -> bytes:
        self.requested_url = url
        return self.payload


def test_rss_parser_extracts_namespaced_and_relative_fields():
    articles = parse_feed(
        RSS_FEED,
        feed_url="https://example.com/feed.xml",
        provider_key="example",
    )

    assert len(articles) == 1
    article = articles[0]
    assert article.external_id == "article-7"
    assert article.headline == "Reliance announces a Unicode-first update"
    assert article.summary == "A useful summary."
    assert article.author == "Author Name"
    assert article.canonical_url == "https://example.com/articles/reliance?utm_source=feed&id=7#fragment"
    assert article.language == "en-IN"
    assert article.published_at_raw == "Sat, 31 Oct 2026 10:30:00 +0530"
    assert article.published_at_utc == datetime(2026, 10, 31, 5, 0, tzinfo=timezone.utc)


def test_atom_parser_prefers_alternate_link_and_extracts_nested_author():
    article = parse_feed(
        ATOM_FEED,
        feed_url="https://example.com/atom/feed.xml",
        provider_key="atom",
    )[0]

    assert article.external_id == "tag:example.com,2026:atom-1"
    assert article.canonical_url == "https://example.com/articles/atom-1"
    assert article.author == "लेखक"
    assert article.language == "hi-IN"
    assert article.published_at_utc == datetime(2026, 10, 31, 5, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("links", "expected"),
    [
        (
            '<link rel="alternate" href="  " /><link rel="self" href="/usable" />',
            "https://example.com/usable",
        ),
        (
            '<link rel="alternate" href="/alternate" /><link rel="self" href="/self" />',
            "https://example.com/alternate",
        ),
        (
            '<link rel="self" href="/self" />',
            "https://example.com/self",
        ),
    ],
)
def test_atom_link_selection_uses_first_usable_preferred_or_fallback_link(links, expected):
    payload = f"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <title>Link test</title>{links}</entry></feed>""".encode()

    article = parse_feed(
        payload,
        feed_url="https://example.com/feed.xml",
        provider_key="atom",
    )[0]

    assert article.canonical_url == expected


def test_empty_feed_returns_empty_collection():
    payload = b"<rss version='2.0'><channel><title>Empty</title></channel></rss>"

    assert parse_feed(payload, feed_url="https://example.com/feed", provider_key="empty") == []


def test_missing_optional_fields_are_retained_without_invented_values():
    payload = b"""<rss version="2.0"><channel><item><title>Only title</title></item></channel></rss>"""

    article = parse_feed(payload, feed_url="https://example.com/feed", provider_key="minimal")[0]

    assert article.headline == "Only title"
    assert article.external_id is None
    assert article.canonical_url is None
    assert article.summary is None
    assert article.published_at_raw is None
    assert article.published_at_utc is None


def test_provider_fetches_through_injected_client_and_parses():
    client = FakeClient(RSS_FEED)
    provider = RssAtomProvider(
        provider_key="example",
        name="Example RSS",
        feed_url="https://example.com/feed.xml",
    )

    articles = provider.parse(provider.fetch(client))

    assert client.requested_url == "https://example.com/feed.xml"
    assert articles[0].provider_key == "example"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"<rss><channel><item>", "Malformed feed XML"),
        (b"<html><body>blocked</body></html>", "HTML"),
        (b"<sitemap><url /></sitemap>", "Unsupported feed XML root"),
    ],
)
def test_invalid_or_unsupported_payloads_raise_typed_error(payload, message):
    with pytest.raises(FeedParseError, match=message):
        parse_feed(payload, feed_url="https://example.com/feed", provider_key="example")


def test_timestamp_parser_leaves_naive_and_malformed_values_unavailable():
    payload = b"""<rss version="2.0"><channel>
      <item><title>Naive</title><pubDate>2026-10-31 10:00:00</pubDate></item>
      <item><title>Malformed</title><pubDate>not-a-date</pubDate></item>
    </channel></rss>"""

    articles = parse_feed(payload, feed_url="https://example.com/feed", provider_key="time")

    assert articles[0].published_at_raw == "2026-10-31 10:00:00"
    assert articles[0].published_at_utc is None
    assert articles[1].published_at_raw == "not-a-date"
    assert articles[1].published_at_utc is None


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("Sat, 31 Oct 2026 10:30:00 GMT", datetime(2026, 10, 31, 10, 30, tzinfo=timezone.utc)),
        ("Sat, 31 Oct 2026 16:00:00 +0530", datetime(2026, 10, 31, 10, 30, tzinfo=timezone.utc)),
        ("2026-10-31T10:30:00Z", datetime(2026, 10, 31, 10, 30, tzinfo=timezone.utc)),
    ],
)
def test_timestamp_parser_accepts_explicit_unambiguous_timezones(timestamp, expected):
    payload = f"""<rss version="2.0"><channel>
      <item><title>Timestamp</title><pubDate>{timestamp}</pubDate></item>
    </channel></rss>""".encode()

    article = parse_feed(
        payload,
        feed_url="https://example.com/feed",
        provider_key="time",
    )[0]

    assert article.published_at_utc == expected


def test_timestamp_parser_rejects_ambiguous_timezone_abbreviations():
    payload = b"""<rss version="2.0"><channel>
      <item><title>Timestamp</title><pubDate>Sat, 31 Oct 2026 10:30:00 CST</pubDate></item>
    </channel></rss>"""

    article = parse_feed(
        payload,
        feed_url="https://example.com/feed",
        provider_key="time",
    )[0]

    assert article.published_at_raw.endswith("CST")
    assert article.published_at_utc is None


def test_url_normalization_removes_fragment_and_preserves_query_parameters():
    first = "HTTPS://Example.com:443/article?b=2&a=1#comments"
    second = "https://example.com/article?b=2&a=1"

    assert normalize_url(first) == second
    assert url_hash(first) == url_hash(second)
    assert "a=1" in normalize_url(first)
    assert "b=2" in normalize_url(first)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "https://Example.com/article?a=1&a=2#fragment",
            "https://example.com/article?a=1&a=2",
        ),
        (
            "https://example.com/article?path=%2F",
            "https://example.com/article?path=%2F",
        ),
        (
            "https://example.com/article?path=/",
            "https://example.com/article?path=/",
        ),
        (
            "https://example.com/article?q=a+b",
            "https://example.com/article?q=a+b",
        ),
        (
            "https://example.com/article?q=a%20b",
            "https://example.com/article?q=a%20b",
        ),
        (
            "https://example.com/article?a=1;b=2",
            "https://example.com/article?a=1;b=2",
        ),
        (
            "https://[2001:DB8::1]:443/article",
            "https://[2001:db8::1]/article",
        ),
        (
            "http://example.com:80/article",
            "http://example.com/article",
        ),
    ],
)
def test_url_normalization_preserves_query_and_handles_authority(value, expected):
    assert normalize_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com:invalid/article",
        "https://user:secret@example.com/article",
        "/relative/article",
        "relative/article",
    ],
)
def test_url_normalization_rejects_unsafe_or_non_global_urls(value):
    assert normalize_url(value) is None
    assert url_hash(value) is None


def test_missing_url_does_not_create_url_hash():
    assert url_hash(None) is None
    assert url_hash("") is None


def test_content_hash_is_stable_and_distinguishes_articles():
    article = NormalizedNewsArticle(
        provider_key="example",
        headline="  Market   Update ",
        summary="The market closed higher.",
        canonical_url="https://example.com/article#top",
        external_id="article-1",
        published_at_raw="Sat, 31 Oct 2026 10:30:00 +0530",
        published_at_utc=datetime(2026, 10, 31, 10, 30, tzinfo=timezone.utc),
    )
    equivalent = article.model_copy(update={"headline": "market update"})
    different = article.model_copy(update={"summary": "The market closed lower."})

    assert content_hash(article) == content_hash(equivalent)
    assert content_hash(article) != content_hash(different)
    assert content_hash(article) == content_hash(article)


@pytest.mark.parametrize(
    "article",
    [
        NormalizedNewsArticle(provider_key="example", headline=None, canonical_url="https://example.com/1"),
        NormalizedNewsArticle(
            provider_key="example",
            headline="Only headline",
            published_at_utc=datetime(2026, 10, 31, 10, 30, tzinfo=timezone.utc),
        ),
        NormalizedNewsArticle(
            provider_key="example",
            headline="Headline",
            summary="Summary",
            published_at_utc=datetime(2026, 10, 31, 10, 30, tzinfo=timezone.utc),
        ),
        NormalizedNewsArticle(
            provider_key="example",
            headline="Headline",
            summary="Summary",
            canonical_url="https://example.com/one",
            published_at_utc=datetime(2026, 10, 31, 10, 30, tzinfo=timezone.utc),
        ),
    ],
)
def test_content_hash_avoids_ambiguous_missing_field_hashes(article):
    if article.headline and article.summary and article.published_at_utc:
        assert content_hash(article) is not None
    else:
        assert content_hash(article) is None


def test_content_hash_does_not_use_url_or_provider_scoped_external_id():
    base = NormalizedNewsArticle(
        provider_key="one",
        headline="Market update",
        summary="The market closed higher.",
        canonical_url="https://one.example/article",
        external_id="provider-one-id",
        published_at_utc=datetime(2026, 10, 31, 10, 30, tzinfo=timezone.utc),
    )
    equivalent = base.model_copy(
        update={
            "provider_key": "two",
            "canonical_url": "https://two.example/article",
            "external_id": "provider-two-id",
        }
    )

    assert content_hash(base) == content_hash(equivalent)


def test_persistence_validation_requires_database_compatible_identity():
    valid = NormalizedNewsArticle(
        provider_key="example",
        headline="Market update",
        canonical_url="https://example.com/article",
    )
    validate_article_for_persistence(valid)

    invalid_articles = [
        valid.model_copy(update={"headline": " "}),
        valid.model_copy(update={"canonical_url": None}),
        valid.model_copy(update={"canonical_url": "/relative"}),
        valid.model_copy(update={"canonical_url": "ftp://example.com/article"}),
        valid.model_copy(update={"canonical_url": "https://user:secret@example.com/article"}),
    ]
    for article in invalid_articles:
        with pytest.raises(PersistenceValidationError):
            validate_article_for_persistence(article)
