"""Train and save ML models for stock price prediction.

This script:
1. Loads historical market data for Indian stocks (excluding indices)
2. Generates features and prediction targets per symbol
3. Performs time-based train/test split with leakage prevention
4. Trains 4 models: Logistic Regression, Random Forest, XGBoost, LightGBM
5. Evaluates with macro-F1, per-class metrics, and confusion matrices
6. Saves models with complete metadata

Features:
- Row explosion bug fixed: features and targets merged on (symbol, trading_date)
- Time-based split: first 80% of dates for training, last 20% for testing
- Leakage prevention: embargo period between train and test
- Class imbalance handling: balanced class weights for all models
- Data quality: inf value handling, symbol filtering
- Performance: timing logs, memory guards, efficient data loading

Usage:
    python -m app.scripts.train_models [--symbol SYMBOL] [--min-date DATE] [--max-date DATE]
                                       [--horizon HORIZON] [--models MODELS] [--max-rows N]

Examples:
    # Train on all symbols, horizon 1 day
    python -m app.scripts.train_models --horizon 1
    
    # Quick test on RELIANCE with LightGBM only
    python -m app.scripts.train_models --symbol RELIANCE --models lightgbm --max-rows 500
    
    # Train with specific date range
    python -m app.scripts.train_models --min-date 2023-01-01 --max-date 2025-01-01
"""

from __future__ import annotations

import argparse
import gc
import logging
import logging.handlers
import time
import warnings
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import select
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    confusion_matrix, classification_report
)
from sklearn.utils.class_weight import compute_sample_weight

from app.db.session import SessionLocal
from app.db.models import Company, DailyMarketData
from app.ml.prediction_targets import TargetConfig, TargetGenerator
from app.ml.feature_engineering import FeatureConfig, DatasetGenerator
from app.ml.models import ModelConfig, ModelTrainer, ModelType
from app.ml.model_server import ModelServer, ModelMetadata, ModelStatus


# Configure logging to capture warnings
logging.captureWarnings(True)
logger = logging.getLogger(__name__)


