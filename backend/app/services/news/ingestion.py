from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import NewsArticle, NewsArticleCompany, NewsIngestionRun, NewsSource
from app.services.news.deduplication import content_hash, url_hash
from app.services.news.providers import HttpClient
from app.services.news.source_providers import build_news_provider
from app.services.news.source_registry import (
    ContentPolicyStatus,
    NewsSourceConfig,
)
from app.services.news.entity_matching import match_article_companies
from app.services.news.types import (
    NormalizedNewsArticle,
    PersistenceValidationError,
    validate_article_for_persistence,
)


class NewsIngestionError(RuntimeError):
    """Base error for rejected or failed news ingestion."""


class NewsSourceNotEnabledError(NewsIngestionError):
    pass


class NewsSourceNotFoundError(NewsIngestionError):
    pass


class NewsSourceInactiveError(NewsIngestionError):
    pass


class NewsContentPolicyError(NewsIngestionError):
    pass


@dataclass(frozen=True, slots=True)
class NewsIngestionResult:
    provider_key: str
    run_id: int
    status: str
    articles_discovered: int
    articles_inserted: int
    articles_skipped: int
    error_message: str | None = None


def ingest_news_source(
    db: Session,
    source_config: NewsSourceConfig,
    client: HttpClient,
    *,
    allow_metadata_only: bool = False,
) -> NewsIngestionResult:
    _validate_source_config(
        source_config,
        allow_metadata_only=allow_metadata_only,
    )
    source = db.scalar(
        select(NewsSource).where(
            NewsSource.provider_key == source_config.provider_key
        )
    )
    if source is None:
        raise NewsSourceNotFoundError(
            f"News source is not registered: {source_config.provider_key}"
        )
    if not source.is_active:
        raise NewsSourceInactiveError(
            f"News source is inactive: {source_config.provider_key}"
        )

    run = NewsIngestionRun(source_id=source.id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        provider = build_news_provider(source_config)
        payload = provider.fetch(client)
        articles = provider.parse(payload)
    except Exception as error:
        return _fail_run(db, run, source_config.provider_key, _safe_error(error))

    try:
        inserted, skipped = _persist_articles(
            db,
            source_id=source.id,
            articles=articles,
            content_policy_status=source_config.content_policy_status,
        )
    except Exception as error:
        db.rollback()
        return _fail_run(db, run, source_config.provider_key, _safe_error(error))

    status = "success" if skipped == 0 else "partial_success"
    return _finish_run(
        db,
        run,
        source_config.provider_key,
        status=status,
        discovered=len(articles),
        inserted=inserted,
        skipped=skipped,
    )


def _validate_source_config(
    source_config: NewsSourceConfig,
    *,
    allow_metadata_only: bool = False,
) -> None:
    if not source_config.is_enabled:
        raise NewsSourceNotEnabledError(
            f"News source is disabled: {source_config.provider_key}"
        )
    allowed_policies = {ContentPolicyStatus.APPROVED_CONTENT_STORAGE}
    if allow_metadata_only:
        allowed_policies.add(ContentPolicyStatus.APPROVED_METADATA_ONLY)
    if source_config.content_policy_status not in allowed_policies:
        raise NewsContentPolicyError(
            f"News source content policy does not approve article storage: "
            f"{source_config.provider_key}"
        )


def _persist_articles(
    db: Session,
    *,
    source_id: int,
    articles: list[NormalizedNewsArticle],
    content_policy_status: ContentPolicyStatus,
) -> tuple[int, int]:
    existing_external_ids = {
        external_id
        for external_id in (
            article.external_id
            for article in articles
            if article.external_id
        )
    }
    existing_url_hashes = {
        article_hash
        for article_hash in (
            url_hash(article.canonical_url)
            for article in articles
            if article.canonical_url
        )
        if article_hash
    }
    existing_rows = db.scalars(
        select(NewsArticle).where(
            NewsArticle.source_id == source_id,
            NewsArticle.external_id.in_(existing_external_ids),
        )
    ).all() if existing_external_ids else []
    known_external_ids = {row.external_id for row in existing_rows if row.external_id}
    existing_rows = db.scalars(
        select(NewsArticle).where(NewsArticle.url_hash.in_(existing_url_hashes))
    ).all() if existing_url_hashes else []
    known_url_hashes = {row.url_hash for row in existing_rows}

    inserted = 0
    skipped = 0
    seen_external_ids: set[str] = set()
    seen_url_hashes: set[str] = set()

    with db.begin_nested():
        for article in articles:
            try:
                validate_article_for_persistence(article)
            except PersistenceValidationError:
                skipped += 1
                continue
            article_url_hash = url_hash(article.canonical_url)
            if (
                article_url_hash is None
                or (
                    article.external_id is not None
                    and article.external_id in known_external_ids
                )
                or article_url_hash in known_url_hashes
                or (
                    article.external_id is not None
                    and article.external_id in seen_external_ids
                )
                or article_url_hash in seen_url_hashes
            ):
                skipped += 1
                continue
            row = _to_model(
                source_id=source_id,
                article=article,
                article_url_hash=article_url_hash,
                content_policy_status=content_policy_status,
            )
            try:
                with db.begin_nested():
                    db.add(row)
                    db.flush()
                    for match in match_article_companies(
                        db,
                        row.headline,
                        row.summary,
                    ):
                        if match.is_ambiguous or match.company_id is None:
                            continue
                        db.add(
                            NewsArticleCompany(
                                article_id=row.id,
                                company_id=match.company_id,
                                match_method=match.match_method or "unknown",
                                match_confidence=match.match_confidence,
                                matched_text=match.matched_text,
                            )
                        )
                    db.flush()
            except IntegrityError:
                skipped += 1
                continue
            inserted += 1
            known_url_hashes.add(article_url_hash)
            seen_url_hashes.add(article_url_hash)
            if article.external_id:
                known_external_ids.add(article.external_id)
                seen_external_ids.add(article.external_id)
    db.commit()

    return inserted, skipped


def _to_model(
    *,
    source_id: int,
    article: NormalizedNewsArticle,
    article_url_hash: str,
    content_policy_status: ContentPolicyStatus,
) -> NewsArticle:
    stored_article = article
    if content_policy_status == ContentPolicyStatus.APPROVED_METADATA_ONLY:
        stored_article = article.model_copy(
            update={"summary": None, "author": None}
        )
    return NewsArticle(
        source_id=source_id,
        external_id=stored_article.external_id,
        canonical_url=stored_article.canonical_url,
        url_hash=article_url_hash,
        headline=stored_article.headline,
        summary=stored_article.summary,
        author=stored_article.author,
        published_at=stored_article.published_at_utc,
        language=stored_article.language,
        content_hash=content_hash(stored_article),
    )


def _finish_run(
    db: Session,
    run: NewsIngestionRun,
    provider_key: str,
    *,
    status: str,
    discovered: int,
    inserted: int,
    skipped: int,
    error_message: str | None = None,
) -> NewsIngestionResult:
    if discovered != inserted + skipped:
        raise NewsIngestionError("Ingestion count invariant was violated")
    run.status = status
    run.completed_at = datetime.now(timezone.utc)
    run.articles_discovered = discovered
    run.articles_inserted = inserted
    run.articles_skipped = skipped
    run.error_message = error_message
    source = db.get(NewsSource, run.source_id) if run.source_id is not None else None
    if source is not None:
        if status == "failed":
            source.last_error = error_message
        else:
            source.last_success_at = run.completed_at
            source.last_error = None
    db.commit()
    return NewsIngestionResult(
        provider_key=provider_key,
        run_id=run.id,
        status=status,
        articles_discovered=discovered,
        articles_inserted=inserted,
        articles_skipped=skipped,
        error_message=error_message,
    )


def _fail_run(
    db: Session,
    run: NewsIngestionRun,
    provider_key: str,
    error_message: str,
) -> NewsIngestionResult:
    return _finish_run(
        db,
        run,
        provider_key,
        status="failed",
        discovered=0,
        inserted=0,
        skipped=0,
        error_message=error_message,
    )


def _safe_error(error: Exception) -> str:
    if isinstance(error, NewsIngestionError):
        return str(error)
    if isinstance(error, PersistenceValidationError):
        return "Article persistence validation failed"
    message = str(error).splitlines()[0][:240]
    message = re.sub(r"https?://\S+", "[redacted-url]", message)
    return f"{type(error).__name__}: {message}"
