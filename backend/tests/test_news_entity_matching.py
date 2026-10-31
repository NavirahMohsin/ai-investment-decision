from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace

import pytest
from sqlalchemy import select

from app.db.models import Company, CompanyAlias, NewsArticle, NewsArticleCompany, NewsSource
from app.services.news import (
    ALIAS_CONFIDENCE,
    ArticleLinkError,
    ContentPolicyStatus,
    EmptyCompanyAliasError,
    NAME_CONFIDENCE,
    SYMBOL_CONFIDENCE,
    add_company_alias,
    deactivate_company_alias,
    find_cross_source_duplicates,
    get_active_company_aliases,
    link_article_companies,
    match_article_companies,
    match_company,
)
from app.services.news.entity_normalization import normalize_company_name
from app.services.news.deduplication import content_hash, url_hash
from app.services.news.types import NormalizedNewsArticle


def add_company(db_session, name, symbol):
    company = Company(
        name=name,
        symbol=symbol,
        provider_symbol=f"{symbol}.NS",
        exchange="NSE",
        instrument_type="company",
    )
    db_session.add(company)
    db_session.commit()
    return company


def add_source(db_session, key):
    source = NewsSource(
        name=key,
        provider_key=key,
        source_type="rss",
        feed_url="https://example.com/feed.xml",
    )
    db_session.add(source)
    db_session.commit()
    return source


def add_article(db_session, source, headline, url, summary=None, published_at=None):
    article = NewsArticle(
        source_id=source.id,
        canonical_url=url,
        url_hash=url_hash(url),
        headline=headline,
        summary=summary,
        published_at=published_at,
        content_hash=content_hash(
            NormalizedNewsArticle(
                provider_key=source.provider_key,
                headline=headline,
                summary=summary,
                canonical_url=url,
                published_at_utc=published_at,
            )
        ),
    )
    db_session.add(article)
    db_session.commit()
    return article


def test_company_normalization_handles_suffixes_punctuation_unicode_and_distinctions():
    assert normalize_company_name("  Reliance Industries, Limited ") == "reliance industries"
    assert normalize_company_name("RELIANCE   INDUSTRIES LTD.") == "reliance industries"
    assert normalize_company_name("Cafe\u0301 Corporation") == "café"
    assert normalize_company_name("Tata Motors") != normalize_company_name("Tata Consultancy Services")
    assert normalize_company_name("ABC") != normalize_company_name("ABCD")


def test_alias_lifecycle_and_validation(db_session):
    company = add_company(db_session, "Reliance Industries Limited", "RELIANCE")
    alias = add_company_alias(db_session, company.id, "RIL", alias_type="ticker")
    assert alias.normalized_alias == "ril"
    assert add_company_alias(db_session, company.id, " ril ").id == alias.id
    assert [item.id for item in get_active_company_aliases(db_session, company.id)] == [alias.id]

    deactivated = deactivate_company_alias(db_session, alias.id)
    assert not deactivated.is_active
    assert get_active_company_aliases(db_session, company.id) == []
    assert add_company_alias(db_session, company.id, "RIL").id == alias.id

    with pytest.raises(EmptyCompanyAliasError):
        add_company_alias(db_session, company.id, "   ")
    with pytest.raises(ValueError):
        add_company_alias(db_session, 99999, "RIL")


def test_exact_matching_priority_and_confidence(db_session):
    company = add_company(db_session, "Reliance Industries Limited", "RELIANCE")
    add_company_alias(db_session, company.id, "RIL")

    symbol = match_company(db_session, "RELIANCE")
    assert symbol.company_id == company.id
    assert symbol.match_method == "exact_symbol"
    assert symbol.match_confidence == SYMBOL_CONFIDENCE

    name = match_company(db_session, "Reliance Industries Limited")
    assert name.match_method == "exact_name"
    assert name.match_confidence == NAME_CONFIDENCE

    alias = match_company(db_session, "ril")
    assert alias.match_method == "alias"
    assert alias.match_confidence == ALIAS_CONFIDENCE
    assert match_company(db_session, "unlisted") .company_id is None


