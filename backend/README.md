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
- `GET /api/v1/ingestion/runs`

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
