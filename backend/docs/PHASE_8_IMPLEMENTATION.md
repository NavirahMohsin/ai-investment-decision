# ArthAI Phase 8 — Company Profiles & Sector Intelligence

## Architecture

Phase 8 extends the Phase 7 Yahoo Finance fundamentals pipeline without adding a provider. `CompanyProfile` stores extended profile metadata, while `Sector` stores normalized Yahoo sector/industry classifications. `Company.sector_id` links tracked companies to classifications; the existing `Company.sector` string remains for backward compatibility with Phase 6/7 APIs and seeded data.

The provider reads Yahoo Finance `Ticker.info` fields that are available for the instrument. Headquarters, fiscal year, industry, employee count, website, business summary, market capitalization, and enterprise value are persisted when supplied. Products/services and revenue segments remain nullable because Yahoo does not provide a consistent, reliable structured representation for all companies.

Sector analytics are calculated from persisted tracked-company data:

- latest two persisted daily prices for daily change;
- persisted fundamental scores for company rankings;
- persisted market capitalization and profile classification;
- no synthetic values for missing prices, scores, sectors, or profile fields.

## API

| Route | Purpose |
|---|---|
| `GET /api/v1/companies/{symbol}/profile` | Extended company profile and metadata |
| `GET /api/v1/sectors` | Sectors and industries represented in the tracked universe |
| `GET /api/v1/sectors/{sector_name}` | Sector company rankings and aggregate market/fundamental signals |

Sector responses explicitly return `data_scope=tracked_universe` and warnings that the aggregates are not market-wide benchmarks.

## Frontend

- Stock detail pages now include a profile card with business description, listing, headquarters, website, industry, employees, fiscal year, currency, freshness, and Yahoo limitations.
- `/sectors` provides sector selection, tracked-company counts, average daily change, average fundamental score, rankings, and missing-data warnings.
- Sidebar navigation includes Sector Intelligence.
- Existing stock explorer, fundamentals, technical indicators, market dashboard, comparison, and News routes are preserved.

## Refresh and setup

Run the existing fundamentals refresh flow to populate Phase 8 metadata:

```text
POST /api/v1/fundamentals/refresh
{"symbols":["RELIANCE"],"include_info":true,"include_statements":false,"include_ratios":false}
```

Apply migrations from `backend` with `alembic upgrade head`. Migration `0010_company_profiles_sectors` creates sectors, adds the company relationship, and creates profile metadata storage.

## Limitations

Yahoo Finance is unofficial and may delay, revise, rate-limit, or omit profile and financial data. Sector aggregates cover only active companies tracked by ArthAI and must not be interpreted as official market-wide sector benchmarks. Company industry classification can change or be unavailable. No products, services, revenue segments, or benchmark values are invented when Yahoo does not report them.
