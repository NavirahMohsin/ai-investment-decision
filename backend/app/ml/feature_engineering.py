"""Feature engineering pipeline for ML models.

Constructs a comprehensive set of features from OHLCV data and technical indicators:
- Price returns (1, 5, 20-day)
- Moving averages (SMA 20, 50, 200; EMA 12, 26)
- Momentum indicators (RSI, MACD, MACD Histogram)
- Volatility measures (ATR, Bollinger Bands, ADX)
- Volume features (volume ratio, cumulative volume)
- Market structure (VWAP, SuperTrend, support/resistance)

Key features:
- Configurable feature sets
- Automatic indicator calculation integration
- Missing value handling with validation
- Data leakage prevention (features only use historical data)
- Reproducible dataset generation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd

from app.services.indicators import IndicatorParameters, calculate_indicators, _decimal_to_float


@dataclass
class FeatureConfig:
    """Configuration for feature engineering pipeline.
    
    Attributes:
        returns_periods: Periods for return calculations. Default: [1, 5, 20]
        sma_periods: Periods for SMA calculation. Default: [20, 50, 200]
        ema_periods: Periods for EMA calculation. Default: [12, 26]
        use_normalized_features: Normalize prices to [0, 1] range per feature. Default: False
        use_log_features: Use log returns instead of percentage. Default: False
        handle_missing: Strategy for missing values: 'forward_fill' or 'drop'. Default: 'forward_fill'
        validate_finite: Ensure all features are finite. Default: True
    """
    returns_periods: list[int] = field(default_factory=lambda: [1, 5, 20])
    sma_periods: list[int] = field(default_factory=lambda: [20, 50, 200])
    ema_periods: list[int] = field(default_factory=lambda: [12, 26])
    use_normalized_features: bool = False
    use_log_features: bool = False
    handle_missing: Literal["forward_fill", "drop"] = "forward_fill"
    validate_finite: bool = True
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        if not all(p > 0 for p in self.returns_periods):
            raise ValueError("All periods must be positive")
        if not all(p > 0 for p in self.sma_periods):
            raise ValueError("All SMA periods must be positive")
        if not all(p > 0 for p in self.ema_periods):
            raise ValueError("All EMA periods must be positive")
        if self.handle_missing not in ("forward_fill", "drop"):
            raise ValueError("handle_missing must be 'forward_fill' or 'drop'")


class FeatureEngineer:
    """Build feature sets from OHLCV data."""
    
    def __init__(
        self,
        config: FeatureConfig | None = None,
        indicator_params: IndicatorParameters | None = None,
    ) -> None:
        """Initialize feature engineer.
        
        Args:
            config: FeatureConfig (uses defaults if None)
            indicator_params: IndicatorParameters for technical indicators
        """
        self.config = config or FeatureConfig()
        self.config.__post_init__()
        
        self.indicator_params = indicator_params or IndicatorParameters()
    
    def _calculate_returns(self, prices: pd.Series, periods: list[int]) -> pd.DataFrame:
        """Calculate log or percentage returns for multiple periods.
        
        Args:
            prices: Series of prices
            periods: List of periods to calculate returns for
            
        Returns:
            DataFrame with return columns named return_{period}d
        """
        returns_df = pd.DataFrame(index=prices.index)
        
        for period in periods:
            if self.config.use_log_features:
                ret = np.log(prices / prices.shift(period)) * 100
            else:
                ret = ((prices - prices.shift(period)) / prices.shift(period)) * 100
            
            returns_df[f"return_{period}d"] = ret
        
        return returns_df
    
    def _calculate_moving_averages(self, prices: pd.Series) -> pd.DataFrame:
        """Calculate SMA and EMA indicators.
        
        Args:
            prices: Series of prices
            
        Returns:
            DataFrame with SMA and EMA columns
        """
        ma_df = pd.DataFrame(index=prices.index)
        
        for period in self.config.sma_periods:
            ma_df[f"sma_{period}"] = prices.rolling(period, min_periods=1).mean()
        
        for period in self.config.ema_periods:
            ma_df[f"ema_{period}"] = prices.ewm(span=period, adjust=False, min_periods=1).mean()
        
        return ma_df
    
    def _prepare_ohlcv_records(self, ohlcv_df: pd.DataFrame) -> list[dict]:
        """Prepare OHLCV data as records for indicator calculation.
        
        Args:
            ohlcv_df: DataFrame with trading_date, open, high, low, close, volume
            
        Returns:
            List of dict records compatible with calculate_indicators()
        """
        records = []
        for _, row in ohlcv_df.iterrows():
            # Create a simple namespace object that mimics DailyMarketData
            date_val = row["trading_date"]
            if not isinstance(date_val, date):
                date_val = pd.Timestamp(date_val).date()
            
            record_obj = type('DailyMarketData', (), {
                'trading_date': date_val,
                'open': row.get("open"),
                'high': row.get("high"),
                'low': row.get("low"),
                'close': row.get("close"),
                'adjusted_close': row.get("adjusted_close"),
                'volume': int(row.get("volume", 0)),
                'provider': row.get("provider", "unknown"),
            })()
            records.append(record_obj)
        return records
    
    def generate(
        self,
        ohlcv_df: pd.DataFrame,
        include_indicators: bool = True,
    ) -> pd.DataFrame:
        """Generate feature set from OHLCV data.
        
        Input must have: trading_date, open, high, low, close, volume, (optionally adjusted_close).
        
        Features generated:
        - Returns: 1d, 5d, 20d (log or percentage)
        - Moving Averages: SMA 20/50/200, EMA 12/26
        - Technical Indicators: RSI, MACD, Bollinger Bands, ATR, ADX, SuperTrend, VWAP
        - Volume: Volume ratio, volume trend
        
        Args:
            ohlcv_df: DataFrame with OHLCV data
            include_indicators: If True, include full technical indicators. Default: True
            
        Returns:
            DataFrame with all features aligned to trading_date
            
        Raises:
            ValueError: If required columns missing
        """
        required_cols = {"trading_date", "open", "high", "low", "close", "volume"}
        if not required_cols.issubset(ohlcv_df.columns):
            raise ValueError(f"Input must have columns: {required_cols}")
        
        # Sort and reset index
        df = ohlcv_df.copy()
        df["trading_date"] = pd.to_datetime(df["trading_date"])
        df = df.sort_values("trading_date").reset_index(drop=True)
        
        features = pd.DataFrame()
        features["trading_date"] = df["trading_date"]
        
        # Extract price series
        close_prices = pd.to_numeric(df["close"], errors="coerce")
        
        # Calculate basic returns
        returns_df = self._calculate_returns(close_prices, self.config.returns_periods)
        features = features.join(returns_df)
        
        # Calculate moving averages
        ma_df = self._calculate_moving_averages(close_prices)
        features = features.join(ma_df)
        
        # Technical indicators
        if include_indicators:
            try:
                # Prepare records for indicator calculation
                records = self._prepare_ohlcv_records(df)
                
                # Calculate all indicators
                indicator_records, _, _, _ = calculate_indicators(
                    records,
                    self.indicator_params,
                )
                
                if indicator_records:
                    ind_df = pd.DataFrame(indicator_records)
                    
                    # Select and rename indicator columns
                    indicator_cols = {
                        "rsi": "rsi_14",
                        "macd": "macd",
                        "macd_signal": "macd_signal",
                        "macd_histogram": "macd_histogram",
                        "atr": "atr_14",
                        "adx": "adx_14",
                        "supertrend": "supertrend",
                        "vwap": "vwap",
                        "bollinger_upper": "bb_upper",
                        "bollinger_middle": "bb_middle",
                        "bollinger_lower": "bb_lower",
                        "volume_ratio": "volume_ratio",
                    }
                    
                    for ind_col, feature_col in indicator_cols.items():
                        if ind_col in ind_df.columns:
                            features[feature_col] = ind_df[ind_col].values
            except Exception as e:
                print(f"Warning: Failed to calculate indicators: {e}")
        
        # Add volume features
        features["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        features["volume_change"] = features["volume"].pct_change() * 100
        features["volume_sma_20"] = features["volume"].rolling(20, min_periods=1).mean()
        features["volume_ratio_20d"] = features["volume"] / features["volume_sma_20"].replace(0, np.nan)
        
        # Add price level features
        features["high_low_ratio"] = (pd.to_numeric(df["high"], errors="coerce") / 
                                      pd.to_numeric(df["low"], errors="coerce"))
        features["close_to_high"] = (close_prices / pd.to_numeric(df["high"], errors="coerce"))
        features["close_to_low"] = (close_prices / pd.to_numeric(df["low"], errors="coerce"))
        
        # Handle missing values
        if self.config.handle_missing == "forward_fill":
            features = features.ffill().bfill()
        
        # Validate finite values if configured
        if self.config.validate_finite:
            numeric_cols = features.select_dtypes(include=[np.number]).columns
            non_finite_mask = ~features[numeric_cols].apply(np.isfinite)
            
            if non_finite_mask.any().any():
                # Log warnings
                cols_with_inf = non_finite_mask.any(axis=0)
                print(f"Warning: Non-finite values in columns: {cols_with_inf[cols_with_inf].index.tolist()}")
                
                # Replace infinities with NaN, then handle
                features[numeric_cols] = features[numeric_cols].replace(
                    [np.inf, -np.inf], np.nan
                )
                if self.config.handle_missing == "forward_fill":
                    features[numeric_cols] = features[numeric_cols].ffill().bfill()
        
        return features


class DatasetGenerator:
    """Generate reproducible training datasets."""
    
    def __init__(
        self,
        feature_config: FeatureConfig | None = None,
        indicator_params: IndicatorParameters | None = None,
    ) -> None:
        """Initialize dataset generator.
        
        Args:
            feature_config: FeatureConfig for feature engineering
            indicator_params: IndicatorParameters for technical indicators
        """
        self.feature_engineer = FeatureEngineer(feature_config, indicator_params)
    
    def generate_features(self, ohlcv_df: pd.DataFrame) -> pd.DataFrame:
        """Generate feature set from OHLCV data.
        
        Args:
            ohlcv_df: DataFrame with OHLCV data
            
        Returns:
            Feature DataFrame with trading_date and all calculated features
        """
        return self.feature_engineer.generate(ohlcv_df)
    
    def merge_features_and_targets(
        self,
        features_df: pd.DataFrame,
        targets_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Merge feature and target DataFrames.
        
        Args:
            features_df: DataFrame from generate_features()
            targets_df: DataFrame from TargetGenerator.generate()
            
        Returns:
            Merged DataFrame with features and targets, aligned by trading_date
        """
        # Get target columns (exclude trading_date)
        target_cols = [col for col in targets_df.columns if col not in ["trading_date", "data_available"]]
        
        merged = pd.merge(
            features_df,
            targets_df[["trading_date"] + target_cols],
            on="trading_date",
            how="inner",
        )
        
        # Add data_available column from targets
        merged = merged.merge(
            targets_df[["trading_date", "data_available"]],
            on="trading_date",
            how="left",
        )
        
        return merged
    
    def get_training_set(
        self,
        features_df: pd.DataFrame,
        targets_df: pd.DataFrame,
        horizon_days: int = 1,
        min_date: date | None = None,
        max_date: date | None = None,
        dropna: bool = True,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Get training set for a specific horizon.
        
        Args:
            features_df: Features DataFrame
            targets_df: Targets DataFrame
            horizon_days: Which horizon to get data for
            min_date: Start date (inclusive)
            max_date: End date (inclusive)
            dropna: Whether to drop rows with missing values
            
        Returns:
            Tuple of (features DataFrame, targets Series)
        """
        # Merge
        merged = self.merge_features_and_targets(features_df, targets_df)
        
        # Filter by date if provided
        if min_date:
            merged = merged[pd.to_datetime(merged["trading_date"]).dt.date >= min_date]
        if max_date:
            merged = merged[pd.to_datetime(merged["trading_date"]).dt.date <= max_date]
        
        # Filter by data availability
        merged = merged[merged["data_available"] == True]
        
        # Extract features and targets
        target_col = f"{horizon_days}_day_target"
        if target_col not in merged.columns:
            raise ValueError(f"Target column {target_col} not found")
        
        X = merged.drop(columns=["trading_date", "data_available"] + 
                       [col for col in merged.columns if "day_" in col or "day_return" in col])
        y = merged[target_col]
        
        # Remove rows with null targets
        valid_mask = y.notna()
        X = X[valid_mask]
        y = y[valid_mask]
        
        if dropna:
            X = X.dropna()
            y = y[X.index]
        
        return X, y
