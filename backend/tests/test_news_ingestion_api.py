from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.api.routes import v1
from app.db.models import NewsIngestionRun, NewsSource
from app.services.news.ingestion import NewsIngestionResult
from app.services.news.source_registry import ContentPolicyStatus, get_source


def enabled_config(key: str = "test_source"):
    config = get_source("rbi_press_releases")
    assert config is not None
    return replace(
        config,
        provider_key=key,
        name="Test Source",
        is_enabled=True,
        content_policy_status=ContentPolicyStatus.APPROVED_CONTENT_STORAGE,
    )


def add_source(db_session, key: str, active: bool = True):
    source = NewsSource(
        name="Test Source",
        provider_key=key,
        source_type="rss",
        feed_url="https://example.com/feed.xml",
        is_active=active,
    )
    db_session.add(source)
    db_session.commit()
    return source


def fake_ingest(db, config, client):
    run = NewsIngestionRun(
        source_id=db.scalar(
            __import__("sqlalchemy").select(NewsSource.id).where(
                NewsSource.provider_key == config.provider_key
            )
        ),
        status="success",
        articles_discovered=3,
        articles_inserted=2,
        articles_skipped=1,
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
    )
    db.add(run)
    db.commit()
    return NewsIngestionResult(
        provider_key=config.provider_key,
        run_id=run.id,
        status="partial_success",
        articles_discovered=3,
        articles_inserted=2,
        articles_skipped=1,
    )


def test_source_validation_returns_expected_conflicts(client, db_session, monkeypatch):
    monkeypatch.setattr(v1, "get_source", lambda key: None)
    assert client.post("/api/v1/news/ingestion/unknown").status_code == 404

    disabled = replace(enabled_config(), is_enabled=False)
    monkeypatch.setattr(v1, "get_source", lambda key: disabled)
    assert client.post("/api/v1/news/ingestion/test_source").status_code == 409

    pending = replace(
        enabled_config(),
        content_policy_status=ContentPolicyStatus.PENDING_REVIEW,
    )
    monkeypatch.setattr(v1, "get_source", lambda key: pending)
    assert client.post("/api/v1/news/ingestion/test_source").status_code == 409

    metadata_only = replace(
        enabled_config(),
        content_policy_status=ContentPolicyStatus.APPROVED_METADATA_ONLY,
    )
    monkeypatch.setattr(v1, "get_source", lambda key: metadata_only)
    assert client.post("/api/v1/news/ingestion/test_source").status_code == 409


def test_missing_and_inactive_database_sources_are_conflicts(client, db_session, monkeypatch):
    config = enabled_config()
    monkeypatch.setattr(v1, "get_source", lambda key: config)
    assert client.post("/api/v1/news/ingestion/test_source").status_code == 409

    add_source(db_session, "test_source", active=False)
    assert client.post("/api/v1/news/ingestion/test_source").status_code == 409


def test_trigger_serializes_existing_service_result(client, db_session, monkeypatch):
    config = enabled_config()
    add_source(db_session, "test_source")
    monkeypatch.setattr(v1, "get_source", lambda key: config)
    monkeypatch.setattr(v1, "ingest_news_source", fake_ingest)

    response = client.post("/api/v1/news/ingestion/test_source")

    assert response.status_code == 200
    assert response.json() == {
        "run_id": 1,
        "source_key": "test_source",
        "source_name": "Test Source",
        "status": "partial_success",
        "discovered_count": 3,
        "inserted_count": 2,
        "skipped_count": 1,
        "failed_count": 0,
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:01:00Z",
        "message": "News ingestion completed with skipped articles",
    }


def test_failed_result_is_not_reported_as_success(client, db_session, monkeypatch):
    config = enabled_config()
    add_source(db_session, "test_source")

    def failed_ingest(db, config, client):
        run = NewsIngestionRun(
            source_id=1,
            status="failed",
            error_message="internal URL https://secret.example/feed",
        )
        db.add(run)
        db.commit()
        return NewsIngestionResult(
            provider_key=config.provider_key,
            run_id=run.id,
            status="failed",
            articles_discovered=0,
            articles_inserted=0,
            articles_skipped=0,
            error_message="internal details",
        )

    monkeypatch.setattr(v1, "get_source", lambda key: config)
    monkeypatch.setattr(v1, "ingest_news_source", failed_ingest)
    response = client.post("/api/v1/news/ingestion/test_source")
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["message"] == "News ingestion completed with failures"


def test_internal_exception_is_sanitized_and_lock_is_released(
    client, db_session, monkeypatch
):
    config = enabled_config()
    add_source(db_session, "test_source")
    monkeypatch.setattr(v1, "get_source", lambda key: config)
    monkeypatch.setattr(
        v1,
        "ingest_news_source",
        lambda db, config, client: (_ for _ in ()).throw(
            RuntimeError("secret https://user:pass@example.com/feed")
        ),
    )
    response = client.post("/api/v1/news/ingestion/test_source")
    assert response.status_code == 500
    assert response.json()["detail"] == "News ingestion failed"
    assert v1._source_ingestion_lock("test_source").acquire(blocking=False)
    v1._source_ingestion_lock("test_source").release()


def test_same_source_lock_rejects_and_other_source_is_independent(
    client, db_session, monkeypatch
):
    first = enabled_config("first")
    second = enabled_config("second")
    add_source(db_session, "first")
    add_source(db_session, "second")
    monkeypatch.setattr(v1, "get_source", lambda key: first if key == "first" else second)
    first_lock = v1._source_ingestion_lock("first")
    second_lock = v1._source_ingestion_lock("second")
    assert first_lock.acquire(blocking=False)
    try:
        assert client.post("/api/v1/news/ingestion/first").status_code == 409
        assert second_lock.acquire(blocking=False)
        second_lock.release()
    finally:
        first_lock.release()
