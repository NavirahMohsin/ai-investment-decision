"""Prediction target generation for multi-class classification.

Generates classification labels (Positive, Negative, Neutral) based on forward returns
over configurable prediction horizons (1, 5, 20 days).

Features:
- Forward return calculation with proper temporal alignment
- Configurable thresholds for classification
- Multi-horizon support (1, 5, 20 days)
- Data leakage prevention via proper date alignment
- Baseline majority-class predictor
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Literal

import numpy as np
import pandas as pd


class PredictionObjective(str, Enum):
    """Classification targets for price prediction."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class TargetConfig:
    """Configuration for target generation.
    
    Attributes:
        thresholds_pct: (lower, upper) threshold percentages for classification.
                       Returns <= lower_pct → Negative
                       Returns between lower_pct and upper_pct → Neutral
                       Returns >= upper_pct → Positive
                       Default: (-1.0, 1.0)
        horizons_days: Prediction horizons in days. Default: [1, 5, 20]
        price_field: Which price field to use for calculations. Default: "close"
    """
    thresholds_pct: tuple[float, float] = (-1.0, 1.0)
    horizons_days: list[int] = field(default_factory=lambda: [1, 5, 20])
    price_field: Literal["close", "adjusted_close"] = "close"
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        if len(self.thresholds_pct) != 2:
            raise ValueError("thresholds_pct must be a tuple of (lower, upper)")
        lower, upper = self.thresholds_pct
        if lower >= upper:
            raise ValueError("Lower threshold must be less than upper threshold")
        if not self.horizons_days or not all(h > 0 for h in self.horizons_days):
            raise ValueError("horizons_days must be non-empty and all positive")
        if self.price_field not in ("close", "adjusted_close"):
            raise ValueError("price_field must be 'close' or 'adjusted_close'")


@dataclass(frozen=True)
class PredictionTarget:
    """Single prediction target instance.
    
    Attributes:
        trading_date: Date of the observation (feature date)
        horizon_days: Number of days forward for this target
        forward_return_pct: Calculated return percentage over horizon
        target: Classification label (positive, negative, neutral)
        data_available: Whether sufficient data was available to compute target
    """
    trading_date: date
    horizon_days: int
    forward_return_pct: float | None
    target: PredictionObjective | None
    data_available: bool


def calculate_forward_returns(
    prices: pd.Series,
    trading_dates: pd.Series,
    horizons_days: list[int],
) -> dict[int, pd.Series]:
    """Calculate forward returns for multiple horizons.
    
    Ensures proper temporal alignment: for a date at index i, the forward return
    looks at prices at indices i + horizon (no future leak).
    
    Args:
        prices: Series of prices (index: position, not date)
        trading_dates: Series of trading dates (same index as prices)
        horizons_days: Horizons to calculate returns for
        
    Returns:
        Dict mapping horizon_days to Series of forward returns (%).
        Returns are NaN where future data is unavailable.
        
    Raises:
        ValueError: If prices and trading_dates have different lengths
    """
    if len(prices) != len(trading_dates):
        raise ValueError("prices and trading_dates must have same length")
    
    returns = {}
    for horizon in horizons_days:
        # Shift prices forward by horizon, then calculate percentage return
        # This creates NaN for the last `horizon` rows (no future data)
        future_prices = prices.shift(-horizon)
        forward_ret = ((future_prices - prices) / prices) * 100
        returns[horizon] = forward_ret
    
    return returns


def classify_return(
    return_pct: float | None,
    thresholds: tuple[float, float],
) -> PredictionObjective | None:
    """Classify a return percentage into objective class.
    
    Args:
        return_pct: Return percentage, or None if unavailable
        thresholds: (lower, upper) threshold percentages
        
    Returns:
        PredictionObjective or None if return is unavailable
    """
    if return_pct is None or not np.isfinite(return_pct):
        return None
    
    lower, upper = thresholds
    if return_pct <= lower:
        return PredictionObjective.NEGATIVE
    elif return_pct >= upper:
        return PredictionObjective.POSITIVE
    else:
        return PredictionObjective.NEUTRAL


