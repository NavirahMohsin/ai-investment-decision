# News Provider Research

Review date: 2026-10-31

This is an engineering and permission review, not legal advice. Technical API
access does not by itself establish permission to persist, publicly display, or
process publisher material with AI/NLP.

## Comparison

| Provider | API access and India coverage | Free limits / pricing observed | Metadata storage and public display | Decision |
|---|---|---|---|---|
| GDELT DOC 2.0 | Public JSON DOC endpoint; global coverage and source-country/query filters are documented. Live tests in this environment were throttled and returned no usable records. | No paid API plan was identified in the reviewed official material. The live endpoint explicitly requested no more than one request every five seconds. | GDELT states that datasets may be reused and redistributed with citation. That does not grant rights to reproduce publisher articles. Store only provider metadata and original links after confirming the intended use and attribution. | `permission_unclear`; technical `NO-GO` for this milestone because live reliability was not demonstrated. |
| The Economic Times RSS | Official Indian markets RSS feed; live tests returned current market, NIFTY, SEBI and earnings headlines with direct ET article URLs. | RSS is presented as a free service; no API key or quota was required in testing. | The official RSS terms allow personal, non-commercial use and require a functional link directly to the full article. This implementation stores only headline, direct URL, publication time and source identity; it does not store excerpts. | Selected for the local personal/non-commercial milestone with explicit metadata-only activation. |
| MarketNewsAPI | REST API advertises worldwide equity/ETF news, including article links, source, timestamps and tickers. Indian coverage should be verified with an authenticated account. | Official docs list Free at 100 requests/day with a 15-minute delay; Pro is listed at $15/month (subject to change). | Terms describe publisher articles as headlines, snippets, summaries and links, but the reviewed terms do not clearly grant ArthAI a permanent public database/archive of those fields. | `permission_unclear`; do not persist without written clarification or a license covering this project. |
| Marketaux | API supports entity symbols, exchanges, countries and global financial news. Indian exchange/entity coverage is technically plausible but requires an API token to verify. | Free access requires registration; current quota details are account/pricing dependent. | The reviewed Terms of Use did not clearly establish permanent metadata retention and public display for this use case. | `permission_unclear`; do not integrate into persistent storage without clarification. |
| NewsAPI.org | Search API provides headlines, descriptions and URLs; it is not selected for India-specific coverage. | Developer plan is development/testing only. Paid pricing and quotas are listed on the official pricing page. | Terms prohibit building a competing news database, prohibit republishing copyrighted material, and restrict public disclosure of returned data. | `NO-GO` for this architecture. |
| Alpha Vantage | `NEWS_SENTIMENT` is documented as part of Alpha Intelligence, but the official docs do not establish adequate NSE/Indian coverage for this milestone. | API-key access and plan limits apply; current quota depends on the selected plan. | The reviewed official documentation is technical and does not establish permission for a permanent public metadata archive or publisher-link display in ArthAI. | `permission_unclear`; reference only. |

## Official sources reviewed

- [GDELT DOC 2.0 API announcement](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)
- [GDELT terms of use](https://www.gdeltproject.org/about.html)
- [Economic Times RSS directory and terms](https://economictimes.indiatimes.com/rss_index.cms)
- [MarketNewsAPI documentation](https://marketnewsapi.com/docs)
- [MarketNewsAPI terms](https://marketnewsapi.com/legal/terms)
- [Marketaux documentation](https://www.marketaux.com/documentation)
- [Marketaux Terms of Use](https://www.marketaux.com/tos)
- [NewsAPI terms](https://newsapi.org/terms)
- [NewsAPI pricing](https://newsapi.org/pricing)
- [Alpha Vantage documentation](https://www.alphavantage.co/documentation/)

## Recommendation

GDELT is the only candidate tested without an API key, but it did not meet the
technical acceptance threshold during the controlled probe. No provider has
been activated or granted a persistent-storage approval in the registry. The
next implementation step requires either a repeatable GDELT access arrangement
that meets its throttle and attribution requirements, or written permission
and credentials for a provider whose terms explicitly cover metadata retention
and the intended display.
