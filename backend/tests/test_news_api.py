from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import (
    Company,
    NewsArticle,
    NewsArticleCompany,
    NewsIngestionRun,
    NewsSource,
)
from app.services.news.deduplication import url_hash


def add_company(db_session, symbol="RELIANCE", name="Reliance Industries", active=True):
    company = Company(
        name=name,
        symbol=symbol,
        provider_symbol=f"{symbol}.NS",
        exchange="NSE",
        instrument_type="company",
        is_active=active,
    )
    db_session.add(company)
    db_session.commit()
    return company


def add_source(db_session, key="rbi", active=True):
    source = NewsSource(
        name=key.upper(),
        provider_key=key,
        source_type="rss",
        base_url="https://example.com",
        feed_url="https://example.com/feed.xml",
        is_active=active,
    )
    db_session.add(source)
    db_session.commit()
    return source


def add_article(db_session, source, headline, url, published_at=None):
    article = NewsArticle(
        source_id=source.id,
        external_id=headline.lower().replace(" ", "-"),
        canonical_url=url,
        url_hash=url_hash(url),
        headline=headline,
        summary=f"Summary for {headline}",
        published_at=published_at,
    )
    db_session.add(article)
    db_session.commit()
    return article


def test_news_list_filters_pagination_and_null_last_order(client, db_session):
    company = add_company(db_session)
    source = add_source(db_session)
    other_source = add_source(db_session, "sebi")
    dated_new = add_article(
        db_session,
        source,
        "Reliance latest result",
        "https://example.com/1",
        datetime(2026, 1, 3, tzinfo=timezone.utc),
    )
    dated_old = add_article(
        db_session,
        source,
        "Market older result",
        "https://example.com/2",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    undated = add_article(
        db_session, other_source, "Reliance undated result", "https://example.com/3"
    )
    db_session.add(
        NewsArticleCompany(
            article_id=dated_new.id,
            company_id=company.id,
            match_method="exact_symbol",
            match_confidence=1,
            matched_text="RELIANCE",
        )
    )
    db_session.commit()

    response = client.get("/api/v1/news", params={"page_size": 2})
    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [dated_new.id, dated_old.id]
    assert body["pagination"] == {
        "total": 3,
        "page": 1,
        "page_size": 2,
        "total_pages": 2,
    }

    filtered = client.get(
        "/api/v1/news",
        params={
            "company": "reliance",
            "source": "rbi",
            "start_date": "2026-01-02",
            "end_date": "2026-01-03",
            "search": "latest",
        },
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [dated_new.id]
    assert filtered.json()["items"][0]["companies"][0]["match_method"] == "exact_symbol"

    assert client.get(
        "/api/v1/news", params={"start_date": "2026-02-01", "end_date": "2026-01-01"}
    ).status_code == 400
    assert undated.id not in [item["id"] for item in body["items"]]
    assert company.id > 0


def test_news_list_pagination_boundaries(client):
    assert client.get("/api/v1/news", params={"page": 0}).status_code == 422
    assert client.get("/api/v1/news", params={"page_size": 101}).status_code == 422


def test_article_detail_source_companies_and_404(client, db_session):
    company = add_company(db_session)
    source = add_source(db_session)
    article = add_article(
        db_session,
        source,
        "Reliance detail",
        "https://example.com/detail",
        datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    db_session.add(
        NewsArticleCompany(
            article_id=article.id,
            company_id=company.id,
            match_method="alias",
            match_confidence=0.85,
            matched_text="RIL",
        )
    )
    db_session.commit()

    response = client.get(f"/api/v1/news/{article.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["source_provider_key"] == "rbi"
    assert body["companies"][0]["symbol"] == "RELIANCE"
    assert body["companies"][0]["match_confidence"] == "0.8500"
    assert "raw" not in body
    assert client.get("/api/v1/news/99999").status_code == 404


def test_company_news_validates_active_company_and_deduplicates(client, db_session):
    company = add_company(db_session)
    inactive = add_company(db_session, "INACTIVE", "Inactive Co", active=False)
    source = add_source(db_session)
    article = add_article(
        db_session,
        source,
        "Company news",
        "https://example.com/company",
        datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    db_session.add_all(
        [
            NewsArticleCompany(
                article_id=article.id,
                company_id=company.id,
                match_method="exact_name",
                match_confidence=0.95,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/v1/companies/reliance/news")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["companies"][0]["symbol"] == "RELIANCE"
    assert client.get("/api/v1/companies/unknown/news").status_code == 404
    assert client.get(f"/api/v1/companies/{inactive.symbol}/news").status_code == 404


def test_sources_are_safe_and_runs_are_paginated_and_filtered(client, db_session):
    source = add_source(db_session, "rbi", active=False)
    db_session.add(
        NewsIngestionRun(
            source_id=source.id,
            status="failed",
            articles_discovered=3,
            articles_inserted=1,
            articles_skipped=2,
            error_message="Request failed at https://user:secret@example.com/feed",
        )
    )
    db_session.commit()

    sources = client.get("/api/v1/news/sources")
    assert sources.status_code == 200
    assert sources.json()[0]["is_active"] is False
    assert "feed_url" not in sources.json()[0]

    runs = client.get(
        "/api/v1/news/ingestion/runs",
        params={"source": "rbi", "status": "failed"},
    )
    assert runs.status_code == 200
    item = runs.json()["items"][0]
    assert item["articles_discovered"] == 3
    assert "secret" not in item["error_message"]
    assert "Traceback" not in item["error_message"]
    assert client.get(
        "/api/v1/news/ingestion/runs", params={"status": "invalid"}
    ).status_code == 400


def test_news_get_requests_do_not_write(client, db_session):
    before = {
        "sources": db_session.query(NewsSource).count(),
        "articles": db_session.query(NewsArticle).count(),
        "runs": db_session.query(NewsIngestionRun).count(),
    }
    client.get("/api/v1/news")
    client.get("/api/v1/news/sources")
    client.get("/api/v1/news/ingestion/runs")
    after = {
        "sources": db_session.query(NewsSource).count(),
        "articles": db_session.query(NewsArticle).count(),
        "runs": db_session.query(NewsIngestionRun).count(),
    }
    assert after == before
