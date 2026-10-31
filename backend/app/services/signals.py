"""Technical signal generation and trend classification"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from app.db.models import DailyMarketData
from app.services.indicators import IndicatorParameters, calculate_indicators


TrendClassification = Literal["STRONG_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONG_BEARISH"]
SignalType = Literal[
    "BULLISH_CROSSOVER",
    "BEARISH_CROSSOVER",
    "RSI_OVERBOUGHT",
    "RSI_OVERSOLD",
    "MACD_BULLISH_CROSSOVER",
    "MACD_BEARISH_CROSSOVER",
    "VOLATILITY_EXPANSION",
    "VOLUME_SPIKE",
    "TREND_REVERSAL",
]


@dataclass(frozen=True)
class TechnicalSignal:
    signal_type: SignalType
    timestamp: date
    price: float
    explanation: str
    indicator_values: dict[str, float | None]
    strength: Literal["STRONG", "MODERATE", "WEAK"]


@dataclass(frozen=True)
class TrendAnalysis:
    classification: TrendClassification
    explanation: str
    current_price: float
    ema_value: float | None
    rsi_value: float | None
    adx_value: float | None
    macd_histogram: float | None


def classify_trend(
    current_price: float,
    ema: float | None,
    rsi: float | None,
    adx: float | None,
    macd_histogram: float | None,
) -> TrendAnalysis:
    """Classify market trend based on technical indicators."""
    
    if ema is None:
        return TrendAnalysis(
            classification="NEUTRAL",
            explanation="Insufficient historical data for trend classification",
            current_price=current_price,
            ema_value=ema,
            rsi_value=rsi,
            adx_value=adx,
            macd_histogram=macd_histogram,
        )
    
    price_above_ema = current_price > ema
    strong_trend = adx is not None and adx >= 25
    moderate_trend = adx is not None and adx >= 20
    
    macd_positive = macd_histogram is not None and macd_histogram > 0
    macd_negative = macd_histogram is not None and macd_histogram < 0
    
    rsi_high = rsi is not None and rsi >= 60
    rsi_low = rsi is not None and rsi <= 40
    
    if price_above_ema and strong_trend and macd_positive and rsi_high:
        return TrendAnalysis(
            classification="STRONG_BULLISH",
            explanation="Price above EMA with strong trend strength (ADX >= 25), positive MACD histogram, and RSI above 60",
            current_price=current_price,
            ema_value=ema,
            rsi_value=rsi,
            adx_value=adx,
            macd_histogram=macd_histogram,
        )
    
    if not price_above_ema and strong_trend and macd_negative and rsi_low:
        return TrendAnalysis(
            classification="STRONG_BEARISH",
            explanation="Price below EMA with strong trend strength (ADX >= 25), negative MACD histogram, and RSI below 40",
            current_price=current_price,
            ema_value=ema,
            rsi_value=rsi,
            adx_value=adx,
            macd_histogram=macd_histogram,
        )
    
    if price_above_ema and (moderate_trend or macd_positive):
        return TrendAnalysis(
            classification="BULLISH",
            explanation="Price above EMA with supporting indicators (ADX >= 20 or positive MACD)",
            current_price=current_price,
            ema_value=ema,
            rsi_value=rsi,
            adx_value=adx,
            macd_histogram=macd_histogram,
        )
    
    if not price_above_ema and (moderate_trend or macd_negative):
        return TrendAnalysis(
            classification="BEARISH",
            explanation="Price below EMA with supporting indicators (ADX >= 20 or negative MACD)",
            current_price=current_price,
            ema_value=ema,
            rsi_value=rsi,
            adx_value=adx,
            macd_histogram=macd_histogram,
        )
    
    return TrendAnalysis(
        classification="NEUTRAL",
        explanation="Price and indicators do not show a clear directional bias",
        current_price=current_price,
        ema_value=ema,
        rsi_value=rsi,
        adx_value=adx,
        macd_histogram=macd_histogram,
    )


def generate_signals(
    rows: list[DailyMarketData],
    parameters: IndicatorParameters,
) -> list[TechnicalSignal]:
    """Generate explainable technical signals from historical data."""
    
    if len(rows) < 2:
        return []
    
    records, _, _, _ = calculate_indicators(rows, parameters)
    
    if len(records) < 2:
        return []
    
    signals: list[TechnicalSignal] = []
    
    latest = records[-1]
    previous = records[-2]
    
    # RSI signals
    if latest["rsi"] is not None:
        if latest["rsi"] >= 70:
            signals.append(
                TechnicalSignal(
                    signal_type="RSI_OVERBOUGHT",
                    timestamp=latest["trading_date"],
                    price=latest["close"] or 0.0,
                    explanation=f"RSI is {latest['rsi']:.2f}, above overbought threshold of 70",
                    indicator_values={"rsi": latest["rsi"]},
                    strength="STRONG" if latest["rsi"] >= 80 else "MODERATE",
                )
            )
        elif latest["rsi"] <= 30:
            signals.append(
                TechnicalSignal(
                    signal_type="RSI_OVERSOLD",
                    timestamp=latest["trading_date"],
                    price=latest["close"] or 0.0,
                    explanation=f"RSI is {latest['rsi']:.2f}, below oversold threshold of 30",
                    indicator_values={"rsi": latest["rsi"]},
                    strength="STRONG" if latest["rsi"] <= 20 else "MODERATE",
                )
            )
    
    # MACD crossover signals
    if (
        latest["macd"] is not None
        and latest["macd_signal"] is not None
        and previous["macd"] is not None
        and previous["macd_signal"] is not None
    ):
        if previous["macd"] <= previous["macd_signal"] and latest["macd"] > latest["macd_signal"]:
            signals.append(
                TechnicalSignal(
                    signal_type="MACD_BULLISH_CROSSOVER",
                    timestamp=latest["trading_date"],
                    price=latest["close"] or 0.0,
                    explanation="MACD line crossed above signal line",
                    indicator_values={
                        "macd": latest["macd"],
                        "macd_signal": latest["macd_signal"],
                        "macd_histogram": latest["macd_histogram"],
                    },
                    strength="STRONG" if latest["macd_histogram"] and latest["macd_histogram"] > 0.5 else "MODERATE",
                )
            )
        elif previous["macd"] >= previous["macd_signal"] and latest["macd"] < latest["macd_signal"]:
            signals.append(
                TechnicalSignal(
                    signal_type="MACD_BEARISH_CROSSOVER",
                    timestamp=latest["trading_date"],
                    price=latest["close"] or 0.0,
                    explanation="MACD line crossed below signal line",
                    indicator_values={
                        "macd": latest["macd"],
                        "macd_signal": latest["macd_signal"],
                        "macd_histogram": latest["macd_histogram"],
                    },
                    strength="STRONG" if latest["macd_histogram"] and latest["macd_histogram"] < -0.5 else "MODERATE",
                )
            )
    
    # EMA crossover signals
    if (
        latest["ema"] is not None
        and latest["close"] is not None
        and previous["ema"] is not None
        and previous["close"] is not None
    ):
        if previous["close"] <= previous["ema"] and latest["close"] > latest["ema"]:
            signals.append(
                TechnicalSignal(
                    signal_type="BULLISH_CROSSOVER",
                    timestamp=latest["trading_date"],
                    price=latest["close"],
                    explanation=f"Price crossed above EMA ({latest['ema']:.2f})",
                    indicator_values={"price": latest["close"], "ema": latest["ema"]},
                    strength="MODERATE",
                )
            )
        elif previous["close"] >= previous["ema"] and latest["close"] < latest["ema"]:
            signals.append(
                TechnicalSignal(
                    signal_type="BEARISH_CROSSOVER",
                    timestamp=latest["trading_date"],
                    price=latest["close"],
                    explanation=f"Price crossed below EMA ({latest['ema']:.2f})",
                    indicator_values={"price": latest["close"], "ema": latest["ema"]},
                    strength="MODERATE",
                )
            )
    
    # Volatility expansion
    if latest["atr"] is not None and previous["atr"] is not None:
        atr_increase = (latest["atr"] - previous["atr"]) / previous["atr"] * 100
        if atr_increase > 20:
            signals.append(
                TechnicalSignal(
                    signal_type="VOLATILITY_EXPANSION",
                    timestamp=latest["trading_date"],
                    price=latest["close"] or 0.0,
                    explanation=f"ATR increased by {atr_increase:.1f}%, indicating volatility expansion",
                    indicator_values={"atr": latest["atr"], "atr_change_pct": atr_increase},
                    strength="STRONG" if atr_increase > 40 else "MODERATE",
                )
            )
    
    # Volume spike
    if latest["volume_ratio"] is not None and latest["volume_ratio"] > 2.0:
        signals.append(
            TechnicalSignal(
                signal_type="VOLUME_SPIKE",
                timestamp=latest["trading_date"],
                price=latest["close"] or 0.0,
                explanation=f"Volume is {latest['volume_ratio']:.1f}x the 20-day average",
                indicator_values={"volume_ratio": latest["volume_ratio"]},
                strength="STRONG" if latest["volume_ratio"] > 3.0 else "MODERATE",
            )
        )
    
    return signals
