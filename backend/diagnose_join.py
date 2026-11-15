"""Diagnostic script to verify the row explosion hypothesis."""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
from sqlalchemy import select

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.session import SessionLocal
from app.db.models import Company, DailyMarketData
from app.ml.prediction_targets import TargetConfig, TargetGenerator
from app.ml.feature_engineering import FeatureConfig, DatasetGenerator


def diagnose():
    """Run diagnostics on the join behavior."""
    
    print("\n" + "="*80)
    print("DIAGNOSTIC: Row Explosion Bug Investigation")
    print("="*80)
    
    # Load 2-3 symbols for quick testing
    with SessionLocal() as db:
        query = select(Company).limit(3)
        companies = db.scalars(query).all()
        
        if not companies:
            print("ERROR: No companies found in database")
            return 1
        
        symbols_to_test = [c.symbol for c in companies]
        print(f"\nTesting with symbols: {symbols_to_test}")
        
        # Load data for each symbol
        ohlcv_data = {}
        for company in companies:
            mkt_query = select(DailyMarketData).where(
                DailyMarketData.company_id == company.id
            ).order_by(DailyMarketData.trading_date)
            
            records = db.scalars(mkt_query).all()
            
            if not records:
                print(f"  {company.symbol}: No data")
                continue
            
            data = []
            for row in records:
                data.append({
                    "trading_date": row.trading_date,
                    "open": float(row.open),
                    "high": float(row.high),
                    "low": float(row.low),
                    "close": float(row.close),
                    "adjusted_close": float(row.adjusted_close or row.close),
                    "volume": int(row.volume) if row.volume else 0,
                })
            
            df = pd.DataFrame(data)
            print(f"  {company.symbol}: {len(df)} trading days")
            ohlcv_data[company.symbol] = df
    
    # Generate features and targets
    dataset_gen = DatasetGenerator()
    target_gen = TargetGenerator(TargetConfig())
    
    all_features = []
    all_targets = []
    
    print("\n--- Per-Symbol Feature/Target Generation ---")
    for symbol, ohlcv_df in ohlcv_data.items():
        features_df = dataset_gen.generate_features(ohlcv_df)
        targets_df = target_gen.generate(ohlcv_df)
        
        features_df['trading_date'] = pd.to_datetime(features_df['trading_date']).dt.date
        targets_df['trading_date'] = pd.to_datetime(targets_df['trading_date']).dt.date
        
        print(f"{symbol}:")
        print(f"  Features shape: {features_df.shape}")
        print(f"  Targets shape: {targets_df.shape}")
        print(f"  Features columns: {features_df.columns.tolist()}")
        print(f"  Targets columns: {targets_df.columns.tolist()}")
        print(f"  Symbol column in features? {('symbol' in features_df.columns)}")
        print(f"  Symbol column in targets? {('symbol' in targets_df.columns)}")
        
        all_features.append(features_df)
        all_targets.append(targets_df)
    
    # Combine
    combined_features = pd.concat(all_features, ignore_index=True)
    combined_targets = pd.concat(all_targets, ignore_index=True)
    
    combined_features['trading_date'] = pd.to_datetime(combined_features['trading_date']).dt.date
    combined_targets['trading_date'] = pd.to_datetime(combined_targets['trading_date']).dt.date
    
    print(f"\n--- After pd.concat ---")
    print(f"Combined features shape: {combined_features.shape}")
    print(f"Combined targets shape: {combined_targets.shape}")
    print(f"Combined features columns: {combined_features.columns.tolist()}")
    print(f"Combined targets columns: {combined_targets.columns.tolist()}")
    
    # Now attempt the join as done in get_training_set
    print(f"\n--- Attempting merge as in get_training_set ---")
    print(f"Merging on 'trading_date' alone (WITHOUT symbol)...")
    
    # This is what currently happens
    target_cols = [col for col in combined_targets.columns if col not in ["trading_date", "data_available"]]
    merged = pd.merge(
        combined_features,
        combined_targets[["trading_date"] + target_cols],
        on="trading_date",
        how="inner",
    )
    
    print(f"Merged result shape: {merged.shape}")
    print(f"Expected shape (should be ~{combined_features.shape[0]}): {merged.shape[0]}")
    
    # Check if row explosion occurred
    if merged.shape[0] > combined_features.shape[0] * 1.5:
        print(f"\n*** ROW EXPLOSION DETECTED ***")
        print(f"Input features: {combined_features.shape[0]} rows")
        print(f"Output after merge: {merged.shape[0]} rows")
        print(f"Explosion factor: {merged.shape[0] / combined_features.shape[0]:.1f}x")
        
        # Analyze what happened
        print(f"\nAnalyzing the explosion:")
        dates_in_features = combined_features['trading_date'].nunique()
        dates_in_targets = combined_targets['trading_date'].nunique()
        print(f"Unique dates in features: {dates_in_features}")
        print(f"Unique dates in targets: {dates_in_targets}")
        
        # Count how many times each date appears
        feature_date_counts = combined_features.groupby('trading_date').size()
        print(f"Feature rows per date stats: min={feature_date_counts.min()}, max={feature_date_counts.max()}, mean={feature_date_counts.mean():.1f}")
        
        target_date_counts = combined_targets.groupby('trading_date').size()
        print(f"Target rows per date stats: min={target_date_counts.min()}, max={target_date_counts.max()}, mean={target_date_counts.mean():.1f}")
        
        # Theoretical: if we have 3 symbols and each date appears 3 times in both, then joining on date creates 3*3=9 rows per date
        print(f"\nHypothesis: Each date appears {len(symbols_to_test)} times in features and targets.")
        print(f"A date-only join creates {len(symbols_to_test)}^2 = {len(symbols_to_test)**2} rows per date.")
        print(f"This matches the observed {merged.shape[0] / combined_features.shape[0]:.1f}x explosion factor (close to {len(symbols_to_test)**2}).")
        
        return 0  # Bug confirmed
    else:
        print(f"\n!!! Row explosion NOT detected !!!")
        print(f"This suggests the hypothesis may be incorrect or the data has changed.")
        return 1


if __name__ == "__main__":
    exit(diagnose())