class TargetGenerator:
    """Generate prediction targets from OHLCV data."""
    
    def __init__(self, config: TargetConfig) -> None:
        """Initialize target generator.
        
        Args:
            config: TargetConfig instance with thresholds and horizons
        """
        config.__post_init__()  # Validate config
        self.config = config
    
    def generate(self, ohlcv_df: pd.DataFrame) -> pd.DataFrame:
        """Generate targets from OHLCV data.
        
        Input DataFrame must have columns: trading_date, close (or adjusted_close).
        Output will have one row per input row, with target columns for each horizon.
        
        Args:
            ohlcv_df: DataFrame with trading_date and close/adjusted_close
            
        Returns:
            DataFrame with columns:
            - trading_date
            - {horizon}_day_return_pct (for each horizon)
            - {horizon}_day_target (for each horizon)
            - data_available (True if all required forward data exists)
            
        Raises:
            ValueError: If required columns are missing
        """
        if "trading_date" not in ohlcv_df.columns:
            raise ValueError("Input must have 'trading_date' column")
        
        price_field = self.config.price_field
        if price_field not in ohlcv_df.columns:
            raise ValueError(f"Input must have '{price_field}' column")
        
        # Work with a copy to avoid modifying input
        df = ohlcv_df.copy()
        df = df.reset_index(drop=True)
        
        # Extract prices and dates
        prices = pd.to_numeric(df[price_field], errors="coerce")
        trading_dates = pd.to_datetime(df["trading_date"]).dt.date
        
        # Calculate forward returns for all horizons
        forward_returns = calculate_forward_returns(
            prices,
            pd.Series(trading_dates),
            self.config.horizons_days,
        )
        
        # Build output DataFrame
        result = pd.DataFrame()
        result["trading_date"] = df["trading_date"]
        
        # Add return and target columns for each horizon
        for horizon in self.config.horizons_days:
            ret_series = forward_returns[horizon]
            
            # Return column
            result[f"{horizon}_day_return_pct"] = ret_series
            
            # Target column (classification)
            result[f"{horizon}_day_target"] = ret_series.apply(
                classify_return,
                args=(self.config.thresholds_pct,),
            )
        
        # Flag rows where we have complete data for all horizons
        max_horizon = max(self.config.horizons_days)
        result["data_available"] = ~prices.isna() & (
            result.index < len(result) - max_horizon
        )
        
        return result
    
    def get_baseline_predictor(
        self,
        targets_df: pd.DataFrame,
        horizon_days: int,
    ) -> PredictionObjective:
        """Get majority-class baseline for a horizon.
        
        Args:
            targets_df: DataFrame from generate()
            horizon_days: Which horizon to get baseline for
            
        Returns:
            Most common classification for this horizon
        """
        col = f"{horizon_days}_day_target"
        if col not in targets_df.columns:
            raise ValueError(f"Column {col} not found in targets")
        
        # Count non-null targets
        target_counts = targets_df[col].value_counts()
        if target_counts.empty:
            # Default to neutral if no data
            return PredictionObjective.NEUTRAL
        
        return target_counts.idxmax()


def generate_targets_for_instruments(
    instrument_data: dict[str, pd.DataFrame],
    config: TargetConfig | None = None,
) -> dict[str, pd.DataFrame]:
    """Batch generate targets for multiple instruments.
    
    Args:
        instrument_data: Dict mapping symbol → OHLCV DataFrame
        config: TargetConfig (uses defaults if None)
        
    Returns:
        Dict mapping symbol → targets DataFrame
    """
    config = config or TargetConfig()
    generator = TargetGenerator(config)
    
    results = {}
    for symbol, df in instrument_data.items():
        try:
            targets = generator.generate(df)
            results[symbol] = targets
        except Exception as e:
            # Log and skip instruments with data issues
            print(f"Warning: Failed to generate targets for {symbol}: {e}")
    
    return results
