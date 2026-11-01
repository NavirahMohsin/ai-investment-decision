from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol
from collections.abc import Mapping
from urllib.parse import quote_plus

from app.services.news.feed_parser import FeedParseError, parse_feed
from app.services.news.http_client import FeedFetchError
from app.services.news.types import NormalizedNewsArticle

RawFeed = bytes


class HttpClient(Protocol):
    def get(self, url: str) -> RawFeed:
        """Return the response body for a provider feed URL."""


class FeedParser(Protocol):
    def __call__(
        self,
        payload: bytes,
        *,
        feed_url: str,
        provider_key: str,
    ) -> list[NormalizedNewsArticle]:
        ...


class NewsProvider(ABC):
    provider_key: str
    name: str
    source_type: str
    feed_url: str

    def fetch(self, client: HttpClient) -> RawFeed:
        return client.get(self.feed_url)

    @abstractmethod
    def parse(self, payload: RawFeed) -> list[NormalizedNewsArticle]:
        raise NotImplementedError


class RssAtomProvider(NewsProvider):
    def __init__(
        self,
        *,
        provider_key: str,
        name: str,
        feed_url: str,
        client_parser: FeedParser = parse_feed,
        source_metadata: Mapping[str, object] | None = None,
    ) -> None:
        self.provider_key = provider_key
        self.name = name
        self.source_type = "rss"
        self.feed_url = feed_url
        self._client_parser = client_parser
        self._source_metadata = dict(source_metadata or {})

    def parse(self, payload: RawFeed) -> list[NormalizedNewsArticle]:
        articles = self._client_parser(
            payload,
            feed_url=self.feed_url,
            provider_key=self.provider_key,
        )
        return [
            article.model_copy(
                update={
                    "source_metadata": {
                        **article.source_metadata,
                        **self._source_metadata,
                    }
                }
            )
            for article in articles
        ]


@dataclass(frozen=True, slots=True)
class CompanyNewsQuery:
    name: str
    aliases: tuple[str, ...] = ()


class GoogleNewsQueryError(RuntimeError):
    """Raised when one or more company-specific Google News queries fail."""


class GoogleNewsRssProvider(NewsProvider):
    """Fetch company-specific RSS searches from Google News."""

    locale = {"hl": "en-IN", "gl": "IN", "ceid": "IN:en"}

    def __init__(
        self,
        *,
        provider_key: str,
        name: str,
        feed_url: str,
        client_parser: FeedParser = parse_feed,
        source_metadata: Mapping[str, object] | None = None,
    ) -> None:
        self.provider_key = provider_key
        self.name = name
        self.source_type = "google_news_rss"
        self.feed_url = feed_url
        self._client_parser = client_parser
        self._source_metadata = dict(source_metadata or {})

    def _query_url(self, query: CompanyNewsQuery) -> str:
        terms = [query.name, *query.aliases]
        search = "(" + " OR ".join(f'"{term}"' for term in terms) + ") when:7d"
        separator = "&" if "?" in self.feed_url else "?"
        params = f"q={quote_plus(search)}&hl={self.locale['hl']}&gl={self.locale['gl']}&ceid={self.locale['ceid']}"
        return f"{self.feed_url}{separator}{params}"

    def fetch_for_companies(
        self,
        client: HttpClient,
        queries: tuple[CompanyNewsQuery, ...],
    ) -> list[NormalizedNewsArticle]:
        articles: list[NormalizedNewsArticle] = []
        failures: list[Exception] = []
        seen_urls: set[str] = set()
        for query in queries:
            url = self._query_url(query)
            try:
                payload = client.get(url)
                parsed = self._client_parser(
                    payload,
                    feed_url=url,
                    provider_key=self.provider_key,
                )
            except (FeedFetchError, FeedParseError) as error:
                failures.append(error)
                continue
            for article in parsed:
                if article.canonical_url and article.canonical_url in seen_urls:
                    continue
                if article.canonical_url:
                    seen_urls.add(article.canonical_url)
                articles.append(
                    article.model_copy(
                        update={
                            "source_metadata": {
                                **article.source_metadata,
                                **self._source_metadata,
                                "company_query": query.name,
                            }
                        }
                    )
                )
        if failures:
            raise GoogleNewsQueryError(
                f"Google News RSS failed for {len(failures)} company queries"
            ) from failures[0]
        return articles

    def fetch(self, client: HttpClient) -> RawFeed:
        return client.get(
            f"{self.feed_url}?q={quote_plus('Indian stock market when:7d')}"
            f"&hl={self.locale['hl']}&gl={self.locale['gl']}&ceid={self.locale['ceid']}"
        )

    def parse(self, payload: RawFeed) -> list[NormalizedNewsArticle]:
        articles = self._client_parser(
            payload,
            feed_url=self.feed_url,
            provider_key=self.provider_key,
        )
        return [
            article.model_copy(
                update={
                    "source_metadata": {
                        **article.source_metadata,
                        **self._source_metadata,
                    }
                }
            )
            for article in articles
        ]
