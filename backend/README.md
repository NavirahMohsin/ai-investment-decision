# ArthAI historical market data pipeline

This first pipeline stores daily OHLCV history for an NSE/BSE instrument universe.
The provider boundary is `app.services.providers.MarketDataProvider`, with
`YahooFinanceProvider` as the development implementation. Yahoo Finance is not
an official NSE or BSE feed; its data availability, accuracy, redistribution
rights, and licensing are subject to Yahoo Finance terms and the upstream
exchange/vendor terms. Do not use this implementation to bypass exchange
access controls or as a production trading feed.

## Setup

```powershell
cd backend
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\alembic.exe upgrade head
```

SQLite is the default database at `backend/data/arthai.db`. Set `DATABASE_URL`
in `backend/.env` to use another SQLAlchemy-compatible database later.

## Seed and ingest

```powershell
.\venv\Scripts\python.exe -m app.scripts.seed_instruments
.\venv\Scripts\python.exe -m app.scripts.ingest_market_data --symbol RELIANCE
.\venv\Scripts\python.exe -m app.scripts.ingest_market_data
```

The default window is approximately five years. Use `--start YYYY-MM-DD` and
`--end YYYY-MM-DD` to select a range. Yahoo downloads use daily interval,
`auto_adjust=False` to preserve raw OHLC values, `actions=True` to request
dividends/splits, and `threads=False` to avoid excessive concurrent requests.

## API

- `GET /api/v1/companies?exchange=NSE&instrument_type=company`
- `GET /api/v1/market/overview`
- `GET /api/v1/stocks/{symbol}/history?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&interval=1d`
- `GET /api/v1/stocks/{symbol}/indicators`
- `GET /api/v1/ingestion/runs`

### Financial news source registry

The news ingestion foundation currently defines seven candidate sources:

- Google News RSS Search
- The Economic Times

- RBI Press Releases
- RBI Notifications
- RBI Speeches
- SEBI Official Updates
- BSE Notices

The Google News RSS Search and Economic Times entries are enabled for
metadata-only ingestion. The remaining five sources are disabled and pending
review. Public RSS availability does not by itself grant permission for
permanent storage, redistribution, or AI/ML processing.

The news source registry and provider adapters are configuration-only until a
source is explicitly approved. The Google News RSS Search and Economic Times
entries are explicitly approved for metadata-only storage; the remaining
entries remain `pending_review`.

### Safe news feed HTTP client

`app.services.news.http_client.SafeFeedHttpClient` is the explicit network
boundary for future RSS/Atom fetching. It uses a 20-second default timeout, a
2 MiB default response-size limit, a bounded redirect policy, and the
`ArthAI-NewsFetcher/0.1` user agent. It accepts common RSS/Atom XML MIME types
and validates `text/plain` responses as RSS or Atom XML before returning raw
bytes.

Requests accept only absolute HTTP(S) URLs without credentials. Redirect
destinations are revalidated, sensitive headers are not forwarded, and DNS
results are checked against localhost, private, loopback, link-local,
reserved, unspecified, and multicast address ranges. This is a defense-in-
depth SSRF boundary, not a complete DNS-rebinding guarantee: a future
production transport should pin or revalidate the connected address if
stronger rebinding protection is required.

The client does not poll automatically, activate registry sources, parse
articles, persist data, or schedule background work. Callers must explicitly
provide a configured source and invoke fetching.

### News ingestion orchestration

`app.services.news.ingestion.ingest_news_source` is the explicit orchestration
boundary for a single source. A source must be enabled in the immutable
registry, have an active matching `NewsSource` database record, and have the
`approved_content_storage` policy before articles may be persisted. The five
real registry entries remain disabled and `pending_review`; metadata-only
approval is intentionally not sufficient for article storage.

The service creates a `running` ingestion run, fetches through the safe HTTP
client, parses through the existing RSS/Atom provider, validates persistence
fields, and stores a batch transactionally. Existing URL hashes and
source-scoped external IDs are skipped, as are duplicate entries within one
feed. `articles_discovered` counts parsed entries, while `articles_inserted`
and `articles_skipped` account for every discovered entry; completed runs
maintain `discovered = inserted + skipped`. Unexpected batch failures roll
back article changes and finalize the run as failed with a sanitized error.

This is an explicit, offline-tested service boundary. It does not activate
sources, poll automatically, schedule work, run a background worker, expose
an API route, or contact the real registry endpoints by itself.

### Controlled source registration and ingestion commands

Source registration is idempotent and uses `provider_key` as the stable
identity. It refreshes configured metadata but never silently changes an
existing source's active state:

```powershell
.\venv\Scripts\python.exe -m app.scripts.register_news_sources
```

