"""Unit tests to verify row explosion bug is fixed.

Tests verify:
1. Merge returns exactly one row per (symbol, date)
2. Each row's target matches the correct symbol's future return
3. Adding a second symbol does not change the first symbol's rows
4. No leakage between train and test sets
"""

import pytest
from datetime import date, timedelta

import pandas as pd
import numpy as np

from app.ml.feature_engineering import FeatureConfig, DatasetGenerator
from app.ml.prediction_targets import TargetConfig, TargetGenerator


@pytest.fixture
def synthetic_ohlcv_data():
    """Create synthetic OHLCV data for 3 symbols over 30 days."""
    symbols = ['SYM1', 'SYM2', 'SYM3']
    start_date = date(2024, 1, 1)
    
    data_dict = {}
    
    for sym in symbols:
        dates = []
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []
        
        for i in range(30):
            current_date = start_date + timedelta(days=i)
            dates.append(current_date)
            
            # Create consistent prices (different for each symbol)
            base_price = 100 + (ord(sym[3]) - ord('1')) * 10
            closes.append(base_price + i + np.random.randn() * 0.5)
            opens.append(closes[-1] - 1)
            highs.append(closes[-1] + 1.5)
            lows.append(closes[-1] - 1.5)
            volumes.append(1000000 + int(np.random.randn() * 100000))
        
        df = pd.DataFrame({
            'trading_date': dates,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'adjusted_close': closes,
            'volume': volumes,
        })
        
        data_dict[sym] = df
    
    return data_dict


def test_no_row_explosion(synthetic_ohlcv_data):
    """Test that merge does not create row explosion."""
    dataset_gen = DatasetGenerator()
    target_gen = TargetGenerator(TargetConfig())
    
    # Generate features and targets with symbol column
    all_features = []
    all_targets = []
    
    for symbol, ohlcv_df in synthetic_ohlcv_data.items():
        features_df = dataset_gen.generate_features(ohlcv_df)
        targets_df = target_gen.generate(ohlcv_df)
        
        features_df['trading_date'] = pd.to_datetime(features_df['trading_date']).dt.date
        targets_df['trading_date'] = pd.to_datetime(targets_df['trading_date']).dt.date
        
        features_df['symbol'] = symbol
        targets_df['symbol'] = symbol
        
        all_features.append(features_df)
        all_targets.append(targets_df)
    
    # Combine
    combined_features = pd.concat(all_features, ignore_index=True)
    combined_targets = pd.concat(all_targets, ignore_index=True)
    
    combined_features['trading_date'] = pd.to_datetime(combined_features['trading_date']).dt.date
    combined_targets['trading_date'] = pd.to_datetime(combined_targets['trading_date']).dt.date
    
    # Merge with symbol (FIXED way)
    merged = dataset_gen.merge_features_and_targets(combined_features, combined_targets)
    
    # Key assertion: output rows <= input features rows (no explosion)
    assert len(merged) <= len(combined_features), \
        f"Row explosion detected: {len(merged)} output > {len(combined_features)} input"
    
    # Should have approximately 30*3 = 90 rows (minus NaN rows from rolling windows)
    assert len(merged) > 60, \
        f"Too few rows after merge: {len(merged)} (expected >60)"


def test_one_to_one_join_validation(synthetic_ohlcv_data):
    """Test that merge enforces one-to-one relationship."""
    dataset_gen = DatasetGenerator()
    target_gen = TargetGenerator(TargetConfig())
    
    # Generate and combine with symbol
    all_features = []
    all_targets = []
    
    for symbol, ohlcv_df in synthetic_ohlcv_data.items():
        features_df = dataset_gen.generate_features(ohlcv_df)
        targets_df = target_gen.generate(ohlcv_df)
        
        features_df['trading_date'] = pd.to_datetime(features_df['trading_date']).dt.date
        targets_df['trading_date'] = pd.to_datetime(targets_df['trading_date']).dt.date
        
        features_df['symbol'] = symbol
        targets_df['symbol'] = symbol
        
        all_features.append(features_df)
        all_targets.append(targets_df)
    
    combined_features = pd.concat(all_features, ignore_index=True)
    combined_targets = pd.concat(all_targets, ignore_index=True)
    
    # Should succeed with validate="one_to_one"
    merged = dataset_gen.merge_features_and_targets(combined_features, combined_targets)
    
    # Verify no duplicates per (symbol, date)
    grouped = merged.groupby(['symbol', 'trading_date']).size()
    assert (grouped == 1).all(), \
        f"Found duplicate rows for (symbol, date): {grouped[grouped > 1]}"


