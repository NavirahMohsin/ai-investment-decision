from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import NewsArticle, NewsSource
from app.services.news.deduplication import content_hash as normalized_content_hash
from app.services.news.deduplication import url_hash
from app.services.news.types import NormalizedNewsArticle


@dataclass(frozen=True, slots=True)
class ArticleDuplicateResult:
    status: str
    matching_article_ids: tuple[int, ...] = ()
    reason: str | None = None

    @property
    def is_duplicate(self) -> bool:
        return self.status == "duplicate"

    @property
    def is_uncertain(self) -> bool:
        return self.status == "uncertain"


def find_cross_source_duplicates(
    db: Session,
    article: NewsArticle | NormalizedNewsArticle,
) -> ArticleDuplicateResult:
    article_url_hash = (
        article.url_hash
        if isinstance(article, NewsArticle)
        else url_hash(article.canonical_url)
    )
    article_content_hash = (
        article.content_hash
        if isinstance(article, NewsArticle)
        else normalized_content_hash(article)
    )
    source_id = article.source_id if isinstance(article, NewsArticle) else db.scalar(
        select(NewsSource.id).where(
            NewsSource.provider_key == article.provider_key
        )
    )
    query = select(NewsArticle)
    if source_id is not None:
        query = query.where(NewsArticle.source_id != source_id)
    candidates = db.scalars(query).all()
    url_matches = [
        row.id for row in candidates
        if article_url_hash and row.url_hash == article_url_hash
    ]
    if url_matches:
        return ArticleDuplicateResult(
            "duplicate", tuple(url_matches), "same canonical URL hash"
        )
    content_matches = [
        row.id for row in candidates
        if article_content_hash and row.content_hash == article_content_hash
    ]
    if content_matches:
        return ArticleDuplicateResult(
            "duplicate", tuple(content_matches), "same strong content hash"
        )
    headline = getattr(article, "headline", None)
    if headline:
        normalized_headline = " ".join(headline.casefold().split())
        uncertain = [
            row.id for row in candidates
            if row.headline
            and " ".join(row.headline.casefold().split()) == normalized_headline
        ]
        if uncertain:
            return ArticleDuplicateResult(
                "uncertain",
                tuple(uncertain),
                "matching headline without sufficient identity evidence",
            )
    return ArticleDuplicateResult("distinct")


detect_cross_source_duplicate = find_cross_source_duplicates
