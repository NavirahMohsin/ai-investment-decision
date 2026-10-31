# News Source Permission Review

Review date: 2026-10-31

This is an operational engineering assessment, not legal advice. Feed
reachability does not establish permission to retain, reproduce, redistribute,
or process content with AI/NLP. No source was approved or activated in this
review.

## Decision summary

| Provider key | Feed reachable | Registered | Activated | Decision |
|---|---:|---:|---:|---|
| `economic_times_markets` | Yes | Yes | Yes, metadata-only | Approved for local personal/non-commercial use |
| `rbi_press_releases` | Yes | Yes | No | `pending_review` |
| `rbi_notifications` | Yes | Yes | No | `pending_review` |
| `rbi_speeches` | Yes | Yes | No | `pending_review` |
| `sebi_official` | Yes | Yes | No | `pending_review` |
| `bse_notices` | No, HTTP 403 | Yes | No | `pending_review` |

## Economic Times markets RSS

- **Feed:** <https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms>
- **Terms/policy reviewed:** <https://economictimes.indiatimes.com/rss_index.cms>
- **Feed check:** HTTP 200; 50 RSS entries were parsed during the controlled
  ingestion on 2026-10-31. The entries supplied headlines, publication
  timestamps, and direct `economictimes.indiatimes.com` article URLs.
- **Link verification:** Representative market and earnings URLs returned
  HTTP 200 without an intermediary redirect. The frontend uses those URLs
  directly for headline and external-link navigation.
- **Permitted scope used here:** The RSS terms describe a free service for
  individuals using the feeds for personal, non-commercial use and require a
  functional link directly to the full article. ArthAI stores only headline,
  direct URL, publisher/source identity, publication time, discovery time and
  deterministic company links. It discards RSS descriptions and author data
  under the metadata-only policy.
- **Attribution:** `Source: The Economic Times`.
- **Decision:** Metadata-only source activated for this local
  personal/non-commercial project. Reassess before commercial deployment,
  redistribution, or public syndication.

## RBI Press Releases

- **Feed:** <https://www.rbi.org.in/pressreleases_rss.xml>
- **Terms/policy reviewed:** <https://www.rbi.org.in/Scripts/Disclaimer.aspx>
- **Feed check:** HTTP success; RSS parsed; 10 entries observed; summaries and
  article links were present. The observed `pubDate` values did not include a
  timezone offset and are therefore retained only as raw source timestamps by
  the parser.
- **Automated retrieval:** The feed was reachable during the controlled check.
  The disclaimer reserves RBI's right to restrict access; it does not
  explicitly grant this application's intended automated retrieval and storage
  rights.
- **Metadata/headline storage:** Not established by the reviewed policy.
- **Summary/content storage:** Not established.
- **AI/NLP processing:** Not established.
- **Attribution:** No required wording was established. Do not invent wording.
- **Decision:** `pending_review`.
- **Required follow-up:** Obtain written permission or authoritative reuse terms
  covering the intended fields and AI/NLP processing.

## RBI Notifications

- **Feed:** <https://rbi.org.in/notifications_rss.xml>
- **Terms/policy reviewed:** <https://www.rbi.org.in/Scripts/Disclaimer.aspx>
- **Feed check:** HTTP success; RSS parsed; 10 entries observed; summaries and
  article links were present. Observed publication timestamps lacked explicit
  timezone offsets.
- **Automated retrieval:** Reachable during the controlled check, but no
  explicit permission for this application's automated retrieval was found.
- **Metadata/headline storage:** Not established.
- **Summary/content storage:** Not established.
- **AI/NLP processing:** Not established.
- **Attribution:** No required wording established.
- **Decision:** `pending_review`.
- **Required follow-up:** Obtain written permission or authoritative reuse terms.

## RBI Speeches

- **Feed:** <https://www.rbi.org.in/speeches_rss.xml>
- **Terms/policy reviewed:** <https://www.rbi.org.in/Scripts/Disclaimer.aspx>
- **Feed check:** HTTP success; RSS parsed; 10 entries observed; summaries and
  article links were present. Observed publication timestamps lacked explicit
  timezone offsets.
- **Automated retrieval:** Reachable during the controlled check, but no
  explicit permission for this application's automated retrieval was found.
- **Metadata/headline storage:** Not established.
- **Summary/content storage:** Not established.
- **AI/NLP processing:** Not established.
- **Attribution:** No required wording established.
- **Decision:** `pending_review`.
- **Required follow-up:** Obtain written permission or authoritative reuse terms.

## SEBI Official Updates

- **Feed:** <https://www.sebi.gov.in/sebirss.xml>
- **Terms/policy reviewed:** <https://www.sebi.gov.in/website-policy.html>
- **Feed check:** HTTP success; RSS parsed; 30 entries observed; summaries and
  article links were present. Observed timestamps included an explicit `+0530`
  offset.
- **Automated retrieval:** The feed was reachable, but the reviewed policy does
  not explicitly grant the intended automated storage and processing use.
- **Metadata/headline storage:** The policy says material may be reproduced
  after proper permission; permission was not obtained for ArthAI.
- **Summary/content storage:** Not permitted on the evidence available.
- **AI/NLP processing:** Not established; third-party material may require
  separate authorization.
- **Attribution:** The policy requires prominent source acknowledgement when
  material is published or issued. Exact ArthAI attribution wording was not
  supplied by SEBI.
- **Decision:** `pending_review`.
- **Required follow-up:** Obtain permission from SEBI and separately assess any
  third-party material.

## BSE Notices

- **Feed:** <https://www.bseindia.com/data/xml/notices.xml>
- **Terms/policy reviewed:** <https://www.bseindia.com/static/about/Terms_condition.htm>
- **Feed check:** HTTP 403 from the registered endpoint; no entries were
  parsed; no linked PDFs were downloaded.
- **Automated retrieval:** Not established; access was denied during the
  controlled check.
- **Metadata/headline storage:** Not established.
- **Summary/content storage:** Not established.
- **AI/NLP processing:** Not established.
- **Attribution:** No required wording established.
- **Decision:** `pending_review`.
- **Required follow-up:** Confirm an authorized feed endpoint and obtain reuse
  permission before any ingestion.

## Activation rule

A source must remain inactive until its immutable registry configuration is
enabled, the intended persistence mode is explicitly approved, the feed is
verified, explicit approval is recorded, and required attribution is supplied.
The activation service persists attribution in `news_sources.attribution_text`.
