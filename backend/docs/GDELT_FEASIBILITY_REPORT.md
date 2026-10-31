# GDELT DOC 2.0 Feasibility Report

Test date: 2026-10-31  
Decision: **NO-GO for persistent integration in Phase 2J**

The test was read-only. It did not modify the production SQLite database, add
sources, or persist provider responses.

## Request configuration

All requests used:

```text
GET https://api.gdeltproject.org/api/v2/doc/doc
mode=artlist
format=json
maxrecords=50 (10 on the cooldown retry)
sort=datedesc
timespan=3d (1d on the cooldown retry)
```

Queries used the documented-style `sourcecountry:india` operator. No API key
was used and no publisher page was fetched.

## Market-wide probes

| Query | HTTP result | Parsed records | Observation |
|---|---:|---:|---|
| `Indian stock market sourcecountry:india` | 429 | 0 | Endpoint instructed clients to limit requests to one every five seconds. |
| `NSE India sourcecountry:india` | 429 | 0 | Same throttle response. |
| `NIFTY 50 sourcecountry:india` | 429 | 0 | Same throttle response. |
| `BSE India sourcecountry:india` | 429 | 0 | Same throttle response. |
| `Indian banking stocks sourcecountry:india` | 429 | 0 | Same throttle response. |
| `RBI monetary policy sourcecountry:india` | 429 | 0 | Same throttle response. |
| `Indian IPOs sourcecountry:india` | 200 | 0 | Response was empty/returned no `articles` array. |
| `Indian corporate earnings sourcecountry:india` | 200 | 0 | Response was empty/returned no `articles` array. |
| cooldown retry: `NSE India sourcecountry:india` | 200 | 0 | Response body was `{}`. |

## Company-specific probes

| Query | HTTP result | Parsed records |
|---|---:|---:|
| `Reliance Industries sourcecountry:india` | 429 | 0 |
| `Tata Consultancy Services sourcecountry:india` | 429 | 0 |
| `HDFC Bank sourcecountry:india` | 200 | 0 |
| `Infosys sourcecountry:india` | 429 | 0 |
| `ICICI Bank sourcecountry:india` | 429 | 0 |

The endpoint returned the following sanitized 429 body:

```text
Please limit requests to one every 5 seconds or contact the GDELT project
for larger queries. High-traffic users should switch to the ngrams dataset.
```

## Data-quality findings

No article records were returned, so there were no valid headlines, original
URLs, publisher domains, publication timestamps, languages, or provider
identifiers to map to `NormalizedNewsArticle`. Consequently:

- relevant Indian financial records: 0 observed;
- distinct publishers: 0 observed;
- duplicate URL assessment: not measurable;
- missing-field and timestamp-preservation assessment: not measurable;
- malformed URL and malformed-record fixtures remain unit-test work, not live
  evidence.

The result is below the acceptance threshold of at least 10 relevant records
from at least five publishers. The repeated 429 responses are a severe
reliability issue for an uncontrolled manual/CLI ingestion workflow.

## Permission assessment

GDELT's official terms state that GDELT datasets may be reused and
redistributed with citation and a link to the GDELT Project. That statement
does not automatically grant rights to reproduce third-party publisher
articles. Any future adapter must therefore persist only permitted metadata,
retain original URLs for attribution, avoid snippets/bodies/images, and obtain
confirmation that the intended public display is covered.

## Final decision and next step

Do not register or activate GDELT, do not add an adapter, and do not ingest
live records until the endpoint is demonstrably repeatable under an approved
request rate and the intended metadata/link display is confirmed. The existing
RBI, SEBI, and BSE sources remain inactive and `pending_review`.

