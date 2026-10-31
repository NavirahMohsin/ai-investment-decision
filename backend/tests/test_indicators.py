from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from app.db.models import Company, DailyMarketData
from app.services.indicators import (
    AdjustedCloseUnavailable,
    IndicatorParameters,
    calculate_indicators,
)


def make_rows(count=35, adjusted=True):
    rows = []
    for index in range(count):
        close = Decimal(str(100 + index))
        rows.append(
            DailyMarketData(
                trading_date=date(2025, 1, 1) + timedelta(days=index),
                open=close - Decimal("1"),
                high=close + Decimal("2"),
                low=close - Decimal("2"),
                close=close,
                adjusted_close=close if adjusted else None,
                volume=1000 + index,
                provider="test",
            )
        )
    return rows


def test_indicators_have_expected_warmup_and_finite_values():
    rows = make_rows()
    parameters = IndicatorParameters(
        sma_period=3,
        ema_period=3,
        rsi_period=3,
        macd_fast_period=2,
        macd_slow_period=4,
        macd_signal_period=2,
        bollinger_period=3,
        atr_period=3,
    )
    records, available, first, last = calculate_indicators(rows, parameters)

    assert available == 35
    assert first == date(2025, 1, 1)
    assert last == date(2025, 2, 4)
    assert records[0]["sma"] is None
    assert records[1]["sma"] is None
    assert records[2]["sma"] == 101.0
    assert records[3]["rsi"] == 100.0
    assert all(
        value is None or np.isfinite(value)
        for record in records
        for key, value in record.items()
        if key != "trading_date"
    )


def test_bollinger_uses_population_standard_deviation():
    rows = make_rows(3)
    parameters = IndicatorParameters(
        sma_period=3,
        ema_period=3,
        rsi_period=3,
        macd_fast_period=1,
        macd_slow_period=2,
        macd_signal_period=1,
        bollinger_period=3,
        atr_period=3,
    )
    records, *_ = calculate_indicators(rows, parameters)
    expected_std = pd.Series([100.0, 101.0, 102.0]).std(ddof=0)
    assert records[-1]["bollinger_middle"] == 101.0
    assert records[-1]["bollinger_upper"] == pytest.approx(101 + 2 * expected_std)
    assert records[-1]["bollinger_lower"] == pytest.approx(101 - 2 * expected_std)


def test_rsi_flat_and_falling_series_are_not_nan():
    rows = make_rows(5)
    for row in rows:
        row.close = Decimal("100")
    parameters = IndicatorParameters(rsi_period=3)
    flat_records, *_ = calculate_indicators(rows, parameters)
    assert flat_records[-1]["rsi"] == 0.0

    falling_rows = make_rows(5)
    for index, row in enumerate(falling_rows):
        row.close = Decimal(str(100 - index))
    falling_records, *_ = calculate_indicators(falling_rows, parameters)
    assert falling_records[-1]["rsi"] == 0.0


def test_macd_histogram_is_macd_minus_signal_and_atr_uses_first_range():
    rows = make_rows(5)
    parameters = IndicatorParameters(
        macd_fast_period=2,
        macd_slow_period=3,
        macd_signal_period=2,
        atr_period=3,
    )
    records, *_ = calculate_indicators(rows, parameters)
    assert records[-1]["macd_histogram"] == pytest.approx(
        records[-1]["macd"] - records[-1]["macd_signal"]
    )
    assert records[2]["atr"] == pytest.approx(4.0)


def test_date_filter_keeps_warmup_history():
    rows = make_rows(10)
    parameters = IndicatorParameters(
        sma_period=3,
        ema_period=3,
        rsi_period=3,
        macd_fast_period=1,
        macd_slow_period=2,
        macd_signal_period=1,
        bollinger_period=3,
        atr_period=3,
    )
    records, available, *_ = calculate_indicators(
        rows, parameters, start_date=date(2025, 1, 4), end_date=date(2025, 1, 6)
    )
    assert available == 6
    assert [record["trading_date"] for record in records] == [
        date(2025, 1, 4),
        date(2025, 1, 5),
        date(2025, 1, 6),
    ]
    assert records[0]["sma"] == 102.0


def test_adjusted_close_requires_values():
    with pytest.raises(AdjustedCloseUnavailable):
        calculate_indicators(make_rows(adjusted=False), IndicatorParameters(price_field="adjusted_close"))


def test_indicator_endpoint_and_validation(client, db_session):
    company = Company(
        name="Example",
        symbol="EXAMPLE",
        provider_symbol="EXAMPLE.NS",
        exchange="NSE",
        instrument_type="company",
    )
    db_session.add(company)
    db_session.commit()
    for row in make_rows(5):
        row.company_id = company.id
        db_session.add(row)
    db_session.commit()

    response = client.get(
        "/api/v1/stocks/example/indicators?sma_period=3&ema_period=3&start_date=2025-01-03"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "EXAMPLE"
    assert payload["available_records"] == 5
    assert payload["returned_records"] == 3
    assert payload["records"][0]["sma"] == 101.0
    assert client.get(
        "/api/v1/stocks/EXAMPLE/indicators?macd_fast_period=26&macd_slow_period=12"
    ).status_code == 400
    assert client.get("/api/v1/stocks/MISSING/indicators").status_code == 404
