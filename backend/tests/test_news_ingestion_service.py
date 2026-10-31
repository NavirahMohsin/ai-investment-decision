from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import select
from app.db.models import NewsArticle, NewsIngestionRun, NewsSource
from app.services.news import (
    ContentPolicyStatus,
    NewsContentPolicyError,
    NewsSourceInactiveError,
    NewsSourceNotEnabledError,
    NewsSourceNotFoundError,
    get_source,
    ingest_news_source,
)


RSS = b"""<rss version="2.0"><channel>
<item><title>First article</title><link>https://example.com/one</link><guid>one</guid></item>
<item><title>Second article</title><link>https://example.com/two</link><guid>two</guid></item>
</channel></rss>"""

ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>Atom article</title><id>atom-1</id><link rel="alternate" href="https://example.com/atom" />
</entry></feed>"""


class FakeClient:
    def __init__(self, payload: bytes | None = RSS, error: Exception | None = None):
        self.payload = payload
        self.error = error

    def get(self, url: str) -> bytes:
        if self.error:
            raise self.error
        assert self.payload is not None
        return self.payload


def enabled_config(provider_key="test_source"):
    source = get_source("rbi_press_releases")
    assert source is not None
    return replace(
        source,
        provider_key=provider_key,
        name="Test Source",
        feed_url="https://example.com/feed.xml",
        base_url="https://example.com",
        is_enabled=True,
        content_policy_status=ContentPolicyStatus.APPROVED_CONTENT_STORAGE,
    )


def add_db_source(db_session, config, active=True):
    source = NewsSource(
        name=config.name,
        provider_key=config.provider_key,
        source_type=config.source_type,
        base_url=config.base_url,
        feed_url=config.feed_url,
        is_active=active,
    )
    db_session.add(source)
    db_session.commit()
    return source


def run_row(db_session, run_id):
    return db_session.scalar(
        select(NewsIngestionRun).where(NewsIngestionRun.id == run_id)
    )


def test_source_guards_reject_disabled_policy_missing_and_inactive(db_session):
    disabled = replace(enabled_config(), is_enabled=False)
    with pytest.raises(NewsSourceNotEnabledError):
        ingest_news_source(db_session, disabled, FakeClient())

    pending = replace(
        enabled_config(),
        content_policy_status=ContentPolicyStatus.PENDING_REVIEW,
    )
    with pytest.raises(NewsContentPolicyError):
        ingest_news_source(db_session, pending, FakeClient())

    metadata_only = replace(
        enabled_config(),
        content_policy_status=ContentPolicyStatus.APPROVED_METADATA_ONLY,
    )
    with pytest.raises(NewsContentPolicyError):
        ingest_news_source(db_session, metadata_only, FakeClient())

    with pytest.raises(NewsSourceNotFoundError):
        ingest_news_source(db_session, enabled_config("missing"), FakeClient())

    add_db_source(db_session, enabled_config("inactive"), active=False)
    with pytest.raises(NewsSourceInactiveError):
        ingest_news_source(
            db_session,
            enabled_config("inactive"),
            FakeClient(),
        )


def test_rss_ingestion_persists_articles_and_accurate_counts(db_session):
    config = enabled_config()
    source = add_db_source(db_session, config)

    result = ingest_news_source(db_session, config, FakeClient(RSS))

    assert result.run_id > 0
    assert result.status == "success"
    assert result.articles_discovered == 2
    assert result.articles_inserted == 2
    assert result.articles_skipped == 0
    assert result.articles_discovered == result.articles_inserted + result.articles_skipped
    articles = db_session.scalars(
        select(NewsArticle).where(NewsArticle.source_id == source.id)
    ).all()
    assert len(articles) == 2
    run = run_row(db_session, result.run_id)
    assert run is not None
    assert run.completed_at is not None
    assert run.status == "success"


def test_metadata_only_ingestion_discards_restricted_fields(db_session):
    config = replace(
        enabled_config(),
        content_policy_status=ContentPolicyStatus.APPROVED_METADATA_ONLY,
    )
    add_db_source(db_session, config)

    result = ingest_news_source(
        db_session,
        config,
        FakeClient(RSS),
        allow_metadata_only=True,
    )

    assert result.status == "success"
    article = db_session.scalar(select(NewsArticle))
    assert article is not None
    assert article.headline == "First article"
    assert article.summary is None
    assert article.author is None


def test_atom_ingestion_and_empty_feed_succeed(db_session):
    config = enabled_config()
    add_db_source(db_session, config)
    result = ingest_news_source(db_session, config, FakeClient(ATOM))
    assert result.status == "success"
    assert result.articles_inserted == 1

    empty_config = enabled_config("empty")
    add_db_source(db_session, empty_config)
    empty = ingest_news_source(
        db_session,
        empty_config,
        FakeClient(b"<rss><channel /></rss>"),
    )
    assert empty.status == "success"
    assert empty.articles_discovered == 0
    assert empty.articles_inserted == 0


def test_duplicate_external_id_url_and_feed_entries_are_skipped(db_session):
    config = enabled_config()
    add_db_source(db_session, config)
    first = ingest_news_source(db_session, config, FakeClient(RSS))
    assert first.articles_inserted == 2

    duplicate = ingest_news_source(db_session, config, FakeClient(RSS))
    assert duplicate.status == "partial_success"
    assert duplicate.articles_discovered == 2
    assert duplicate.articles_inserted == 0
    assert duplicate.articles_skipped == 2

    duplicate_feed = RSS.replace(
        b"</channel>",
        b"<item><title>First article</title><link>https://example.com/one</link></item></channel>",
    )
    duplicate_result = ingest_news_source(
        db_session,
        config,
        FakeClient(duplicate_feed),
    )
    assert duplicate_result.articles_inserted == 0
    assert duplicate_result.articles_skipped == 3


def test_invalid_articles_are_skipped_and_counted(db_session):
    config = enabled_config()
    add_db_source(db_session, config)
    invalid = b"""<rss><channel>
    <item><title></title><link>https://example.com/invalid</link></item>
    <item><title>Invalid URL</title><link>https://user:secret@example.com/invalid</link></item>
    <item><title>Valid</title><link>https://example.com/valid</link></item>
    </channel></rss>"""

    result = ingest_news_source(db_session, config, FakeClient(invalid))

    assert result.status == "partial_success"
    assert result.articles_discovered == 3
    assert result.articles_inserted == 1
    assert result.articles_skipped == 2


@pytest.mark.parametrize(
    "error",
    [TimeoutError("timeout at https://user:secret@example.com/feed"), ValueError("malformed feed")],
)
def test_fetch_or_parse_failures_finalize_failed_run(db_session, error):
    config = enabled_config()
    add_db_source(db_session, config)
    result = ingest_news_source(db_session, config, FakeClient(error=error))

    assert result.status == "failed"
    assert result.articles_discovered == 0
    assert result.articles_inserted == 0
    assert result.articles_skipped == 0
    assert result.error_message is not None
    assert "secret" not in result.error_message
    run = run_row(db_session, result.run_id)
    assert run is not None
    assert run.status == "failed"
    assert run.completed_at is not None


def test_existing_article_fields_are_not_overwritten(db_session):
    config = enabled_config()
    add_db_source(db_session, config)
    ingest_news_source(db_session, config, FakeClient(RSS))
    changed = RSS.replace(b"First article", b"Changed headline")

    ingest_news_source(db_session, config, FakeClient(changed))

    article = db_session.scalar(
        select(NewsArticle).where(NewsArticle.external_id == "one")
    )
    assert article is not None
    assert article.headline == "First article"


def test_integrity_failure_rolls_back_article_batch(db_session, monkeypatch):
    config = enabled_config()
    add_db_source(db_session, config)

    calls = 0

    import app.services.news.ingestion as ingestion_module

    original_to_model = ingestion_module._to_model

    def failing_to_model(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("database failure")
        return original_to_model(*args, **kwargs)

    monkeypatch.setattr(ingestion_module, "_to_model", failing_to_model)
    result = ingest_news_source(db_session, config, FakeClient(RSS))

    assert result.status == "failed"
    assert db_session.scalars(select(NewsArticle)).all() == []
