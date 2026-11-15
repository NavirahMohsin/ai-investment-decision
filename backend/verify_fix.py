"""Verify that the row explosion bug is fixed."""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import select

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.session import SessionLocal
from app.db.models import Company, DailyMarketData
from app.ml.prediction_targets import TargetConfig, TargetGenerator
from app.ml.feature_engineering import FeatureConfig, DatasetGenerator


def verify_fix():
    """Verify the fix works."""
    
    print("\n" + "="*80)
    print("VERIFICATION: Row Explosion Bug Fix")
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
    
    # Generate features and targets using the FIXED process_data_by_symbol
    dataset_gen = DatasetGenerator()
    target_gen = TargetGenerator(TargetConfig())
    
    all_features = []
    all_targets = []
    
    print("\n--- Per-Symbol Feature/Target Generation (WITH SYMBOL COLUMN) ---")
    for symbol, ohlcv_df in ohlcv_data.items():
        features_df = dataset_gen.generate_features(ohlcv_df)
        targets_df = target_gen.generate(ohlcv_df)
        
        features_df['trading_date'] = pd.to_datetime(features_df['trading_date']).dt.date
        targets_df['trading_date'] = pd.to_datetime(targets_df['trading_date']).dt.date
        
        # FIX: Add symbol column
        features_df['symbol'] = symbol
        targets_df['symbol'] = symbol
        
        print(f"{symbol}:")
        print(f"  Features shape: {features_df.shape}")
        print(f"  Targets shape: {targets_df.shape}")
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
    
    # Now attempt the FIXED merge using symbol + trading_date
    print(f"\n--- Attempting merge using FIXED merge_features_and_targets ---")
    print(f"Merging on (symbol, trading_date) with validate='one_to_one'...")
    
    try:
        merged = dataset_gen.merge_features_and_targets(combined_features, combined_targets)
        print(f"Merged result shape: {merged.shape}")
        print(f"Expected shape (should be ~{combined_features.shape[0]}): {merged.shape[0]}")
        
        # Check if row explosion is FIXED
        if merged.shape[0] == combined_features.shape[0]:
            print(f"\n✓ SUCCESS: No row explosion! Merge preserved row count.")
            print(f"  Input: {combined_features.shape[0]} rows")
            print(f"  Output: {merged.shape[0]} rows")
            print(f"  Ratio: 1.0x (no explosion)")
            return 0
        elif merged.shape[0] > combined_features.shape[0] * 1.5:
            print(f"\n✗ FAILURE: Row explosion still present")
            print(f"  Input: {combined_features.shape[0]} rows")
            print(f"  Output: {merged.shape[0]} rows")
            print(f"  Explosion factor: {merged.shape[0] / combined_features.shape[0]:.1f}x")
            return 1
        else:
            print(f"\n! WARNING: Rows changed but not explosive")
            print(f"  Input: {combined_features.shape[0]} rows")
            print(f"  Output: {merged.shape[0]} rows")
            print(f"  Ratio: {merged.shape[0] / combined_features.shape[0]:.1f}x")
            return 2
    
    except Exception as e:
        print(f"\n✗ ERROR during merge: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(verify_fix())
