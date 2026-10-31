from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

from app.services.news.types import NormalizedNewsArticle


def normalize_url(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    try:
        parts = urlsplit(value.strip())
        if not parts.scheme or not parts.netloc:
            return None
        if parts.username is not None or parts.password is not None:
            return None
        hostname = parts.hostname
        if not hostname:
            return None
        port = parts.port
    except ValueError:
        return None

    scheme = parts.scheme.lower()
    hostname = hostname.lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    netloc = hostname
    if port is not None and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        netloc += f":{port}"
    path = parts.path or "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def url_hash(value: str | None) -> str | None:
    normalized = normalize_url(value)
    return _sha256(normalized) if normalized else None


def content_hash(article: NormalizedNewsArticle) -> str | None:
    """Hash headline, summary, and normalized UTC publication time only.

    URL identity is handled separately by ``url_hash``. Provider-scoped
    external IDs are intentionally excluded because they are not comparable
    across providers without an explicit global-ID scope.
    """
    headline = _normalize_text(article.headline)
    summary = _normalize_text(article.summary)
    published_at = article.published_at_utc
    if not headline or not summary or published_at is None:
        return None
    stable_value = "\x1f".join(
        (headline, summary, published_at.isoformat())
    )
    return _sha256(stable_value)


def _normalize_text(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip().casefold() or None


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
