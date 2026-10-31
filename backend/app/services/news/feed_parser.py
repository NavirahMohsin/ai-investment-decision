from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re
from urllib.parse import urljoin
from xml.etree import ElementTree

from app.services.news.types import NormalizedNewsArticle


class FeedParseError(ValueError):
    """Raised when a payload is not a supported RSS or Atom feed."""


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    timestamp = value.strip()
    timezone_name = re.search(r"\s([A-Za-z]{2,5})$", timestamp)
    if timezone_name and timezone_name.group(1).upper() not in {"GMT", "UTC"}:
        return None
    try:
        parsed = parsedate_to_datetime(timestamp)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def parse_feed(
    payload: bytes | str,
    *,
    feed_url: str,
    provider_key: str,
) -> list[NormalizedNewsArticle]:
    if not payload:
        raise FeedParseError("Feed payload is empty")
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    if _looks_like_html(payload):
        raise FeedParseError("Feed payload is HTML, not RSS or Atom XML")
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as error:
        raise FeedParseError(f"Malformed feed XML: {error}") from error

    root_name = _local_name(root.tag)
    if root_name == "rss":
        return _parse_rss(root, feed_url=feed_url, provider_key=provider_key)
    if root_name == "feed":
        return _parse_atom(root, feed_url=feed_url, provider_key=provider_key)
    raise FeedParseError(f"Unsupported feed XML root: {root_name}")


def _parse_rss(root: ElementTree.Element, *, feed_url: str, provider_key: str) -> list[NormalizedNewsArticle]:
    channel = next((child for child in root if _local_name(child.tag) == "channel"), None)
    if channel is None:
        raise FeedParseError("RSS feed does not contain a channel")
    channel_language = _child_text(channel, {"language"})
    articles = []
    for item in channel:
        if _local_name(item.tag) != "item":
            continue
        values = _direct_child_values(item)
        link = values.get("link")
        articles.append(
            _article(
                provider_key=provider_key,
                external_id=values.get("guid"),
                headline=values.get("title"),
                summary=values.get("description"),
                author=values.get("author") or values.get("creator"),
                link=link,
                published=values.get("pubdate") or values.get("published") or values.get("date"),
                language=values.get("language") or channel_language,
                feed_url=feed_url,
                format_name="rss",
            )
        )
    return articles


def _parse_atom(root: ElementTree.Element, *, feed_url: str, provider_key: str) -> list[NormalizedNewsArticle]:
    feed_language = root.attrib.get("{http://www.w3.org/XML/1998/namespace}lang")
    articles = []
    for entry in root:
        if _local_name(entry.tag) != "entry":
            continue
        values = _direct_child_values(entry)
        link = _atom_link(entry, feed_url)
        author = values.get("author")
        if author is None:
            author_element = _first_child(entry, {"author"})
            if author_element is not None:
                author = _child_text(author_element, {"name"})
        articles.append(
            _article(
                provider_key=provider_key,
                external_id=values.get("id"),
                headline=values.get("title"),
                summary=values.get("summary") or values.get("content"),
                author=author,
                link=link,
                published=values.get("published") or values.get("updated"),
                language=values.get("language") or feed_language,
                feed_url=feed_url,
                format_name="atom",
            )
        )
    return articles


def _article(
    *,
    provider_key: str,
    external_id: str | None,
    headline: str | None,
    summary: str | None,
    author: str | None,
    link: str | None,
    published: str | None,
    language: str | None,
    feed_url: str,
    format_name: str,
) -> NormalizedNewsArticle:
    raw_timestamp = _clean(published)
    return NormalizedNewsArticle(
        provider_key=provider_key,
        external_id=_clean(external_id),
        headline=_clean(headline),
        summary=_clean(summary),
        author=_clean(author),
        canonical_url=urljoin(feed_url, link) if link else None,
        published_at_raw=raw_timestamp,
        published_at_utc=parse_timestamp(raw_timestamp),
        language=_clean(language),
        source_metadata={"feed_url": feed_url, "format": format_name},
    )


def _atom_link(entry: ElementTree.Element, feed_url: str) -> str | None:
    links = [child for child in entry if _local_name(child.tag) == "link"]
    alternate = next(
        (
            link
            for link in links
            if link.attrib.get("rel", "alternate") == "alternate"
            and link.attrib.get("href", "").strip()
        ),
        None,
    )
    selected = (
        alternate
        if alternate is not None
        else next(
            (link for link in links if link.attrib.get("href", "").strip()),
            None,
        )
    )
    href = selected.attrib.get("href").strip() if selected is not None else None
    return urljoin(feed_url, href) if href else None


def _direct_child_values(element: ElementTree.Element) -> dict[str, str]:
    values = {}
    for child in element:
        name = _local_name(child.tag)
        text = "".join(child.itertext()).strip()
        if text:
            values[name] = text
    return values


def _first_child(element: ElementTree.Element, names: set[str]) -> ElementTree.Element | None:
    return next((child for child in element if _local_name(child.tag) in names), None)


def _child_text(element: ElementTree.Element, names: set[str]) -> str | None:
    child = _first_child(element, names)
    return "".join(child.itertext()).strip() if child is not None and "".join(child.itertext()).strip() else None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _looks_like_html(payload: bytes) -> bool:
    prefix = payload.lstrip()[:500].lower()
    return b"<html" in prefix or b"<!doctype html" in prefix
