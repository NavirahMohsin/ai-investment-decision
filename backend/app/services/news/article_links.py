from __future__ import annotations

from collections.abc import Iterable
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import NewsArticle, NewsArticleCompany
from app.services.news.entity_matching import CompanyMatch


class ArticleLinkError(ValueError):
    pass


def link_article_companies(
    db: Session,
    article_id: int,
    matches: Iterable[CompanyMatch],
) -> list[NewsArticleCompany]:
    if db.get(NewsArticle, article_id) is None:
        raise ArticleLinkError(f"News article does not exist: {article_id}")
    linked: list[NewsArticleCompany] = []
    try:
        with db.begin_nested():
            for match in matches:
                if match.is_ambiguous or match.company_id is None:
                    continue
                existing = db.scalar(
                    select(NewsArticleCompany).where(
                        NewsArticleCompany.article_id == article_id,
                        NewsArticleCompany.company_id == match.company_id,
                    )
                )
                if existing is not None:
                    linked.append(existing)
                    continue
                relation = NewsArticleCompany(
                    article_id=article_id,
                    company_id=match.company_id,
                    match_method=match.match_method or "unknown",
                    match_confidence=match.match_confidence,
                    matched_text=match.matched_text,
                )
                db.add(relation)
                try:
                    with db.begin_nested():
                        db.flush()
                except IntegrityError:
                    continue
                linked.append(relation)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise ArticleLinkError("Article-company links could not be saved") from error
    return linked
