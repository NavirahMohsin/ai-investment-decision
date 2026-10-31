from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from math import isfinite
from typing import Literal, Sequence

import numpy as np
import pandas as pd

from app.db.models import DailyMarketData

PriceField = Literal["close", "adjusted_close"]


class AdjustedCloseUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class IndicatorParameters:
    price_field: PriceField = "close"
    sma_period: int = 20
    ema_period: int = 20
    rsi_period: int = 14
    macd_fast_period: int = 12
    macd_slow_period: int = 26
    macd_signal_period: int = 9
    bollinger_period: int = 20
    bollinger_std_dev: float = 2.0
    atr_period: int = 14


def validate_parameters(parameters: IndicatorParameters) -> None:
    periods = (
        parameters.sma_period,
        parameters.ema_period,
        parameters.rsi_period,
        parameters.macd_fast_period,
        parameters.macd_slow_period,
        parameters.macd_signal_period,
        parameters.bollinger_period,
        parameters.atr_period,
    )
    if any(period < 1 or period > 2000 for period in periods):
        raise ValueError("Indicator periods must be between 1 and 2000")
    if parameters.macd_fast_period >= parameters.macd_slow_period:
        raise ValueError("macd_fast_period must be smaller than macd_slow_period")
    if not isfinite(parameters.bollinger_std_dev) or parameters.bollinger_std_dev <= 0:
        raise ValueError("bollinger_std_dev must be finite and greater than zero")


def _decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if isfinite(number) else None


def _finite_or_none(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    return number if isfinite(number) else None


def _wilder_rsi(close: pd.Series, period: int) -> pd.Series:
    changes = close.diff()
    gains = changes.clip(lower=0)
    losses = -changes.clip(upper=0)
    average_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    average_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    relative_strength = average_gain / average_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + relative_strength))
    rsi = rsi.where(average_loss != 0, 100.0)
    return rsi.where(~((average_gain == 0) & (average_loss == 0)), 0.0)