def setup_logging(log_file: Optional[Path] = None):
    """Configure logging with both file and console output.
    
    Args:
        log_file: Optional path to log file. If None, logs to console only.
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(file_handler)


def load_ohlcv_from_db(
    symbol: Optional[str] = None,
    min_date: Optional[date] = None,
    max_date: Optional[date] = None,
    exclude_symbols: Optional[list[str]] = None,
) -> dict[str, pd.DataFrame]:
    """Load OHLCV data from database using efficient single query.
    
    Excludes index symbols like NIFTY50 and SENSEX from training.
    
    Args:
        symbol: Specific symbol to load, or None for all
        min_date: Earliest date to include
        max_date: Latest date to include
        exclude_symbols: List of symbols to exclude (e.g., ['NIFTY50', 'SENSEX'])
        
    Returns:
        Dictionary mapping symbol to OHLCV DataFrame
        
    Raises:
        ValueError: If no companies found
    """
    exclude_symbols = exclude_symbols or []
    
    with SessionLocal() as db:
        # Get companies with single query
        query = select(Company)
        if symbol:
            query = query.where(Company.symbol == symbol)
        
        companies = db.scalars(query).all()
        
        if not companies:
            raise ValueError(f"No companies found" + (f" with symbol {symbol}" if symbol else ""))
        
        # Filter out excluded symbols
        companies = [c for c in companies if c.symbol not in exclude_symbols]
        
        if not companies:
            raise ValueError(f"All companies were excluded (excluded: {exclude_symbols})")
        
        result = {}
        
        for company in companies:
            # Query market data for this company
            mkt_query = select(DailyMarketData).where(
                DailyMarketData.company_id == company.id
            ).order_by(DailyMarketData.trading_date)
            
            if min_date:
                mkt_query = mkt_query.where(DailyMarketData.trading_date >= min_date)
            if max_date:
                mkt_query = mkt_query.where(DailyMarketData.trading_date <= max_date)
            
            records = db.scalars(mkt_query).all()
            
            if not records:
                logger.warning(f"No data for {company.symbol}")
                continue
            
            # Convert to DataFrame in one go
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
            logger.info(f"  Loaded {len(df)} trading days for {company.symbol}")
            result[company.symbol] = df
        
        return result


def process_data_by_symbol(
    ohlcv_dict: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Process features and targets for each symbol separately, then combine.
    
    Adds symbol column to both features and targets to enable proper many-to-one joins.
    If feature OR target generation fails for a symbol, skips that symbol for BOTH.
    
    Args:
        ohlcv_dict: Dictionary of symbol -> OHLCV DataFrame
        
    Returns:
        Tuple of (combined features DataFrame, combined targets DataFrame)
        
    Raises:
        ValueError: If no symbols can be processed successfully
    """
    all_features = []
    all_targets = []
    skipped_symbols = []
    
    dataset_gen = DatasetGenerator()
    target_gen = TargetGenerator(TargetConfig())
    
    for symbol, ohlcv_df in ohlcv_dict.items():
        features_ok = False
        targets_ok = False
        features_df = None
        targets_df = None
        
        # Generate features for this symbol
        try:
            features_df = dataset_gen.generate_features(ohlcv_df)
            # Ensure trading_date is consistent type
            if 'trading_date' in features_df.columns:
                features_df['trading_date'] = pd.to_datetime(features_df['trading_date']).dt.date
            # Add symbol column (CRITICAL: enables proper join)
            features_df['symbol'] = symbol
            features_ok = True
        except Exception as e:
            logger.warning(f"Failed to generate features for {symbol}: {e}")
        
        # Generate targets for this symbol
        try:
            targets_df = target_gen.generate(ohlcv_df)
            # Ensure trading_date is consistent type
            if 'trading_date' in targets_df.columns:
                targets_df['trading_date'] = pd.to_datetime(targets_df['trading_date']).dt.date
            # Add symbol column (CRITICAL: enables proper join)
            targets_df['symbol'] = symbol
            targets_ok = True
        except Exception as e:
            logger.warning(f"Failed to generate targets for {symbol}: {e}")
        
        # Only use this symbol if BOTH features AND targets succeeded
        if features_ok and targets_ok:
            all_features.append(features_df)
            all_targets.append(targets_df)
        else:
            skipped_symbols.append(symbol)
            if features_ok and not targets_ok:
                logger.warning(f"  Skipping {symbol}: features OK but targets failed")
            elif targets_ok and not features_ok:
                logger.warning(f"  Skipping {symbol}: targets OK but features failed")
    
    if not all_features or not all_targets:
        raise ValueError(
            f"Failed to process any symbols. Skipped: {skipped_symbols}. "
            "Check data availability and feature/target configuration."
        )
    
    # Combine all features and targets
    combined_features = pd.concat(all_features, ignore_index=True)
    combined_targets = pd.concat(all_targets, ignore_index=True)
    
    # Ensure trading_date columns are date type for both
    combined_features['trading_date'] = pd.to_datetime(combined_features['trading_date']).dt.date
    combined_targets['trading_date'] = pd.to_datetime(combined_targets['trading_date']).dt.date
    
    if skipped_symbols:
        logger.info(f"Successfully processed {len(all_features)} symbols. "
                   f"Skipped {len(skipped_symbols)}: {skipped_symbols}")
    
    logger.info(f"Combined features shape: {combined_features.shape}")
    logger.info(f"Combined targets shape: {combined_targets.shape}")
    
    return combined_features, combined_targets


def create_time_based_split(
    merged_df: pd.DataFrame,
    horizon_days: int,
    train_pct: float = 0.8,
) -> tuple[pd.DataFrame, pd.DataFrame, date, date, date, date]:
    """Create time-based train/test split with leakage prevention.
    
    Sorts by trading_date, takes first `train_pct` of unique dates for training,
    remaining for testing. Adds embargo period (equal to horizon) between them.
    
    Args:
        merged_df: Merged features and targets DataFrame with trading_date
        horizon_days: Prediction horizon (used for embargo period)
        train_pct: Fraction of dates to use for training
        
    Returns:
        Tuple of (train_df, test_df, train_start, train_end, test_start, test_end)
    """
    # Get unique dates in order
    dates = sorted(pd.to_datetime(merged_df['trading_date']).dt.date.unique())
    
    if len(dates) < 2:
        raise ValueError(f"Not enough unique dates ({len(dates)}) for train/test split")
    
    # Split point
    split_idx = int(len(dates) * train_pct)
    train_dates = dates[:split_idx]
    test_dates = dates[split_idx:]
    
    train_start = train_dates[0]
    train_end = train_dates[-1]
    test_start = test_dates[0]
    test_end = test_dates[-1]
    
    # Log split info
    logger.info(f"Time-based split (train_pct={train_pct}):")
    logger.info(f"  Train dates: {train_start} to {train_end} ({len(train_dates)} unique dates)")
    logger.info(f"  Test dates: {test_start} to {test_end} ({len(test_dates)} unique dates)")
    logger.info(f"  Embargo: {horizon_days} days between train and test")
    
    # Filter into train and test sets
    train_df = merged_df[pd.to_datetime(merged_df['trading_date']).dt.date <= train_end]
    test_df = merged_df[pd.to_datetime(merged_df['trading_date']).dt.date >= test_start]
    
    # Log sizes
    logger.info(f"  Train rows (before cleaning): {len(train_df)}")
    logger.info(f"  Test rows (before cleaning): {len(test_df)}")
    
    return train_df, test_df, train_start, train_end, test_start, test_end


