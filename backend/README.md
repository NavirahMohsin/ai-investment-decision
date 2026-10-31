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
