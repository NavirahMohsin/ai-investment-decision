from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db.models import NewsArticle, NewsSource
from app.db.session import SessionLocal
from app.services.news.deduplication import content_hash, url_hash
from app.services.news.entity_matching import match_article_companies
from app.services.news.http_client import SafeFeedHttpClient
from app.services.news.ingestion import ingest_news_source
from app.services.news.ingestion import get_company_news_queries
from app.services.news.providers import GoogleNewsRssProvider
from app.services.news.source_providers import build_news_provider
from app.services.news.source_registry import NewsSourceConfig, get_enabled_sources, get_source
from app.services.news.types import validate_article_for_persistence


def _selected_sources(source_keys: list[str] | None, all_eligible: bool) -> tuple[NewsSourceConfig, ...]:
    if all_eligible:
        return get_enabled_sources()
    if not source_keys:
        raise SystemExit("Select --source at least once or use --all-eligible")
    configs: list[NewsSourceConfig] = []
    for provider_key in source_keys:
        config = get_source(provider_key)
        if config is None:
            raise SystemExit(f"Unknown news source registry key: {provider_key}")
        configs.append(config)
    return tuple(configs)


def _dry_run(db, config: NewsSourceConfig, client: SafeFeedHttpClient) -> None:
    provider = build_news_provider(config)
    if isinstance(provider, GoogleNewsRssProvider):
        articles = provider.fetch_for_companies(client, get_company_news_queries(db))
    else:
        articles = provider.parse(provider.fetch(client))
    known_urls = set(db.scalars(select(NewsArticle.url_hash)))
    source_id = db.scalar(
        select(NewsSource.id).where(
            NewsSource.provider_key == config.provider_key
        )
    )
    known_external_ids = (
        {
            external_id
            for external_id in db.scalars(
                select(NewsArticle.external_id).where(
                    NewsArticle.source_id == source_id
                )
            )
            if external_id
        }
        if source_id is not None
        else set()
    )
    inserted = 0
    skipped = 0
    invalid = 0
    matched = 0
    duplicate_urls = 0
    duplicate_external_ids = 0
    url_hashed = 0
    content_hashed = 0
    seen_urls: set[str] = set()
    seen_external_ids: set[str] = set()
    for article in articles:
        try:
            validate_article_for_persistence(article)
        except ValueError:
            invalid += 1
            skipped += 1
            continue
        article_url_hash = url_hash(article.canonical_url)
        article_content_hash = content_hash(article)
        if article_url_hash is not None:
            url_hashed += 1
        if article_content_hash is not None:
            content_hashed += 1
        url_duplicate = (
            article_url_hash is None
            or article_url_hash in known_urls
            or article_url_hash in seen_urls
        )
        external_id_duplicate = (
            article.external_id is not None
            and (
                article.external_id in known_external_ids
                or article.external_id in seen_external_ids
            )
        )
        duplicate = (
            url_duplicate or external_id_duplicate
        )
        if duplicate:
            skipped += 1
            if url_duplicate:
                duplicate_urls += 1
            if external_id_duplicate:
                duplicate_external_ids += 1
            continue
        if match_article_companies(db, article.headline, article.summary):
            matched += 1
        inserted += 1
        seen_urls.add(article_url_hash)
        if article.external_id:
            seen_external_ids.add(article.external_id)
    print(
        f"{config.provider_key}: DRY-RUN discovered={len(articles)} "
        f"valid_candidates={inserted} skipped={skipped} invalid={invalid} "
        f"duplicate_urls={duplicate_urls} "
        f"duplicate_external_ids={duplicate_external_ids} "
        f"url_hashes={url_hashed} content_hashes={content_hashed} "
        f"articles_with_company_matches={matched}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest selected registry news sources through the safe pipeline."
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        help="Registry provider key. Repeat to select multiple sources.",
    )
    parser.add_argument(
        "--all-eligible",
        action="store_true",
        help="Run every source enabled and approved in the registry.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and inspect entries without creating runs or changing data.",
    )
    parser.add_argument(
        "--allow-metadata-only",
        action="store_true",
        help="Permit explicitly approved metadata-only sources; restricted fields are discarded.",
    )
    args = parser.parse_args()
    configs = _selected_sources(args.sources, args.all_eligible)
    client = SafeFeedHttpClient()
    failures = 0
    with SessionLocal() as db:
        for config in configs:
            try:
                if args.dry_run:
                    _dry_run(db, config, client)
                else:
                    result = ingest_news_source(
                        db,
                        config,
                        client,
                        allow_metadata_only=args.allow_metadata_only,
                    )
                    print(
                        f"{config.provider_key}: {result.status} "
                        f"run_id={result.run_id} discovered={result.articles_discovered} "
                        f"inserted={result.articles_inserted} skipped={result.articles_skipped}"
                    )
                    if result.status == "failed":
                        failures += 1
            except Exception as error:
                failures += 1
                print(f"{config.provider_key}: failed ({type(error).__name__})")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
