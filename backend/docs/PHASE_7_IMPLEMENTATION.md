# ArthAI Phase 7 — Company Fundamentals

## Scope and architecture

Phase 7 extends the existing FastAPI/SQLAlchemy application with company fundamentals sourced only from Yahoo Finance through `yfinance`. The provider adapter in `app/services/providers/yahoo.py` normalizes company metadata and annual/quarterly income, balance-sheet, cash-flow, and ratio values. `CompanyFundamentalInfo` stores point-in-time metadata; `CompanyFinancial` stores reported observations and TTM ratios; `FundamentalDataUpdateRun` records refresh outcomes.

The read path is deliberately provider-free: API routes call query, ratio, historical-performance, analysis, and scoring services over persisted data. This prevents a slow or unavailable Yahoo request from blocking a stock-detail page. Refreshes are explicitly triggered by the refresh endpoint or the low-frequency scheduler and use per-company isolation, a process lock, retries, and run tracking.

## API surface

All routes are under `/api/v1/fundamentals`:

| Route | Purpose |
|---|---|
| `GET /{symbol}` | Company overview, highlights, ratios, assessment, and score |
| `GET /{symbol}/statements?statement_type=income\|balance\|cashflow` | Persisted annual or quarterly statement lines |
| `GET /{symbol}/ratios?period_type=annual\|quarterly\|ttm` | Calculated and retrieved ratios |
| `GET /{symbol}/history?period_type=annual\|quarterly` | Historical series, growth, trends, margins, and cash conversion |
| `GET /{symbol}/analysis` | Explainable dimension assessments |
| `GET /{symbol}/score` | Weighted score with completeness and exclusions |
| `GET /compare?symbols=A&symbols=B` | Multi-company comparison, rankings, and comparability warnings |
| `GET /dashboard` | Dashboard-level fundamental summaries |
| `GET /health` | Provider/update health and stale-company status |
| `POST /refresh` | Controlled manual refresh for selected companies or all companies |

The frontend consumes these routes from the stock-detail page, dashboard, and `/stocks/compare`.

## Calculation methodology

- Growth: `(current - previous) / previous`; a missing value or zero prior value produces unavailable data, never zero.
- Margins: profit divided by revenue, expressed as a percentage.
- ROE/ROA/ROCE: earnings or operating profit divided by the corresponding persisted equity/assets/capital base.
- Liquidity and leverage: current assets/current liabilities, debt/equity, quick ratio, and interest coverage where inputs exist.
- Cash conversion: operating cash flow and free cash flow relative to net income.
- P/E, P/B, EV/EBITDA, and P/S use Yahoo-retrieved TTM values when available, otherwise calculate only when the required persisted inputs exist.
- Historical trend classification requires sufficient observations and reports incomplete or inconsistent series explicitly.

The explainable analysis applies sector-aware threshold rules to profitability, growth, stability, valuation, and cash-flow dimensions. The score combines included dimensions using configured weights; dimensions with insufficient data are excluded and reported. Scores are assessments of reported financial condition, not investment advice or return predictions.

## Setup and operations

1. Install `backend/requirements.txt`.
2. Set the normal application settings in `.env`, including `ENABLE_FUNDAMENTALS_SCHEDULER` and `FUNDAMENTALS_REFRESH_INTERVAL_HOURS` when scheduled updates are desired.
3. Run `alembic upgrade head` from `backend`.
4. Start FastAPI and the Next.js frontend as documented in the respective READMEs.
5. Trigger a targeted refresh with `POST /api/v1/fundamentals/refresh` after companies have been seeded.

## Yahoo Finance limitations

Yahoo Finance is the only approved market-data provider for this phase. Its data may be delayed, stale, revised, rate-limited, incomplete, differently named across issuers, or unavailable for a particular period. Financial statement period coverage and ratio definitions can vary by company. ArthAI preserves missing values as unavailable, exposes freshness and warnings, and does not fabricate zeros. Users should verify material decisions against authoritative filings.

## Verification status

Backend fundamentals, comparison, reliability, and regression tests are in `backend/tests`. Frontend validation uses `npm run lint`, `npx tsc --noEmit`, and `npm run build` from `frontend`. The final phase report should record the exact command result for the current environment.