The controlled ingestion command accepts registry keys only; it never accepts
an arbitrary URL:

```powershell
.\venv\Scripts\python.exe -m app.scripts.ingest_news --source rbi_press_releases --dry-run
.\venv\Scripts\python.exe -m app.scripts.ingest_news --all-eligible
```

Dry-run fetches and parses a selected registry feed, validates entries,
calculates duplicate candidates, and previews company matches without creating
ingestion runs or changing database state. It is allowed for source review
even while a source is pending policy review, but it is not an approval or
ingestion operation.

Normal ingestion requires an enabled registry source, an active registered
database source, and `approved_content_storage`. The optional
`--allow-metadata-only` flag is an explicit operational choice for a source
with `approved_metadata_only`; it stores only headline, URL, source identity,
publication time, language, and external ID, discarding summary and author.
It does not override registry activation or approval checks.

Migration `0005_news_source_attribution` adds the nullable attribution field
needed to record the attribution supplied during any future explicit source
activation. It does not activate or approve any current registry entry.

The ingestion service updates `last_success_at` after successful or partial
runs and records a sanitized `last_error` for failed runs. Company matching is
performed through the existing deterministic matcher and unambiguous matches
are linked during the same article persistence transaction. No scheduled
polling is installed.

The `google_news_search` provider builds one Google News RSS search per active
company, including its symbol and active aliases, then merges duplicate URLs
before persistence. Google wrapper links are retained as metadata URLs and are
not resolved to publisher URLs.

Inspect registered sources and ingestion history through:

```text
GET /api/v1/news/sources
GET /api/v1/news/ingestion/runs
```

Repeat ingestion is safe after a source is approved and activated. URL hashes,
source-scoped external IDs, and duplicate entries in one feed are skipped;
existing article fields are not overwritten. A second run is still recorded.
For troubleshooting, an HTTP 403 indicates that the feed endpoint denied the
request, malformed XML is recorded as a failed run, and an unavailable or
unapproved source is rejected before fetching. These failures do not
automatically disable or delete a source.

The existing RBI, SEBI, and BSE source state remains five inactive,
`pending_review` sources. The Economic Times metadata-only source is
explicitly activated separately as documented below. See
`docs/NEWS_SOURCE_PERMISSION_REVIEW.md` for the official-source review.

### Phase 2J provider gate

The mandatory GDELT DOC feasibility probe was run on 2026-10-31 without
changing the production database. The endpoint returned repeated HTTP 429
throttle responses and empty 200 responses for the tested Indian market and
company queries, so it did not meet the required coverage threshold. GDELT
was not registered or activated. Provider research and the exact measured
results are documented in `docs/NEWS_PROVIDER_RESEARCH.md` and
`docs/GDELT_FEASIBILITY_REPORT.md`; the implementation status is in
`docs/PHASE_2J_IMPLEMENTATION.md`.

Do not run live ingestion for an unapproved source. A future approved source
must first be registered, explicitly activated, and then invoked through the
controlled CLI below. No automatic scheduler is installed.

The Economic Times markets RSS source is the one locally approved
metadata-only source. Its activation is explicit and stores only headlines,
direct publisher URLs, timestamps, discovery timestamps and company links:

```powershell
.\venv\Scripts\python.exe -m app.scripts.register_news_sources `
  --source economic_times_markets --activate-metadata-only
.\venv\Scripts\python.exe -m app.scripts.ingest_news `
  --source economic_times_markets --allow-metadata-only
```

The source terms require personal, non-commercial use and a functional direct
link to the full article. Google News RSS is not used because its item links
remain Google intermediary URLs and its feed terms restrict use to personal,
non-commercial feed readers.

`POST /api/v1/news/ingestion/{source_key}` is the controlled operational
trigger for an explicitly eligible registered source. It accepts only the
registry key; callers cannot provide a feed URL or override provider or policy
configuration. The registry source must be enabled, have `approved_content_storage` or
`approved_metadata_only` policy, and have a matching active `NewsSource`
database record. Unknown sources return `404`; disabled, unapproved, missing,
or inactive sources return `409`. The response contains the persisted run ID,
status, timestamps, discovered/inserted/skipped counts, a zero
`failed_count` (the current ingestion model has no failed-article counter),
and a safe message.

The trigger uses a non-blocking in-process lock keyed by provider key. A
second request for the same source returns `409` instead of starting another
fetch; locks are released after both success and failure. Different source
keys have independent locks. This protects only one backend process and is
not distributed across multiple Uvicorn workers or backend instances. The
endpoint currently has no authentication or authorization and should not be
publicly exposed without access control. It is an operational ingestion
trigger, not a public arbitrary-URL fetcher.

