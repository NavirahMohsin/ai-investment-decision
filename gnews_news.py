"""
Company-specific news from Google News RSS search (free, no account, no API key).

Install:   pip install requests feedparser
Optional:  pip install googlenewsdecoder      (only for --resolve, see below)

Usage:
    python gnews_news.py                      # last 7 days, all companies, saves to news.db
    python gnews_news.py --days 2             # incremental refresh
    python gnews_news.py --days 30 --resolve  # also resolve publisher URLs (slower, more 429 risk)
    python gnews_news.py --show "Infosys"     # print stored items for one company

Notes:
- Google News RSS is UNOFFICIAL and undocumented. The syntax can change without notice.
- Each call returns at most ~100 items. For long backfills, use windows (see windowed_queries).
- Links in the feed are Google wrappers (news.google.com/rss/articles/...), not publisher URLs.
  They open fine in a browser. Use --resolve only if your pipeline needs the real URL.
- Feed gives headline + link + date + publisher. It does NOT give article text.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
import urllib.parse as up
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

# --------------------------------------------------------------------------
# 1) COMPANY MASTER TABLE  - edit this. One entry per company.
#    name     : the exact, full name used in the exact-match query
#    aliases  : other names/tickers people use in headlines
#    exclude  : words that cause false matches (e.g. "Tata Motors" vs "Tata Steel")
# --------------------------------------------------------------------------
COMPANIES = [
    {"name": "Reliance Industries", "aliases": ["RIL"], "exclude": []},
    {"name": "Infosys", "aliases": [], "exclude": []},
    {"name": "HDFC Bank", "aliases": [], "exclude": []},
    {"name": "Tata Motors", "aliases": [], "exclude": []},
    # ... add the rest of your 20 companies here
]

# Google News locale for India. The syntax is reverse-engineered, so verify once
# with --show / a single manual request that results actually come back.
LOCALE = {"hl": "en-IN", "gl": "IN", "ceid": "IN:en"}

BASE = "https://news.google.com/rss/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research-project/1.0)"}
DB_PATH = "news.db"
PAUSE_BETWEEN_COMPANIES = 2.0   # seconds; be polite, avoid 429s
MAX_RETRIES = 3


# --------------------------------------------------------------------------
# 2) QUERY BUILDING
# --------------------------------------------------------------------------
def build_query(company: dict, days: int | None = None,
                after: str | None = None, before: str | None = None) -> str:
    """Build the q= string.  ("Name" OR "Alias") -word when:7d"""
    terms = [company["name"], *company.get("aliases", [])]
    q = "(" + " OR ".join(f'"{t}"' for t in terms) + ")"
    for word in company.get("exclude", []):
        q += f' -"{word}"' if " " in word else f" -{word}"
    if after or before:                       # day-level date window
        if after:
            q += f" after:{after}"            # YYYY-MM-DD
        if before:
            q += f" before:{before}"
    elif days:
        q += f" when:{days}d"                 # h / d / m units are accepted
    return q


def build_url(query: str) -> str:
    params = {"q": query, **LOCALE}
    return f"{BASE}?{up.urlencode(params, quote_via=up.quote_plus)}"


def windowed_queries(company: dict, start: datetime, end: datetime, step_days: int = 7):
    """For backfills: split a long range into windows so each stays under the ~100 item cap."""
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=step_days), end)
        yield build_query(company, after=cur.strftime("%Y-%m-%d"),
                          before=nxt.strftime("%Y-%m-%d"))
        cur = nxt


# --------------------------------------------------------------------------
# 3) FETCH + PARSE
# --------------------------------------------------------------------------
def fetch_feed(url: str) -> bytes | None:
    """GET with redirects, timeout and bounded exponential backoff."""
    delay = 5.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        except requests.RequestException as e:
            print(f"  network error ({e}); attempt {attempt}/{MAX_RETRIES}", file=sys.stderr)
        else:
            if r.status_code == 200 and r.content:
                return r.content
            if r.status_code in (429, 503):
                print(f"  HTTP {r.status_code} (rate limited); waiting {delay:.0f}s", file=sys.stderr)
            elif r.status_code == 200:
                print("  empty response body (check query syntax / locale); giving up", file=sys.stderr)
                return None
            else:
                print(f"  HTTP {r.status_code}; giving up on this query", file=sys.stderr)
                return None
        time.sleep(delay)
        delay *= 2
    return None


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


def parse_feed(content: bytes) -> list[dict]:
    feed = feedparser.parse(content)
    items = []
    for e in feed.entries:
        publisher = (e.get("source") or {}).get("title") or ""
        title = e.get("title", "").strip()
        # Google appends " - Publisher" to titles. Strip it so titles dedupe cleanly.
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(f" - {publisher}")].strip()
        try:
            published = parsedate_to_datetime(e.get("published", "")).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            published = None
        items.append({
            "guid": e.get("id") or e.get("guid") or e.get("link"),
            "title": title,
            "publisher": publisher,
            "google_url": e.get("link"),
            "published": published,
        })
    return items


def dedupe(items: list[dict]) -> list[dict]:
    """Same story is often syndicated; keep the first copy of each normalized title."""
    seen, out = set(), []
    for it in items:
        key = _norm_title(it["title"])
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


# --------------------------------------------------------------------------
# 4) OPTIONAL: resolve Google wrapper links to real publisher URLs
#    Google's IDs are opaque since 2024; this uses the third-party googlenewsdecoder
#    package, which calls Google endpoints that may change or rate-limit you.
# --------------------------------------------------------------------------
def resolve_urls(urls: list[str], interval: float = 1.0) -> dict[str, str | None]:
    try:
        from googlenewsdecoder import gnewsdecoder
    except ImportError:
        sys.exit("--resolve needs:  pip install googlenewsdecoder")
    out = {}
    for u in urls:
        try:
            res = gnewsdecoder(u, interval=interval)
            out[u] = res.get("decoded_url") if res.get("success") else None
        except Exception as e:  # package does not document its exceptions
            print(f"  resolve failed: {e}", file=sys.stderr)
            out[u] = None
    return out


# --------------------------------------------------------------------------
# 5) STORAGE (SQLite). Re-running is safe: duplicates are ignored by guid.
# --------------------------------------------------------------------------
def init_db(path: str = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS news (
            guid TEXT NOT NULL,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            publisher TEXT,
            google_url TEXT,
            publisher_url TEXT,
            published TEXT,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (guid, company)
        )""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_news_company_pub ON news(company, published)")
    return con


def save(con: sqlite3.Connection, company: str, items: list[dict]) -> int:
    now = datetime.now(timezone.utc).isoformat()
    before = con.total_changes
    con.executemany(
        "INSERT OR IGNORE INTO news(guid,company,title,publisher,google_url,publisher_url,published,fetched_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        [(i["guid"], company, i["title"], i["publisher"], i["google_url"],
          i.get("publisher_url"), i["published"], now) for i in items],
    )
    con.commit()
    return con.total_changes - before


# --------------------------------------------------------------------------
# 6) MAIN
# --------------------------------------------------------------------------
def run(days: int, resolve: bool, db_path: str = DB_PATH) -> None:
    con = init_db(db_path)
    for idx, comp in enumerate(COMPANIES):
        q = build_query(comp, days=days)
        print(f"[{idx + 1}/{len(COMPANIES)}] {comp['name']}  q={q}")
        content = fetch_feed(build_url(q))
        if content is None:
            print("  -> no data (will retry next run)")
            continue
        items = dedupe(parse_feed(content))
        if resolve and items:
            mapping = resolve_urls([i["google_url"] for i in items])
            for i in items:
                i["publisher_url"] = mapping.get(i["google_url"])
        new = save(con, comp["name"], items)
        print(f"  -> {len(items)} items, {new} new")
        time.sleep(PAUSE_BETWEEN_COMPANIES)


def show(company: str, limit: int = 15, db_path: str = DB_PATH) -> None:
    con = init_db(db_path)
    rows = con.execute(
        "SELECT published, publisher, title FROM news WHERE company=? "
        "ORDER BY published DESC LIMIT ?", (company, limit)).fetchall()
    for pub, src, title in rows:
        print(f"{(pub or '')[:16]}  [{src}]  {title}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--resolve", action="store_true", help="resolve publisher URLs (slower)")
    ap.add_argument("--show", metavar="COMPANY")
    args = ap.parse_args()
    show(args.show) if args.show else run(args.days, args.resolve)
