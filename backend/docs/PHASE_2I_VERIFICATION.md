# Phase 2I Verification

Verification date: 2026-10-31

## What was implemented

- Registered all five existing registry configurations through the existing
  idempotent registration command.
- Preserved all sources as inactive.
- Added the auditable `news_sources.attribution_text` field and migration
  `0005_news_source_attribution`.
- Preserved controlled activation requirements.
- Reused the existing safe HTTP client, RSS/Atom parser, validation,
  deduplication, ingestion service, and deterministic company matcher.
- Added the registry-key-only ingestion CLI dry-run and actual-ingestion
  commands.
- Added metadata-only field enforcement when explicitly requested for an
  approved metadata-only source.
- Updated backend operational documentation.

## Source registration

Initial registration created:

```text
rbi_press_releases -> source_id=1, active=False
rbi_notifications  -> source_id=2, active=False
rbi_speeches       -> source_id=3, active=False
sebi_official      -> source_id=4, active=False
bse_notices        -> source_id=5, active=False
```

A second registration pass updated all five records without creating
duplicates or changing their inactive state.

## Permission and activation

No source was approved or activated. All five remain
`pending_review` because the reviewed evidence does not establish the
intended rights to persist and process feed content. SEBI's policy requires
permission before reproduction. The RBI material reviewed did not grant the
intended application rights. BSE returned HTTP 403 and its permitted-use
status could not be established.

The full assessment is in
[NEWS_SOURCE_PERMISSION_REVIEW.md](./NEWS_SOURCE_PERMISSION_REVIEW.md).

## Real feed verification

The command used was:

```powershell
python -m app.scripts.ingest_news `
  --source rbi_press_releases `
  --source rbi_notifications `
  --source rbi_speeches `
  --source sebi_official `
  --source bse_notices `
  --dry-run
```

Results:

```text
rbi_press_releases: discovered=10 valid_candidates=10 skipped=0 invalid=0 duplicate_urls=0 duplicate_external_ids=0 url_hashes=10 content_hashes=0 company_matches=0
rbi_notifications: discovered=10 valid_candidates=10 skipped=0 invalid=0 duplicate_urls=0 duplicate_external_ids=0 url_hashes=10 content_hashes=0 company_matches=1
rbi_speeches: discovered=10 valid_candidates=10 skipped=0 invalid=0 duplicate_urls=0 duplicate_external_ids=0 url_hashes=10 content_hashes=0 company_matches=0
sebi_official: discovered=30 valid_candidates=30 skipped=0 invalid=0 duplicate_urls=0 duplicate_external_ids=0 url_hashes=30 content_hashes=30 company_matches=0
bse_notices: FeedHTTPStatusError (HTTP 403)
```

The dry-run created no ingestion runs, articles, or source status changes.
No actual ingestion was run because no source qualified.

## Actual ingestion and repeat ingestion

Actual ingestion: none.

Repeat-ingestion test: not applicable to production because no source was
approved or activated. Offline ingestion tests verify URL deduplication,
source-scoped external-ID deduplication, duplicate entries within a feed,
non-overwrite behavior, and transactional rollback.

## Company matching

Real dry-run candidates produced one candidate with a deterministic company
match. No production article-company links were created.

Offline tests cover:

- Exact symbols.
- Normalized company names.
- Explicit aliases.
- Multiple matches.
- Ambiguous aliases without automatic links.
- Duplicate-link prevention.
- Match method, deterministic score, and matched text.

Match scores are deterministic rule scores, not trained probabilities.

## Database counts

| Metric | Before | After |
|---|---:|---:|
| Companies | 22 | 22 |
| Daily market data | 25,952 | 25,952 |
| Registered news sources | 0 | 5 |
| Active news sources | 0 | 0 |
| News articles | 0 | 0 |
| Article-company links | 0 | 0 |
| Ingestion runs | 0 | 0 |
| Successful runs | 0 | 0 |
| Partial-success runs | 0 | 0 |
| Failed runs | 0 | 0 |

Current Alembic revision: `0005_news_source_attribution`.

Integrity checks confirmed:

- Five distinct provider keys.
- No duplicate article URL hashes.
- No duplicate article-company pairs.
- No orphaned records were found in the empty news tables.
- No ingestion runs are stuck in `running`.

## Frontend integration

The existing frontend routes and API integration were preserved. Since no
permitted articles exist, the expected empty news state remains the correct
production behavior. No mock articles were inserted.

Browser automation was performed against local development servers:

- `/news`: rendered empty state, company/source selectors, date fields, and
  clear control.
- `/news/sources`: rendered all five registered sources with inactive status.
- `/news/ingestion`: rendered empty history, source filter, status filter, and
  read-only security notice.
- `/news/invalid-article-id`: rendered the invalid article ID state.
- `/stocks`: rendered the 22-instrument stock explorer.
- `/stocks/RELIANCE`: rendered the valid stock detail page, historical chart,
  and technical-analysis controls.
- Desktop viewport: `1280x900`.
- Mobile viewport: `390x844`.
- No uncaught page errors were observed.
- No horizontal overflow was observed on the tested pages.
- Local route navigation and sidebar links rendered correctly.

The empty database prevented meaningful populated-card, article-detail,
pagination-next-page, and related-company-news testing. No records were added
to overcome that limitation.

Frontend validation also passed:

- `npm run lint`
- `npm run build`

## Tests

Passed:

- `python -m compileall -q app`
- `python -m pytest -q` — 151 passed
- `npm run lint`
- `npm run build`
- `git diff --check`

## Known limitations and remaining actions

- No source has documented permission for the intended persistent storage and
  AI/NLP processing workflow.
- RBI timestamps without offsets cannot be safely normalized to UTC.
- BSE's registered feed currently returns HTTP 403.
- No actual production ingestion or repeat-ingestion run was possible.
- Browser verification remains pending.
- Obtain written permissions and attribution wording before enabling a source.
- Re-verify BSE's authorized feed endpoint before considering it.
- Only then activate a source through the controlled activation flow and run
  actual ingestion.

## Status

**Phase 2I is partially complete.** Registration, safety controls, dry-run
verification, documentation, offline tests, and build validation are complete.
Controlled activation and actual ingestion remain blocked by unresolved source
permission and access evidence.
