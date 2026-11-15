# Implementation Plan: Fix Row-Explosion Bug and Multi-Hour Runtime

## Root Cause (VERIFIED)

The bug is in `process_data_by_symbol()` and `get_training_set()`:
- Features and targets DataFrames are built per-symbol but lack a `symbol` column
- When concatenated, each date appears 3+ times (once per symbol)
- `get_training_set()` merges on `trading_date` alone, creating a many-to-many join
- Result: 3^2 = 9 rows per original date (row explosion factor matches observed ~3x after filtering)
- This causes memory exhaustion during model training

## Implementation Sections (A-G)

### A. Fix the join (PRIMARY)
1. Add `symbol` column in `process_data_by_symbol()` for both features and targets
2. Merge on `["symbol", "trading_date"]` with `validate="one_to_one"` in `get_training_set()`
3. Add guard assertion: `assert len(X) <= len(features_df)`
4. Keep `symbol` as identifier, not feature
5. Expected: ~19k rows (not 8.5M)

### B. Error handling in `process_data_by_symbol`
1. If feature OR target generation fails, skip BOTH for that symbol
2. If all symbols fail, raise clear ValueError
3. Log summary of skipped symbols

### C. Train/test split (time-based, leakage-free)
1. Remove index-based split `X[:split_idx]`
2. Split by date cutoff: first 80% of unique dates for train, last 20% for test
3. Add embargo of `horizon_days` between train and test
4. Fit StandardScaler on training data only
5. Add optional `--cv` flag with TimeSeriesSplit (off by default)

### D. Data quality
1. Fix `volume_change` inf values: use `.pct_change()` then `replace([np.inf, -np.inf], np.nan)`
2. Add assertion: no `inf` in any feature column
3. Exclude NIFTY50 and SENSEX from training, optionally use as market-context features
4. Investigate TATAMOTORS "No data" case

### E. Class imbalance
1. Use `class_weight="balanced"` for Logistic Regression and Random Forest
2. For XGBoost: compute `sample_weight` with `sklearn.utils.class_weight.compute_sample_weight`
3. For LightGBM: use `class_weight="balanced"`
4. Log macro-F1, per-class precision/recall, confusion matrix, and majority-class baseline

### F. Performance and memory
1. Add timing logs around each stage
2. Convert `X` to `float32` before training
3. Replace row-by-row loop in `load_ohlcv_from_db` with single query
4. Delete unused imports and code
5. Set explicit model hyperparameters with sensible bounds
6. Train models one at a time with `gc.collect()`
7. Add `--max-rows` and `--models` debugging flags
8. Capture warnings through logging
9. Add memory guard before training

### G. Saving models safely
1. Include scope in `model_id` (e.g., `stock_prediction_<model_type>_all`)
2. Ensure hyperparameters are JSON-serializable
3. Save train/test date ranges, row counts, class distribution in metadata
4. Load and smoke-test each model after saving
5. Document file format and location

## Verification Steps

1. Before/after row counts printed during run
2. Unit test with 3-symbol, 30-day synthetic dataset
3. Leakage test assertion on date ranges
4. Full run on all symbols with timing table
5. Quick run on RELIANCE with LightGBM < 1 minute
6. No `inf` values, no FutureWarning, clean logs
7. Horizons 5 and 20 run without errors

## Estimated Changes

- `feature_engineering.py`: Add `symbol` column in `process_data_by_symbol()` 
- `feature_engineering.py`: Fix `volume_change` inf handling
- `feature_engineering.py`: Update `get_training_set()` merge logic and add time-based split
- `models.py`: Fix hyperparameters, class weighting, add class_weight support to XGBoost
- `train_models.py`: Rewrite to fix joins, add time-based split, add flags, add timing/memory guards
- `model_server.py`: Ensure metadata is JSON-serializable, add smoke test
- New test file: `test_row_explosion_fix.py` with pytest tests