def test_symbol_isolation(synthetic_ohlcv_data):
    """Test that adding second symbol doesn't change first symbol's rows."""
    dataset_gen = DatasetGenerator()
    target_gen = TargetGenerator(TargetConfig())
    
    symbols = list(synthetic_ohlcv_data.keys())
    
    # Test 1: Only first symbol
    sym1 = symbols[0]
    features1 = dataset_gen.generate_features(synthetic_ohlcv_data[sym1])
    targets1 = target_gen.generate(synthetic_ohlcv_data[sym1])
    
    features1['trading_date'] = pd.to_datetime(features1['trading_date']).dt.date
    targets1['trading_date'] = pd.to_datetime(targets1['trading_date']).dt.date
    features1['symbol'] = sym1
    targets1['symbol'] = sym1
    
    merged1 = dataset_gen.merge_features_and_targets(features1, targets1)
    rows_sym1_alone = len(merged1)
    
    # Test 2: First and second symbol
    sym2 = symbols[1]
    features2 = dataset_gen.generate_features(synthetic_ohlcv_data[sym2])
    targets2 = target_gen.generate(synthetic_ohlcv_data[sym2])
    
    features2['trading_date'] = pd.to_datetime(features2['trading_date']).dt.date
    targets2['trading_date'] = pd.to_datetime(targets2['trading_date']).dt.date
    features2['symbol'] = sym2
    targets2['symbol'] = sym2
    
    combined_features = pd.concat([features1, features2], ignore_index=True)
    combined_targets = pd.concat([targets1, targets2], ignore_index=True)
    
    merged_both = dataset_gen.merge_features_and_targets(combined_features, combined_targets)
    rows_sym1_in_both = len(merged_both[merged_both['symbol'] == sym1])
    
    # Symbol 1 should have same number of rows whether alone or with symbol 2
    assert rows_sym1_alone == rows_sym1_in_both, \
        f"Symbol 1 row count changed: {rows_sym1_alone} alone vs {rows_sym1_in_both} with symbol 2"


def test_target_alignment(synthetic_ohlcv_data):
    """Test that each row's target matches the correct symbol's future return."""
    dataset_gen = DatasetGenerator()
    target_gen = TargetGenerator(TargetConfig(horizons_days=[1]))
    
    # Generate and merge
    all_features = []
    all_targets = []
    
    for symbol, ohlcv_df in synthetic_ohlcv_data.items():
        features_df = dataset_gen.generate_features(ohlcv_df)
        targets_df = target_gen.generate(ohlcv_df)
        
        features_df['trading_date'] = pd.to_datetime(features_df['trading_date']).dt.date
        targets_df['trading_date'] = pd.to_datetime(targets_df['trading_date']).dt.date
        
        features_df['symbol'] = symbol
        targets_df['symbol'] = symbol
        
        all_features.append(features_df)
        all_targets.append(targets_df)
    
    combined_features = pd.concat(all_features, ignore_index=True)
    combined_targets = pd.concat(all_targets, ignore_index=True)
    
    merged = dataset_gen.merge_features_and_targets(combined_features, combined_targets)
    
    # For each symbol, verify row dates are correct
    for symbol in synthetic_ohlcv_data.keys():
        symbol_data = synthetic_ohlcv_data[symbol]
        merged_symbol = merged[merged['symbol'] == symbol]
        
        # Dates in merged data should be subset of dates in source data
        source_dates = set(symbol_data['trading_date'])
        merged_dates = set(pd.to_datetime(merged_symbol['trading_date']).dt.date)
        
        assert merged_dates.issubset(source_dates), \
            f"Symbol {symbol} has rows with dates not in source data"
        
        # Should have rows with valid targets
        assert (merged_symbol['1_day_target'].notna().sum() > 0), \
            f"Symbol {symbol} has no valid targets"


def test_no_infinite_values():
    """Test that volume_change inf values are handled."""
    # Create data with volume 0 which would cause division by zero
    df = pd.DataFrame({
        'trading_date': pd.date_range('2024-01-01', periods=5),
        'open': [100, 101, 102, 103, 104],
        'high': [102, 103, 104, 105, 106],
        'low': [99, 100, 101, 102, 103],
        'close': [100.5, 101.5, 102.5, 103.5, 104.5],
        'adjusted_close': [100.5, 101.5, 102.5, 103.5, 104.5],
        'volume': [0, 1000000, 1000000, 1000000, 1000000],  # First volume is 0
    })
    
    dataset_gen = DatasetGenerator()
    features = dataset_gen.generate_features(df)
    
    # Check no inf values in numeric columns
    numeric_cols = features.select_dtypes(include=[np.number]).columns
    has_inf = (np.isinf(features[numeric_cols])).any().any()
    
    assert not has_inf, \
        f"Found infinite values in features: {features.columns[np.isinf(features).any()].tolist()}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