def test_matching_uses_boundaries_and_reports_ambiguous_aliases(db_session):
    first = add_company(db_session, "Alpha Holdings", "ALPHA")
    second = add_company(db_session, "Beta Holdings", "BETA")
    add_company_alias(db_session, first.id, "common")
    add_company_alias(db_session, second.id, "common")

    ambiguous = match_company(db_session, "common")
    assert ambiguous.is_ambiguous
    assert ambiguous.company_id is None
    assert ambiguous.candidate_company_ids == (first.id, second.id)
    assert match_article_companies(db_session, "uncommon results", None) == ()


def test_article_matching_supports_multiple_fields_and_longer_terms(db_session):
    reliance = add_company(db_session, "Reliance Industries Limited", "RELIANCE")
    tata = add_company(db_session, "Tata Consultancy Services", "TCS")
    add_company_alias(db_session, reliance.id, "RIL")
    add_company_alias(db_session, tata.id, "Tata Consultancy")

    matches = match_article_companies(
        db_session,
        "Reliance Industries and Tata Consultancy Services",
        "RIL and TCS reported results; ITC unrelated.",
    )
    company_ids = {match.company_id for match in matches}
    assert company_ids == {reliance.id, tata.id}
    assert all(match.matched_text for match in matches)
    assert any(match.match_method == "exact_name" for match in matches)


def test_ambiguous_article_alias_is_not_linkable(db_session):
    first = add_company(db_session, "Alpha One", "AONE")
    second = add_company(db_session, "Beta Two", "BTWO")
    add_company_alias(db_session, first.id, "shared")
    add_company_alias(db_session, second.id, "shared")
    matches = match_article_companies(db_session, "Shared announced an update", None)
    assert len(matches) == 1
    assert matches[0].is_ambiguous
    assert matches[0].candidate_company_ids == (first.id, second.id)


def test_article_links_are_idempotent_and_skip_ambiguity(db_session):
    company = add_company(db_session, "Reliance Industries Limited", "RELIANCE")
    source = add_source(db_session, "source-one")
    article = add_article(db_session, source, "Reliance update", "https://example.com/1")
    match = match_company(db_session, "RELIANCE")
    assert len(link_article_companies(db_session, article.id, [match])) == 1
    assert len(link_article_companies(db_session, article.id, [match])) == 1
    assert db_session.scalar(
        select(NewsArticleCompany).where(NewsArticleCompany.article_id == article.id)
    ).company_id == company.id

    ambiguous = replace(
        match,
        company_id=None,
        is_ambiguous=True,
        candidate_company_ids=(company.id,),
    )
    assert link_article_companies(db_session, article.id, [ambiguous]) == []


def test_article_link_rejects_missing_article(db_session):
    company = add_company(db_session, "Reliance Industries Limited", "RELIANCE")
    match = match_company(db_session, "RELIANCE")
    with pytest.raises(ArticleLinkError):
        link_article_companies(db_session, 99999, [match])


def test_cross_source_duplicate_policy_is_conservative(db_session):
    first_source = add_source(db_session, "source-one")
    second_source = add_source(db_session, "source-two")
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first = add_article(
        db_session,
        first_source,
        "Same headline",
        "https://example.com/one",
        "Same summary",
        timestamp,
    )
    same_url = NormalizedNewsArticle(
        provider_key="source-two",
        headline="Different headline",
        canonical_url=first.canonical_url,
    )
    assert find_cross_source_duplicates(db_session, same_url).is_duplicate

    same_content = NormalizedNewsArticle(
        provider_key="source-two",
        headline="Same headline",
        summary="Same summary",
        canonical_url="https://other.example/two",
        published_at_utc=timestamp,
    )
    content_result = find_cross_source_duplicates(db_session, same_content)
    assert content_result.is_duplicate
    assert first.id in content_result.matching_article_ids

    headline_only = NormalizedNewsArticle(
        provider_key="source-two",
        headline="Same headline",
        canonical_url="https://other.example/three",
    )
    uncertain = find_cross_source_duplicates(db_session, headline_only)
    assert uncertain.is_uncertain
    assert not uncertain.is_duplicate

    different = NormalizedNewsArticle(
        provider_key="source-two",
        headline="Same headline",
        summary="Unrelated summary",
        canonical_url="https://other.example/four",
        published_at_utc=timestamp,
    )
    assert find_cross_source_duplicates(db_session, different).is_uncertain