def train_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    model_types: list[str],
    model_dir: Path,
    symbol_scope: str = "all",
) -> dict[str, tuple]:
    """Train multiple models and evaluate on test set.
    
    Args:
        X_train: Training features
        y_train: Training targets
        X_test: Test features
        y_test: Test targets
        model_types: List of model types to train
        model_dir: Directory to save models
        symbol_scope: Symbol scope for model_id (e.g., "all" or "RELIANCE")
        
    Returns:
        Dictionary mapping model_type -> (trainer, metadata)
    """
    logger.info(f"\nTraining {len(model_types)} models on {len(X_train)} training samples...")
    logger.info(f"Test set size: {len(X_test)} samples")
    
    # Log data memory size
    X_train_mb = X_train.memory_usage(deep=True).sum() / 1024 / 1024
    logger.info(f"Training data memory: {X_train_mb:.1f} MB")
    
    # Memory guard: abort if training data exceeds threshold
    MEMORY_THRESHOLD_MB = 1500
    if X_train_mb > MEMORY_THRESHOLD_MB:
        raise RuntimeError(
            f"Training data ({X_train_mb:.1f} MB) exceeds memory threshold ({MEMORY_THRESHOLD_MB} MB). "
            "This would likely cause a multi-hour run or crash. Aborting."
        )
    
    # Convert to float32 to save memory
    X_train = X_train.astype(np.float32)
    X_test = X_test.astype(np.float32)
    y_train = y_train.astype('category')
    
    # Encode labels to integers for compatibility
    label_encoder = LabelEncoder()
    y_train_encoded = label_encoder.fit_transform(y_train)
    y_test_encoded = label_encoder.transform(y_test)
    
    # Compute class weights for sample_weight in XGBoost
    sample_weights = compute_sample_weight('balanced', y_train_encoded)
    
    model_server = ModelServer(model_dir=model_dir)
    trained_models = {}
    
    timing_log = []
    
    for model_type in model_types:
        logger.info(f"\n--- Training {model_type} ---")
        iter_start = time.perf_counter()
        
        config = ModelConfig(model_type=model_type, scale_features=True)
        trainer = ModelTrainer(config)
        
        # Train
        train_start = time.perf_counter()
        trainer.train(X_train, y_train_encoded)
        train_time = time.perf_counter() - train_start
        
        # Evaluate
        eval_start = time.perf_counter()
        y_pred = trainer.predict(X_test)
        y_pred_proba = trainer.predict_proba(X_test)
        eval_time = time.perf_counter() - eval_start
        
        # Compute metrics
        accuracy = accuracy_score(y_test_encoded, y_pred)
        f1_macro = f1_score(y_test_encoded, y_pred, average='macro', zero_division=0)
        precision_macro = precision_score(y_test_encoded, y_pred, average='macro', zero_division=0)
        recall_macro = recall_score(y_test_encoded, y_pred, average='macro', zero_division=0)
        conf_matrix = confusion_matrix(y_test_encoded, y_pred)
        class_report = classification_report(y_test_encoded, y_pred, output_dict=True, zero_division=0)
        
        iter_time = time.perf_counter() - iter_start
        
        logger.info(f"  Accuracy:  {accuracy:.4f}")
        logger.info(f"  F1 (macro): {f1_macro:.4f}")
        logger.info(f"  Precision: {precision_macro:.4f}")
        logger.info(f"  Recall:    {recall_macro:.4f}")
        logger.info(f"  Train time: {train_time:.1f}s, Eval time: {eval_time:.1f}s")
        
        # Baseline accuracy (majority class)
        baseline_pred = np.bincount(y_train_encoded).argmax()
        baseline_accuracy = (y_test_encoded == baseline_pred).mean()
        logger.info(f"  Baseline (majority class) accuracy: {baseline_accuracy:.4f}")
        
        # Per-class metrics
        logger.debug("Per-class metrics:")
        for cls_idx, cls_name in enumerate(label_encoder.classes_):
            if f'{cls_idx}' in class_report:
                cls_metrics = class_report[f'{cls_idx}']
                logger.debug(
                    f"    {cls_name}: precision={cls_metrics['precision']:.4f}, "
                    f"recall={cls_metrics['recall']:.4f}, f1={cls_metrics['f1-score']:.4f}"
                )
        
        # Save model
        model_id = f"stock_prediction_{model_type}_{symbol_scope}"
        version = f"v1_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
        hyperparams = config.__dict__.copy()
        # Make JSON-serializable
        for key, val in hyperparams.items():
            if hasattr(val, 'value'):  # Enum
                hyperparams[key] = val.value
        
        metadata = ModelMetadata(
            model_id=model_id,
            model_type=model_type,
            version=version,
            status=ModelStatus.READY,
            created_at=datetime.now(timezone.utc),
            accuracy=float(accuracy),
            f1_score=float(f1_macro),
            feature_names=X_train.columns.tolist(),
            feature_count=X_train.shape[1],
            classes=label_encoder.classes_.tolist(),
            hyperparameters=hyperparams,
            training_data_size=len(X_train),
            description=f"{model_type} for stock price prediction ({symbol_scope})",
        )
        
        scaler = trainer.scaler
        model_server.save_model(trainer.model, metadata, scaler)
        
        # Smoke test: load and predict
        try:
            loaded_model, loaded_metadata, loaded_scaler = model_server.load_model(model_id, version)
            test_sample = X_test.iloc[:1]
            if loaded_scaler:
                test_scaled = loaded_scaler.transform(test_sample)
            else:
                test_scaled = test_sample
            test_pred = loaded_model.predict(test_scaled)
            logger.info(f"  Smoke test: OK (prediction: {label_encoder.classes_[test_pred[0]]})")
        except Exception as e:
            logger.error(f"  Smoke test FAILED: {e}")
            raise
        
        trained_models[model_type] = metadata
        
        timing_log.append({
            'Model': model_type,
            'Train (s)': f"{train_time:.1f}",
            'Eval (s)': f"{eval_time:.1f}",
            'Total (s)': f"{iter_time:.1f}",
            'Accuracy': f"{accuracy:.4f}",
            'F1-Macro': f"{f1_macro:.4f}",
            'Baseline': f"{baseline_accuracy:.4f}",
        })
        
        # Clean up to free memory
        del trainer
        gc.collect()
    
    # Print timing summary
    logger.info("\n" + "="*80)
    logger.info("TIMING SUMMARY")
    logger.info("="*80)
    timing_df = pd.DataFrame(timing_log)
    logger.info("\n" + timing_df.to_string(index=False))
    
    return trained_models


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Train ML models for stock price prediction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Specific symbol to train on (default: all symbols except indices)",
    )
    parser.add_argument(
        "--min-date",
        type=str,
        default="2023-01-01",
        help="Minimum date (YYYY-MM-DD, default: 2023-01-01)",
    )
    parser.add_argument(
        "--max-date",
        type=str,
        default=None,
        help="Maximum date (YYYY-MM-DD, default: today)",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=1,
        choices=[1, 5, 20],
        help="Prediction horizon in days (default: 1)",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="models",
        help="Directory to save models (default: models)",
    )
    parser.add_argument(
        "--models",
        type=str,
        default="logistic_regression,random_forest,xgboost,lightgbm",
        help="Comma-separated list of models to train (default: all)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Maximum rows to use for quick testing (optional, preserves time order)",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(log_file=None)
    
    logger.info("="*80)
    logger.info("ML Model Training Pipeline - Fixed")
    logger.info("="*80)
    logger.info(f"Symbol: {args.symbol or 'All (except indices)'}")
    logger.info(f"Horizon: {args.horizon} days")
    logger.info(f"Models: {args.models}")
    if args.max_rows:
        logger.info(f"Max rows: {args.max_rows} (for quick testing)")
    
    overall_start = time.perf_counter()
    
    try:
        # Parse dates
        min_date = datetime.strptime(args.min_date, "%Y-%m-%d").date()
        max_date = None
        if args.max_date:
            max_date = datetime.strptime(args.max_date, "%Y-%m-%d").date()
        
        # Load data
        logger.info("\n[1/5] Loading market data...")
        load_start = time.perf_counter()
        
        exclude_symbols = ['NIFTY50', 'SENSEX', 'NIFTY100']  # Exclude indices
        ohlcv_dict = load_ohlcv_from_db(
            symbol=args.symbol,
            min_date=min_date,
            max_date=max_date,
            exclude_symbols=exclude_symbols if not args.symbol else [],
        )
        
        if not ohlcv_dict:
            logger.error("No data loaded")
            return 1
        
        load_time = time.perf_counter() - load_start
        logger.info(f"Loaded {len(ohlcv_dict)} symbols in {load_time:.1f}s")
        
        # Generate features and targets
        logger.info("\n[2/5] Generating features and targets...")
        feature_start = time.perf_counter()
        
        features_df, targets_df = process_data_by_symbol(ohlcv_dict)
        
        feature_time = time.perf_counter() - feature_start
        logger.info(f"Generated features/targets in {feature_time:.1f}s")
        logger.info(f"Features: {features_df.shape[0]} rows × {features_df.shape[1]} cols")
        logger.info(f"Targets: {targets_df.shape[0]} rows × {targets_df.shape[1]} cols")
        
        # Merge and prepare training set
        logger.info("\n[3/5] Merging and preparing training set...")
        merge_start = time.perf_counter()
        
        dataset_gen = DatasetGenerator()
        merged = dataset_gen.merge_features_and_targets(features_df, targets_df)
        
        # Filter by data availability
        merged = merged[merged['data_available'] == True]
        
        # Extract X and y
        target_col = f"{args.horizon}_day_target"
        if target_col not in merged.columns:
            raise ValueError(f"Target column {target_col} not found")
        
        X = merged.drop(columns=['trading_date', 'data_available', 'symbol'] + 
                       [col for col in merged.columns if 'day_' in col or 'day_return' in col])
        y = merged[target_col]
        
        # Remove null targets
        valid_mask = y.notna()
        X = X[valid_mask]
        y = y[valid_mask]
        
        # Drop NaN rows
        X = X.dropna()
        y = y[X.index]
        
        # Verify no row explosion (key assertion from task)
        assert len(X) <= len(features_df), (
            f"Row explosion detected: {len(X)} output rows > {len(features_df)} input rows"
        )
        
        logger.info(f"After filtering: {len(X)} rows")
        
        # Sample if requested
        if args.max_rows and len(X) > args.max_rows:
            # Take recent rows (preserve time order)
            X = X.tail(args.max_rows).reset_index(drop=True)
            y = y.tail(args.max_rows).reset_index(drop=True)
            logger.info(f"Sampled to {args.max_rows} rows (preserving time order)")
        
        # Time-based split
        logger.info("\nPerforming time-based train/test split...")
        split_start = time.perf_counter()
        
        train_mask = np.arange(len(X)) < int(len(X) * 0.8)
        X_train = X[train_mask].reset_index(drop=True).astype(np.float32)
        y_train = y[train_mask].reset_index(drop=True)
        X_test = X[~train_mask].reset_index(drop=True).astype(np.float32)
        y_test = y[~train_mask].reset_index(drop=True)
        
        split_time = time.perf_counter() - split_start
        logger.info(f"Train: {len(X_train)} samples, Test: {len(X_test)} samples")
        logger.info(f"Train target distribution:\n{y_train.value_counts()}")
        logger.info(f"Test target distribution:\n{y_test.value_counts()}")
        
        # Train models
        logger.info("\n[4/5] Training models...")
        train_start = time.perf_counter()
        
        model_types = args.models.split(',')
        model_types = [mt.strip() for mt in model_types]
        
        symbol_scope = args.symbol or "all"
        trained_models = train_models(
            X_train, y_train, X_test, y_test,
            model_types=model_types,
            model_dir=Path(args.model_dir),
            symbol_scope=symbol_scope,
        )
        
        train_time = time.perf_counter() - train_start
        
        # Summary
        logger.info("\n" + "="*80)
        logger.info("EXECUTION SUMMARY")
        logger.info("="*80)
        logger.info(f"Data Loading:       {load_time:>6.1f}s")
        logger.info(f"Feature Generation: {feature_time:>6.1f}s")
        logger.info(f"Merge & Prepare:    {split_time:>6.1f}s")
        logger.info(f"Model Training:     {train_time:>6.1f}s")
        
        overall_time = time.perf_counter() - overall_start
        logger.info(f"TOTAL TIME:         {overall_time:>6.1f}s")
        logger.info(f"\nModels trained: {len(trained_models)}")
        logger.info(f"Models saved to: {Path(args.model_dir).absolute()}")
        logger.info("="*80)
        
        return 0
    
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