def calculate_indicators(
    rows: Sequence[DailyMarketData],
    parameters: IndicatorParameters,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[list[dict[str, object]], int, str | None, str | None]:
    validate_parameters(parameters)
    if not rows:
        return [], 0, None, None
    frame = pd.DataFrame(
        [
            {
                "trading_date": row.trading_date,
                "open": _decimal_to_float(row.open),
                "high": _decimal_to_float(row.high),
                "low": _decimal_to_float(row.low),
                "close": _decimal_to_float(row.close),
                "adjusted_close": _decimal_to_float(row.adjusted_close),
                "volume": row.volume,
                "provider": row.provider,
            }
            for row in rows
        ]
    ).sort_values("trading_date", kind="stable")
    frame = frame.drop_duplicates("trading_date", keep="last").reset_index(drop=True)
    if end_date is not None:
        frame = frame[frame["trading_date"] <= end_date].reset_index(drop=True)
    if parameters.price_field == "adjusted_close" and frame["adjusted_close"].isna().any():
        raise AdjustedCloseUnavailable(
            "adjusted_close is unavailable for one or more historical records in the calculation range"
        )
    selected = frame[parameters.price_field].astype(float)

    frame["selected_price"] = selected
    frame["sma"] = selected.rolling(parameters.sma_period, min_periods=parameters.sma_period).mean()
    frame["ema"] = selected.ewm(
        span=parameters.ema_period,
        adjust=False,
        min_periods=parameters.ema_period,
    ).mean()
    frame["rsi"] = _wilder_rsi(selected, parameters.rsi_period)

    fast = selected.ewm(
        span=parameters.macd_fast_period,
        adjust=False,
        min_periods=parameters.macd_fast_period,
    ).mean()
    slow = selected.ewm(
        span=parameters.macd_slow_period,
        adjust=False,
        min_periods=parameters.macd_slow_period,
    ).mean()
    frame["macd"] = fast - slow
    frame["macd_signal"] = frame["macd"].ewm(
        span=parameters.macd_signal_period,
        adjust=False,
        min_periods=parameters.macd_signal_period,
    ).mean()
    frame["macd_histogram"] = frame["macd"] - frame["macd_signal"]

    frame["bollinger_middle"] = selected.rolling(
        parameters.bollinger_period,
        min_periods=parameters.bollinger_period,
    ).mean()
    standard_deviation = selected.rolling(
        parameters.bollinger_period,
        min_periods=parameters.bollinger_period,
    ).std(ddof=0)
    frame["bollinger_upper"] = frame["bollinger_middle"] + parameters.bollinger_std_dev * standard_deviation
    frame["bollinger_lower"] = frame["bollinger_middle"] - parameters.bollinger_std_dev * standard_deviation

    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    frame["atr"] = true_range.ewm(
        alpha=1 / parameters.atr_period,
        adjust=False,
        min_periods=parameters.atr_period,
    ).mean()

    typical_price = (frame["high"] + frame["low"] + frame["close"]) / 3
    cumulative_volume = frame["volume"].replace(0, np.nan).cumsum()
    frame["vwap"] = (typical_price * frame["volume"]).cumsum() / cumulative_volume

    upward_move = frame["high"].diff()
    downward_move = -frame["low"].diff()
    plus_dm = upward_move.where(
        (upward_move > downward_move) & (upward_move > 0), 0.0
    )
    minus_dm = downward_move.where(
        (downward_move > upward_move) & (downward_move > 0), 0.0
    )
    smoothed_range = true_range.ewm(
        alpha=1 / parameters.atr_period,
        adjust=False,
        min_periods=parameters.atr_period,
    ).mean()
    plus_di = 100 * plus_dm.ewm(
        alpha=1 / parameters.atr_period,
        adjust=False,
        min_periods=parameters.atr_period,
    ).mean() / smoothed_range
    minus_di = 100 * minus_dm.ewm(
        alpha=1 / parameters.atr_period,
        adjust=False,
        min_periods=parameters.atr_period,
    ).mean() / smoothed_range
    directional_sum = (plus_di + minus_di).replace(0, np.nan)
    directional_index = 100 * (plus_di - minus_di).abs() / directional_sum
    frame["adx"] = directional_index.ewm(
        alpha=1 / parameters.atr_period,
        adjust=False,
        min_periods=parameters.atr_period,
    ).mean()

    multiplier = 3.0
    midpoint = (frame["high"] + frame["low"]) / 2
    upper_band = midpoint + multiplier * frame["atr"]
    lower_band = midpoint - multiplier * frame["atr"]
    supertrend = pd.Series(np.nan, index=frame.index, dtype=float)
    direction = pd.Series(1, index=frame.index, dtype=int)
    for index in frame.index:
        if index == frame.index[0]:
            supertrend.loc[index] = upper_band.loc[index]
            continue
        previous = index - 1
        if frame.loc[index, "close"] > upper_band.loc[previous]:
            direction.loc[index] = 1
        elif frame.loc[index, "close"] < lower_band.loc[previous]:
            direction.loc[index] = -1
        else:
            direction.loc[index] = direction.loc[previous]
        supertrend.loc[index] = (
            lower_band.loc[index] if direction.loc[index] == 1 else upper_band.loc[index]
        )
    frame["supertrend"] = supertrend
    frame["support"] = frame["low"].rolling(20, min_periods=1).min()
    frame["resistance"] = frame["high"].rolling(20, min_periods=1).max()
    frame["volume_average"] = frame["volume"].rolling(20, min_periods=1).mean()
    frame["volume_ratio"] = frame["volume"] / frame["volume_average"].replace(0, np.nan)
    frame["trend"] = np.select(
        [
            (selected > frame["ema"]) & (frame["adx"] >= 20),
            (selected < frame["ema"]) & (frame["adx"] >= 20),
        ],
        ["bullish", "bearish"],
        default="neutral",
    )
    frame["signal"] = np.select(
        [
            (selected > frame["ema"]) & (frame["macd_histogram"] > 0),
            (selected < frame["ema"]) & (frame["macd_histogram"] < 0),
        ],
        ["buy", "sell"],
        default="hold",
    )

    output = frame
    if start_date is not None:
        output = output[output["trading_date"] >= start_date]

    records: list[dict[str, object]] = []
    for row in output.to_dict("records"):
        records.append(
            {
                "trading_date": row["trading_date"],
                "selected_price": _finite_or_none(row["selected_price"]),
                "close": _finite_or_none(row["close"]),
                "sma": _finite_or_none(row["sma"]),
                "ema": _finite_or_none(row["ema"]),
                "rsi": _finite_or_none(row["rsi"]),
                "macd": _finite_or_none(row["macd"]),
                "macd_signal": _finite_or_none(row["macd_signal"]),
                "macd_histogram": _finite_or_none(row["macd_histogram"]),
                "bollinger_middle": _finite_or_none(row["bollinger_middle"]),
                "bollinger_upper": _finite_or_none(row["bollinger_upper"]),
                "bollinger_lower": _finite_or_none(row["bollinger_lower"]),
                "atr": _finite_or_none(row["atr"]),
                "vwap": _finite_or_none(row["vwap"]),
                "adx": _finite_or_none(row["adx"]),
                "supertrend": _finite_or_none(row["supertrend"]),
                "support": _finite_or_none(row["support"]),
                "resistance": _finite_or_none(row["resistance"]),
                "volume_ratio": _finite_or_none(row["volume_ratio"]),
            }
        )
    available_dates = frame["trading_date"]
    first_date = available_dates.iloc[0] if not available_dates.empty else None
    last_date = available_dates.iloc[-1] if not available_dates.empty else None
    return records, len(frame), first_date, last_date
