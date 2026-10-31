from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Company,
    CompanyAlias,
    NewsArticle,
    NewsArticleCompany,
    NewsIngestionRun,
    NewsSource,
)


def add_source(db_session):
    source = NewsSource(
        name="Example Feed",
        provider_key="example_feed",
        source_type="rss",
        feed_url="https://example.com/feed.xml",
    )
    db_session.add(source)
    db_session.commit()
    return source


def add_article(db_session, source, url_hash="a" * 64, external_id=None):
    article = NewsArticle(
        source_id=source.id,
        external_id=external_id,
        canonical_url=f"https://example.com/articles/{url_hash}",
        url_hash=url_hash,
        headline="Example market headline",
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(article)
    db_session.commit()
    return article


def add_company(db_session):
    company = Company(
        name="Example Industries",
        symbol="EXAMPLE",
        provider_symbol="EXAMPLE.NS",
        exchange="NSE",
        instrument_type="company",
    )
    db_session.add(company)
    db_session.commit()
    return company


def test_news_source_and_article_creation(db_session):
    source = add_source(db_session)
    article = add_article(db_session, source)

    assert source.provider_key == "example_feed"
    assert article.source_id == source.id
    assert article.discovered_at.tzinfo is not None


def test_news_source_provider_key_is_unique(db_session):
    add_source(db_session)
    db_session.add(NewsSource(name="Duplicate", provider_key="example_feed", source_type="api"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_url_hash_is_unique(db_session):
    source = add_source(db_session)
    add_article(db_session, source)
    db_session.add(
        NewsArticle(
            source_id=source.id,
            canonical_url="https://example.com/other",
            url_hash="a" * 64,
            headline="Duplicate URL hash",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_external_id_is_unique_per_source_and_nullable(db_session):
    source = add_source(db_session)
    add_article(db_session, source, url_hash="b" * 64, external_id="external-1")
    db_session.add(
        NewsArticle(
            source_id=source.id,
            external_id="external-1",
            canonical_url="https://example.com/duplicate-external",
            url_hash="c" * 64,
            headline="Duplicate external ID",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    add_article(db_session, source, url_hash="d" * 64)
    add_article(db_session, source, url_hash="e" * 64)


def test_article_company_link_and_duplicate_prevention(db_session):
    source = add_source(db_session)
    article = add_article(db_session, source)
    company = add_company(db_session)
    link = NewsArticleCompany(
        article_id=article.id,
        company_id=company.id,
        match_method="exact_name",
        match_confidence=Decimal("0.9000"),
        matched_text="Example Industries",
    )
    db_session.add(link)
    db_session.commit()
    assert link.match_confidence == Decimal("0.9000")

    db_session.add(
        NewsArticleCompany(
            article_id=article.id,
            company_id=company.id,
            match_method="alias",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_company_alias_link_and_duplicate_prevention(db_session):
    company = add_company(db_session)
    alias = CompanyAlias(
        company_id=company.id,
        alias="Example",
        normalized_alias="example",
        alias_type="common_name",
    )
    db_session.add(alias)
    db_session.commit()
    assert alias.company_id == company.id

    db_session.add(
        CompanyAlias(
            company_id=company.id,
            alias="EXAMPLE",
            normalized_alias="example",
            alias_type="ticker",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_news_ingestion_run_status_and_counts(db_session):
    source = add_source(db_session)
    run = NewsIngestionRun(
        source_id=source.id,
        status="partial_success",
        articles_discovered=4,
        articles_inserted=2,
        articles_updated=1,
        articles_skipped=1,
    )
    db_session.add(run)
    db_session.commit()
    assert run.status == "partial_success"
    assert run.articles_discovered == 4


def test_news_foreign_keys_are_declared(db_session):
    source = add_source(db_session)
    article = add_article(db_session, source)
    company = add_company(db_session)
    assert NewsArticle.__table__.c.source_id.foreign_keys
    assert NewsArticleCompany.__table__.c.article_id.foreign_keys
    assert NewsArticleCompany.__table__.c.company_id.foreign_keys
    assert CompanyAlias.__table__.c.company_id.foreign_keys
    assert NewsIngestionRun.__table__.c.source_id.foreign_keys
    assert article.source_id == source.id
    assert company.id > 0


def test_invalid_article_source_is_rejected_by_sqlite(db_session):
    db_session.add(
        NewsArticle(
            source_id=999999,
            canonical_url="https://example.com/missing-source",
            url_hash="f" * 64,
            headline="Invalid source",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_invalid_article_company_is_rejected_by_sqlite(db_session):
    source = add_source(db_session)
    article = add_article(db_session, source)
    db_session.add(
        NewsArticleCompany(
            article_id=article.id,
            company_id=999999,
            match_method="exact_name",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_source_cascades_articles(db_session):
    source = add_source(db_session)
    article = add_article(db_session, source)
    article_id = article.id
    db_session.delete(source)
    db_session.commit()
    db_session.expire_all()

    assert db_session.get(NewsArticle, article_id) is None


def test_deleting_source_sets_ingestion_run_source_to_null(db_session):
    source = add_source(db_session)
    run = NewsIngestionRun(source_id=source.id, status="running")
    db_session.add(run)
    db_session.commit()

    db_session.delete(source)
    db_session.commit()
    db_session.expire(run)

    assert run.source_id is None


def test_news_timestamps_round_trip_as_aware_utc(db_session):
    source = add_source(db_session)
    article = add_article(db_session, source)
    db_session.expire(article)
    db_session.refresh(article)

    assert article.created_at.tzinfo == timezone.utc
    assert article.discovered_at.tzinfo == timezone.utc


def test_non_utc_timestamp_is_normalized_on_round_trip(db_session):
    source = add_source(db_session)
    timestamp = datetime(
        2025, 1, 15, 16, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))
    )
    article = NewsArticle(
        source_id=source.id,
        canonical_url="https://example.com/non-utc-time",
        url_hash="g" * 64,
        headline="Timezone test",
        published_at=timestamp,
    )
    db_session.add(article)
    db_session.commit()
    db_session.expire(article)

    assert article.published_at == datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc)
    assert article.published_at.tzinfo == timezone.utc


def test_naive_timestamp_is_interpreted_as_utc(db_session):
    source = add_source(db_session)
    naive_timestamp = datetime(2025, 1, 15, 10, 30)
    article = NewsArticle(
        source_id=source.id,
        canonical_url="https://example.com/naive-time",
        url_hash="h" * 64,
        headline="Naive timezone test",
        published_at=naive_timestamp,
    )
    db_session.add(article)
    db_session.commit()
    db_session.expire(article)

    assert article.published_at == naive_timestamp.replace(tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "invalid"),
        ("articles_discovered", -1),
        ("articles_inserted", -1),
        ("articles_updated", -1),
        ("articles_skipped", -1),
    ],
)
def test_ingestion_run_constraints_reject_invalid_values(db_session, field, value):
    source = add_source(db_session)
    values = {
        "source_id": source.id,
        "status": "running",
        "articles_discovered": 0,
        "articles_inserted": 0,
        "articles_updated": 0,
        "articles_skipped": 0,
    }
    values[field] = value
    db_session.add(NewsIngestionRun(**values))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("confidence", [Decimal("-0.0001"), Decimal("1.0001")])
def test_article_company_confidence_constraint_rejects_out_of_range(db_session, confidence):
    source = add_source(db_session)
    article = add_article(db_session, source)
    company = add_company(db_session)
    db_session.add(
        NewsArticleCompany(
            article_id=article.id,
            company_id=company.id,
            match_method="exact_name",
            match_confidence=confidence,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
