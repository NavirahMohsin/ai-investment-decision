from __future__ import annotations

import ipaddress
import socket
from collections.abc import Mapping
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)
from xml.etree import ElementTree


DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
DEFAULT_USER_AGENT = "ArthAI-NewsFetcher/0.1"
DEFAULT_ACCEPTED_CONTENT_TYPES = frozenset(
    {
        "application/atom+xml",
        "application/rss+xml",
        "application/xml",
        "text/xml",
        "text/plain",
    }
)
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class FeedFetchError(RuntimeError):
    """Base exception for safe feed-fetch failures."""


class InvalidFeedURLError(FeedFetchError):
    pass


class FeedHTTPStatusError(FeedFetchError):
    def __init__(self, status: int, url: str) -> None:
        super().__init__(f"Feed request returned HTTP status {status} for {url}")
        self.status = status


class FeedContentTypeError(FeedFetchError):
    pass


class FeedResponseTooLargeError(FeedFetchError):
    pass


class FeedTimeoutError(FeedFetchError):
    pass


class FeedRedirectError(FeedFetchError):
    pass


class TransportResponse(Protocol):
    status: int
    headers: Mapping[str, str]
    url: str

    def read(self, size: int = -1) -> bytes:
        ...

    def close(self) -> None:
        ...


class FeedTransport(Protocol):
    def open(self, request: Request, *, timeout: float) -> TransportResponse:
        ...


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UrllibFeedTransport:
    def __init__(self) -> None:
        self._opener = build_opener(_NoRedirectHandler)

    def open(self, request: Request, *, timeout: float) -> TransportResponse:
        return self._opener.open(request, timeout=timeout)


class SafeFeedHttpClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        user_agent: str = DEFAULT_USER_AGENT,
        accepted_content_types: frozenset[str] = DEFAULT_ACCEPTED_CONTENT_TYPES,
        max_redirects: int = 3,
        transport: FeedTransport | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        if max_redirects < 0:
            raise ValueError("max_redirects cannot be negative")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.user_agent = user_agent
        self.accepted_content_types = frozenset(
            content_type.lower().split(";", 1)[0].strip()
            for content_type in accepted_content_types
        )
        self.max_redirects = max_redirects
        self._transport = transport or UrllibFeedTransport()

    def get(self, url: str) -> bytes:
        current_url = self._validate_url(url)
        visited: set[str] = set()

        for redirect_count in range(self.max_redirects + 1):
            if current_url in visited:
                raise FeedRedirectError("Feed redirect loop detected")
            visited.add(current_url)
            self._validate_resolved_host(current_url)
            request = Request(
                current_url,
                headers={
                    "Accept": ", ".join(sorted(self.accepted_content_types)),
                    "User-Agent": self.user_agent,
                },
                method="GET",
            )
            try:
                response = self._transport.open(
                    request,
                    timeout=self.timeout_seconds,
                )
            except (socket.timeout, TimeoutError) as error:
                raise FeedTimeoutError(
                    "Feed request timed out"
                ) from error
            except HTTPError as error:
                if error.code in REDIRECT_STATUSES:
                    response = error
                else:
                    raise FeedHTTPStatusError(error.code, current_url) from error
            except URLError as error:
                if isinstance(error.reason, TimeoutError) or "timed out" in str(error.reason).lower():
                    raise FeedTimeoutError("Feed request timed out") from error
                raise FeedFetchError("Feed connection failed") from error
            except OSError as error:
                raise FeedFetchError("Feed connection failed") from error

            try:
                if response.status in REDIRECT_STATUSES:
                    location = response.headers.get("Location")
                    if not location:
                        raise FeedRedirectError(
                            f"Feed redirect from {current_url} has no Location"
                        )
                    if redirect_count >= self.max_redirects:
                        raise FeedRedirectError("Feed redirect limit exceeded")
                    current_url = self._validate_url(
                        urljoin(current_url, location)
                    )
                    continue
                if response.status < 200 or response.status >= 300:
                    raise FeedHTTPStatusError(response.status, current_url)
                self._validate_content_type(response.headers.get("Content-Type", ""))
                return self._read_body(response, current_url)
            finally:
                response.close()

        raise FeedRedirectError("Feed redirect limit exceeded")

    def _validate_url(self, url: str) -> str:
        if not isinstance(url, str) or not url.strip():
            raise InvalidFeedURLError("Feed URL must be a non-empty absolute URL")
        try:
            parts = urlsplit(url.strip())
            if parts.scheme.lower() not in {"http", "https"}:
                raise InvalidFeedURLError("Feed URL must use HTTP or HTTPS")
            if not parts.netloc:
                raise InvalidFeedURLError("Feed URL must be absolute")
            if parts.username is not None or parts.password is not None:
                raise InvalidFeedURLError("Feed URL cannot contain credentials")
            parts.port
        except ValueError as error:
            raise InvalidFeedURLError("Feed URL has a malformed port") from error
        return url.strip()

    def _validate_resolved_host(self, url: str) -> None:
        hostname = urlsplit(url).hostname
        if not hostname or hostname.lower() == "localhost":
            raise InvalidFeedURLError("Feed host is not allowed")
        try:
            if self._is_private_address(hostname):
                raise InvalidFeedURLError("Feed host resolves to a non-public address")
        except ValueError:
            pass
        try:
            addresses = {
                address[4][0]
                for address in socket.getaddrinfo(
                    hostname,
                    None,
                    type=socket.SOCK_STREAM,
                )
            }
        except OSError as error:
            raise FeedFetchError("Feed host could not be resolved") from error
        if not addresses or any(self._is_private_address(address) for address in addresses):
            raise InvalidFeedURLError("Feed host resolves to a non-public address")

    @staticmethod
    def _is_private_address(value: str) -> bool:
        address = ipaddress.ip_address(value)
        return (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
            or address.is_multicast
        )

    def _validate_content_type(self, value: str) -> None:
        media_type = value.lower().split(";", 1)[0].strip()
        if media_type not in self.accepted_content_types:
            raise FeedContentTypeError(
                f"Unsupported feed content type: {media_type or 'missing'}"
            )

    def _read_body(self, response: TransportResponse, url: str) -> bytes:
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > self.max_response_bytes:
                    raise FeedResponseTooLargeError(
                        f"Feed response exceeds {self.max_response_bytes} bytes"
                    )
            except ValueError as error:
                raise FeedFetchError("Feed response has invalid Content-Length") from error

        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(min(64 * 1024, self.max_response_bytes - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > self.max_response_bytes:
                raise FeedResponseTooLargeError(
                    f"Feed response exceeds {self.max_response_bytes} bytes"
                )
            chunks.append(chunk)
        if total == 0:
            raise FeedFetchError(f"Feed response was empty for {url}")
        body = b"".join(chunks)
        if body.lstrip()[:500].lower().startswith((b"<html", b"<!doctype html")):
            raise FeedContentTypeError("Feed response is HTML")
        media_type = response.headers.get("Content-Type", "").lower().split(";", 1)[0].strip()
        if media_type == "text/plain":
            try:
                root = ElementTree.fromstring(body)
            except ElementTree.ParseError as error:
                raise FeedContentTypeError(
                    "text/plain feed response is not valid XML"
                ) from error
            if root.tag.rsplit("}", 1)[-1].lower() not in {"rss", "feed"}:
                raise FeedContentTypeError(
                    "text/plain feed response is not RSS or Atom XML"
                )
        return body
