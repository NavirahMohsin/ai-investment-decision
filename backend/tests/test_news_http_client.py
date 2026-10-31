from __future__ import annotations

from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request

import pytest

from app.services.news import (
    FeedContentTypeError,
    FeedFetchError,
    FeedHTTPStatusError,
    FeedRedirectError,
    FeedResponseTooLargeError,
    FeedTimeoutError,
    InvalidFeedURLError,
    SafeFeedHttpClient,
    get_source,
    build_news_provider,
)


RSS = b"<rss><channel><item><title>Test</title></item></channel></rss>"
ATOM = b"<feed xmlns='http://www.w3.org/2005/Atom'><entry><title>Test</title></entry></feed>"


@dataclass
class FakeResponse:
    status: int = 200
    headers: dict[str, str] | None = None
    body: bytes = RSS
    url: str = "https://example.com/feed.xml"

    def __post_init__(self) -> None:
        self.headers = self.headers or {"Content-Type": "application/rss+xml"}
        self._position = 0
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self.body) - self._position
        start = self._position
        self._position += size
        return self.body[start : start + size]

    def close(self) -> None:
        self.closed = True


class FakeTransport:
    def __init__(self, responses=None, error=None) -> None:
        self.responses = list(responses or [])
        self.error = error
        self.requests: list[Request] = []

    def open(self, request: Request, *, timeout: float) -> FakeResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(
        "app.services.news.http_client.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (2, 1, 6, "", ("93.184.216.34", 0)),
        ],
    )


def client(transport, **kwargs):
    return SafeFeedHttpClient(
        transport=transport,
        **kwargs,
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/feed.xml",
        "http://example.com/feed.xml",
    ],
)
def test_valid_urls_are_accepted(url):
    transport = FakeTransport([FakeResponse()])
    assert client(transport).get(url) == RSS


@pytest.mark.parametrize(
    "url",
    [
        "/feed.xml",
        "ftp://example.com/feed.xml",
        "https://user:pass@example.com/feed.xml",
        "https://example.com:not-a-port/feed.xml",
        "http://localhost/feed.xml",
        "http://127.0.0.1/feed.xml",
        "http://10.0.0.1/feed.xml",
        "http://169.254.1.1/feed.xml",
    ],
)
def test_invalid_or_private_urls_are_rejected(url):
    transport = FakeTransport([FakeResponse()])
    with pytest.raises(InvalidFeedURLError):
        client(transport).get(url)
    assert not transport.requests


def test_dns_resolved_private_address_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "app.services.news.http_client.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("192.168.1.10", 0))],
    )
    transport = FakeTransport([FakeResponse()])

    with pytest.raises(InvalidFeedURLError):
        client(transport).get("https://example.com/feed.xml")


@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        ("application/rss+xml", RSS),
        ("application/atom+xml; charset=utf-8", ATOM),
        ("application/xml", RSS),
        ("text/xml", RSS),
        ("text/plain", RSS),
    ],
)
def test_successful_rss_and_atom_content_types_are_returned_unchanged(content_type, body):
    transport = FakeTransport([FakeResponse(headers={"Content-Type": content_type}, body=body)])

    assert client(transport).get("https://example.com/feed.xml") == body


def test_non_success_status_is_rejected():
    transport = FakeTransport([FakeResponse(status=404)])

    with pytest.raises(FeedHTTPStatusError) as error:
        client(transport).get("https://example.com/feed.xml")

    assert error.value.status == 404


def test_timeout_and_connection_errors_are_typed():
    with pytest.raises(FeedTimeoutError):
        client(FakeTransport(error=TimeoutError())).get("https://example.com/feed.xml")
    with pytest.raises(FeedFetchError):
        client(FakeTransport(error=URLError("connection failed"))).get("https://example.com/feed.xml")


def test_empty_body_is_rejected():
    transport = FakeTransport([FakeResponse(body=b"")])

    with pytest.raises(FeedFetchError, match="empty"):
        client(transport).get("https://example.com/feed.xml")


def test_wrong_content_type_and_html_are_rejected():
    wrong_type = FakeTransport([FakeResponse(headers={"Content-Type": "text/html"}, body=RSS)])
    with pytest.raises(FeedContentTypeError):
        client(wrong_type).get("https://example.com/feed.xml")

    html = FakeTransport(
        [FakeResponse(headers={"Content-Type": "application/xml"}, body=b"<html>blocked</html>")]
    )
    with pytest.raises(FeedContentTypeError):
        client(html).get("https://example.com/feed.xml")


def test_text_plain_must_contain_rss_or_atom_xml():
    transport = FakeTransport(
        [FakeResponse(headers={"Content-Type": "text/plain"}, body=b"not xml")]
    )
    with pytest.raises(FeedContentTypeError):
        client(transport).get("https://example.com/feed.xml")


def test_response_size_is_checked_from_content_length_and_while_reading():
    content_length = FakeTransport(
        [
            FakeResponse(
                headers={"Content-Type": "application/rss+xml", "Content-Length": "10"},
                body=RSS,
            )
        ]
    )
    with pytest.raises(FeedResponseTooLargeError):
        client(content_length, max_response_bytes=5).get("https://example.com/feed.xml")

    chunked = FakeTransport([FakeResponse(body=b"123456")])
    with pytest.raises(FeedResponseTooLargeError):
        client(chunked, max_response_bytes=5).get("https://example.com/feed.xml")


def test_valid_redirect_is_followed_and_sensitive_headers_are_not_forwarded():
    transport = FakeTransport(
        [
            FakeResponse(
                status=302,
                headers={"Location": "https://example.com/next"},
            ),
            FakeResponse(body=RSS),
        ]
    )

    assert client(transport).get("https://example.com/start") == RSS
    assert len(transport.requests) == 2
    assert transport.requests[0].get_header("User-agent")
    assert transport.requests[0].get_header("Authorization") is None
    assert transport.requests[1].get_header("Authorization") is None


@pytest.mark.parametrize(
    "location",
    [
        "ftp://example.com/feed",
        "https://localhost/feed",
        "https://192.168.1.10/feed",
    ],
)
def test_redirect_destination_is_revalidated(location):
    transport = FakeTransport(
        [FakeResponse(status=302, headers={"Location": location})]
    )

    with pytest.raises(InvalidFeedURLError):
        client(transport).get("https://example.com/start")


def test_redirect_loop_and_limit_are_rejected():
    loop = FakeTransport(
        [
            FakeResponse(status=302, headers={"Location": "https://example.com/start"}),
        ]
    )
    with pytest.raises(FeedRedirectError, match="loop"):
        client(loop).get("https://example.com/start")

    limited = FakeTransport(
        [
            FakeResponse(status=302, headers={"Location": "https://example.com/one"}),
            FakeResponse(status=302, headers={"Location": "https://example.com/two"}),
        ]
    )
    with pytest.raises(FeedRedirectError, match="limit"):
        client(limited, max_redirects=1).get("https://example.com/start")


def test_provider_fetch_uses_client_and_returns_raw_bytes_to_parser():
    source = get_source("rbi_press_releases")
    assert source is not None
    provider = build_news_provider(source)
    transport = FakeTransport([FakeResponse(body=RSS)])

    payload = provider.fetch(client(transport))

    assert payload == RSS
    assert provider.parse(payload)[0].headline == "Test"
