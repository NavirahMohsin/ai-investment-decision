from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol
from collections.abc import Mapping

from app.services.news.feed_parser import parse_feed
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