### Company entity matching and news deduplication

Company matching is deterministic and rule-based. Explicit aliases are
normalized before storage and can be deactivated without deleting history;
aliases are never inferred or added automatically. Matching priority is exact
symbol, exact normalized company name, then exact active alias. Article text
matching scans headline and summary with token boundaries, prefers longer
phrases, and can return multiple companies.

Match confidence values are fixed rule scores, not trained probabilities:
exact symbols use `1.0`, company names use `0.95`, and aliases use `0.85`.
When an alias belongs to multiple companies, the result is marked ambiguous
with all candidate IDs and no article-company link is created.

Unambiguous matches may be stored in `news_article_companies` with their
method, fixed confidence, and matched text. Existing links are preserved and
duplicate links are ignored.

Cross-source duplicate detection is advisory and does not merge or delete
records. A matching canonical URL hash or strong content hash is a duplicate;
matching headlines without sufficient identity evidence are `uncertain`.
Provider-specific external IDs and headline similarity alone are never treated
as globally comparable identity. No fuzzy matching, NLP model, or LLM is used.

### Read-only financial news APIs

The news API returns stored database records only; GET requests never fetch
external feeds or trigger ingestion:

- `GET /api/v1/news` lists articles with `page` (default `1`) and `page_size`
  (default `20`, maximum `100`), plus optional `company`, `source`,
  `start_date`, `end_date`, and headline `search` filters.
- `GET /api/v1/news/{article_id}` returns article, source, and company-match
  metadata.
- `GET /api/v1/companies/{symbol}/news` lists news linked to an active company
  and supports pagination and publication date filters.
- `GET /api/v1/news/sources` lists safe source identity and status fields.
- `GET /api/v1/news/ingestion/runs` lists paginated ingestion history with
  optional `source` and `status` filters.

Article and company-news list responses use:

```json
{
  "items": [],
  "pagination": {
    "total": 0,
    "page": 1,
    "page_size": 20,
    "total_pages": 0
  }
}
```

Articles are ordered by publication time descending, with undated articles
after dated articles and article ID as a deterministic tie-breaker. Invalid
date ranges return `400`; unknown articles or inactive/unknown companies return
`404`; invalid pagination and ingestion statuses return standard validation
errors. Responses do not expose raw provider payloads, feed URLs, credentials,
stack traces, or unsanitized internal error details.

### Technical indicators

`GET /api/v1/stocks/{symbol}/indicators` calculates indicators on demand from
the instrument's stored daily records. It does not download data or persist
calculated values. The default parameters are:

| Query parameter | Default | Description |
| --- | ---: | --- |
| `price_field` | `close` | `close` or `adjusted_close` for price-based indicators |
| `sma_period` | `20` | Simple moving average period |
| `ema_period` | `20` | Exponential moving average period |
| `rsi_period` | `14` | Wilder RSI period |
| `macd_fast_period` | `12` | MACD fast EMA period |
| `macd_slow_period` | `26` | MACD slow EMA period |
| `macd_signal_period` | `9` | MACD signal EMA period |
| `bollinger_period` | `20` | Bollinger rolling-window period |
| `bollinger_std_dev` | `2.0` | Bollinger population standard-deviation multiplier |
| `atr_period` | `14` | Wilder ATR period |
| `start_date`, `end_date` | absent | Optional inclusive output dates |

For example:

```text
/api/v1/stocks/RELIANCE/indicators?start_date=2025-01-01&price_field=close
```

The response contains one record per stored trading date in the requested
output range, plus the selected parameters and metadata. Calculations are
performed using all records through `end_date` before `start_date` is applied,
so prior history contributes to the warm-up period. Indicator values are
`null` until their full warm-up window is available; missing values are never
forward-filled. An unknown or inactive symbol returns `404`, invalid dates or
period combinations return `400`, and an empty history returns a successful
response with an empty `records` list.

SMA uses a full rolling window. EMA uses `ewm(adjust=False)`. RSI and ATR use
Wilder smoothing. Bollinger Bands use population standard deviation (`ddof=0`).
ATR uses raw high, low, and previous raw close. Therefore, when
`price_field=adjusted_close`, price-based indicators use adjusted close but ATR
is explicitly not fully split-adjusted. This endpoint is analytical output,
not investment advice or a trading signal.

Run the app with:

```powershell
.\venv\Scripts\uvicorn.exe app.main:app --reload
```

## Tests

```powershell
.\venv\Scripts\pytest.exe
```

Tests use a synthetic in-memory dataset and a mocked provider only. Synthetic
prices are never inserted into the development database.
